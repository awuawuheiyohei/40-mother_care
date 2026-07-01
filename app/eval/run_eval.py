"""Eval harness: measures retrieval accuracy against labeled queries.

Usage:
    python -m app.eval.run_eval                  # uses mock index if no real key
    python -m app.eval.run_eval --report md     # also writes Markdown report
    python -m app.eval.run_eval --top-k 1 3 5   # reports Hit@1, Hit@3, Hit@5

Output: per-query hit rate + per-scenario breakdown + overall MRR.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from app.config import get_settings
from app.kb.loader import load_kb
from app.rag.embedder import get_embedder
from app.rag.retriever import Retriever, RetrievalHit, reset_retriever
from app.rag.vector_store import FaissStore


@dataclass
class EvalQuery:
    query: str
    expected_id: str
    scenario: str = ""
    age_range: str = ""
    variant: str = ""  # canonical / paraphrase / user_realistic


@dataclass
class EvalResult:
    query: EvalQuery
    hit_ids: list[str]
    expected_rank: int | None  # 1-indexed; None if not in top-k
    scores: list[float] = field(default_factory=list)


@dataclass
class EvalSummary:
    total: int = 0
    hit_at_1: int = 0
    hit_at_3: int = 0
    hit_at_5: int = 0
    mrr_sum: float = 0.0
    by_scenario: dict[str, dict[str, float]] = field(default_factory=dict)
    misses: list[EvalResult] = field(default_factory=list)

    def to_dict(self, k_values: list[int]) -> dict:
        return {
            "total": self.total,
            "hit_at_k": {f"hit@{k}": getattr(self, f"hit_at_{k}") / max(1, self.total) for k in k_values},
            "mrr": self.mrr_sum / max(1, self.total),
            "by_scenario": self.by_scenario,
            "miss_count": len(self.misses),
        }


def load_eval_set(path: str | Path) -> list[EvalQuery]:
    queries: list[EvalQuery] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            queries.append(EvalQuery(**data))
    return queries


def _build_retriever() -> Retriever:
    s = get_settings()
    if not Path(s.rag_index_path).exists():
        raise FileNotFoundError(f"Index not found at {s.rag_index_path}. Run build_index first.")
    store = FaissStore.load(s.rag_index_path, dim=s.embed_dim)
    items = load_kb(s.rag_kb_path)
    # Sanity: indexed items should match KB
    if len(store.kb.items) != len(items):
        raise RuntimeError(
            f"KB/Index mismatch: KB has {len(items)} items, index has {len(store.kb.items)}."
        )
    embedder = get_embedder()
    return Retriever(
        embedder=embedder,
        store=store,
        source_weights=s.source_weights,
        min_score=0.0,  # Don't filter during eval
        top_k=max(5, 5),
    )


def evaluate(retriever: Retriever, queries: Iterable[EvalQuery], top_k: int = 5) -> EvalSummary:
    summary = EvalSummary()
    scenario_buckets: dict[str, list[EvalResult]] = defaultdict(list)

    for q in queries:
        hits = retriever.retrieve(q.query)[:top_k]
        hit_ids = [h.item.id for h in hits]
        expected_rank = None
        for i, hid in enumerate(hit_ids, start=1):
            if hid == q.expected_id:
                expected_rank = i
                break
        result = EvalResult(
            query=q,
            hit_ids=hit_ids,
            expected_rank=expected_rank,
            scores=[h.score for h in hits],
        )
        summary.total += 1
        if expected_rank == 1:
            summary.hit_at_1 += 1
        if expected_rank is not None and expected_rank <= 3:
            summary.hit_at_3 += 1
        if expected_rank is not None and expected_rank <= 5:
            summary.hit_at_5 += 1
        if expected_rank is not None:
            summary.mrr_sum += 1.0 / expected_rank
        else:
            summary.misses.append(result)
        scenario_buckets[q.scenario or "unknown"].append(result)

    # Per-scenario aggregation
    for scenario, results in scenario_buckets.items():
        n = len(results)
        if n == 0:
            continue
        summary.by_scenario[scenario] = {
            "n": n,
            "hit_at_1": sum(1 for r in results if r.expected_rank == 1) / n,
            "hit_at_3": sum(1 for r in results if r.expected_rank is not None and r.expected_rank <= 3) / n,
            "hit_at_5": sum(1 for r in results if r.expected_rank is not None and r.expected_rank <= 5) / n,
        }
    return summary


def render_report(summary: EvalSummary, embedder_mode: str, k_values: list[int]) -> str:
    out = []
    out.append("# Retrieval Evaluation Report")
    out.append("")
    out.append(f"- Embedder mode: **{embedder_mode}**")
    out.append(f"- Total queries: **{summary.total}**")
    out.append("")
    out.append("## Overall")
    out.append("")
    out.append("| Metric | Score |")
    out.append("|---|---|")
    for k in k_values:
        hit = getattr(summary, f"hit_at_{k}") / max(1, summary.total)
        out.append(f"| Hit@{k} | {hit:.3f} ({getattr(summary, f'hit_at_{k}')}/{summary.total}) |")
    out.append(f"| MRR | {summary.mrr_sum / max(1, summary.total):.3f} |")
    out.append("")
    out.append("## By scenario")
    out.append("")
    out.append("| Scenario | N | Hit@1 | Hit@3 | Hit@5 |")
    out.append("|---|---|---|---|---|")
    for scenario, stats in sorted(summary.by_scenario.items()):
        out.append(
            f"| {scenario} | {int(stats['n'])} | "
            f"{stats['hit_at_1']:.2f} | {stats['hit_at_3']:.2f} | {stats['hit_at_5']:.2f} |"
        )
    out.append("")
    if summary.misses:
        out.append(f"## Misses ({len(summary.misses)})")
        out.append("")
        out.append("| Query | Expected | Top-3 hits |")
        out.append("|---|---|---|")
        for m in summary.misses[:30]:
            q = m.query.query.replace("|", "/")[:50]
            top3 = ", ".join(m.hit_ids[:3]) or "(empty)"
            out.append(f"| {q} | {m.query.expected_id} | {top3} |")
        if len(summary.misses) > 30:
            out.append(f"\n_… and {len(summary.misses) - 30} more misses_")
    return "\n".join(out)


def main() -> None:
    parser = argparse.ArgumentParser(description="Retrieval evaluation harness")
    parser.add_argument("--eval-path", default="./app/kb/eval_data.jsonl")
    parser.add_argument("--top-k", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument("--report", choices=["none", "md"], default="none")
    args = parser.parse_args()

    reset_retriever()
    retriever = _build_retriever()
    embedder = retriever.embedder
    embedder_mode = "MOCK (hash-based)" if embedder.mock else f"REAL ({embedder.model})"

    queries = load_eval_set(args.eval_path)
    if not queries:
        raise SystemExit(f"No eval queries in {args.eval_path}")

    print(f"[eval] embedder: {embedder_mode}")
    print(f"[eval] loaded {len(queries)} eval queries")

    summary = evaluate(retriever, queries, top_k=max(args.top_k))

    print()
    print("=" * 60)
    print(f"Total: {summary.total}")
    for k in args.top_k:
        hit = getattr(summary, f"hit_at_{k}") / max(1, summary.total)
        print(f"Hit@{k}: {hit:.3f}  ({getattr(summary, f'hit_at_{k}')}/{summary.total})")
    print(f"MRR:    {summary.mrr_sum / max(1, summary.total):.3f}")
    print("=" * 60)

    print()
    print("By scenario:")
    for scenario, stats in sorted(summary.by_scenario.items()):
        print(
            f"  {scenario:24s} n={int(stats['n']):3d}  "
            f"H@1={stats['hit_at_1']:.2f}  H@3={stats['hit_at_3']:.2f}  H@5={stats['hit_at_5']:.2f}"
        )

    if summary.misses:
        print(f"\nMisses ({len(summary.misses)}):")
        for m in summary.misses[:10]:
            print(f"  Q: {m.query.query[:60]}")
            print(f"     expected={m.query.expected_id} got_top3={m.hit_ids[:3]}")

    if args.report == "md":
        report = render_report(summary, embedder_mode, args.top_k)
        out_path = Path("./data/eval_report.md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"\nReport saved: {out_path}")


if __name__ == "__main__":
    main()