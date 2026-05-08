# CLAUDE.md — context for this project

This is HW3 Exercise 1: a real-time product price scraper across Amazon,
BestBuy, Walmart, Newegg, with a 4-tier fallback pipeline per site, parallel
asyncio orchestration, and SSE streaming to a Next.js frontend.

## Working style for this project

- **Step-by-step with confirmation gates.** The user wants to confirm each
  numbered step (below) before the next one starts. Do not chain phases.
- **Make each step a runnable artifact.** No half-finished steps; every step
  ends with something the user can run.
- **One focused git commit per step.** The user has the repo connected to a
  private GitHub repo. Only commit when the user asks.
- **Keep the codebase organized.** Folders/files per the structure below.
- **Single `.env` only.** No `.env.example` — document required vars in
  README. (User explicitly removed `.env.example` and asked for one env file.)
- **Do NOT echo `.env` contents into chat output, commits, or example files.**
  Live keys live only in `.env`, which is gitignored.

## Stack (locked)

| Layer | Choice |
|---|---|
| Frontend | Next.js 16 + TypeScript + App Router + Tailwind v4 |
| Backend | FastAPI + `sse-starlette` + asyncio |
| Tier 1 — Basic | `httpx` + `beautifulsoup4` + `lxml` |
| Tier 2 — Browser | `playwright` + `playwright-stealth` |
| Tier 3 — LLM | OpenAI **GPT-4o-mini** via `openai` SDK + Pydantic schema |
| Tier 4 — External | `firecrawl-py` SDK |
| Similarity | `rapidfuzz` (`token_set_ratio`, threshold ~55) |
| Real-time | SSE (`sse-starlette`) |
| Chart (extra feature) | `recharts` — price comparison bar chart |
| Python pkgs | `uv` + `pyproject.toml` |
| Node pkgs | `npm` |

> Heads up: this Next.js is **v16.2.6**, newer than my training data. Read
> `frontend/node_modules/next/dist/docs/` (especially `01-app/`) before
> writing any new frontend code per `frontend/AGENTS.md`. `'use client'` is
> still the directive; standard Tailwind utilities still work.

## Folder structure (target)

```
assignment3-exercise1/
├── .env                           # gitignored
├── .gitignore                     # populated
├── README.md                      # how to run
├── CLAUDE.md                      # this file
│
├── backend/
│   ├── pyproject.toml             # uv-managed
│   ├── app/
│   │   ├── main.py                # FastAPI app + SSE /search
│   │   ├── config.py              # Pydantic Settings, reads ../.env
│   │   ├── models.py              # ScrapeResult, Method, Status enums
│   │   ├── orchestrator.py        # 4-tier pipeline + asyncio.gather
│   │   ├── matching.py            # rapidfuzz similarity
│   │   ├── validators.py          # is_valid_result()
│   │   ├── sites/{base,amazon,bestbuy,walmart,newegg}.py
│   │   └── tiers/{basic,browser,llm,firecrawl}.py
│   └── tests/{test_matching,test_validators}.py
│
└── frontend/
    └── src/
        ├── app/{layout.tsx,page.tsx,globals.css}
        ├── components/{SearchBar,ResultsTable,ResultRow,StatusBadge,PriceChart}.tsx
        ├── lib/{sse.ts,types.ts}
        └── hooks/useSearch.ts
```

## Build plan — 13 confirmation gates

Full plan with rationale lives at:
`/Users/roeesivan/.claude/plans/i-need-to-build-precious-quill.md`

Phase A — Foundation
1. ✅ **Project skeleton** — folders, `.gitignore`, README, both apps init'd,
   FastAPI `/health` endpoint, Next.js page calls it. *Both servers verified
   running.*

Phase B — Backend core (Python-first)
2. ⏳ **Models + matching + validators** — `ScrapeResult`/`Method`/`Status`
   enums in `models.py`; `matching.py` (`pick_best_candidate`, `score`);
   `validators.py` (`is_valid_result`); pytest coverage for both.
3. ⏳ **Tier 1 (Basic) for Amazon only** — `tiers/basic.py` + `sites/amazon.py`
   + small CLI shim `python -m app.cli "<query>"`.
4. ⏳ **Tier 2 (Browser) for Amazon** — `tiers/browser.py` w/ Playwright +
   stealth. Same CLI demo.
5. ⏳ **Tier 3 (LLM) for Amazon** — `tiers/llm.py`. Feeds **visible text**
   (not raw HTML) into GPT-4o-mini with a Pydantic schema. Acts as a
   rescue parser when upstream selectors fail.
6. ⏳ **Tier 4 (Firecrawl) for Amazon** — `tiers/firecrawl.py`. Firecrawl's
   `extract` with a JSON schema; this tier fetches its own pages.

Phase C — Multi-site
7. ⏳ **Orchestrator + Amazon end-to-end fallback** — `orchestrator.py` chains
   tiers 1→4 with the validation gate between each. Demo by forcing tier 1
   to fail.
8. ⏳ **Add BestBuy + Walmart + Newegg** — new `sites/<name>.py` per site;
   tiers stay generic.
9. ⏳ **Parallel orchestration** — `asyncio.gather(..., return_exceptions=True)`
   + `asyncio.Queue` for streaming. One-site failure does not block others.

Phase D — Real-time + Frontend
10. ⏳ **SSE endpoint** — `GET /search?q=...` returns `EventSourceResponse`,
    yielding one `event: result` per site as it completes, plus `event: done`.
    Test with `curl -N` first.
11. ⏳ **Frontend wiring** — `useSearch` hook opens an `EventSource`, table
    renders incrementally with skeletons + `StatusBadge`.

Phase E — Polish
12. ⏳ **Extra feature: PriceChart** — `recharts` bar chart of prices,
    cheapest highlighted, updates as prices stream in.
13. ⏳ **Polish + record video** — README polish, error/loading states, smoke
    test on 3 queries, then the demo recording for submission.

## Domain notes

### "Most similar product" (critical assignment requirement)
- Score each search-page candidate title with
  `rapidfuzz.fuzz.token_set_ratio(query, title)`.
- Pick highest above threshold (default **55**); else fall through.
- After product page is fetched, **re-verify** the final title's similarity.

### Validation rules (`validators.py`)
A `ScrapeResult` is valid iff:
- `title` non-empty AND `len(title) > 5`
- `price` is a positive float
- `similarity(query, title) >= threshold`
- title/page text doesn't contain bot/captcha phrases
  (`"robot check"`, `"are you a human"`, `"enter the characters"`, …)
- rating / review_count are allowed to be `null` (legitimately missing on
  many products)

### Per-site pipeline (pseudocode)

```python
async def run_pipeline(site, query):
    for tier in (basic, browser, llm, firecrawl):
        try:
            result = await tier.scrape(site, query)
            if is_valid(result, query):
                return result.with_method(tier.name)
        except Exception:
            continue
    return ScrapeResult.failed(site.name)
```

## Risks (already considered in the plan)

- Amazon/Newegg block tier 1 → tier 2 (stealth) is the workhorse.
- Newegg may need tier 4 (Cloudflare). Assignment only requires 3/4.
- LLM hallucinations → JSON schema + low temp + validators gate (price > 0,
  similarity threshold).
- SSE timeout on slow networks → emit a heartbeat event every ~10s.

## Out of scope

- No caching (every search is fresh).
- No auth, no DB, no cloud deploy.
- One extra feature only (the chart).
