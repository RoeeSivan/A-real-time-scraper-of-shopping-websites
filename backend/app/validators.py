import re

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

# Accessory phrases — match if the title says "<accessory> for <something>" or
# starts with the accessory term. Skipped if the query itself names the
# accessory (e.g. "iPhone 16 case" should match cases).
# Word-boundary regex avoids matching "case" inside "Briefcase".
ACCESSORY_PATTERNS = (
    re.compile(r"\bcase for\b", re.I),
    re.compile(r"\bcover for\b", re.I),
    re.compile(r"\bstand for\b", re.I),
    re.compile(r"\bmount for\b", re.I),
    re.compile(r"\bsleeve for\b", re.I),
    re.compile(r"\bskin for\b", re.I),
    re.compile(r"\breplacement\b", re.I),
    re.compile(r"\bscreen protector\b", re.I),
    re.compile(r"\bcharging cable\b", re.I),
    re.compile(r"\bcharger for\b", re.I),
)
ACCESSORY_QUERY_TOKENS = (
    "case", "cover", "stand", "mount", "sleeve", "skin",
    "screen protector", "cable", "charger", "replacement",
)

# Reject refurbished / renewed / pre-owned listings — different price tier,
# clutters the demo. Word-boundary regex to avoid false positives.
REFURB_PATTERNS = (
    re.compile(r"\brefurbished\b", re.I),
    re.compile(r"\brenewed\b", re.I),
    re.compile(r"\bpre[- ]owned\b", re.I),
    re.compile(r"\bopen[- ]box\b", re.I),
    re.compile(r"\bused\b", re.I),
)
REFURB_QUERY_TOKENS = ("refurbished", "renewed", "pre-owned", "preowned", "open box", "used")

MIN_TITLE_LEN = 6


def _query_allows(query: str, tokens: tuple[str, ...]) -> bool:
    """True if the user's query itself contains one of these tokens — in which
    case the corresponding filter is skipped."""
    q = query.lower()
    return any(t in q for t in tokens)


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

    if not _query_allows(query, ACCESSORY_QUERY_TOKENS):
        if any(p.search(result.title) for p in ACCESSORY_PATTERNS):
            return False

    if not _query_allows(query, REFURB_QUERY_TOKENS):
        if any(p.search(result.title) for p in REFURB_PATTERNS):
            return False

    if score(query, result.title) < threshold:
        return False

    return True
