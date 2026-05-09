# Pricewise — Real-Time Product Price Scraper

University assignment (HW3, Exercise 1). Type a product, the app scrapes
**Amazon, BestBuy, Walmart, and Newegg in parallel**, and streams results
back row-by-row over Server-Sent Events.

Each site flows through a 4-tier fallback pipeline:

1. **Basic** — `httpx` + BeautifulSoup
2. **Browser** — Playwright + `playwright-stealth`
3. **LLM** — GPT-4o-mini (structured outputs) over the search page text
4. **Firecrawl** — AI extraction with a Pydantic schema

If a tier is blocked, returns the wrong product, or fails the validator
gate, the next tier takes over. If all four fail, that site is reported as
failed and the others continue.

## Features

- 4-tier fallback per site (basic → browser → llm → firecrawl)
- Parallel `asyncio.gather` orchestration — one slow site does not block others
- SSE streaming with per-row skeletons that flip to results as they land
- USD ↔ ILS toggle (live ECB rate, cached 1h via Frankfurter)
- Live price-comparison bar chart, cheapest highlighted
- Per-row method badge so the cascade is visible

## Stack

- **Frontend:** Next.js 16 + TypeScript + App Router + Tailwind v4 + recharts
- **Backend:** FastAPI + `sse-starlette` + asyncio
- **Scraping:** httpx, BeautifulSoup, Playwright, OpenAI (GPT-4o-mini), Firecrawl
- **Similarity:** `rapidfuzz` `partial_ratio` (threshold 75)

## Setup

### 1. Environment variables

Create a `.env` at the repo root:

```
FIRECRAWL_API_KEY=<your firecrawl key>
OPENAI_API_KEY=<your openai key>
```

Both keys are required to exercise the full 4-tier pipeline. Tiers 1 and 2
work without them; tier 3 needs `OPENAI_API_KEY`; tier 4 needs
`FIRECRAWL_API_KEY`.

### 2. One-shot dev (recommended)

From the repo root:

```bash
./dev.sh
```

Starts backend (uvicorn :8000) and frontend (next dev :3000) in one
terminal, with logs prefixed `[backend]` / `[frontend]`. Ctrl+C stops both.

Open <http://localhost:3000>. Backend health: <http://localhost:8000/health>.

### 3. Manual (two terminals)

```bash
# Terminal A
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000

# Terminal B
cd frontend && npm install && npm run dev
```

First-time backend setup also needs `uv run playwright install chromium`
for tier 2.

## Tests

```bash
cd backend && uv run pytest
```

38 offline tests cover matching, validators, and per-site fixture
parsing — no network calls.

## Project layout

```
.
├── .env                         # gitignored — your real keys
├── dev.sh                       # one-shot dev runner
├── backend/
│   ├── pyproject.toml
│   └── app/
│       ├── main.py              # FastAPI + SSE /search
│       ├── orchestrator.py      # 4-tier pipeline + asyncio.gather
│       ├── matching.py          # rapidfuzz scoring
│       ├── validators.py        # is_valid_result gate
│       ├── exchange.py          # USD↔ILS rate (Frankfurter)
│       ├── sites/               # per-site URL builders + selectors
│       └── tiers/               # the 4 extraction methods
└── frontend/
    └── src/
        ├── app/page.tsx         # search UI
        ├── components/          # SearchBar, ResultsTable, PriceChart, …
        ├── hooks/               # useSearch (SSE), useCurrency
        └── lib/                 # sse client, currency helpers, types
```

## Status

All 13 build phases complete. See [CLAUDE.md](CLAUDE.md) for full
phase-by-phase notes and follow-ups.
