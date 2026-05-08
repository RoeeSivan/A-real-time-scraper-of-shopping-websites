import re
from dataclasses import dataclass

from app.models import Candidate


@dataclass
class ProductFields:
    """Raw scraped fields, before they're combined with site/method into a ScrapeResult."""

    title: str | None = None
    price: float | None = None
    rating: float | None = None
    review_count: int | None = None


class SiteConfig:
    """Per-site contract used by tiers 1 & 2 (basic + browser).

    Tier 3 (LLM) and tier 4 (Firecrawl) bypass site-specific parsing and use
    a generic prompt / extraction schema, so they only need `name`,
    `base_url`, and `build_search_url`. The parser methods default to empty
    implementations — a site without selectors will fail tier 1/2 cleanly
    ("no candidates parsed") and fall through to tier 3/4.
    """

    name: str = "<override me>"
    base_url: str = "<override me>"
    # Set True only when the site has working selectors for both
    # `parse_search_candidates` and `parse_product`. If False, the
    # orchestrator skips tiers 1 + 2 (basic + browser) for this site
    # and goes straight to tier 4 (Firecrawl).
    has_selectors: bool = False

    def build_search_url(self, query: str) -> str:
        raise NotImplementedError

    def parse_search_candidates(self, html: str) -> list[Candidate]:
        return []

    def parse_product(self, html: str) -> ProductFields:
        return ProductFields()


# Shared text-extraction helpers (used by every site implementation).

def parse_price(text: str | None) -> float | None:
    """First decimal/integer in 'US $1,299.99' / '$332.54' / '€20'."""
    if not text:
        return None
    cleaned = text.replace(",", "")
    match = re.search(r"\d+(?:\.\d+)?", cleaned)
    return float(match.group()) if match else None


def parse_rating(text: str | None) -> float | None:
    """First decimal/integer in '4.7 out of 5 stars'."""
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def parse_int(text: str | None) -> int | None:
    """First integer in '315 ratings' / '1,234 reviews'."""
    if not text:
        return None
    cleaned = text.replace(",", "")
    match = re.search(r"\d+", cleaned)
    return int(match.group()) if match else None
