"""KB lint: enforce quality and consistency rules on KB entries.

Rules:
1. Required fields: id, question, content, source, tags, confidence
2. Recommended fields: source_url, warning_signs, last_updated
3. confidence must be one of: high / medium / low
4. source_url must be present (empty string allowed for verified-personal sources)
5. id must be unique across all files
6. Tags must be non-empty list

Usage:
    python -m app.kb.lint                # check only, exit 1 if errors
    python -m app.kb.lint --fix-urls     # auto-fill missing source_url from source heuristic
    python -m app.kb.lint --strict       # warnings treated as errors
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


REQUIRED = ["id", "question", "content", "source", "tags", "confidence"]
RECOMMENDED = ["source_url", "warning_signs", "last_updated"]
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


# Heuristic URL fillers: based on `source` text, suggest a URL
SOURCE_URL_RULES = [
    (r"中国国家卫健委.*?指南.*?（?(\d{4})）?", "http://www.nhc.gov.cn/yzygj/s7659/"),
    (r"中国国家卫健委", "http://www.nhc.gov.cn/yzygj/"),
    (r"中华医学会.*?指南", "https://www.cma.org.cn/"),
    (r"中华医学会", "https://www.cma.org.cn/"),
    (r"WHO", "https://www.who.int/zh"),
    (r"CDC", "https://www.cdc.gov/"),
    (r"UpToDate", "https://www.uptodate.com/"),
    (r"NICE", "https://www.nice.org.uk/"),
    (r"AAP", "https://www.healthychildren.org/"),
    (r"UpToDate", "https://www.uptodate.com/"),
    (r"梅奥诊所", "https://www.mayoclinic.org/zh-hans"),
    (r"uptodate", "https://www.uptodate.com/"),
]


def suggest_url(source: str) -> str:
    """Suggest a URL based on source text pattern."""
    if not source:
        return ""
    for pattern, url in SOURCE_URL_RULES:
        if re.search(pattern, source):
            return url
    return ""


def lint_kb(
    strict: bool = False,
    fix_urls: bool = False,
    downgrade_unverified: bool = False,
) -> tuple[int, int, list[str]]:
    """Lint all KB files. Returns (errors, warnings, messages)."""
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()

    files = sorted(Path("app/kb/data").glob("*.jsonl"))
    if not files:
        errors.append("❌ No KB files found in app/kb/data/")
        return len(errors), len(warnings), errors + warnings

    for f in files:
        entries: list[tuple[int, dict]] = []
        with f.open() as fh:
            for lineno, raw in enumerate(fh, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    d = json.loads(raw)
                except json.JSONDecodeError as e:
                    errors.append(f"❌ {f.name}:{lineno} JSON 解析失败: {e}")
                    continue
                entries.append((lineno, d))

        for lineno, d in entries:
            entry_id = d.get("id", f"<unnamed @ {f.name}:{lineno}>")
            prefix = f"  {f.name}:{lineno} {entry_id}"

            # Required fields
            for field in REQUIRED:
                if field not in d:
                    errors.append(f"❌{prefix} 缺必填字段: {field}")
                elif not d.get(field) and field != "tags":
                    errors.append(f"❌{prefix} 必填字段为空: {field}")
            # tags must be non-empty list
            if "tags" in d and (not isinstance(d.get("tags"), list) or not d["tags"]):
                errors.append(f"❌{prefix} tags 必须是非空列表")

            # confidence value
            if d.get("confidence") not in ALLOWED_CONFIDENCE:
                errors.append(
                    f"❌{prefix} confidence 必须是 {ALLOWED_CONFIDENCE} 之一，得到: {d.get('confidence')!r}"
                )

            # source_url: present but can be empty for verified-personal
            if "source_url" not in d:
                if fix_urls and d.get("source"):
                    suggested = suggest_url(d["source"])
                    if suggested:
                        d["source_url"] = suggested
                        warnings.append(f"🔧{prefix} 自动填 source_url: {suggested}")
                    else:
                        d["source_url"] = ""
                        warnings.append(f"🔧{prefix} 自动填 source_url: \"\"（无规则匹配）")
                else:
                    errors.append(f"❌{prefix} 缺 source_url 字段（即使为空也要写）")
            elif d.get("source_url") is None:
                # Convert explicit null to empty string (more consistent)
                if fix_urls:
                    d["source_url"] = ""
                    warnings.append(f"🔧{prefix} source_url: null → \"\"（统一规范）")
                else:
                    warnings.append(f"⚠️{prefix} source_url 是 null（建议改成空字符串）")

            # CRITICAL safety rule: high confidence requires source_url
            # Unless the source is a doctor/nurse record (no public URL exists,
            # but the record itself is high-trust per the user's verification).
            source = d.get("source", "")
            is_medical_record = (
                source.startswith("Doctor") or source.startswith("Nurse")
            )

            if d.get("confidence") == "high" and not d.get("source_url") and not is_medical_record:
                if downgrade_unverified:
                    d["confidence"] = "medium"
                    warnings.append(
                        f"⬇️{prefix} confidence: high → medium（因 source_url 缺失，避免误信）"
                    )
                else:
                    errors.append(
                        f"❌{prefix} confidence=high 但 source_url 为空（不安全：用户会误信），"
                        f"要么填具体 URL，要么把 confidence 降到 medium/low"
                    )
            elif is_medical_record and not d.get("source_url"):
                # Medical records (Doctor/Nurse) can be high without URL,
                # but require the source field to mention a hospital/doctor name
                if "@" not in source:
                    errors.append(
                        f"❌{prefix} Doctor/Nurse 来源必须有 @医院名 标注（无 URL 必须靠医院标识补偿）"
                    )
                elif not re.search(r"\d{4}-\d{2}-\d{2}", source):
                    errors.append(
                        f"❌{prefix} Doctor/Nurse 来源必须包含日期（YYYY-MM-DD 格式）"
                    )

            # Recommended fields
            for field in RECOMMENDED:
                if field == "source_url":
                    continue  # handled above
                if field not in d:
                    warnings.append(f"⚠️{prefix} 缺推荐字段: {field}")
                elif field == "warning_signs" and (not isinstance(d.get(field), list)):
                    warnings.append(f"⚠️{prefix} warning_signs 应为列表")

            # ID uniqueness
            if entry_id in seen_ids:
                errors.append(f"❌{prefix} 重复 ID: {entry_id}")
            else:
                seen_ids.add(entry_id)

            # Content sanity
            content = d.get("content", "")
            if isinstance(content, str) and len(content) < 20:
                warnings.append(f"⚠️{prefix} content 太短（{len(content)} 字符），可能不完整")

            # Question must end with ? or ？
            q = d.get("question", "")
            if isinstance(q, str) and q and not q.rstrip().endswith(("?", "？", "。")):
                warnings.append(f"⚠️{prefix} question 结尾不规范: {q[-20:]}")

        # Write back if any auto-fix happened
        needs_write = False
        if fix_urls and any("自动填" in m or "统一规范" in m for m in warnings if f.name in m):
            needs_write = True
        if downgrade_unverified and any("⬇️" in m for m in warnings if f.name in m):
            needs_write = True
        if needs_write:
            with f.open("w", encoding="utf-8") as fh:
                for _, d in entries:
                    fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    return len(errors), len(warnings), errors + warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Lint the KB for quality and consistency")
    parser.add_argument("--fix-urls", action="store_true", help="Auto-fill missing source_url from source pattern")
    parser.add_argument("--downgrade-unverified", action="store_true",
                        help="Auto-downgrade confidence high → medium for entries with empty source_url")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args()

    print("🔍 Linting KB files...")
    print()

    errors, warnings, messages = lint_kb(
        strict=args.strict,
        fix_urls=args.fix_urls,
        downgrade_unverified=args.downgrade_unverified,
    )

    # Print categorized
    for m in messages:
        print(m)

    print()
    print("━" * 50)
    print(f"❌ Errors:   {errors}")
    print(f"⚠️  Warnings: {warnings}")
    print(f"📁 Total files: {len(list(Path('app/kb/data').glob('*.jsonl')))}")
    total_entries = sum(1 for f in Path("app/kb/data").glob("*.jsonl") for line in f.open() if line.strip())
    print(f"📊 Total entries: {total_entries}")
    print()

    if errors > 0:
        print("💡 Tip: run with --fix-urls to auto-fix missing source_url fields")
        return 1
    if args.strict and warnings > 0:
        print("⚠️ Strict mode: warnings are errors")
        return 1
    print("✅ KB looks good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
