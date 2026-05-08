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
from collections.abc import AsyncIterator, Awaitable, Callable

from app.models import ScrapeResult, ScrapeStatus
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
    """Walk tiers for one site; return the first result that validates."""
    last_failure: ScrapeResult | None = None
    for tier_name, tier_fn in _tiers_for(site):
        try:
            result = await tier_fn(site, query)
        except Exception as exc:  # belt-and-braces — tier funcs already catch
            log.warning("%s/%s raised: %s", site.name, tier_name, exc)
            last_failure = ScrapeResult(
                site=site.name,
                status=ScrapeStatus.FAILED,
                error=f"{tier_name}: {type(exc).__name__}: {exc}",
            )
            continue

        if is_valid_result(result, query):
            log.info("%s succeeded via tier=%s", site.name, tier_name)
            return result

        log.info(
            "%s/%s rejected by validator: status=%s title=%r price=%r",
            site.name, tier_name, result.status, result.title, result.price,
        )
        last_failure = result

    if last_failure is not None:
        # Promote the last attempt's error message so the user sees *why* it failed.
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error=last_failure.error or "all tiers failed validation",
        )
    return ScrapeResult.failed(site.name)


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
        try:
            return await run_pipeline(site, query)
        except Exception as exc:  # final guard — one site never breaks the run
            return ScrapeResult(
                site=site.name,
                status=ScrapeStatus.FAILED,
                error=f"orchestrator: {type(exc).__name__}: {exc}",
            )

    tasks = [asyncio.create_task(_safe(site)) for site in targets]
    for completed in asyncio.as_completed(tasks):
        yield await completed
