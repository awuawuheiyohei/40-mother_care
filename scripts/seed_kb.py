"""Load KB JSONL files (neonate / infant / prenatal) into the KB directory.

Idempotent: skips files that already exist at the destination.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.config import get_settings


# Files to seed from app/kb/data/ to RAG_KB_PATH
SOURCE_FILES = ["neonate.jsonl", "infant.jsonl", "prenatal.jsonl"]


def main() -> None:
    s = get_settings()
    src_dir = Path(__file__).parent.parent / "app" / "kb" / "data"
    dst_dir = Path(s.rag_kb_path)
    dst_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for name in SOURCE_FILES:
        src = src_dir / name
        dst = dst_dir / name
        if not src.exists():
            print(f"[seed_kb] source missing: {src}")
            continue
        if dst.exists():
            print(f"[seed_kb] {dst} already exists, skipping (delete it first to re-seed)")
            continue
        shutil.copy(src, dst)
        n = sum(1 for _ in dst.open(encoding="utf-8") if _.strip())
        total += n
        print(f"[seed_kb] copied {src.name} -> {dst} ({n} entries)")

    print(f"[seed_kb] total new entries: {total}")


if __name__ == "__main__":
    main()