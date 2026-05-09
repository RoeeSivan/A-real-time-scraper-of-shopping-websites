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
5. ✅ **Tier 3 (LLM rescue) — DONE 2026-05-09.** `tiers/llm.py` reuses
   tier 1's `HEADERS` + `LOCALE_COOKIES` to fetch the **search page** with
   httpx, strips to visible text via BeautifulSoup `.get_text(separator=" ")`
   (drops `<script|style|noscript|svg|iframe>`), truncates to 25K chars
   (cost cap, well under gpt-4o-mini's 128K context), then calls
   `client.beta.chat.completions.parse(model="gpt-4o-mini", temperature=0,
   response_format=ProductExtraction)` — OpenAI's structured-outputs API.
   Imports `ProductExtraction` from `tiers/firecrawl.py` so both AI-driven
   tiers share one Pydantic schema. Slotted into the orchestrator between
   `browser` and `firecrawl` ([orchestrator.py:33-36](backend/app/orchestrator.py#L33-L36)).
   **Cost note**: ~6K input tokens per call → fractions of a cent on
   gpt-4o-mini. Live verified: Amazon "Sony WH-1000XM5" returned title /
   $199.99 / 4.2★ / 19400 reviews in ~3.2s, OpenAI 200 OK.

   **Side effect**: since BestBuy / Walmart / Newegg all have
   `has_selectors=False`, the LLM tier is now their **primary** path
   (firecrawl is the safety net beneath it). Amazon also goes LLM-first
   today (selectors disabled — see Amazon follow-up). Methods badge in the
   UI will mostly read `llm` until step 8 enables selectors.
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
8. ✅ **Add BestBuy + Walmart + Newegg** — `sites/{bestbuy,walmart,newegg}.py`
   each implement `build_search_url` + `parse_search_candidates` +
   `parse_product` with `has_selectors=True`. Orchestrator's `_tiers_for`
   routes them through tiers 1+2 first, then 3+4. Search-card short-circuit
   in [tiers/basic.py](backend/app/tiers/basic.py) skips the product-page
   fetch when the card already has price (Walmart/BB/Newegg all do). 38
   pytest tests pass (8 BB/Walmart/Newegg fixture tests included).
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
    with `StatusBadge`. **Link column** added — opens `product_url` in a
    new tab. *Pending in this step:* USD↔ILS display toggle, and a
    distinctive visual redesign (currently in flight, see follow-up).

    **Bugfixes baked in (2026-05-09):**
    - `ResultsTable.tsx:7` — `SITES` array now matches backend casing
      exactly (`"Amazon.com"`, `"BestBuy.com"`, `"Walmart.com"`,
      `"Newegg.com"`). Lowercase keys silently produced an empty `<tbody>`.
    - `ResultRow.tsx:24` — site cell renders `result.site` directly; the
      old `charAt(0).toUpperCase() + slice(1) + ".com"` would have produced
      `"Amazon.com.com"` once names matched.
    - `sse.ts` — `error` listener now no-ops when `receivedDone === true`.
      EventSource fires a spurious `error` after the server closes the
      stream cleanly; without this guard, every successful run flashed the
      red banner.

Phase E — Polish
12. ✅ **Extra feature: PriceChart** — `recharts` bar chart of prices in
    [PriceChart.tsx](frontend/src/components/PriceChart.tsx). Cheapest bar
    rendered in `--color-coral` (`#c75d3f`), others in `--color-coral-soft`
    (`#e8a896`); axis ticks/labels in muted ink, hairline X-axis, no Y-axis
    line, mono tabular price labels above each bar. Header uses Fraunces
    italic + sage cheapest-price callout, matching the soft-editorial
    palette. USD↔ILS multiplier flows through `useCurrency()`. TS error in
    `Tooltip` formatter fixed by typing `value` as `unknown` and narrowing
    inline.
13. ✅ **Polish + record video** — [README.md](README.md) rewritten with
    features list, 4-tier explanation, test command, project layout, and
    the dev/manual run paths. Frontend `npm run build` clean, `tsc --noEmit`
    clean, ESLint clean, 38 backend tests pass. No leftover `console.log`
    in [sse.ts](frontend/src/lib/sse.ts) or
    [useSearch.ts](frontend/src/hooks/useSearch.ts) (already removed).
    Smoke test on 3 queries + demo video recording remain as user-driven
    final steps before submission.

## Domain notes

### "Most similar product" (critical assignment requirement)
- Score each search-page candidate title with
  `rapidfuzz.fuzz.partial_ratio(query, title)` — **best-substring** match,
  not token-set. The latter (used previously) collapsed real product /
  wrong product / accessory titles to identical scores for verbose queries
  like "Lenovo Tab P12-2024".
- Pick highest above **`DEFAULT_THRESHOLD = 75.0`** in `matching.py`.
- After product page is fetched, **re-verify** the final title's similarity.
- Live benchmark documented in
  [matching.py](backend/app/matching.py): real product 84.8, wrong product
  66.7, accessory 78.9 (still passes — see follow-ups), unrelated ~25.

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

> ✅ **Done 2026-05-09 — Frontend redesign (soft editorial).** PRICE.TERMINAL
> was abandoned in favor of a calmer, magazine-like aesthetic the user
> explicitly asked for ("human friendly and nice to look at"). Plan file:
> `~/.claude/plans/lets-do-a-design-gentle-melody.md`. Rewrote
> `layout.tsx` (Fraunces + Geist + Geist Mono), `globals.css` (Tailwind v4
> `@theme` with cream/ink/coral/sage/amber/brick tokens — all CRT/scanline
> CSS deleted), `page.tsx` (oversized italic-serif "Pricewise" wordmark,
> coral accent), `SearchBar.tsx` (paper card with coral focus glow),
> `ResultsTable.tsx` (hairline dividers, no zebra), `ResultRow.tsx`
> (Fraunces italic product titles, tabular Geist Mono prices, soft cream
> skeletons), `StatusBadge.tsx` (text-only "Found" / "No match" labels,
> no pill backgrounds). **Favicon** installed via Next.js 16 App Router
> convention: source `frontend/512 pricewise.png` copied to
> `frontend/src/app/icon.png` and `frontend/src/app/apple-icon.png` —
> Next auto-injects the `<link>` tags, no metadata config needed.

1. **Wishlist / search history (next feature — user-requested).** Add an
   "Add to wishlist" button per result row so a returning user can see
   everything they previously searched for. Implementation sketch (no
   external services needed for v1):
   - **Storage:** `localStorage` keyed by query — store
     `{ query, savedAt, results: ScrapeResult[] }`. Survives refreshes,
     no backend, no auth. If the user wants cross-device later, swap to
     a Supabase row keyed by anon UUID — but don't build that now.
   - **UI:** small bookmark icon in the row's action column (next to
     `View →`), filled when saved. Plus a `/wishlist` route (or a
     drawer) that lists past queries with their cheapest price at save
     time and a "search again" button that re-runs the SSE stream and
     updates the entry.
   - **Open question for user:** save **per-row** (one product on one
     site) or save **per-query** (the whole 4-site comparison)? Default
     recommendation: **per-query** — matches the assignment's framing
     and is less click-heavy.

2. **Step 8 — Per-site selectors for BestBuy / Walmart / Newegg.** Today
   they ride tier 4 only (`has_selectors=False`), so the demo's fallback
   story is "LLM → Firecrawl" with no tier 1/2 in sight. Add
   `parse_search_candidates` + `parse_product` to each so tiers 1+2 can
   run for cheaper/faster results, and the cascade is **visibly four-tier
   deep** for grading.

3. **Step 12 — `PriceChart` polish (extra feature).** Already wired
   into `page.tsx`, but currently has a pre-existing TS type error in
   the recharts `formatter` prop. Tighten the type, restyle to match
   the new soft-editorial palette (coral bars, cream background, no
   harsh axis lines), and confirm cheapest is highlighted.

> ✅ **Done 2026-05-09 — USD↔ILS toggle.** New
> [lib/currency.ts](frontend/src/lib/currency.ts) (`formatPrice` helper),
> [hooks/useCurrency.tsx](frontend/src/hooks/useCurrency.tsx) (context
> provider that fetches `GET /rate?target=ILS` once on mount; falls back
> to USD-only and disables the ILS pill if the fetch fails),
> [components/CurrencyToggle.tsx](frontend/src/components/CurrencyToggle.tsx)
> (pill toggle styled to match soft-editorial palette, shows live rate).
> `<CurrencyProvider>` wraps `page.tsx`. `ResultRow` and `PriceChart`
> route through `useCurrency().format()`; chart bars + axis + labels
> rescale when switched to ILS. Backend untouched.

> ✅ **Done 2026-05-09 — `LiveClock.tsx` deleted** (user). Resolves the
> pre-existing `hour24` TS errors carried over from the abandoned
> PRICE.TERMINAL aesthetic.

4. **Cleanup before demo recording.** Remove the diagnostic `console.log`
   calls in
   [frontend/src/lib/sse.ts](frontend/src/lib/sse.ts) and
   [frontend/src/hooks/useSearch.ts](frontend/src/hooks/useSearch.ts)
   (added during the empty-rows debug session — they were left in
   intentionally). 

5. **Step 13 — Polish + demo video.** README polish, error/loading states
   tightened, smoke test on 3 queries (one easy: headphones; one with a
   typo / partial query; one out-of-stock or rare item to exercise the
   fallback gauntlet), then record the submission demo.

6. **Amazon tier 1/2 price extraction is still flaky** — see Amazon
   follow-up below. Not blocking (tier 3 LLM and tier 4 Firecrawl both
   rescue it), but worth fixing for grading on the fallback narrative.

## Known bugs (dedicated debugging session — not blockers individually)

User flagged several quality issues across recent searches. Bundle these
into a single focused session — most share root causes (LLM/Firecrawl
non-determinism + similarity-only matching).

1. **LLM non-determinism on Amazon for under-specified queries.** Same
   query, consecutive runs, different outcomes:
   - Run A: returns the *right* product ("Lenovo Tab P12 128 GB W128594033")
     with `price=None` — multi-variant card, no headline price.
     Validator (relaxed) now accepts via "See variants →" — ✓ user-facing OK.
   - Run B: returns the *wrong* product ("Lenovo Idea Tab Pro") with a
     real price ($335.24) — similarity 66.7 → validator rejects.
   The model picks different listings each call. Mitigations:
   `temperature=0` is already set; consider tightening the user prompt to
   anchor on the query's primary identifier ("must contain 'P12-2024' or
   'P12 (2024)' near the title start"), or re-ranking the top-K LLM
   suggestions by our own similarity gate before extracting price.

2. **Contract / down-payment prices showing as headline price.** Live
   examples:
   - "iPhone 16" on Walmart → tier 1 returned **$6.00** (T-Mobile
     down-payment) for `T-Mobile iPhone 16 128GB Ultramarine`, not the
     actual phone price.
   - Title was correct; price extraction picked the marketing
     "$6/month" or "$6 down" headline. Validator only checks `price > 0`.
   Fix: a "plausible price" floor per query category (smartphones >$300,
   laptops >$300, headphones >$30, …) — or compare extracted price
   against Firecrawl's price for the same query and reject obvious
   outliers.

3. **Wrong-variant false positive (similarity = 100% by substring).**
   Live: "iPhone 16" → Newegg returned `Refurbished iPhone 16 PRO MAX
   512GB` at $1094.99, sim=100. Query "iPhone 16" is a substring of the
   title, so partial_ratio rules it valid. Same family of bug as the
   Sony XM4-vs-XM5 / Lenovo accessory cases already documented under
   "Similarity metric still has known false positives" below.
   Fix: same negative-keyword / model-number-anchoring approach.

4. **Firecrawl extraction inconsistency.** For the same query, Firecrawl
   sometimes returns `{title=valid, price=valid}`, sometimes
   `{title=null, price=null}`, and sometimes `{title=query echoed,
   price=null}`. The "echo" case is now safely rejected because we
   stopped falling back `product_url` to the search URL (2026-05-09).
   But it explains why some users see a row succeed once and fail the
   next refresh. Mitigations: cache stable extractions for N seconds, or
   retry once on empty extractions before falling through.

5. **"Site does not carry this product" rendered as generic "Failed".**
   When BestBuy / Newegg legitimately don't sell the queried item (e.g.
   "Converse sneakers"), every tier returns null and the row says
   "Failed". UX-wise this looks like a scraper bug. Add a `not_carried`
   status (or just an inline subtitle on Failed rows: "No matching
   listing on this site") so the user knows it's a domain reality, not
   our fault.

6. **No visible "tier trace" in the UI.** Every result rolls up to a
   single `method` badge, but the cascade is one of the assignment's
   key features. Add a small expandable per-row that shows
   `basic ✗ → browser ✗ → llm ✗ → firecrawl ✓` so the grader (and the
   user) can see the fall-through happen. Cheap to add: orchestrator
   already has the info, just needs to be returned with `ScrapeResult`
   and rendered.

## Follow-ups (revisit later, not blockers)

- **Similarity metric still has known false positives** that no single
  scalar score can resolve cleanly. With `partial_ratio` + threshold 75,
  these all pass:
  - **Same-family different version** — "Sony WH-1000XM5" matches
    "Sony WH-1000XM4" at 96.6
  - **Base vs Pro variants** — "iPhone 16" vs "iPhone 16 Pro Max" both 100
  - **Accessory FOR product** — "Lenovo Tab P12-2024" vs
    "BONAEVER Keyboard Case for Lenovo Tab P12" scores 78.9 → accepted
    even though it's an accessory, not the tablet (observed live on
    Newegg's Firecrawl extraction).

  Resolving these requires either (a) an accessory/negative-keyword filter
  (e.g. reject titles containing `case|cover|stand|cable|charger|adapter`
  unless the *query* contains the same word), (b) a model-number extractor
  that requires the query's primary model identifier to appear in the
  title, or (c) asking the LLM/Firecrawl prompt to refuse accessories.
  Out of scope until the assignment basics ship.

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
