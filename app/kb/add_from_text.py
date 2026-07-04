"""Extract knowledge base entries from user-provided content (e.g. XHS posts).

Three-stage compliance pipeline (人命关天):

  Stage 1: LLM EXTRACT  — 信息抽取员，从原帖提取结构化 KB 条目
  Stage 2: LLM REVIEW   — 医学审核员，独立判断提取出的答案是否医学合理
  Stage 3: HUMAN APPROVE — 家长最终确认入库

Only entries passing all three stages can be added to the KB.

Workflow:
1. User copies content from XHS into inputs/xhs_pending.json (see example).
2. Run: python -m app.kb.add_from_text --input inputs/xhs_pending.json
3. Tool uses LLM to extract candidate KB entries (Stage 1).
4. Tool sends extracted entries to LLM for medical review (Stage 2).
5. Review file is written to outputs/xhs_kb_review.md with all 3 stages visible.
6. User reviews, then runs: python -m app.kb.add_from_text --commit outputs/xhs_kb_review.md
7. Approved entries are appended to app/kb/data/curated.jsonl.
8. Rebuild index: python -m app.rag.build_index.

This is a compliance-first workflow: NO automated scraping, NO bypassing
any access controls. Users paste content they've already read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.llm import get_llm  # noqa: E402


# ============================================================
# Stage 1: 信息抽取（EXTRACT）
# ============================================================
EXTRACT_SYSTEM_PROMPT = """你是母婴健康知识库的**信息抽取员**。家长会从社交媒体（如小红书）复制一些母婴相关的笔记给你，你要**总结、精简**地提取结构化信息。

## 输入格式（家长可能粘的格式）

家长可能粘以下任一格式：
- 直接复制 XHS 原文（图文笔记）
- 自己看完视频/图片后的口述总结
- 混合：原文 + 【我的总结】...（推荐）

请**自动识别格式**，统一处理：
- 如果有【原文】和【我的总结】两个部分 → 整合两边信息
- 如果只有一段 → 直接抽取
- **优先信任家长的总结**（家长是 KB 的最终用户，他们最知道自己要什么）

## 核心原则（人命关天）

1. **总结、精简**：
   - content **必须 ≤ 250 字**（超过就精简）
   - 删除口水话、情绪化表达、个人感受（"我家宝宝"、"真是"、"太难了"）
   - 删除晒娃、无关内容
   - 保留**事实**和**可操作建议**

2. **医学严谨**：
   - 涉及药物剂量的，必须标"按说明书/遵医嘱"，**不要写具体数字**
   - 不要复述原帖全部内容
   - 如果原帖有医学错误或缺乏循证依据，**必须**在 content 末尾明确说明"该经验来自个人分享，未经医学验证"
   - 不要添加你自己的医学知识（你是抽取员，不是医生）

3. **判断是否值得加入知识库**：
   - ✅ 适合：具体的、可操作的母婴护理经验、踩坑提醒、辅食做法、就医经验
   - ❌ 不适合：纯个人情绪发泄、无具体内容的晒娃、纯产品种草文、医疗错误信息、迷信内容

## 输出格式

严格输出 JSON（不要任何其他文字）：
```json
{
  "verdict": "include" | "exclude",
  "reason": "为什么 include/exclude",
  "entries": [
    {
      "id": "XHS-NNN",
      "question": "用家长会问的问题形式重写",
      "content": "≤250字的事实+建议，末尾标'该经验来自个人分享，未经医学验证'（如适用）",
      "source": "XHS @作者, 日期",
      "source_url": "原文 URL（如果有）",
      "tags": ["3-5个关键词"],
      "warning_signs": ["如适用，列出需要立即就医的警示信号"]
    }
  ]
}
```
"""


# ============================================================
# Stage 2: 医学审核（MEDICAL REVIEW）
# ============================================================
MEDICAL_REVIEW_SYSTEM_PROMPT = """你是一位**循证医学背景的儿科主治医生**，负责审核知识库条目的医学合理性。

## 你的工作

家长（或知识库管理员）会把从社交媒体提取的母婴健康条目给你看，你需要独立判断：
1. content 中的医学建议是否与主流共识一致？
2. 是否有**明显错误**（如禁忌药品、错误剂量、错误操作建议）？
3. 是否有**绝对化承诺**（如"一定有效"、"绝对安全"）？
4. warning_signs 是否覆盖了**关键就医警示**？
5. question 是否是家长真正会问的问题？

