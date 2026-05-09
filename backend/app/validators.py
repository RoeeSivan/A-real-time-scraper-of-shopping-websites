from app.matching import DEFAULT_THRESHOLD, score
from app.models import ScrapeResult, ScrapeStatus

# Phrases that indicate a bot-block / captcha / wrong page rather than a real listing.
BOT_CHECK_PHRASES = (
    "robot check",
    "are you a human",
    "enter the characters",
    "captcha",
    "type the characters",
    "access denied",
    "request blocked",
    "page not found",
    "to discuss automated access",
)

MIN_TITLE_LEN = 6


def is_valid_result(
    result: ScrapeResult,
    query: str,
    threshold: float = DEFAULT_THRESHOLD,
) -> bool:
    """Gate between tiers: True iff the result is complete, sane, and on-topic.

    rating and review_count are intentionally optional — many legitimate
    products have no reviews yet.

    `price` is also optional, but ONLY when we have a `product_url` — for
    Amazon's multi-variant cards (the listing page shows "see options"
    instead of a headline price) we still want to surface the row so the
    user can click through and check variants. Without a URL, a missing
    price is just an unusable result.
    """
    if result.status is not ScrapeStatus.SUCCESS:
        return False
    if not result.title or len(result.title.strip()) < MIN_TITLE_LEN:
        return False

    if result.price is not None and result.price <= 0:
        return False
    if result.price is None and not result.product_url:
        return False

    title_lower = result.title.lower()
    if any(phrase in title_lower for phrase in BOT_CHECK_PHRASES):
        return False

    if score(query, result.title) < threshold:
        return False

    return True
