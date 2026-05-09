from app.tiers.firecrawl import canonicalize_product_url


def test_amazon_url_with_slug_and_tracking_collapses_to_dp_asin():
    url = (
        "https://www.amazon.com/Sony-WH-1000XM5-Wireless-Industry-Leading-Headphones/"
        "dp/B09XS7JWHH/ref=sr_1_1?keywords=sony"
    )
    assert canonicalize_product_url("Amazon.com", url) == (
        "https://www.amazon.com/dp/B09XS7JWHH"
    )


def test_amazon_gp_product_url_collapses_to_dp_asin():
    url = "https://www.amazon.com/gp/product/B0CHX1W1XY?tag=foo&psc=1"
    assert canonicalize_product_url("Amazon.com", url) == (
        "https://www.amazon.com/dp/B0CHX1W1XY"
    )


def test_amazon_search_url_without_asin_is_rejected():
    # Amazon search URLs route to "Sorry we couldn't find that page" when
    # opened expecting a product detail page — strip them so the validator
    # can fall back to a deterministic search URL.
    assert canonicalize_product_url(
        "Amazon.com", "https://www.amazon.com/s?k=sony"
    ) is None


def test_amazon_image_cdn_url_is_rejected():
    assert canonicalize_product_url(
        "Amazon.com", "https://m.media-amazon.com/images/I/foo.jpg"
    ) is None


def test_amazon_lowercase_asin_is_uppercased():
    url = "https://www.amazon.com/dp/b09xs7jwhh"
    assert canonicalize_product_url("Amazon.com", url) == (
        "https://www.amazon.com/dp/B09XS7JWHH"
    )


def test_non_amazon_urls_are_passed_through_unchanged():
    walmart = "https://www.walmart.com/ip/Sony-WH-1000XM5/123456"
    newegg = "https://www.newegg.com/p/0TH-01UG-00075"
    bestbuy = "https://www.bestbuy.com/site/sony.../skuId=6505727"
    assert canonicalize_product_url("Walmart.com", walmart) == walmart
    assert canonicalize_product_url("Newegg.com", newegg) == newegg
    assert canonicalize_product_url("BestBuy.com", bestbuy) == bestbuy


def test_none_url_returns_none():
    assert canonicalize_product_url("Amazon.com", None) is None
    assert canonicalize_product_url("Walmart.com", None) is None