## 评分标准

- `safety_score` 1-10：**医学安全性**
  - 10 = 完全安全，无任何风险
  - 7-9 = 基本安全，少数点需注意
  - 4-6 = 有潜在风险，需家长谨慎
  - 1-3 = 不建议入库（可能误导家长做出错误决定）

- `accuracy_score` 1-10：**医学准确性**
  - 10 = 与最新指南完全一致
  - 7-9 = 大致准确
  - 4-6 = 部分准确，有争议
  - 1-3 = 不准确

## 输出格式

严格输出 JSON（不要任何其他文字）：
```json
{
  "verdict": "approve" | "caution" | "reject",
  "reason": "为什么这个 verdict",
  "safety_score": 8,
  "accuracy_score": 7,
  "issues": ["问题1", "问题2"],
  "suggested_revision": "建议修改的内容（如适用）",
  "missing_warnings": ["如果 warning_signs 缺关键警示，列在这里"]
}
```

verdict 决策：
- `approve`: safety ≥ 7 AND accuracy ≥ 7 AND issues 为空
- `caution`: safety 4-6 或 accuracy 4-6（可入库但 confidence=low）
- `reject`: safety < 4 或 accuracy < 4（不要入库，会误导家长）
"""


def build_user_prompt(item: dict) -> str:
    return f"""## 待处理内容

**标题：** {item.get('title', '')}
**来源：** {item.get('source', '未知')}
**URL：** {item.get('url') or '（无）'}

**正文：**
{item.get('content', '')}

请判断是否值得加入知识库，并按格式输出。
"""


def build_review_prompt(entry: dict) -> str:
    return f"""## 待审核 KB 条目

**Question:** {entry.get('question', '')}
**Content:** {entry.get('content', '')}
**Source:** {entry.get('source', '')}
**Warning Signs:** {', '.join(entry.get('warning_signs', []))}
**Tags:** {', '.join(entry.get('tags', []))}

请审核这个条目是否医学合理，并按格式输出。
"""


def parse_llm_output(text: str) -> dict:
    """Extract JSON from LLM response."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"verdict": "exclude", "reason": "无法解析 LLM 输出", "entries": []}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"verdict": "exclude", "reason": "JSON 解析失败", "entries": []}


