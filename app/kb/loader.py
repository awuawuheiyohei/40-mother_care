"""KB loader: read JSONL files from the KB directory."""

from __future__ import annotations

import json
from pathlib import Path

from app.kb import KnowledgeItem


def load_kb(kb_dir: str | Path) -> list[KnowledgeItem]:
    """Load all `.jsonl` files from `kb_dir` and parse into KnowledgeItem.

    Silently skips empty files. Raises on malformed lines.
    """
    kb_dir = Path(kb_dir)
    items: list[KnowledgeItem] = []
    if not kb_dir.exists():
        return items

    for jsonl_file in sorted(kb_dir.glob("*.jsonl")):
        with jsonl_file.open("r", encoding="utf-8") as f:
            for lineno, raw in enumerate(f, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    data = json.loads(raw)
                    items.append(KnowledgeItem(**data))
                except (json.JSONDecodeError, ValueError) as e:
                    raise ValueError(
                        f"Malformed KB entry in {jsonl_file}:{lineno}: {e}"
                    ) from e
    return items


def iter_embedding_inputs(items: list[KnowledgeItem]) -> list[tuple[str, str]]:
    """Return list of (item_id, text) for embedding.

    Each item produces one embedding input (concatenated question+content).
    """
    return [(item.id, item.to_embedding_text()) for item in items]