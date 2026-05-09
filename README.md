# Real-Time Product Price Scraper

University assignment (HW3, Exercise 1). User types a product name, the app
scrapes Amazon, BestBuy, Walmart, and Newegg **in parallel**, and streams the
results back row-by-row over Server-Sent Events.

Each site flows through a 4-tier fallback pipeline:
**Basic (httpx + BS4) → Browser (Playwright + stealth) → LLM (GPT-4o-mini) →
Firecrawl**. If a tier is blocked or the data is incomplete/wrong-product, the
next tier takes over. If all four fail, that one site is reported as failed and
the others continue.

## Stack

- **Frontend:** Next.js 16 + TypeScript + App Router + Tailwind v4
- **Backend:** FastAPI + `sse-starlette` + asyncio
- **Scraping:** httpx, BeautifulSoup, Playwright, OpenAI (GPT-4o-mini),
  Firecrawl
- **Similarity:** `rapidfuzz` (token-set ratio against the user's query)

## Setup

### 1. Environment variables

Create a `.env` at the repo root:

```
FIRECRAWL_API_KEY=<your firecrawl key>
OPENAI_API_KEY=<your openai key>
```

Both keys are required to exercise the full 4-tier pipeline. Tiers 1 and 2 work
without them; tier 3 needs `OPENAI_API_KEY`; tier 4 needs `FIRECRAWL_API_KEY`.

### 2. One-shot dev (recommended)

From the repo root:

```bash
./dev.sh
```

Starts both the backend (uvicorn :8000) and the frontend (next dev :3000) in
one terminal, with logs prefixed `[backend]` / `[frontend]`. Ctrl+C stops both.

Open <http://localhost:3000>. Backend health check: <http://localhost:8000/health>.

### 3. Manual (two terminals)

If you'd rather run them separately:

```bash
# Terminal A
cd backend && uv sync && uv run uvicorn app.main:app --reload --port 8000

# Terminal B
cd frontend && npm install && npm run dev
```

First-time backend setup also needs `uv run playwright install chromium` for
tier 2.

## Project layout

```
.
├── .env                  # gitignored — your real keys
├── backend/
│   ├── pyproject.toml
│   └── app/
│       ├── main.py       # FastAPI app
│       ├── config.py     # env loading
│       ├── sites/        # per-site URL builders + selectors
│       └── tiers/        # the 4 extraction methods
└── frontend/
    └── src/app/page.tsx  # the search UI
```

## Status

Build is staged into 13 phases — see `CLAUDE.md` for current progress and the
plan file referenced therein for full detail.
