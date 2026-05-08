"""Tier 4: Firecrawl. External scraping API — handles fetching, bot evasion,
and structured extraction in a single call. The "give up on our own infra" tier.

We hand Firecrawl the **search** URL plus a Pydantic schema and let it do AI
extraction server-side. One round trip per site, no selector or stealth-cookie
work on our side. Returns title / price / rating / review_count / product_url
already structured.
"""

import logging
from typing import Any

from firecrawl import AsyncFirecrawl
from firecrawl.v2.types import JsonFormat
from pydantic import BaseModel, Field

from app.config import settings
from app.matching import score
from app.models import Method, ScrapeResult, ScrapeStatus
from app.sites.base import SiteConfig

log = logging.getLogger(__name__)


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
        f"You are looking at a product search results page. Find the listing "
        f"that best matches the query: \"{query}\". Extract its fields per the "
        f"schema. The product_url MUST be a direct link to that product's "
        f"detail page (not an image CDN URL, not the search page). Use null "
        f"for any field that is not visibly shown on the page — do not invent "
        f"values."
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
    product_url = data.get("product_url") or search_url

    if not title:
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error="firecrawl: extraction missing title",
        )

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
        similarity=score(query, title),
    )
