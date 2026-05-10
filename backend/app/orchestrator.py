"""Per-site fallback pipeline + parallel multi-site runner.

`run_pipeline(site, query)` walks the available tiers in order:
    basic (httpx) → browser (Playwright) → llm (gpt-4o-mini) → firecrawl
and stops at the first one whose result clears the validators.

Sites with `has_selectors=False` skip basic+browser and start at the
LLM tier (which only needs the search page's visible text, no per-site
selectors).
"""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable

from app.models import ScrapeResult, ScrapeStatus, TierAttempt
from app.sites.amazon import amazon
from app.sites.base import SiteConfig
from app.sites.bestbuy import bestbuy
from app.sites.newegg import newegg
from app.sites.walmart import walmart
from app.tiers.basic import basic_scrape
from app.tiers.browser import browser_scrape
from app.tiers.firecrawl import firecrawl_scrape
from app.tiers.llm import llm_scrape
from app.validators import is_valid_result

log = logging.getLogger(__name__)

# In-memory pipeline cache. Keyed by (site_name, query_lower); only successful
# results are cached so failures keep retrying with fresh tier runs.
# TTL is short (60s) so demo replays are stable but the data stays fresh.
CACHE_TTL_SECONDS = 60
_pipeline_cache: dict[tuple[str, str], tuple[float, ScrapeResult]] = {}


def _cache_get(site_name: str, query: str) -> ScrapeResult | None:
    key = (site_name, query.strip().lower())
    entry = _pipeline_cache.get(key)
    if entry is None:
        return None
    expires_at, result = entry
    if time.monotonic() > expires_at:
        _pipeline_cache.pop(key, None)
        return None
    return result


def _cache_put(site_name: str, query: str, result: ScrapeResult) -> None:
    key = (site_name, query.strip().lower())
    _pipeline_cache[key] = (time.monotonic() + CACHE_TTL_SECONDS, result)


def clear_cache() -> None:
    """Test/CLI hook — drop all cached entries."""
    _pipeline_cache.clear()

ALL_SITES: list[SiteConfig] = [amazon, bestbuy, walmart, newegg]

TierFn = Callable[[SiteConfig, str], Awaitable[ScrapeResult]]
SELECTOR_TIERS: list[tuple[str, TierFn]] = [
    ("basic", basic_scrape),
    ("browser", browser_scrape),
]
EXTERNAL_TIERS: list[tuple[str, TierFn]] = [
    ("llm", llm_scrape),
    ("firecrawl", firecrawl_scrape),
]


def _tiers_for(site: SiteConfig) -> list[tuple[str, TierFn]]:
    """Selector tiers only run for sites whose `has_selectors` is True.

    LLM + Firecrawl are universal — they parse the search page's text /
    Firecrawl's AI extraction, so they don't need per-site selectors.
    """
    if site.has_selectors:
        return SELECTOR_TIERS + EXTERNAL_TIERS
    return EXTERNAL_TIERS


async def run_pipeline(site: SiteConfig, query: str) -> ScrapeResult:
    """Walk tiers for one site; return the first result that validates.

    Records every tier's outcome on the returned `ScrapeResult.tier_trace`
    so the frontend can show the actual cascade (`basic ✗ → llm ✓` etc.).
    """
    last_failure: ScrapeResult | None = None
    trace: list[TierAttempt] = []
    for tier_name, tier_fn in _tiers_for(site):
        try:
            result = await tier_fn(site, query)
        except Exception as exc:  # belt-and-braces — tier funcs already catch
            log.warning("%s/%s raised: %s", site.name, tier_name, exc)
            err = f"{type(exc).__name__}: {exc}"
            trace.append(TierAttempt(tier=tier_name, outcome="errored", error=err))
            last_failure = ScrapeResult(
                site=site.name,
                status=ScrapeStatus.FAILED,
                error=f"{tier_name}: {err}",
            )
            continue

        if is_valid_result(result, query):
            log.info("%s succeeded via tier=%s", site.name, tier_name)
            trace.append(TierAttempt(tier=tier_name, outcome="succeeded"))
            # Attach the trace so the row carries it through SSE.
            result.tier_trace = trace
            return result

        log.info(
            "%s/%s rejected by validator: status=%s title=%r price=%r",
            site.name, tier_name, result.status, result.title, result.price,
        )
        trace.append(
            TierAttempt(
                tier=tier_name,
                outcome="rejected",
                error=result.error or _summarize_rejection(result),
            )
        )
        last_failure = result

    if last_failure is not None:
        # Promote the last attempt's error message so the user sees *why* it failed.
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error=last_failure.error or "all tiers failed validation",
            tier_trace=trace,
        )
    return ScrapeResult(
        site=site.name,
        status=ScrapeStatus.FAILED,
        error="No tiers configured for this site",
        tier_trace=trace,
    )


def _summarize_rejection(result: ScrapeResult) -> str:
    """Human-friendly reason when a tier returned SUCCESS but the validator
    rejected it (low similarity, missing fields, etc.)."""
    if not result.title:
        return "no title extracted"
    if result.price is None and not result.product_url:
        return "no price and no product link"
    if result.price is not None and result.price <= 0:
        return "non-positive price"
    return "low similarity to query"


async def run_all_sites(
    query: str,
    sites: list[SiteConfig] | None = None,
) -> AsyncIterator[ScrapeResult]:
    """Run all site pipelines concurrently, yielding each result as it finishes.

    Order is determined by completion time, not by the `sites` argument —
    that's the whole point of streaming.
    """
    targets = sites or ALL_SITES

    async def _safe(site: SiteConfig) -> ScrapeResult:
        cached = _cache_get(site.name, query)
        if cached is not None:
            log.info("%s served from cache", site.name)
            return cached
        try:
            result = await run_pipeline(site, query)
        except Exception as exc:  # final guard — one site never breaks the run
            return ScrapeResult(
                site=site.name,
                status=ScrapeStatus.FAILED,
                error=f"orchestrator: {type(exc).__name__}: {exc}",
            )
        if result.status is ScrapeStatus.SUCCESS:
            _cache_put(site.name, query, result)
        return result

    tasks = [asyncio.create_task(_safe(site)) for site in targets]
    for completed in asyncio.as_completed(tasks):
        yield await completed
