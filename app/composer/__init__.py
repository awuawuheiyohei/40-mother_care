"""Answer Composer: turn retrieval hits into a structured response.

Pipeline: prompt construction -> LLM call -> parse to structured fields
(Conclusion / Recommendations / Warning Signs / Sources).

Falls back to extracting structure from KB items directly when LLM is mocked.

When no KB hits are found, falls back to LLM-only path with a stronger prompt
that explicitly warns the user the answer is NOT based on authoritative sources.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.llm import LLMClient
from app.rag.retriever import RetrievalHit


SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system.txt"
FALLBACK_SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "fallback_system.txt"


@dataclass
class StructuredAnswer:
    conclusion: str = ""
    recommendations: list[str] = field(default_factory=list)
    warning_signs: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    confidence: str = "medium"
    used_kb: bool = True  # False when answer is LLM-only fallback

    def to_text(self) -> str:
        """WeChat/DingTalk-friendly Markdown text. Friendly tone."""
        lines: list[str] = []

        if not self.used_kb:
            lines.append(
                "> ⚠️ **这个回答来自大模型通用知识，不是来自权威医学知识库**，"
                "可能不准确。重要问题请就医确认。\n"
            )

        if self.conclusion:
            lines.append(self.conclusion)
        if self.recommendations:
            lines.append("")
            lines.append("**建议：**")
            for r in self.recommendations:
                lines.append(f"- {r}")
        if self.warning_signs:
            lines.append("")
            lines.append("**需要注意：**")
            for w in self.warning_signs:
                lines.append(f"- {w}")
        if self.sources:
            lines.append("")
            lines.append(f"_参考：{'、'.join(self.sources)}_")

        if not lines:
            lines.append("抱歉，我没能生成一个有用的回答。")
        return "\n".join(lines)


def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def load_fallback_system_prompt() -> str:
    return FALLBACK_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def build_user_prompt(query: str, hits: list[RetrievalHit]) -> str:
    parts = [f"## 家长提问\n{query}\n"]
    parts.append("## 已查到的权威知识（按相关度排序）")
    for i, hit in enumerate(hits, start=1):
        item = hit.item
        parts.append(
            f"\n[{i}] id={item.id} source={item.source} "
            f"score={hit.score:.3f}\n{item.content}"
        )
        if item.warning_signs:
            parts.append(f"警示信号：{'、'.join(item.warning_signs)}")
    parts.append(
        "\n## 回答要求\n"
        "- 语气要像一个有医学背景的家长朋友在给另一个家长解释，平实、有温度。\n"
        "- 严格只用上面给出的知识，不要加入你自己训练数据里的医学知识。\n"
        "- 输出严格 JSON，不要有任何 JSON 之外的文字。\n"
        "- 格式：{\"conclusion\": str, \"recommendations\": [str], "
        "\"warning_signs\": [str], \"sources\": [str], \"confidence\": \"high|medium|low\"}\n"
        "- sources 字段必须填写每条引用对应的 source 标签。\n"
        "- 如果证据不足，conclusion 写\"证据不足，建议就医\"，confidence 设为 \"low\"。"
    )
    return "\n".join(parts)


def build_fallback_user_prompt(query: str) -> str:
    """Used when KB has no hits — LLM answers from general knowledge with strong safety net."""
    return (
        f"## 家长提问\n{query}\n\n"
        "## 重要：你的知识库中没找到对应的权威条目\n"
        "请基于大模型通用医学知识回答，但必须遵守以下安全规则：\n\n"
        "1. **不确定就说不知道**。医学问题宁可承认不知道也不能瞎猜。\n"
        "2. **不要给具体药物剂量**。\n"
        "3. **高危症状必须警告就医**：\n"
        "   - 3 个月以下发烧\n"
        "   - 呼吸困难/口唇发紫\n"
        "   - 抽搐/意识丧失\n"
        "   - 严重出血\n"
        "   - 持续呕吐/脱水\n"
        "   - 任何你判断为紧急的情况\n"
        "4. 答案开头必须有一句明确的免责说明：以下回答基于大模型通用知识，不是来自权威医学资料。\n"
        "5. 答案结尾必须建议：重要问题请就医或拨打 12320 卫生热线。\n\n"
        "## 输出 JSON 格式\n"
        "{\"conclusion\": str, \"recommendations\": [str], "
        "\"warning_signs\": [str], \"sources\": [\"LLM 通用知识 (非权威)\"], "
        "\"confidence\": \"low\"}\n"
    )


def compose(query: str, hits: list[RetrievalHit], llm: LLMClient) -> StructuredAnswer:
    system = load_system_prompt()
    user = build_user_prompt(query, hits)
    resp = llm.chat(system=system, user=user, temperature=0.2)
    answer = _parse(resp.text, hits)
    answer.used_kb = bool(hits)
    return answer


def compose_fallback(query: str, llm: LLMClient) -> StructuredAnswer:
    """Used when no KB hits: LLM answers from general knowledge with safety net."""
    system = load_fallback_system_prompt()
    user = build_fallback_user_prompt(query)
    resp = llm.chat(system=system, user=user, temperature=0.2)
    return _parse_fallback(resp.text)


def _parse(text: str, hits: list[RetrievalHit] | None = None) -> StructuredAnswer:
    # Try to extract JSON block from the LLM response
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group(0))
            return StructuredAnswer(
                conclusion=str(data.get("conclusion", "")).strip(),
                recommendations=[str(x).strip() for x in data.get("recommendations", []) if x],
                warning_signs=[str(x).strip() for x in data.get("warning_signs", []) if x],
                sources=[str(x).strip() for x in data.get("sources", []) if x],
                confidence=str(data.get("confidence", "medium")).strip(),
            )
        except (json.JSONDecodeError, ValueError):
            pass

    if hits:
        top = hits[0].item
        warning_signs: list[str] = []
        for hit in hits:
            warning_signs.extend(hit.item.warning_signs)
        seen = set()
        deduped_ws = []
        for w in warning_signs:
            if w and w not in seen:
                seen.add(w)
                deduped_ws.append(w)

        return StructuredAnswer(
            conclusion=top.content,
            recommendations=[h.item.content[:80] + "..." for h in hits[1:3]],
            warning_signs=deduped_ws[:5],
            sources=[f"{h.item.source} ({h.item.id})" for h in hits],
            confidence=hits[0].item.confidence,
        )
    return StructuredAnswer(
        conclusion="（无法生成回答）",
        sources=[],
        confidence="low",
    )


def _parse_fallback(text: str) -> StructuredAnswer:
    """Parse fallback response. Forces 'used_kb=False' and adjusts sources."""
    answer = _parse(text)
    answer.used_kb = False
    # Override sources to make the non-authoritative nature explicit
    if not any("非权威" in s or "LLM" in s or "通用" in s for s in answer.sources):
        answer.sources.append("LLM 通用知识 (非权威来源)")
    answer.confidence = "low"
    return answer