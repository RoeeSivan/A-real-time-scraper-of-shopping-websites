"""Tier 2: real Chromium via Playwright + stealth evasions.

Slower than tier 1 (browser launch + page render) but defeats the bot-checks
that block bare httpx requests. Uses the **same site-specific parsers** as
tier 1 — we just feed Playwright's rendered HTML into them.
"""

from urllib.parse import urlparse

from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)
from playwright_stealth import Stealth

from app.matching import pick_best_candidate, score
from app.models import Method, ScrapeResult, ScrapeStatus
from app.sites.base import SiteConfig
from app.tiers.basic import HEADERS, LOCALE_COOKIES

PAGE_TIMEOUT_MS = 30_000


def _cookie_domain(base_url: str) -> str:
    """Return ".amazon.com" given "https://www.amazon.com" — works for any site."""
    host = urlparse(base_url).hostname or ""
    parts = host.split(".")
    if len(parts) >= 2:
        return "." + ".".join(parts[-2:])
    return host


async def browser_scrape(site: SiteConfig, query: str) -> ScrapeResult:
    """Run tier 2 for one site and return a ScrapeResult."""
    try:
        async with Stealth().use_async(async_playwright()) as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    user_agent=HEADERS["User-Agent"],
                    locale="en-US",
                    timezone_id="America/Los_Angeles",
                    viewport={"width": 1366, "height": 900},
                )

                # Same locale cookies as tier 1, scoped to this site's parent domain.
                domain = _cookie_domain(site.base_url)
                await context.add_cookies(
                    [
                        {"name": k, "value": v, "domain": domain, "path": "/"}
                        for k, v in LOCALE_COOKIES.items()
                    ]
                )

                page = await context.new_page()
                page.set_default_timeout(PAGE_TIMEOUT_MS)

                # 1) search
                await page.goto(
                    site.build_search_url(query), wait_until="domcontentloaded"
                )
                search_html = await page.content()
                candidates = site.parse_search_candidates(search_html)
                if not candidates:
                    return ScrapeResult(
                        site=site.name,
                        status=ScrapeStatus.FAILED,
                        error="browser: no candidates parsed (challenge page or layout change)",
                    )

                picked = pick_best_candidate(query, candidates)
                if picked is None:
                    return ScrapeResult(
                        site=site.name,
                        status=ScrapeStatus.FAILED,
                        error="browser: no candidate cleared similarity threshold",
                    )
                candidate, search_sim = picked

                # 2) product page
                await page.goto(candidate.url, wait_until="domcontentloaded")
                product_html = await page.content()
                fields = site.parse_product(product_html)

                # Re-score similarity against the FINAL product-page title.
                final_similarity = (
                    score(query, fields.title) if fields.title else search_sim
                )

                return ScrapeResult(
                    site=site.name,
                    status=ScrapeStatus.SUCCESS,
                    method=Method.BROWSER,
                    title=fields.title,
                    price=fields.price,
                    rating=fields.rating,
                    review_count=fields.review_count,
                    product_url=candidate.url,
                    similarity=final_similarity,
                )
            finally:
                await browser.close()
    except PlaywrightTimeoutError as exc:
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error=f"browser: timeout: {exc}",
        )
    except Exception as exc:
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error=f"browser: {type(exc).__name__}: {exc}",
        )
