# Mother Care Knowledge Base

**Status**: 51 entries, lint clean (0 errors / 0 warnings)

## Schema（每条必须）

```json
{
  "id": "KB-001",                // 必填，全局唯一，格式: KB-NNN 或 XHS-NNN
  "question": "新生儿发烧多少度算危险？",  // 必填，家长问句形式
  "content": "...",              // 必填，≥ 20 字，医学准确性必须有据可查
  "source": "AAP",               // 必填，发布机构或来源名（如 AAP / WHO / 中国国家卫健委 / XHS (verified)）
  "source_url": "https://...",   // 必填（可空字符串），可点击的原始 URL
  "confidence": "high",          // 必填，high / medium / low
  "tags": ["发烧", "新生儿"],    // 必填，≥ 1 个关键词
  "age_range": "0-3m",           // 推荐，0-3m / 0-6m / 0-1y / 0-6y 等
  "scenario": "fever",           // 推荐，分类（fever / feeding / jaundice / emergency / ...）
  "warning_signs": ["..."],      // 推荐，就医警示信号列表
  "last_updated": "2026-06-26"   // 推荐，YYYY-MM-DD
}
```

## Confidence 规则（关键安全约束）

| confidence | source_url 必须 | 含义 |
|---|---|---|
| **high** | ✅ 非空 | 用户可以**放心信任**该条目；来源是 AAP / WHO / 中国国家卫健委指南等官方权威 |
| **medium** | ⚠️ 可空 | 条目质量可信但缺少可点击 URL；或来自个人分享（XHS verified）|
| **low** | ⚠️ 可空 | 仅作为参考；用户需自行核实 |

**为什么严格？** 用户看到 high confidence 会更信任 → 必须有可溯源 URL 否则就是误信。
`app/kb/lint.py` 会**自动报错**：high + 空 URL。

## 当前 KB 状态

| 文件 | 条目数 | confidence 分布 |
|---|---|---|
| `app/kb/data/neonate.jsonl` | 30 | newborn (0-1m) |
| `app/kb/data/infant.jsonl` | 14 | infant (1m-1y) |
| `app/kb/data/prenatal.jsonl` | 4 | prenatal (产前) |
| `app/kb/data/curated.jsonl` | 1 | user-verified (XHS 等) |

**confidence 分布**：high=18, medium=33, low=0

## Lint 命令

```bash
# 检查 KB（0 errors 必须）
python -m app.kb.lint

# 自动修：
#  - 把 source_url: null → ""
#  - 按 source 文本模式猜 URL
python -m app.kb.lint --fix-urls

# 自动降 confidence：所有 high + 空 URL → medium（避免误信）
python -m app.kb.lint --downgrade-unverified
```

## 添加新条目（手动）

1. 打开对应 jsonl（如 `neonate.jsonl`）
2. **复制一条类似的条目**作为模板
3. 改 id / question / content / source / source_url / tags
4. 跑 `python -m app.kb.lint` 确认 0 errors
5. 跑 `python -m app.rag.build_index` 重建索引

## 添加新条目（XHS 等社交媒体）

```bash
# 极简交互模式（推荐）
python -m app.kb.add_from_text
# 粘贴 → 看完 AI 提取 → y/n 决定 → 自动入库
```

或批量模式：编辑 `inputs/xhs_pending.json` 然后：
```bash
python -m app.kb.add_from_text --input inputs/xhs_pending.json
# 审核 outputs/xhs_kb_review.md
python -m app.kb.add_from_text --commit outputs/xhs_kb_review.md
python -m app.kb.lint
python -m app.rag.build_index
```

## ⚠️ 待查证清单（25 条 source_url 待补）

`source_url` 是空字符串的中等 confidence 条目，用户可以**查阅官方源后填入**：
升级后 confidence 可恢复到 high（lint 会自动放行）。

查看清单：
```bash
python -m app.kb.lint --fix-urls --strict  # 列出待查证条目
```

或直接查看哪些 KB 条目 source_url 是空：

```bash
grep -L '"source_url":' app/kb/data/*.jsonl  # 没有 source_url 字段的
python3 -c "
import json
from pathlib import Path
for f in sorted(Path('app/kb/data').glob('*.jsonl')):
    for ln, line in enumerate(f.open(), 1):
        d = json.loads(line)
        if not d.get('source_url'):
            print(f'{f.name}:{ln} {d[\"id\"]}: {d[\"source\"][:50]}')
"
```

## 重要原则

1. **拒绝编造** —— 没有 URL 就标 medium confidence，不要凑数
2. **拒绝凑数** —— 内容不完整宁可删掉，不要硬填
3. **可溯源** —— 每条都能追到原始来源
4. **人工审核** —— XHS 等社交媒体内容必须人工审核才能入库
5. **医学警示** —— 危险场景必须有 `warning_signs`（就医信号）
