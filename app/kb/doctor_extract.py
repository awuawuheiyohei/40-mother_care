"""Medical advice extraction — CONSERVATIVE mode for doctor/nurse instructions.

Unlike XHS extraction (which summarizes + condenses), this module extracts
STRUCTURE without changing wording. Doctor/nurse instructions must be
preserved verbatim to ensure accuracy (人命关天).
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


# Conservative prompt: do NOT rewrite, do NOT summarize, preserve doctor wording
DOCTOR_EXTRACT_SYSTEM_PROMPT = """你是医疗建议的**结构化助手**。家长会把医生/护士的口头/书面建议粘给你，你要把它**原样结构化**入库。

## 核心原则：人命关天，医嘱一字不改

✅ 允许做：
- 把口语化医嘱拆成 question / content / warning_signs / tags
- 保留**所有数字**（剂量、时间、阈值、复查时间）
- 保留医嘱**原话**（"医生说"、"医嘱"、"复查"、"护士提醒"等）
- 保留触发场景（"5天大"、"黄疸15"、"发烧39度"等）

❌ 禁止做（任何一条都不能违反）：
- ❌ **不要精简、不要总结、不要润色**
- ❌ **不要改数字**（剂量、时间、阈值）
- ❌ **不要把"医生说"改成"建议"**（保留医生身份）
- ❌ **不要把"医嘱"改成"提示"**（保留医嘱语气）
- ❌ **不要添加你自己的医学知识**
- ❌ **不要加 disclaimer**（如"该经验来自个人分享，未经医学验证"）
  —— 这是专业医生建议，不是个人分享
- ❌ **不要把"发烧到39度去医院"改成"高烧就医"**
  —— 必须保留具体数字

## 拆分策略（重要）

**默认整段作为一条 content**，保留完整医嘱（所有数字、所有医嘱原话）。

只有以下情况才拆成多条：
- 医嘱里明显是**两个独立场景**（如"另：关于辅食提醒..."）
- 家长主动用【】或换行标记了不同主题

**不要主动拆**。一段医嘱一条 entry，让检索时整段命中。

## source 字段规范

- 如果家长记录了医院/医生 → "Doctor @三甲医院新生儿科, 2026-06-28"
- 如果只有护士 → "Nurse @三甲医院, 2026-06-28"
- 如果没记录医院 → "Doctor (家长记录，未注明医院), 2026-06-28"
- 日期格式：YYYY-MM-DD

## 输出格式

严格输出 JSON（不要其他文字）：
```json
{
  "verdict": "include",
  "entries": [
    {
      "id": "DOC-NNN",
      "question": "家长会问的问题形式（基于医嘱触发场景）",
      "content": "整段医嘱原文整理（保留所有数字和医嘱原话）",
      "source": "Doctor @医院科室, YYYY-MM-DD",
      "tags": ["触发场景关键词"],
      "warning_signs": ["医嘱中提到的就医警示信号"]
    }
  ],
  "confidence": "high",
  "source_missing_info": ["如果医院/医生姓名缺失，列在这里"]
}
```
"""


def build_doctor_prompt(user_text: str) -> str:
    today = date.today().isoformat()
    return f"""## 家长记录的医嘱（请原样结构化）

```
{user_text}
```

## 当前日期
{today}

## 你的工作

1. 提取 question（基于医嘱触发场景，如"5天大新生儿黄疸15怎么办"）
2. 提取 content（**保留所有数字和医嘱原话**）
3. 提取 tags
4. 提取 warning_signs（医嘱提到的就医警示）
5. 设置 source（Doctor @医院 + 日期，或 Doctor (未注明医院) + 日期）
6. **不要精简、不要润色、不要改字**

请按 JSON 格式输出。
"""


def parse_doctor_output(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"verdict": "exclude", "reason": "无法解析 LLM 输出", "entries": []}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"verdict": "exclude", "reason": "JSON 解析失败", "entries": []}


def extract_medical_advice(llm, user_text: str) -> dict:
    """Run conservative medical-advice extraction."""
    resp = llm.chat(
        system=DOCTOR_EXTRACT_SYSTEM_PROMPT,
        user=build_doctor_prompt(user_text),
        temperature=0.1,
    )
    return parse_doctor_output(resp.text)