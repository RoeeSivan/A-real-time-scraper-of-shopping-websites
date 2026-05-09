import pytest

from app.models import Method, ScrapeResult, ScrapeStatus
from app.validators import is_valid_result

QUERY = "Lenovo Tab P12-2024"
GOOD_TITLE = "Lenovo Tab P12-2024 - Expansive Touchscreen Tablet, 12.7 Inch"


def make_result(**overrides) -> ScrapeResult:
    """Defaults to a fully valid Amazon row; tests override one field at a time."""
    base = {
        "site": "Amazon.com",
        "status": ScrapeStatus.SUCCESS,
        "method": Method.BASIC,
        "title": GOOD_TITLE,
        "price": 332.54,
        "rating": 4.7,
        "review_count": 315,
        "product_url": "https://www.amazon.com/dp/B0EXAMPLE",
    }
    base.update(overrides)
    return ScrapeResult(**base)


def test_valid_result_passes():
    assert is_valid_result(make_result(), QUERY) is True


def test_failed_status_is_invalid():
    r = make_result(status=ScrapeStatus.FAILED, error="something")
    assert is_valid_result(r, QUERY) is False


def test_missing_title_is_invalid():
    assert is_valid_result(make_result(title=None), QUERY) is False


def test_too_short_title_is_invalid():
    # 5 chars (whitespace stripped) — under MIN_TITLE_LEN.
    assert is_valid_result(make_result(title="iPad "), QUERY) is False


def test_missing_price_is_valid_when_product_url_present():
    """Multi-variant cards (Amazon "see options") show no headline price.
    We still surface the row so the user can click through and check."""
    assert is_valid_result(make_result(price=None), QUERY) is True


def test_missing_price_AND_missing_url_is_invalid():
    """Without either a price or a URL, the row is unusable."""
    r = make_result(price=None, product_url=None)
    assert is_valid_result(r, QUERY) is False


@pytest.mark.parametrize("price", [0, -1.0, -100.5])
def test_non_positive_price_is_invalid(price):
    assert is_valid_result(make_result(price=price), QUERY) is False


def test_bot_check_phrase_is_invalid():
    r = make_result(title="Robot Check - Amazon.com")
    assert is_valid_result(r, QUERY) is False


def test_captcha_phrase_is_invalid():
    r = make_result(title="Please complete the captcha to continue")
    assert is_valid_result(r, QUERY) is False


def test_low_similarity_title_is_invalid():
    # Right shape (long, has price) but completely different product.
    r = make_result(title="Apple iPad Pro 11-inch (M4) Wi-Fi 256GB")
    assert is_valid_result(r, QUERY) is False


def test_missing_rating_and_reviews_still_valid():
    """Many real product pages legitimately have no reviews — these are optional."""
    r = make_result(rating=None, review_count=None)
    assert is_valid_result(r, QUERY) is True
