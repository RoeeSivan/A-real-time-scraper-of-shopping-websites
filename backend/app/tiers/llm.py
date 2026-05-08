"""Tier 3: LLM rescue parser.

When tiers 1 (basic httpx) and 2 (Playwright stealth) fail — usually because
selectors broke or the page layout changed — we fall back to letting an LLM
read the search page directly.

Pipeline:
    1. Fetch the search page with httpx (same headers/cookies as tier 1).
    2. Strip to visible text via BeautifulSoup `.get_text()`.
    3. Truncate to a budget the model can handle cheaply.
    4. Ask `gpt-4o-mini` to pick the listing that best matches the query and
       return {title, price, rating, review_count, product_url} as structured
       output (Pydantic schema → OpenAI's structured-outputs API).
    5. Re-score similarity against what the model returned and build a
       `ScrapeResult` with `method=LLM`.

This is positioned between tier 2 and tier 4: cheaper than Firecrawl, but
slower / more expensive than the deterministic scrapers.
"""

import logging
from typing import Any

import httpx
from bs4 import BeautifulSoup
from openai import AsyncOpenAI

from app.config import settings
from app.matching import score
from app.models import Method, ScrapeResult, ScrapeStatus
from app.sites.base import SiteConfig
from app.tiers.basic import HEADERS, LOCALE_COOKIES, REQUEST_TIMEOUT
from app.tiers.firecrawl import ProductExtraction

log = logging.getLogger(__name__)

# Visible-text budget. gpt-4o-mini's context is huge (128K), so this is a
# cost cap, not a context cap. ~25K chars ≈ ~6K tokens of input — fits
# comfortably with the schema + system prompt and stays cheap.
MAX_TEXT_CHARS = 25_000

MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "You read product search pages and extract the listing that best matches "
    "the user's query. Return strictly the fields requested by the schema. "
    "Use null for any field not visible on the page. Do not invent values. "
    "Prefer prices in USD; if you only see another currency, return null for "
    "the price. The product_url MUST be a direct link to the product detail "
    "page (not an image, not the search page itself, not an ad)."
)


def _extract_visible_text(html: str) -> str:
    """Strip HTML to a flat blob of visible text.

    BeautifulSoup's `get_text(separator=' ')` is good enough — we don't need
    to preserve structure, only enough lexical content for the LLM to identify
    the matching listing and its fields.
    """
    soup = BeautifulSoup(html, "lxml")
    # Drop noisy regions that crowd the budget without carrying product info.
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS]
    return text


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
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


async def llm_scrape(site: SiteConfig, query: str) -> ScrapeResult:
    if not settings.openai_api_key:
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error="llm: OPENAI_API_KEY not configured",
        )

    search_url = site.build_search_url(query)
    log.debug("llm: %s search_url=%s", site.name, search_url)

    # 1. Fetch the search page (same setup as tier 1 — USD locale cookies etc.).
    async with httpx.AsyncClient(
        headers=HEADERS,
        cookies=LOCALE_COOKIES,
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
    ) as client:
        try:
            resp = await client.get(search_url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            return ScrapeResult(
                site=site.name,
                status=ScrapeStatus.FAILED,
                error=f"llm: search fetch failed: {exc}",
            )

    visible_text = _extract_visible_text(resp.text)
    if len(visible_text) < 200:
        # Nothing to feed the model — page was probably bot-blocked.
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error=f"llm: search page text too short ({len(visible_text)} chars) — likely bot-blocked",
        )

    # 2. Hand to gpt-4o-mini with the structured-output schema.
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    user_prompt = (
        f"Query: {query!r}\n\n"
        f"Site: {site.name}\n\n"
        "Below is the visible text of the search results page. Find the "
        "listing that best matches the query and extract its fields per "
        "the schema.\n\n"
        f"--- BEGIN PAGE TEXT ---\n{visible_text}\n--- END PAGE TEXT ---"
    )

    try:
        completion = await client.beta.chat.completions.parse(
            model=MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ProductExtraction,
        )
    except Exception as exc:
        log.error("llm openai call failed for %s: %s: %s", site.name, type(exc).__name__, exc)
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error=f"llm: openai call failed: {type(exc).__name__}: {str(exc)[:200]}",
        )

    extracted = completion.choices[0].message.parsed
    if extracted is None:
        # Refusal or schema validation failure.
        refusal = getattr(completion.choices[0].message, "refusal", None)
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error=f"llm: model returned no structured output (refusal={refusal!r})",
        )

    title = extracted.title
    if not title:
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error="llm: extraction missing title",
        )

    price = _coerce_float(extracted.price)
    rating = _coerce_float(extracted.rating)
    review_count = _coerce_int(extracted.review_count)
    product_url = extracted.product_url or search_url

    log.info(
        "llm %s: title=%r price=%s rating=%s reviews=%s",
        site.name, title, price, rating, review_count,
    )

    return ScrapeResult(
        site=site.name,
        status=ScrapeStatus.SUCCESS,
        method=Method.LLM,
        title=title,
        price=price,
        rating=rating,
        review_count=review_count,
        product_url=product_url,
        similarity=score(query, title),
    )
