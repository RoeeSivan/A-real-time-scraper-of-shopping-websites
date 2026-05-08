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
2. ✅ **Models + matching + validators** — `ScrapeResult`/`Method`/`Status`
   enums in `models.py`; `matching.py` (`pick_best_candidate`, `score`,
   `DEFAULT_THRESHOLD = 55`); `validators.py` (`is_valid_result` — gates on
   status, title length, positive price, bot-check phrases, similarity).
   **20 pytest tests pass**, no network calls.
3. ✅ **Tier 1 (Basic) for Amazon only** — `sites/base.py` (SiteConfig +
   ProductFields + parse helpers), `sites/amazon.py` (URL builder + selectors,
   robust price selector chain), `tiers/basic.py` (httpx + BS4, re-verifies
   similarity against the **final product-page title**), `app/cli.py`
   (`uv run python -m app.cli "<query>"`). 10 offline fixture tests added —
   **all 30 tests pass**. Threshold bumped 55 → 70 after empirical check
   (token_set_ratio gives "Lenovo Tab P12-2024" vs "Lenovo Idea Tab Pro" = 69,
   correct vs unrelated cases give 100 / ~21 — 70 splits cleanly).
   **Currency: USD forced via `i18n-prefs=USD` + `lc-main=en_US` cookies on
   the httpx client.** Without these, Israeli geo gets ILS. Same cookies
   should be set on the Playwright context in step 4. Plan a USD↔ILS
   display toggle in the frontend (step 11) — backend always stores USD.
4. ✅ **Tier 2 (Browser) for Amazon** — `tiers/browser.py` uses
   `Stealth().use_async(async_playwright())` (playwright-stealth 2.x API).
   Reuses tier 1's `HEADERS`, `LOCALE_COOKIES`, and Amazon parsers — only
   the fetch mechanism differs. Cookie domain is derived from `site.base_url`
   so the same code works for all 4 sites later. Chromium installed via
   `uv run playwright install chromium`. **Verified live**: stealth-passed
   Amazon, returned title/rating/reviews, and currency confirmed **USD**
   (`$39.99` etc., not `ILS…`). CLI: `uv run python -m app.cli "<q>" amazon browser`.
5. ⏳ **Tier 3 (LLM) for Amazon** — `tiers/llm.py`. Feeds **visible text**
   (not raw HTML) into GPT-4o-mini with a Pydantic schema. Acts as a
   rescue parser when upstream selectors fail. **Deferred** — built tier 4
   first as an "easy win" pivot. **OpenAI API reachability verified
   2026-05-09** via 5-token ping (`gpt-4o-mini-2024-07-18` returned `ok`,
   13 tokens billed) — key in `.env` works, so this step is unblocked.
6. ✅ **Tier 4 (Firecrawl) — works for all 4 sites** (regressed → restored
   2026-05-09). `tiers/firecrawl.py` calls
   `AsyncFirecrawl.scrape(search_url, formats=[JsonFormat(type="json",
   prompt=..., schema=ProductExtraction)])` — one round trip per site,
   Firecrawl does fetching + bot evasion + **AI extraction** server-side and
   returns a structured dict at `doc.json`. Schema is a Pydantic model with
   `title / price (USD float) / rating / review_count / product_url` and
   field-level descriptions that double as extraction hints. We coerce
   numbers from strings (e.g. `"$278.00"` → `278.0`) before building the
   `ScrapeResult`. Site configs for BestBuy / Walmart / Newegg added with
   just `build_search_url` (no selectors needed for tier 4).
   `sites/base.py` parse methods default to empty so tier 1/2 fail cleanly
   on sites without selectors. Live test (`Sony WH-1000XM5 headphones`):
   - Amazon: $246.78, 4.2★, 19400 reviews ✅
   - BestBuy: $278.00, 4.6★, 6285 reviews ✅
   - Walmart: $278.00, 4.3★, 1421 reviews ✅
   - Newegg: $239.95, 4.7★, 5 reviews ✅

   **API import path** (firecrawl-py 4.25.x): `JsonFormat` is no longer at
   the package root — it lives at `firecrawl.v2.types.JsonFormat`. The
   response field is `doc.json` (a dict matching the schema). Importing
   `from firecrawl import JsonFormat` will fail.

Phase C — Multi-site
7. ✅ **Orchestrator + Amazon end-to-end fallback** — `orchestrator.py` chains
   tiers 1→4 with the validation gate between each. Demo by forcing tier 1
   to fail.
8. ⏳ **Add BestBuy + Walmart + Newegg** — new `sites/<name>.py` per site;
   tiers stay generic.
