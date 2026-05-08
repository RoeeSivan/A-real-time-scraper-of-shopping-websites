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
    """A search-page hit before we commit to fetching the product page."""

    title: str
    url: str


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

    @classmethod
    def failed(cls, site: str, error: str = "All tiers failed") -> "ScrapeResult":
        return cls(site=site, status=ScrapeStatus.FAILED, error=error)
