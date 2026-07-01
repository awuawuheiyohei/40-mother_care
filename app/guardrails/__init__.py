"""Guardrails: safety checks at multiple stages of the pipeline.

Layers:
1. EMERGENCY keyword short-circuit (pre-retrieval) -> canned response
2. Medical-citation-required guard (post-retrieval): queries that touch
   dosages, age thresholds, or medication names must hit KB items that have
   a verifiable source_url. Otherwise refuse to answer.
3. Off-topic guard: queries unrelated to maternal/infant care refuse.
4. Always-on disclaimer appended to every answer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.rag.retriever import RetrievalHit


# =============================================================================
# Emergency short-circuit
# =============================================================================

EMERGENCY_KEYWORDS: list[str] = [
    "抽搐",
    "惊厥",
    "失去意识",
    "昏迷",
    "呼吸停止",
    "面色发紫",
    "口唇发紫",
    "全身青紫",
    "严重出血",
    "大出血",
    "误吞药品",
    "中毒",
    "严重烫伤",
    "大面积烫伤",
    "溺水",
    "坠楼",
    "车祸",
]

EMERGENCY_RESPONSE = (
    "⚠️ 紧急情况\n\n"
    "你描述的情况可能是医疗急症，请立即采取以下行动：\n"
    "1. 拨打 120 急救电话\n"
    "2. 如果是新生儿呛奶/窒息，按急救步骤处理（见知识库条目 KB-012）\n"
    "3. 保留现场，等待专业人员到场\n\n"
    "本助手无法替代专业医疗救治。"
)


@dataclass
class GuardrailResult:
    ok: bool
    response: str | None = None
    reason: str = ""


def check_emergency(query: str) -> GuardrailResult:
    """Pre-retrieval: if query contains emergency keywords, short-circuit."""
    q = query.lower()
    for kw in EMERGENCY_KEYWORDS:
        if kw in q:
            return GuardrailResult(ok=False, response=EMERGENCY_RESPONSE, reason=f"emergency:{kw}")
    return GuardrailResult(ok=True)


# =============================================================================
# Medical-citation-required guard
# =============================================================================

# Patterns that suggest the user is asking about medication, dosage, or
# specific age thresholds where an unsourced answer is dangerous.
MEDICAL_SENSITIVE_PATTERNS = [
    r"多少(度|毫升|毫升|毫克|克|mg|ml|kg|斤)",
    r"几(度|毫升|毫克|克)",
    r"多大剂量",
    r"用(多|几)少",
    r"吃(多|几)少",
    r"剂量",
    r"用量",
    r"能(不)?能吃",
    r"能(不)?能用",
    r"什么时候(开始|添加|吃|用)",
    r"多大(开始|可以)",
    r"几(个)?月(可以|开始|龄)",
    r"正常(范围|值)",
    r"指标",
    r"用(对乙酰氨基酚|布洛芬|泰诺林|美林)",
    r"打(疫苗|预防针)",
]

_MEDICAL_RE = re.compile("|".join(MEDICAL_SENSITIVE_PATTERNS), re.IGNORECASE)


def is_medical_sensitive_query(query: str) -> bool:
    """Return True if the query touches dosage/age thresholds/medication."""
    return bool(_MEDICAL_RE.search(query))


def check_citation_required(query: str, hits: list[RetrievalHit]) -> GuardrailResult:
    """For medical-sensitive queries, require source_url on top hit."""
    if not is_medical_sensitive_query(query):
        return GuardrailResult(ok=True)
    if not hits:
        return GuardrailResult(
            ok=False,
            response=NO_ANSWER_RESPONSE,
            reason="no_evidence_for_sensitive_query",
        )
    top = hits[0]
    if not top.item.source_url:
        return GuardrailResult(
            ok=False,
            response=(
                "抱歉，针对你这个问题，我检索到的最高优先级知识条目缺少可点击的来源链接。"
                "为避免给出没有来源支撑的建议，我选择不回答。\n\n"
                f"建议：1）直接咨询儿科医生；2）拨打 12320 卫生热线；"
                f"3）参考该知识条目的人工来源：{top.item.source}。"
            ),
            reason=f"sensitive_query_no_citation:{top.item.id}",
        )
    return GuardrailResult(ok=True)


# =============================================================================
# Off-topic guard
# =============================================================================

# Topic whitelist — if NONE of these terms appear in query, AND query has no
# retrieval hits, refuse as off-topic.
MOTHER_CARE_HINTS = [
    "宝宝", "婴儿", "新生儿", "幼儿", "小孩", "孩子", "儿童",
    "妈", "孕", "产", "出生", "月", "周岁",
    "奶", "辅食", "黄疸", "发烧", "退烧", "疫苗",
    "奶嘴", "尿布", "脐带", "睡眠", "趴", "翻身",
]

NO_ANSWER_RESPONSE = (
    "抱歉，我的知识库暂未覆盖这个问题。\n\n"
    "建议：\n"
    "1. 咨询儿科医生或拨打 12320 卫生热线\n"
    "2. 前往就近医院儿科就诊\n\n"
    "（我不会在不确认的情况下给出医疗建议）"
)


def check_retrieval_quality(query: str, hits: list[RetrievalHit]) -> GuardrailResult:
    """After retrieval: if no good hits, refuse to answer."""
    if hits:
        return GuardrailResult(ok=True)

    # If query has mother-care hints but no hits, suggest rephrasing
    has_hint = any(h in query for h in MOTHER_CARE_HINTS)
    if has_hint:
        return GuardrailResult(
            ok=False,
            response=(
                "抱歉，我在你这个问题上没找到对应的知识条目。\n\n"
                "建议：换一种说法试试，例如：\n"
                "1) 用更具体的症状/场景描述\n"
                "2) 加上宝宝月龄\n"
                "3) 直接咨询儿科医生"
            ),
            reason="no_hits_with_hint",
        )

    return GuardrailResult(ok=False, response=NO_ANSWER_RESPONSE, reason="off_topic_or_no_evidence")


# =============================================================================
# Citation enforcement (post-composition)
# =============================================================================

def enforce_citation(answer_text: str) -> str:
    """Ensure Sources section is present in the composed answer."""
    has_sources = bool(re.search(r"【来源】|sources?\s*:", answer_text, re.IGNORECASE))
    if not has_sources:
        return answer_text.rstrip() + "\n\n【来源】未引用（提示词可能未遵守，请检查）"
    return answer_text


# =============================================================================
# Disclaimer (always appended)
# =============================================================================

MEDICAL_DISCLAIMER = (
    "\n\n——\n"
    "本工具仅供参考，不构成医疗诊断或处方。如有疑虑，请就医或拨打 12320 卫生热线。"
)


def append_disclaimer(text: str) -> str:
    if "本工具仅供参考" in text:
        return text
    return text.rstrip() + MEDICAL_DISCLAIMER