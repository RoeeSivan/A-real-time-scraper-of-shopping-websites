"""LLM-backed sanity layer on top of the scraper cascade.

Three helpers, each independently disable-able:

1. `rewrite_queries(query, sites)` — one structured-output call that maps a
   sloppy user query ("bose qc ultra") to the canonical product name each
   retailer's search engine indexes ("Bose QuietComfort Ultra Headphones").
   Called once per multi-site search, only for cache-miss sites.

2. `verify_title(query, title)` — yes/no judgement on whether a scraped
   title is the product the user actually asked for. Wired into the tier
   loop after `is_valid_result`; a False reading is treated identically to
   a validator rejection and triggers the next tier.

3. `flag_price_outliers(results, deviation)` — pure cross-site median
   gate. Returns site names whose price deviates more than `deviation`
   from the median of all SUCCESS prices. Needs ≥3 priced samples or
   it returns [] (too noisy to judge).

Module-level `AsyncOpenAI` client is shared with `tiers.llm` via
`get_openai_client()` so a search no longer pays the per-call client
construction tax.

Every helper degrades gracefully: if `enable_llm_verification` is False,
or `OPENAI_API_KEY` is missing, or the LLM call raises, they return a
safe pass-through (identity rewrite / verify=True / no outliers). That
keeps the offline test suite and demo replays green without mocks.
"""

import logging
import statistics

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.config import settings
from app.models import ScrapeResult, ScrapeStatus

log = logging.getLogger(__name__)

# gpt-4o-mini is the cost/latency sweet spot for short structured calls —
# matches the tier-3 LLM scraper so we don't pay for two model variants.
MODEL = "gpt-4o-mini"

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI | None:
    """Lazy-singleton AsyncOpenAI. Returns None when no API key is configured
    so callers can short-circuit instead of crashing."""
    global _client
    if not settings.openai_api_key:
        return None
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _client


def reset_client() -> None:
    """Test hook: drop the cached client so re-reading settings takes effect."""
    global _client
    _client = None


def _enabled() -> bool:
    return bool(settings.enable_llm_verification and settings.openai_api_key)


# ---------------------------------------------------------------------------
# 1. Per-site query rewrite
# ---------------------------------------------------------------------------

class _RewriteEntry(BaseModel):
    site: str = Field(..., description="Site name exactly as given in the input list.")
    rewritten_query: str = Field(
        ...,
        description=(
            "Canonical product name the site's search engine indexes. Expand "
            "abbreviations, fix spelling, add the product line, but do NOT add "
            "specs the user didn't mention. If the original query is already "
            "canonical, return it unchanged."
        ),
    )


class _RewriteResponse(BaseModel):
    rewrites: list[_RewriteEntry]


_REWRITE_SYSTEM = (
    "You are a search-query normalizer for product comparison shopping. "
    "Given a user's raw query and a list of retailer site names, return one "
    "canonical search string per site that maximizes the chance their on-site "
    "search returns the product the user meant. "
    "Rules: expand shorthand (qc → QuietComfort, mbp → MacBook Pro), fix "
    "obvious typos, keep brand + product-line + model identifier. NEVER add "
    "specs (color, storage, RAM, CPU) the user didn't specify. NEVER invent a "
    "newer/older version. If the query is already clean, repeat it verbatim. "
    "Output one entry per requested site, using the exact site name."
)


