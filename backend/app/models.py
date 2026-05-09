from enum import Enum

from pydantic import BaseModel


class Method(str, Enum):
    BASIC = "basic"
    BROWSER = "browser"
    LLM = "llm"
    FIRECRAWL = "firecrawl"
    NONE = "n/a"


class ScrapeStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class Candidate(BaseModel):
    """A search-page hit before we commit to fetching the product page.

    `price`/`rating`/`review_count` are optional. If a site renders the
    full product info on its search-result card (e.g. Walmart), the site
    parser can populate them here and the basic/browser tiers will skip
    the redundant product-page fetch.
    """

    title: str
    url: str
    price: float | None = None
    rating: float | None = None
    review_count: int | None = None


class TierAttempt(BaseModel):
    """One tier's attempt during the cascade — succeeded, failed, or rejected
    by the validator. Aggregated into `ScrapeResult.tier_trace` so the UI can
    show the actual fall-through path (e.g. `basic ✗ → browser ✗ → llm ✓`).
    """

    tier: str  # "basic" | "browser" | "llm" | "firecrawl"
    outcome: str  # "succeeded" | "rejected" | "errored"
    error: str | None = None


class ScrapeResult(BaseModel):
    """Final per-site outcome that the frontend renders as one table row."""

    site: str
    status: ScrapeStatus
    method: Method = Method.NONE
    title: str | None = None
    price: float | None = None
    rating: float | None = None
    review_count: int | None = None
    product_url: str | None = None
    similarity: float | None = None
    error: str | None = None
    tier_trace: list[TierAttempt] = []
