"""Tier 1: requests + BeautifulSoup. Fast, free, easily blocked."""

import httpx

from app.matching import pick_best_candidate, score
from app.models import Method, ScrapeResult, ScrapeStatus
from app.sites.base import SiteConfig

# Headers cribbed from the oxylabs Amazon scraping guide
# (https://github.com/oxylabs/how-to-scrape-amazon-product-data) — Safari-on-Mac
# UA + Google referer is the combo their tutorial recommends and it tends to
# get past Amazon's basic bot heuristics more reliably than a Chrome UA.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_1) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.1 Safari/605.1.15"
    ),
    "Accept-Language": "da, en-gb, en",
    # Only advertise encodings httpx auto-decodes. Including "br" or "zstd"
    # makes some sites (BestBuy, Newegg) return brotli/zstd-compressed HTML
    # that httpx hands back as raw bytes — tier 1 BS4 parses garbage,
    # tier 3 LLM gets binary noise. Plain gzip/deflate is always decoded.
    "Accept-Encoding": "gzip, deflate",
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Referer": "https://www.google.com/",
}

REQUEST_TIMEOUT = 20.0

# Pin Amazon (and any site that honours these cookies) to USD pricing,
# regardless of the geo of the IP making the request. Without this, an
# Israeli IP gets ILS prices on amazon.com.
LOCALE_COOKIES = {
    "i18n-prefs": "USD",
    "lc-main": "en_US",
}


async def basic_scrape(site: SiteConfig, query: str) -> ScrapeResult:
    """Run the basic-tier pipeline for one site.

    Flow: search URL → BS4 candidates → pick best → product page → parse fields.
    Returns a ScrapeResult with status=SUCCESS and method=BASIC iff every step
    produced data; otherwise a FAILED result with a descriptive `error`.
    The orchestrator decides whether to fall through to tier 2 based on the
    validators, not on the status alone.
    """
    async with httpx.AsyncClient(
        headers=HEADERS,
        cookies=LOCALE_COOKIES,
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        try:
            search_resp = await client.get(site.build_search_url(query))
            search_resp.raise_for_status()
        except httpx.HTTPError as exc:
            return ScrapeResult(
                site=site.name,
                status=ScrapeStatus.FAILED,
                error=f"basic: search fetch failed: {exc}",
            )

        candidates = site.parse_search_candidates(search_resp.text)
        if not candidates:
            return ScrapeResult(
                site=site.name,
                status=ScrapeStatus.FAILED,
                error="basic: no candidates parsed (likely bot-blocked or layout changed)",
            )

        picked = pick_best_candidate(query, candidates)
        if picked is None:
            return ScrapeResult(
                site=site.name,
                status=ScrapeStatus.FAILED,
                error="basic: no candidate cleared similarity threshold",
            )
        candidate, similarity = picked

        # Short-circuit: if the search card already populated all of
        # title+price (rating/reviews allowed null), skip the product-page
        # fetch entirely. Sites like Walmart render everything we need on
        # the search-results page itself.
        if candidate.price is not None:
            return ScrapeResult(
                site=site.name,
                status=ScrapeStatus.SUCCESS,
                method=Method.BASIC,
                title=candidate.title,
                price=candidate.price,
                rating=candidate.rating,
                review_count=candidate.review_count,
                product_url=candidate.url,
                similarity=similarity,
            )

        try:
            product_resp = await client.get(candidate.url)
            product_resp.raise_for_status()
        except httpx.HTTPError as exc:
            return ScrapeResult(
                site=site.name,
                status=ScrapeStatus.FAILED,
                error=f"basic: product fetch failed: {exc}",
            )

        fields = site.parse_product(product_resp.text)

        # Re-verify similarity against the FINAL product-page title. Search-page
        # cards sometimes show one title while the product page is a different
        # listing (sponsored swaps, redirects, etc.). The orchestrator's
        # validator gate will fall through if this dropped below threshold.
        final_similarity = (
            score(query, fields.title) if fields.title else similarity
        )

        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.SUCCESS,
            method=Method.BASIC,
            title=fields.title,
            price=fields.price,
            rating=fields.rating,
            review_count=fields.review_count,
            product_url=candidate.url,
            similarity=final_similarity,
        )