async def rewrite_queries(query: str, site_names: list[str]) -> dict[str, str]:
    """Return `{site_name: canonical_query}` for every site in `site_names`.

    Identity (`{site: query}` for all) is returned when verification is
    disabled, the API key is missing, the site list is empty, or the call
    raises. Sites the model omits get the original query.
    """
    if not site_names:
        return {}
    if not _enabled():
        return {s: query for s in site_names}
    client = get_openai_client()
    if client is None:
        return {s: query for s in site_names}

    user_prompt = (
        f"User query: {query!r}\n"
        f"Retailer sites: {site_names}\n\n"
        "Return one rewrite per site."
    )
    try:
        completion = await client.beta.chat.completions.parse(
            model=MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": _REWRITE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            response_format=_RewriteResponse,
        )
    except Exception as exc:
        log.warning("rewrite_queries LLM call failed: %s: %s", type(exc).__name__, exc)
        return {s: query for s in site_names}

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        log.warning("rewrite_queries returned no parsed output")
        return {s: query for s in site_names}

    out: dict[str, str] = {}
    for entry in parsed.rewrites:
        cleaned = (entry.rewritten_query or "").strip()
        if entry.site in site_names and cleaned:
            out[entry.site] = cleaned
    # Fill any site the model skipped with the original query.
    for s in site_names:
        out.setdefault(s, query)
    log.info("rewrite_queries(%r) → %s", query, out)
    return out


# ---------------------------------------------------------------------------
# 2. Title verification
# ---------------------------------------------------------------------------

class _VerifyResponse(BaseModel):
    matches: bool = Field(..., description="True iff the title is the product the user asked for.")
    reason: str = Field(
        ...,
        description="One short sentence. If matches=False, explain what's off.",
    )


_VERIFY_SYSTEM = (
    "You judge whether a scraped product title is what the user searched for. "
    "Return matches=True only when the title clearly refers to the SAME product "
    "family, line, AND model/version the user named. "
    "Reject (matches=False) if the title is: a different version (XM4 vs XM5), "
    "a different variant when the user didn't specify one (Pro vs base), an "
    "accessory (case, cover, mount, stand, charger, cable), refurbished/renewed "
    "when the user didn't ask for it, or just unrelated. "
    "Tolerate small noise: bundles, color/storage suffixes when the user didn't "
    "specify, retailer SKU codes."
)


async def verify_title(query: str, title: str | None) -> tuple[bool, str]:
    """LLM yes/no on title↔query alignment. Returns `(matches, reason)`.

    Pass-through `(True, "skipped")` when disabled or no API key, so callers
    can treat skipped == accepted without a separate code path.
    """
    if not title:
        return False, "empty title"
    if not _enabled():
        return True, "skipped"
    client = get_openai_client()
    if client is None:
        return True, "skipped"

    user_prompt = f"Query: {query!r}\nTitle: {title!r}\n\nDoes the title match the query?"
    try:
        completion = await client.beta.chat.completions.parse(
            model=MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": _VERIFY_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            response_format=_VerifyResponse,
        )
    except Exception as exc:
        log.warning("verify_title LLM call failed: %s: %s — passing through", type(exc).__name__, exc)
        return True, "verify-call-failed"

    parsed = completion.choices[0].message.parsed
    if parsed is None:
        return True, "verify-no-parse"
    log.info("verify_title(%r ↔ %r) → matches=%s reason=%s", query, title, parsed.matches, parsed.reason)
    return parsed.matches, parsed.reason


# ---------------------------------------------------------------------------
# 3. Cross-site price outlier flag
# ---------------------------------------------------------------------------

# Sentinel for the helper signature — kept here so consumers don't repeat the
# literal threshold in every call site.
DEFAULT_PRICE_DEVIATION = 0.30


def flag_price_outliers(
    results: list[ScrapeResult],
    deviation: float = DEFAULT_PRICE_DEVIATION,
) -> tuple[list[str], float | None]:
    """Return (outlier_site_names, median_price). Pure function.

    A result is an outlier iff `abs(price - median) / median > deviation` —
    i.e. the price differs from the cross-site median by more than the
    threshold (default 30%). Requires at least 3 valid priced samples;
    fewer than that and the median is statistically too noisy → returns
    ([], median) or ([], None).
    """
    priced = [
        r for r in results
        if r.status is ScrapeStatus.SUCCESS
        and r.price is not None
        and r.price > 0
    ]
    if len(priced) < 3:
        return [], (statistics.median(r.price for r in priced) if priced else None)

    median = statistics.median(r.price for r in priced)
    if median <= 0:
        return [], median

    outliers: list[str] = []
    for r in priced:
        if abs(r.price - median) / median > deviation:
            outliers.append(r.site)
    return outliers, median
