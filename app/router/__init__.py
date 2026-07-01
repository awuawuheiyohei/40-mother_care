"""Query Router.

Simple keyword-based classification. MVP: enough to keep emergency/knowledge
chats on different paths. Future: replace with a small LLM-based classifier.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.guardrails import check_emergency, GuardrailResult


class Route(str, Enum):
    EMERGENCY = "emergency"
    KNOWLEDGE = "knowledge"
    AMBIGUOUS = "ambiguous"


@dataclass
class RouteResult:
    route: Route
    guardrail: GuardrailResult


# Triggers that hint at action-oriented queries (need richer guidance, KB+RAG)
ACTION_TRIGGERS = [
    "怎么办",
    "怎么处理",
    "如何处理",
    "怎么缓解",
    "如何缓解",
    "要不要去医院",
    "需要就医吗",
]

# Knowledge-y hints
KNOWLEDGE_TRIGGERS = [
    "多少算",
    "什么是",
    "什么叫",
    "怎么判断",
    "什么时候开始",
    "多久",
    "为什么",
    "几天",
    "几个月",
    "正常吗",
]


def route_query(query: str) -> RouteResult:
    # 1. Emergency short-circuit (highest priority)
    em = check_emergency(query)
    if not em.ok:
        return RouteResult(route=Route.EMERGENCY, guardrail=em)

    # 2. Naive keyword classification
    q = query.strip()
    if any(t in q for t in ACTION_TRIGGERS):
        return RouteResult(route=Route.KNOWLEDGE, guardrail=GuardrailResult(ok=True))
    if any(t in q for t in KNOWLEDGE_TRIGGERS):
        return RouteResult(route=Route.KNOWLEDGE, guardrail=GuardrailResult(ok=True))

    # 3. Default: KB+RAG path (safer than LLM-direct)
    return RouteResult(route=Route.AMBIGUOUS, guardrail=GuardrailResult(ok=True))