"""Assistant pipeline: orchestrate router -> retriever -> composer -> guardrails.

Single entry point `handle_query(user_id, query)` returns a PipelineResult
that can be serialized to JSON for the API / WeChat reply.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.composer import StructuredAnswer, compose, compose_fallback
from app.config import get_settings
from app.guardrails import (
    EMERGENCY_RESPONSE,
    NO_ANSWER_RESPONSE,
    append_disclaimer,
    check_citation_required,
    check_emergency,
    check_retrieval_quality,
    enforce_citation,
    is_medical_sensitive_query,
)
from app.llm import get_llm
from app.rag.retriever import RetrievalHit, get_retriever, reset_retriever
from app.router import Route, route_query

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    trace_id: str
    route: str
    answer: StructuredAnswer
    confidence: str
    hits: list[dict[str, Any]] = field(default_factory=list)
    warning: str | None = None

    def to_text(self) -> str:
        """WeChat-friendly text representation."""
        lines = [self.answer.to_text()]
        if self.warning:
            lines.append(f"\n⚠️ {self.warning}")
        if self.answer.confidence == "low":
            lines.append("\n（本回答置信度较低，建议就医确认）")
        # Always append the medical disclaimer
        return append_disclaimer("\n".join(lines))

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "route": self.route,
            "answer": {
                "conclusion": self.answer.conclusion,
                "recommendations": self.answer.recommendations,
                "warning_signs": self.answer.warning_signs,
                "sources": self.answer.sources,
                "confidence": self.answer.confidence,
            },
            "confidence": self.confidence,
            "hits": self.hits,
            "warning": self.warning,
        }


def handle_query(user_id: str, query: str) -> PipelineResult:
    """Top-level pipeline. Synchronous — caller can run in threadpool."""
    trace_id = uuid.uuid4().hex[:12]
    logger.info("[%s] query user=%s q=%r", trace_id, user_id, query[:80])

    # 1. Route
    route_res = route_query(query)
    if route_res.route == Route.EMERGENCY:
        conclusion = route_res.guardrail.response or EMERGENCY_RESPONSE
        return PipelineResult(
            trace_id=trace_id,
            route="emergency",
            answer=StructuredAnswer(
                conclusion=conclusion,
                confidence="high",
                sources=["Emergency Protocol"],
            ),
            confidence="high",
            warning="emergency_protocol",
        )

    # 2. Retrieve
    try:
        retriever = get_retriever()
    except FileNotFoundError as e:
        logger.warning("[%s] %s", trace_id, e)
        return PipelineResult(
            trace_id=trace_id,
            route="no_index",
            answer=StructuredAnswer(
                conclusion="系统尚未构建知识库索引。",
                recommendations=["运行 scripts/seed_kb.py + python -m app.rag.build_index 后重试。"],
                confidence="low",
            ),
            confidence="low",
            warning="index_missing",
        )

    hits = retriever.retrieve(query)

    # 3. Retrieval quality + medical-citation guards
    quality = check_retrieval_quality(query, hits)
    if not quality.ok:
        # LLM fallback: answer from general knowledge with strong safety net
        llm = get_llm()
        if is_medical_sensitive_query(query):
            # Medical-sensitive query with no KB evidence — refuse rather than guess
            return PipelineResult(
                trace_id=trace_id,
                route=route_res.route.value,
                answer=StructuredAnswer(
                    conclusion=NO_ANSWER_RESPONSE,
                    confidence="low",
                ),
                confidence="low",
                warning=quality.reason + "+no_kb_evidence_for_medical_query",
            )
        answer = compose_fallback(query, llm)
        return PipelineResult(
            trace_id=trace_id,
            route=route_res.route.value,
            answer=answer,
            confidence="low",
            warning=quality.reason + "+llm_fallback",
            hits=[_hit_to_dict(h) for h in hits],
        )

    citation = check_citation_required(query, hits)
    if not citation.ok:
        return PipelineResult(
            trace_id=trace_id,
            route=route_res.route.value,
            answer=StructuredAnswer(
                conclusion=citation.response or NO_ANSWER_RESPONSE,
                confidence="low",
            ),
            confidence="low",
            warning=citation.reason,
        )

    # 4. Compose
    llm = get_llm()
    answer = compose(query, hits, llm)

    # 5. Post-check
    _ = enforce_citation(answer.to_text())

    return PipelineResult(
        trace_id=trace_id,
        route=route_res.route.value,
        answer=answer,
        confidence=answer.confidence,
        hits=[_hit_to_dict(h) for h in hits],
        warning=None,
    )


def _hit_to_dict(h: RetrievalHit) -> dict[str, Any]:
    return {
        "id": h.item.id,
        "score": round(h.score, 4),
        "raw_score": round(h.raw_score, 4),
        "source": h.item.source,
        "source_url": h.item.source_url,
        "question": h.item.question,
    }


__all__ = ["PipelineResult", "handle_query", "reset_retriever"]