"""Offline parser tests for the Amazon site config — no network calls."""

from app.sites.amazon import amazon
from app.sites.base import parse_int, parse_price, parse_rating

# A trimmed-down search-results snippet matching the structure Amazon serves.
SEARCH_HTML = """
<html><body>
  <div data-component-type="s-search-result" data-asin="B0EXAMPLE1">
    <h2><a class="a-link-normal" href="/Lenovo-Tab-P12-2024-Tablet/dp/B0EXAMPLE1/">
      <span>Lenovo Tab P12-2024 - Expansive Touchscreen Tablet, 12.7 Inch</span>
    </a></h2>
  </div>
  <div data-component-type="s-search-result" data-asin="B0EXAMPLE2">
    <h2><a class="a-link-normal" href="/Apple-iPad-Pro/dp/B0EXAMPLE2/">
      <span>Apple iPad Pro 11-inch (M4)</span>
    </a></h2>
  </div>
  <div data-component-type="s-search-result" data-asin="B0EXAMPLE3">
    <h2><a href="https://www.amazon.com/Already-Absolute/dp/B0EXAMPLE3/">
      <span>Already-Absolute URL Variant</span>
    </a></h2>
  </div>
  <div data-component-type="s-search-result" data-asin="B0NOLINK">
    <!-- No link at all — should be skipped. -->
  </div>
</body></html>
"""


PRODUCT_HTML = """
<html><body>
  <span id="productTitle">  Lenovo Tab P12-2024 - Expansive Touchscreen Tablet, 12.7 Inch  </span>

  <div id="corePriceDisplay_desktop_feature_div">
    <span class="a-price"><span class="a-offscreen">$332.54</span></span>
  </div>

  <span data-hook="rating-out-of-text">4.7 out of 5</span>

  <span id="acrCustomerReviewText">315 ratings</span>
</body></html>
"""


def test_search_extracts_only_well_formed_cards():
    candidates = amazon.parse_search_candidates(SEARCH_HTML)
    titles = [c.title for c in candidates]

    # Three valid cards, the empty one is skipped.
    assert len(candidates) == 3
    assert "Lenovo Tab P12-2024 - Expansive Touchscreen Tablet, 12.7 Inch" in titles
    assert "Apple iPad Pro 11-inch (M4)" in titles
    assert "Already-Absolute URL Variant" in titles


def test_search_resolves_relative_urls_to_absolute():
    candidates = amazon.parse_search_candidates(SEARCH_HTML)
    for c in candidates:
        assert c.url.startswith("https://www.amazon.com/")


def test_search_handles_empty_html():
    assert amazon.parse_search_candidates("<html></html>") == []


def test_product_parses_all_fields():
    fields = amazon.parse_product(PRODUCT_HTML)
    assert fields.title == "Lenovo Tab P12-2024 - Expansive Touchscreen Tablet, 12.7 Inch"
    assert fields.price == 332.54
    assert fields.rating == 4.7
    assert fields.review_count == 315


def test_product_handles_missing_optional_fields():
    html = "<html><body><span id='productTitle'>Some Product</span></body></html>"
    fields = amazon.parse_product(html)
    assert fields.title == "Some Product"
    assert fields.price is None
    assert fields.rating is None
    assert fields.review_count is None


def test_product_multi_offer_picks_buy_box_not_accessory():
    """On multi-offer pages Amazon renders accessory prices via the same
    ``span.a-offscreen`` class — sometimes BEFORE the buy-box container in
    the DOM. The focused-selector chain must pick the corePriceDisplay
    value (the actual product price), not the accessory leak.
    """
    html = """
    <html><body>
      <span id="productTitle">Apple iPhone 16 Pro Max 256GB</span>

      <!-- Frequently-bought accessory (case) renders FIRST. -->
      <div id="hsx-frequently-bought-together">
        <span class="a-price"><span class="a-offscreen">$9.99</span></span>
      </div>

      <!-- Real buy-box price. -->
      <div id="corePriceDisplay_desktop_feature_div">
        <span class="a-price"><span class="a-offscreen">$1,199.00</span></span>
      </div>

      <!-- Refurb offer also on the page, lower than the buy-box. -->
      <div id="usedAndNewSection">
        <span class="a-price"><span class="a-offscreen">$899.00</span></span>
      </div>
    </body></html>
    """
    fields = amazon.parse_product(html)
    assert fields.price == 1199.00


def test_product_falls_back_to_generic_offscreen_when_focused_missing():
    """If none of the focused buy-box selectors hit, the generic
    ``span.a-offscreen`` fallback still surfaces a price."""
    html = """
    <html><body>
      <span id="productTitle">Generic Product</span>
      <span class="a-price"><span class="a-offscreen">$42.00</span></span>
    </body></html>
    """
    fields = amazon.parse_product(html)
    assert fields.price == 42.00


def test_product_falls_back_to_acrPopover_title_attr_for_rating():
    html = """
    <html><body>
      <span id="productTitle">X</span>
      <span class="a-price"><span class="a-offscreen">$10.00</span></span>
      <span id="acrPopover" title="4.3 out of 5 stars"></span>
    </body></html>
    """
    fields = amazon.parse_product(html)
    assert fields.rating == 4.3


def test_search_url_uses_k_param():
    url = amazon.build_search_url("Lenovo Tab P12-2024")
    assert url == "https://www.amazon.com/s?k=Lenovo+Tab+P12-2024"


# Helper-function smoke tests.

def test_parse_price_strips_commas_and_currency():
    assert parse_price("US $1,299.99") == 1299.99
    assert parse_price("$10") == 10.0
    assert parse_price(None) is None
    assert parse_price("") is None


def test_parse_price_rejects_installment_markers():
    # Walmart (T-Mobile, Affirm) and BestBuy (Citizens Pay) often surface
    # a per-month or "down today" figure as the headline number on search
    # cards. Without this filter, the orchestrator accepted "$6/mo" as a
    # legitimate iPhone price.
    assert parse_price("$6/mo") is None
    assert parse_price("$25 down today") is None
    assert parse_price("$6 monthly") is None
    assert parse_price("$899/month for 36 months") is None
    assert parse_price("$50/wk") is None


def test_parse_price_keeps_normal_prices_with_qualifiers():
    # "Now $259.00, Was $398.00" is a real Walmart string — first number
    # wins. The "Was" word does NOT trigger the installment filter.
    assert parse_price("Now $259.00, Was $398.00") == 259.0


def test_parse_rating_picks_first_decimal():
    assert parse_rating("4.7 out of 5 stars") == 4.7
    assert parse_rating("rated 5 stars") == 5.0
    assert parse_rating(None) is None


def test_parse_int_strips_commas():
    assert parse_int("1,234 reviews") == 1234
    assert parse_int("0 ratings") == 0
    assert parse_int(None) is None
