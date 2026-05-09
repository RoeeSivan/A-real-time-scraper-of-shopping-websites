"""Tier 4: Firecrawl. External scraping API — handles fetching, bot evasion,
and structured extraction in a single call. The "give up on our own infra" tier.

We hand Firecrawl the **search** URL plus a Pydantic schema and let it do AI
extraction server-side. One round trip per site, no selector or stealth-cookie
work on our side. Returns title / price / rating / review_count / product_url
already structured.
"""

import logging
import re
from typing import Any

from firecrawl import AsyncFirecrawl
from firecrawl.v2.types import JsonFormat
from pydantic import BaseModel, Field

from app.config import settings
from app.matching import score
from app.models import Method, ScrapeResult, ScrapeStatus
from app.sites.base import SiteConfig

log = logging.getLogger(__name__)

# Amazon ASINs are always 10 alphanumeric chars. Both `/dp/<ASIN>` and
# `/gp/product/<ASIN>` are valid product page paths; everything else
# (search URLs, tracking links, image CDN paths, slug-based URLs without
# an ASIN) routes to Amazon's "Sorry, we couldn't find that page" 404.
_AMAZON_ASIN = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})", re.IGNORECASE)


def canonicalize_product_url(site_name: str, url: str | None) -> str | None:
    """Normalise a product URL so the frontend's "View →" link doesn't 404.

    For Amazon, extract the ASIN and rebuild as `https://www.amazon.com/dp/<ASIN>`
    — strips slug, tracking params, and the rare image-CDN URL the LLM/Firecrawl
    extractor sometimes produces. Returns `None` when no ASIN can be found, so
    the validator can fall through to a deterministic search URL.

    For non-Amazon sites this is a no-op for now; their URL formats are simpler
    and slug-based, and we haven't observed broken links from those tiers.
    """
    if not url:
        return None
    if "amazon." in site_name.lower() or "amazon." in url.lower():
        m = _AMAZON_ASIN.search(url)
        if m:
            asin = m.group(1).upper()
            return f"https://www.amazon.com/dp/{asin}"
        return None
    return url


class ProductExtraction(BaseModel):
    """Schema Firecrawl's AI extractor fills in from the search-results page."""

    title: str | None = Field(
        default=None,
        description="Full product title as shown on the listing.",
    )
    price: float | None = Field(
        default=None,
        description="Current price in USD as a plain number (e.g. 278.00). "
        "Do not include currency symbols. If the price is shown in another "
        "currency, leave null.",
    )
    rating: float | None = Field(
        default=None,
        description="Average star rating between 0 and 5 (e.g. 4.6). "
        "Null if not displayed.",
    )
    review_count: int | None = Field(
        default=None,
        description="Total number of reviews/ratings. Null if not displayed.",
    )
    product_url: str | None = Field(
        default=None,
        description="Absolute URL to the product detail page (not an image, "
        "not the search page itself).",
    )


def _build_prompt(query: str) -> str:
    return (
        f"You are looking at a product search results page. Find the ORGANIC "
        f"listing (not sponsored, not 'related items', not accessories) that "
        f"BEST matches the query: \"{query}\". The listing's title MUST contain "
        f"the model identifier from the query (e.g. for 'iPhone 16' the title "
        f"must say 'iPhone 16'; for 'Sony WH-1000XM5' it must say 'XM5'). "
        f"REJECT accessories — anything whose title starts with 'Case for', "
        f"'Cover for', 'Stand for', 'Charger for', or contains keywords like "
        f"'replacement', 'screen protector', 'cable', 'mount' UNLESS the query "
        f"itself asks for those. If no organic listing matches the query "
        f"closely, return null for ALL fields rather than guessing.\n\n"
        f"Extract the matched listing per the schema. The product_url MUST be "
        f"a direct link to that product's detail page (not an image CDN URL, "
        f"not the search page). Use null for any field that is not visibly "
        f"shown on the page — do not invent values."
    )


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Strip currency / whitespace; first match of an int/decimal wins.
        import re
        cleaned = value.replace(",", "")
        match = re.search(r"\d+(?:\.\d+)?", cleaned)
        return float(match.group()) if match else None
    return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        import re
        cleaned = value.replace(",", "")
        match = re.search(r"\d+", cleaned)
        return int(match.group()) if match else None
    return None


async def firecrawl_scrape(site: SiteConfig, query: str) -> ScrapeResult:
    if not settings.firecrawl_api_key:
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error="firecrawl: FIRECRAWL_API_KEY not configured",
        )

    fc = AsyncFirecrawl(api_key=settings.firecrawl_api_key)
    search_url = site.build_search_url(query)
    log.debug("firecrawl: %s search_url=%s", site.name, search_url)

    try:
        doc = await fc.scrape(
            search_url,
            formats=[
                JsonFormat(
                    type="json",
                    prompt=_build_prompt(query),
                    schema=ProductExtraction,
                )
            ],
            only_main_content=True,
            location={"country": "US", "languages": ["en-US"]},
        )
    except Exception as exc:
        log.error("firecrawl scrape error for %s: %s: %s", site.name, type(exc).__name__, exc)
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error=f"firecrawl: {type(exc).__name__}: {str(exc)[:200]}",
        )

    extracted = getattr(doc, "json", None)
    if not extracted:
        log.warning("firecrawl: %s returned no JSON extraction", site.name)
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error="firecrawl: empty extraction",
        )

    # Firecrawl may return either a dict or a model instance depending on SDK
    # version — normalise to a plain dict.
    if hasattr(extracted, "model_dump"):
        data = extracted.model_dump()
    elif isinstance(extracted, dict):
        data = extracted
    else:
        data = dict(extracted)  # last-ditch coercion

    title = data.get("title")
    price = _coerce_float(data.get("price"))
    rating = _coerce_float(data.get("rating"))
    review_count = _coerce_int(data.get("review_count"))
    product_url = canonicalize_product_url(site.name, data.get("product_url"))

    if not title:
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error="firecrawl: extraction missing title",
        )

    # If the extractor returned a real title that scores above similarity
    # threshold, but couldn't pin down a product URL (or it was an Amazon
    # URL we rejected because it had no ASIN), fall back to the search URL
    # so the user gets a clickable result. This only kicks in when the
    # title is clearly on-topic — echo-back hallucinations
    # (title==query verbatim) score lower and won't qualify.
    sim = score(query, title)
    if not product_url and sim >= 70:
        product_url = search_url

    log.info(
        "firecrawl %s: title=%r price=%s rating=%s reviews=%s",
        site.name, title, price, rating, review_count,
    )

    return ScrapeResult(
        site=site.name,
        status=ScrapeStatus.SUCCESS,
        method=Method.FIRECRAWL,
        title=title,
        price=price,
        rating=rating,
        review_count=review_count,
        product_url=product_url,
        similarity=sim,
    )
