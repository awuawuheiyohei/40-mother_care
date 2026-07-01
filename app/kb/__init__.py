"""Knowledge Base data schema.

Each KB entry is a structured record. We persist them as JSONL for human
editability and ease of versioning.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

ConfidenceLevel = Literal["high", "medium", "low"]


class KnowledgeItem(BaseModel):
    """One knowledge entry in the KB."""

    id: str = Field(..., description="Unique ID, e.g. NB-001")
    question: str = Field(..., description="Canonical question this entry answers")
    content: str = Field(..., description="Answer body (factual, sourced)")
    source: str = Field(..., description="Source label, e.g. WHO, Hospital, Curated")
    source_url: str | None = Field(None, description="Optional URL to the source")
    confidence: ConfidenceLevel = "high"
    tags: list[str] = Field(default_factory=list)
    age_range: str | None = Field(
        None,
        description="Applicable age range, e.g. '0-1m', '1-6m', 'pregnancy'",
    )
    scenario: str | None = Field(
        None, description="Scenario tag, e.g. 'fever', 'jaundice', 'feeding'"
    )
    warning_signs: list[str] = Field(
        default_factory=list,
        description="Concrete 'go to hospital' red flags",
    )
    last_updated: date = Field(default_factory=date.today)

    def to_embedding_text(self) -> str:
        """Concatenate question + content + tags for embedding."""
        parts = [self.question, self.content]
        if self.tags:
            parts.append("标签：" + "、".join(self.tags))
        if self.warning_signs:
            parts.append("警示：" + "、".join(self.warning_signs))
        return "\n".join(parts)