9. ✅ **Parallel orchestration** — `asyncio.gather(..., return_exceptions=True)`
   + `asyncio.Queue` for streaming. One-site failure does not block others.

Phase D — Real-time + Frontend
10. ✅ **SSE endpoint** — `GET /search?q=...` returns `EventSourceResponse`,
    yielding one `event: result` per site as it completes, plus `event: done`.
    Test with `curl -N` first.
11. ✅ **Frontend wiring** — `useSearch` hook (`hooks/useSearch.ts`) opens an
    `EventSource` via `lib/sse.ts`, dedupes by `site`, cleans up on unmount.
    `app/page.tsx` renders `SearchBar` + `ResultsTable`; rows show skeletons
    until that site's `event: result` arrives, then flip to `ResultRow`
    with `StatusBadge`. *Pending in this step:* USD↔ILS display toggle (see
    follow-up below — backend already exposes `GET /rate?target=ILS`).

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

## What's left (open work, in priority order)

1. **Step 5 — Tier 3 (LLM rescue)** — write `tiers/llm.py`. OpenAI access
   is already verified (see step 5). Plan: pull visible text from the
   product page (not raw HTML), pass to `gpt-4o-mini` with a Pydantic
   schema mirroring `ProductExtraction`, return a `ScrapeResult`. Slot it
   into the orchestrator between `browser` and `firecrawl`.
2. **Step 8 — Per-site selectors for BestBuy / Walmart / Newegg.** Today
   they ride tier 4 only (`has_selectors=False`). Add `parse_search_candidates`
   + `parse_product` so tiers 1+2 can run for cheaper/faster results.
3. **Step 12 — `PriceChart` (extra feature).** `recharts` bar chart of
   per-site prices, cheapest highlighted, updates as SSE events arrive.
4. **Step 13 — Polish + demo video.** README polish, error/loading states,
   smoke test on 3 queries, then record the submission demo.
5. **USD↔ILS frontend toggle.** Backend done (`GET /rate?target=ILS`).
   Frontend needs to fetch once on mount and multiply USD prices when
   user clicks.
6. **Amazon tier 1/2 price extraction is still flaky** — see follow-up
   below. Not blocking since tier 4 (firecrawl) rescues it, but worth
   fixing for assignment grading on the fallback story.

## Follow-ups (revisit later, not blockers)

- **Don't regress firecrawl back to markdown-only parsing.** On 2026-05-08
  the tier was rewritten to `formats=["markdown"]` + regex link scraping,
  which (a) hardcoded `price=None`, making every result fail validation
  (validators.py requires `price > 0`), and (b) extracted titles from the
  first `[text](url)` link, which on Amazon is an `<img>` alt — leaving
  titles like `"![Sony WH-1000XM5..."` and `product_url` pointing at an
  image CDN. Fix (2026-05-09) restored the JSON-schema extraction path.
  If you ever need to debug firecrawl extractions, ADD a markdown fallback,
  don't REPLACE the JSON path.
- ~~Verify USD cookie actually flips Amazon prices~~ ✅ confirmed in step 4
  via Playwright peek (`$X.XX` not `ILSX.XX`).
- **Amazon price extraction is currently broken on most product pages**:
  - Switched to oxylabs-style headers (Safari UA + Google referer) — keep.
  - Switched to oxylabs-style price selector (`span.a-offscreen` first match)
    — too greedy, picks up accessory / "frequently bought together" prices.
    Recent live runs returned $5, $21.95, $39.99 for the Sony WH-1000XM5
    page where real prices range $16–$398. Saved one such page at
    `/tmp/amazon_xm5.html` for later forensics.
  - Also: search-card layout flipped — link is no longer inside `<h2>`.
    Updated `parse_search_candidates` to handle both old + new layouts.
  - **Plan to fix:** rely on tier 3 (LLM extraction) and tier 4 (Firecrawl)
    to rescue Amazon price extraction. Tier 1/2 will keep returning bogus
    prices for some pages — the orchestrator's validators (with a sane price
    range check) will reject them and fall through.
- **USD↔ILS display toggle** in the frontend table (step 11/13). Backend
  side is **done**: `app/exchange.py` + `GET /rate?target=ILS` returns
  `{base,target,rate}` from Frankfurter (ECB data, no API key, 1h cache).
  Frontend just needs to fetch this once on mount and multiply USD prices
  when the user clicks the toggle.

## Out of scope

- No caching (every search is fresh).
- No auth, no DB, no cloud deploy.
- One extra feature only (the chart).