def parse_review_output(text: str) -> dict:
    """Extract review JSON from LLM response."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"verdict": "reject", "reason": "无法解析审核输出"}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"verdict": "reject", "reason": "审核输出 JSON 解析失败"}


def review_entry(llm, entry: dict) -> dict:
    """Stage 2: medical review of an extracted entry."""
    user = build_review_prompt(entry)
    resp = llm.chat(system=MEDICAL_REVIEW_SYSTEM_PROMPT, user=user, temperature=0.1)
    review = parse_review_output(resp.text)

    # Adjust entry confidence based on review
    if review.get("verdict") == "approve":
        # Keep author's confidence, but cap at medium for XHS
        entry.setdefault("confidence", "medium")
        if entry["confidence"] == "high":
            entry["confidence"] = "medium"  # XHS can never be high even if accurate
        review_summary = f"✅ 审核通过 (safety={review.get('safety_score', '?')}, accuracy={review.get('accuracy_score', '?')})"
    elif review.get("verdict") == "caution":
        entry["confidence"] = "low"
        review_summary = f"⚠️ 审核:谨慎 (safety={review.get('safety_score', '?')}, accuracy={review.get('accuracy_score', '?')})"
    else:  # reject
        entry["confidence"] = "low"
        review_summary = f"❌ 审核拒绝 (safety={review.get('safety_score', '?')}, accuracy={review.get('accuracy_score', '?')})"
        entry["_rejected"] = True
        entry["_reject_reason"] = review.get("reason", "")

    entry["_review"] = review
    entry["_review_summary"] = review_summary
    return entry


def cmd_extract(args: argparse.Namespace) -> int:
    """Extract candidate KB entries from input JSON, run medical review, write review file.

    Three-stage pipeline:
      Stage 1 (EXTRACT):  extract structured entries from raw content
      Stage 2 (REVIEW):   medical accuracy/safety review by LLM
      Stage 3 (HUMAN):    user reviews review file and marks ✅/❌
    """
    llm = get_llm()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"ERROR: input file not found: {input_path}")
        return 1

    data = json.loads(input_path.read_text(encoding="utf-8"))
    items = data.get("items", [])
    if not items:
        print(f"No items found in {input_path}")
        return 1

    print(f"📥 处理 {len(items)} 条原帖...")
    print("🔍 三道关卡：抽取 → 医学审核 → 人工最终确认\n")

    candidates: list[dict] = []

    for idx, item in enumerate(items, start=1):
        print(f"  [{idx}/{len(items)}] Stage 1 抽取: {item.get('title', '?')[:50]}...")
        user = build_user_prompt(item)
        resp = llm.chat(system=EXTRACT_SYSTEM_PROMPT, user=user, temperature=0.2)
        result = parse_llm_output(resp.text)
        result["_source_item"] = {
            "title": item.get("title"),
            "source": item.get("source"),
            "url": item.get("url"),
        }

        # Stage 2: medical review each entry
        reviewed_entries: list[dict] = []
        if result.get("verdict") == "include" and result.get("entries"):
            for entry in result["entries"]:
                print(f"           Stage 2 审核: {entry.get('question', '?')[:50]}...")
                entry = review_entry(llm, entry)
                reviewed_entries.append(entry)
        result["entries"] = reviewed_entries
        candidates.append(result)

    # Write review file
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append("# XHS → KB 候选条目审核（人命关天三道关卡）\n")
    lines.append(f"_生成时间：{date.today().isoformat()}_\n")
    lines.append("")
    lines.append("## 流程说明")
    lines.append("")
    lines.append("每条候选都经过三道关卡：")
    lines.append("")
    lines.append("1. **Stage 1 — 信息抽取**（LLM 作为抽取员，从原帖提取精简 KB 条目）")
    lines.append("2. **Stage 2 — 医学审核**（LLM 作为儿科医生，独立判断医学合理性）")
    lines.append("   - safety_score ≥ 7 且 accuracy_score ≥ 7 → approve")
    lines.append("   - 否则 caution 或 reject（confidence 自动降级）")
    lines.append("3. **Stage 3 — 你（家长）确认** ⬅️ 你在这里")
    lines.append("")
    lines.append("**判定说明**：")
    lines.append("- ✅ 保留：medical review approve，且你看过内容也认可")
    lines.append("- ❌ 拒绝：medical review reject（医学不安全/不准确），或你自己觉得不行")
    lines.append("")
    lines.append("⚠️ **被 reject 的条目默认 ❌，除非你明确要留。**")
    lines.append("")
    lines.append("---")
    lines.append("")

    next_id = 1
    approved_count = 0
    caution_count = 0
    rejected_count = 0
    for idx, c in enumerate(candidates, start=1):
        item = c.get("_source_item", {})
        lines.append(f"\n## 来源 {idx}: {item.get('title', '?')}\n")
        lines.append(f"- **来源标注**：{item.get('source', '?')}")
        if item.get("url"):
            lines.append(f"- **URL**：{item['url']}")
        lines.append(f"\n**Stage 1 抽取结果：** {c.get('verdict', '?')}（{c.get('reason', '?')}）")
        lines.append("")

        for entry in c.get("entries", []):
            lines.append(f"### 候选条目 `{entry.get('id', 'XHS-' + str(next_id).zfill(3))}`\n")
            lines.append(f"**Question:** {entry.get('question', '')}")
            lines.append("")
            lines.append(f"**Content** ({len(entry.get('content', ''))} 字):")
            lines.append(f"> {entry.get('content', '')}")
            lines.append("")
            lines.append(f"- **Source:** {entry.get('source', '')}")
            if entry.get("source_url"):
                lines.append(f"- **Source URL:** {entry.get('source_url')}")
            lines.append(f"- **Tags:** {', '.join(entry.get('tags', []))}")
            if entry.get("warning_signs"):
                lines.append(f"- **Warning Signs:** {', '.join(entry['warning_signs'])}")
            lines.append(f"- **Confidence:** {entry.get('confidence', 'medium')}")
            lines.append("")

            # Stage 2 review
            review = entry.get("_review", {})
            lines.append("**🩺 Stage 2 医学审核结果：**")
            lines.append(f"> {entry.get('_review_summary', '?')}")
            if review.get("issues"):
                lines.append("")
                lines.append(f"> **Issues:** {', '.join(review['issues'])}")
            if review.get("suggested_revision"):
                lines.append("")
                lines.append(f"> **建议修改:** {review['suggested_revision']}")
            if review.get("missing_warnings"):
                lines.append("")
                lines.append(f"> **缺失警示:** {', '.join(review['missing_warnings'])}")
            lines.append("")

            # Stage 3 human decision
            if entry.get("_rejected"):
                lines.append("**🚫 Stage 3 你的决定：✅ / ❌** （默认 ❌，因为医学审核拒绝）")
                rejected_count += 1
            elif review.get("verdict") == "caution":
                lines.append("**⚠️ Stage 3 你的决定：✅ / ❌** （医学审核标注谨慎，标 ✅ 前请仔细阅读 content）")
                caution_count += 1
            else:
                lines.append("**Stage 3 你的决定：✅ / ❌**")
                approved_count += 1
            lines.append("")
            next_id += 1
        lines.append("\n---\n")

    # Summary at end
    lines.append("\n## 📊 审核总结\n")
    lines.append(f"- ✅ 通过医学审核：{approved_count} 条")
    lines.append(f"- ⚠️ 谨慎：{caution_count} 条（标 ✅ 前请仔细阅读）")
    lines.append(f"- ❌ 拒绝：{rejected_count} 条（默认 ❌）")
    lines.append("")
    lines.append("**下一步**：编辑本文件，把 ✅ / ❌ 写到每条候选的「Stage 3 你的决定」后面，")
    lines.append(f"然后跑 `python -m app.kb.add_from_text --commit {output_path}`")

    output_path.write_text("\n".join(lines), encoding="utf-8")

    print()
    print("━" * 50)
    print(f"✅ Stage 1+2 完成，review 文件：{output_path}")
    print(f"   ✅ 通过：{approved_count}  ⚠️ 谨慎：{caution_count}  ❌ 拒绝：{rejected_count}")
    print()
    print("下一步：")
    print(f"  1. 打开 {output_path}")
    print("  2. 每条标 ✅ 或 ❌")
    print(f"  3. python -m app.kb.add_from_text --commit {output_path}")
    print("  4. python -m app.kb.lint")
    print("  5. python -m app.rag.build_index")
    return 0


def cmd_commit(args: argparse.Namespace) -> int:
    """Read reviewed file, extract ✅ entries, append to curated.jsonl."""
    review_path = Path(args.commit)
    if not review_path.exists():
        print(f"ERROR: review file not found: {review_path}")
        return 1

    content = review_path.read_text(encoding="utf-8")
    # Parse entries — look for `**审核：✅` lines and extract the preceding entry block
    blocks = re.split(r"\n---\n", content)
    approved: list[dict] = []
    for block in blocks:
        if "**审核：✅**" not in block:
            continue
        # Extract fields with regex
        entry: dict = {}
        for line in block.split("\n"):
            if line.startswith("- **ID**：`"):
                entry["id"] = line.split("`")[1]
            elif line.startswith("- **Question**："):
                entry["question"] = line.replace("- **Question**：", "").strip()
            elif line.startswith("- **Content**："):
                entry["content"] = line.replace("- **Content**：", "").strip()
            elif line.startswith("- **Source**："):
                entry["source"] = line.replace("- **Source**：", "").strip()
            elif line.startswith("- **Source URL**："):
                entry["source_url"] = line.replace("- **Source URL**：", "").strip()
            elif line.startswith("- **Tags**："):
                entry["tags"] = [t.strip() for t in line.replace("- **Tags**：", "").split(",") if t.strip()]
            elif line.startswith("- **Confidence**："):
                entry["confidence"] = line.replace("- **Confidence**：", "").strip()
            elif line.startswith("- **Warning Signs**："):
                entry["warning_signs"] = [w.strip() for w in line.replace("- **Warning Signs**：", "").split(",") if w.strip()]
        if "id" in entry and "question" in entry and "content" in entry:
            entry.setdefault("source", "User-provided")
            entry.setdefault("confidence", "medium")
            entry.setdefault("tags", [])
            entry.setdefault("warning_signs", [])
            entry["last_updated"] = date.today().isoformat()
            # Mark XHS-sourced entries as "XHS (verified)" so they get the proper
            # boost in source_weights (after the user updates .env).
            if entry.get("source", "").startswith("XHS") and not entry["source"].startswith("XHS (verified)"):
                entry["source"] = "XHS (verified)"
            approved.append(entry)

    if not approved:
        print("No ✅ approved entries found in review file.")
        return 1

    # Append to curated.jsonl
    kb_path = Path(__file__).parent / "data" / "curated.jsonl"
    kb_path.parent.mkdir(parents=True, exist_ok=True)
    with kb_path.open("a", encoding="utf-8") as f:
        for entry in approved:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"✓ Appended {len(approved)} entries to {kb_path}")
    print("Next: rebuild the index:")
    print("  python -m app.rag.build_index")
    return 0


def cmd_interactive(args: argparse.Namespace) -> int:
    """Truly simple: paste XHS content, get a KB entry, approve inline."""
    llm = get_llm()

    print("=" * 60)
    print("小红书 → 知识库 · 三道关卡版")
    print("=" * 60)
    print()
    print("人命关天 — 每条入库前经过：")
    print("  Stage 1: LLM 抽取 + 总结、精简到 250 字以内")
    print("  Stage 2: LLM 作为儿科医生，审核医学合理性")
    print("  Stage 3: 你（家长）最后确认")
    print()
    print("─" * 30)
    print("粘贴什么？（任意格式都支持）")
    print("─" * 30)
    print("✅ XHS 复制原文（图文笔记直接复制）")
    print("✅ 视频笔记：自己看完后总结要点")
    print("✅ 图片笔记：自己看完后用自己的话描述")
    print("✅ 原文 + 你的总结 一起粘（推荐）")
    print()
    print("如果原文是混合类型，可以这样标：")
    print("  【原文】...")
    print("  【我的总结】...")
    print()
    print("─" * 30)
    print("怎么用：")
    print("─" * 30)
    print("  1. 看 XHS 笔记（图文/视频/图片都行）")
    print("  2. 复制能复制的文字，自己口述剩下的")
    print("  3. 粘到下面（多行 OK）")
    print("  4. 输两次回车结束")
    print("  5. AI 抽取 → 医学审核 → 显示结果")
    print("  6. 你输入 y 保留 / n 跳过 / q 退出")
    print()
    print("=" * 60)
    print()

    counter = 0
    while True:
        print("─" * 60)
        print("请粘贴小红书内容（两次回车结束）")
        print("（输入 q 回车退出）")
        print("─" * 60)
        lines: list[str] = []
        empty_count = 0
        while True:
            try:
                line = input()
            except EOFError:
                break
            if line.strip() == "q" and not lines:
                print("退出。")
                return 0
            if line.strip() == "":
                empty_count += 1
                if empty_count >= 2:
                    break
                lines.append(line)
            else:
                empty_count = 0
                lines.append(line)
        if not any(line.strip() for line in lines):
            print("（空内容，已跳过）")
            continue
        content = "\n".join(lines).strip()
        # If still ends with the double-blank we used as terminator, trim
        while content.endswith("\n\n"):
            content = content[:-1]

        # Heuristic: split title from body
        # XHS typically has first line as title, rest as body
        parts = content.split("\n", 1)
        title = parts[0].strip() if parts else ""
        body = parts[1].strip() if len(parts) > 1 else ""

        if len(title) > 80 or len(body) < 20:
            title = "用户提供的笔记"
            body = content

        print()
        print(f"📋 识别到标题：{title[:60]}{'...' if len(title) > 60 else ''}")
        print(f"📝 正文长度：{len(body)} 字")
        print()
        print("🤖 Stage 1: AI 正在抽取 + 精简（≤250字）...")

        item = {"title": title, "content": body, "source": "XHS (interactive)", "url": ""}
        user_prompt = build_user_prompt(item)
        resp = llm.chat(system=EXTRACT_SYSTEM_PROMPT, user=user_prompt, temperature=0.2)
        result = parse_llm_output(resp.text)

        verdict = result.get("verdict", "exclude")
        reason = result.get("reason", "")
        entries = result.get("entries", [])

        print()
        print(f"⚖️  Stage 1 判定：{verdict}（{reason}）")
        print()
        if verdict == "exclude" or not entries:
            print("❌ Stage 1 觉得这条不值得加入知识库。")
            print("   如果你觉得有道理，输入 n 继续下一条")
            print("   如果你想强留，输入 y（不推荐）")
            ans = input("   y/n/q? ").strip().lower()
            if ans == "q":
                return 0
            continue

        # Stage 2: medical review each entry
        print()
        print("🩺 Stage 2: 医学审核（每个候选都过一遍）...")
        for entry in entries:
            review_entry(llm, entry)

        # Show candidates
        accepted: list[dict] = []
        for i, entry in enumerate(entries, start=1):
            print()
            print(f"━━━ 候选 {i}/{len(entries)} ━━━")
            print(f"Q: {entry.get('question', '')}")
            print()
            print(f"📝 Content ({len(entry.get('content', ''))} 字):")
            print(f"   {entry.get('content', '')}")
            print()
            print(f"标签: {', '.join(entry.get('tags', []))}")
            if entry.get("warning_signs"):
                print(f"警示: {', '.join(entry['warning_signs'])}")

            # Show Stage 2 review
            review = entry.get("_review", {})
            print()
            verdict_icon = {"approve": "✅", "caution": "⚠️", "reject": "❌"}.get(review.get("verdict"), "?")
            print(f"🩺 Stage 2 医学审核: {verdict_icon} {review.get('verdict', '?').upper()}")
            print(f"   安全性: {review.get('safety_score', '?')}/10  准确性: {review.get('accuracy_score', '?')}/10")
            if review.get("issues"):
                print(f"   ⚠️ 问题: {', '.join(review['issues'])}")
            if review.get("suggested_revision"):
                print(f"   💡 建议修改: {review['suggested_revision'][:100]}")
            if review.get("missing_warnings"):
                print(f"   🚨 缺警示: {', '.join(review['missing_warnings'])}")
            print(f"   → confidence 自动设为: {entry.get('confidence', '?')}")
            print()

            # Block rejected entries unless user insists
            if entry.get("_rejected"):
                print("   🚫 医学审核拒绝，默认 n（不建议入库）")
                print("   如果你坚持要留（你已看清楚风险），输入 y")
                ans = input("   y/n/q? ").strip().lower()
                if ans == "q":
                    if accepted:
                        _save_entries(accepted)
                        print(f"\n✓ 已保存 {len(accepted)} 条，退出。")
                    return 0
                if ans == "y":
                    accepted.append(entry)
                    print("   ⚠️ 强行加入（已记录警告）")
                continue

            # Normal flow: y/n/e/q
            ans = input("✅ Stage 3 你的决定？(y/n/e=编辑标题/q=退出): ").strip().lower()
            if ans == "q":
                if accepted:
                    _save_entries(accepted)
                    print(f"\n✓ 已保存 {len(accepted)} 条，退出。")
                return 0
            if ans == "e":
                new_q = input(f"  新标题 (当前: {entry.get('question', '')[:50]}...): ").strip()
                if new_q:
                    entry["question"] = new_q
                accepted.append(entry)
                print("  ✓ 已加入")
            elif ans == "y":
                accepted.append(entry)
                print("  ✓ 已加入")

        if accepted:
            _save_entries(accepted)
            counter += len(accepted)
            print()
            print(f"✅ 已写入 {len(accepted)} 条到知识库！")
            print(f"   本次累计: {counter} 条")
            print()
            print("⚠️ 记得跑 `python -m app.rag.build_index` 让检索生效")
        else:
            print()
            print("（本条全部跳过）")

    return 0


def _save_entries(entries: list[dict]) -> None:
    """Write approved entries to curated.jsonl."""
    today = date.today().isoformat()
    kb_path = Path(__file__).parent / "data" / "curated.jsonl"
    kb_path.parent.mkdir(parents=True, exist_ok=True)
    with kb_path.open("a", encoding="utf-8") as f:
        for entry in entries:
            entry.setdefault("source", "XHS (verified)")
            if not entry["source"].startswith("XHS"):
                entry["source"] = "XHS (verified)"
            entry.setdefault("confidence", "medium")
            entry.setdefault("tags", [])
            entry.setdefault("warning_signs", [])
            entry["last_updated"] = today
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract KB entries from user-provided content")
    parser.add_argument("--input", help="Input JSON file (XHS items)")
    parser.add_argument("--output", default="outputs/xhs_kb_review.md", help="Output review file")
    parser.add_argument("--commit", help="Review file to commit (extract ✅ entries)")
    args = parser.parse_args()

    if args.commit:
        return cmd_commit(args)
    if args.input:
        return cmd_extract(args)
    # No args → interactive mode
    return cmd_interactive(args)


if __name__ == "__main__":
    sys.exit(main())
