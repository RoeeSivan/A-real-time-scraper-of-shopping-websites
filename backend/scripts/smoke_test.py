"""Smoke-test the full 4-site cascade for 3 representative queries.

Runs `run_all_sites(query)` end-to-end (real HTTP + OpenAI + Firecrawl),
prints a per-site summary, and writes the raw JSON to
`backend/scripts/smoke_results.json` for the demo write-up.

Usage:
    uv run python -m scripts.smoke_test
"""

import asyncio
import json
import logging
import time
from pathlib import Path

from app.orchestrator import run_all_sites

QUERIES = [
    "Sony WH-1000XM5",
    "iPhone 16",
    "Lenovo Yoga Slim 7i",
]

OUT_PATH = Path(__file__).parent / "smoke_results.json"


def _fmt_trace(trace) -> str:
    if not trace:
        return "-"
    parts = []
    for attempt in trace:
        sigil = {"succeeded": "✓", "rejected": "✗", "errored": "!"}.get(
            attempt.outcome, "?"
        )
        parts.append(f"{attempt.tier}{sigil}")
    return " → ".join(parts)


async def run_query(query: str) -> dict:
    print(f"\n=== {query} ===")
    started = time.perf_counter()
    rows = []
    async for result in run_all_sites(query):
        elapsed = time.perf_counter() - started
        rows.append(result)
        winning_tier = next(
            (a.tier for a in (result.tier_trace or []) if a.outcome == "succeeded"),
            None,
        )
        price = f"${result.price:.2f}" if result.price is not None else "-"
        title = (result.title or "")[:60]
        print(
            f"  [{elapsed:5.1f}s] {result.site:<8} {result.status.value:<10} "
            f"tier={winning_tier or '-':<10} {price:<10} | {title}"
        )
        print(f"           trace: {_fmt_trace(result.tier_trace)}")
        if result.product_url:
            print(f"           url:   {result.product_url}")
        if result.error:
            print(f"           error: {result.error}")
    return {
        "query": query,
        "elapsed_total": round(time.perf_counter() - started, 2),
        "results": [r.model_dump(mode="json") for r in rows],
    }


async def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(name)s | %(levelname)s | %(message)s")
    runs = []
    for q in QUERIES:
        runs.append(await run_query(q))

    OUT_PATH.write_text(json.dumps(runs, indent=2))
    print(f"\n→ wrote {OUT_PATH}")

    print("\n=== SUMMARY ===")
    for run in runs:
        succeeded = sum(1 for r in run["results"] if r["status"] == "success")
        print(f"  {run['query']:<28} {succeeded}/4 sites succeeded ({run['elapsed_total']}s)")


if __name__ == "__main__":
    asyncio.run(main())
