from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from app.models import Candidate
from app.sites.base import ProductFields, SiteConfig, parse_int, parse_price, parse_rating

# Ordered list of selectors targeting the main "buy box" price on a product
# page. We try them in order and stop at the first that yields a positive
# number. The bare `span.a-offscreen` fallback is intentionally last — it
# also matches accessory/refurb prices on multi-offer pages, so it should
# only fire when the focused selectors miss.
_PRICE_SELECTORS: tuple[str, ...] = (
    "#corePriceDisplay_desktop_feature_div span.a-price > span.a-offscreen",
    "#corePrice_feature_div span.a-price > span.a-offscreen",
    "#apex_desktop span.a-price > span.a-offscreen",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    "#priceblock_saleprice",
    "span.a-offscreen",
)


class AmazonSite(SiteConfig):
    name = "Amazon.com"
    base_url = "https://www.amazon.com"
    has_selectors = True

    def build_search_url(self, query: str) -> str:
        return f"{self.base_url}/s?k={quote_plus(query)}"

    def parse_search_candidates(self, html: str) -> list[Candidate]:
        """Adapted from the oxylabs guide. Their `[data-asin] h2 a` selector
        worked when the link was a child of the `<h2>` — Amazon's current
        layout has the title in `<h2><span>...</span></h2>` and the product
        link as a separate `<a href="/dp/…">` *sibling*. So we look for both:
        the `[data-asin]` (or `s-search-result`) card, then pull title from
        the `<h2>` text and url from any `a[href*="/dp/"]` inside the card.
        """
        soup = BeautifulSoup(html, "lxml")
        seen_urls: set[str] = set()
        candidates: list[Candidate] = []

        cards = soup.select(
            'div[data-component-type="s-search-result"][data-asin]'
        )
        if not cards:
            cards = soup.select("[data-asin]")

        for card in cards:
            if not card.get("data-asin"):
                continue
            link = card.select_one('a[href*="/dp/"]')
            if not link:
                continue
            href = link.get("href", "")
            url = href if href.startswith("http") else f"{self.base_url}{href}"
            if url in seen_urls:
                continue

            title_el = card.select_one("h2")
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                # Fallback for older layouts where the title was inside the link.
                inner = link.find("span")
                title = inner.get_text(strip=True) if inner else ""
            if not title:
                continue

            seen_urls.add(url)
            candidates.append(Candidate(title=title, url=url))

        return candidates

    def parse_product(self, html: str) -> ProductFields:
        """Selectors from the oxylabs Amazon scraping guide, hardened against
        multi-offer pages:
          - title: `#productTitle`
          - price: focused buy-box selectors (`_PRICE_SELECTORS`), with the
            generic `span.a-offscreen` as a last-resort fallback
          - rating: `#acrPopover[title]` → "4.7 out of 5 stars"
        Plus a `#acrCustomerReviewText` extension for review count.
        """
        soup = BeautifulSoup(html, "lxml")

        title_el = soup.select_one("#productTitle")
        title = title_el.get_text(strip=True) if title_el else None

        # Walk focused selectors first (buy-box / core price containers),
        # then fall back to the generic `span.a-offscreen`. This keeps us
        # from picking up accessory or "frequently bought together" prices
        # that share the offscreen class on multi-offer pages.
        price = None
        for selector in _PRICE_SELECTORS:
            for el in soup.select(selector):
                candidate_price = parse_price(el.get_text(strip=True))
                if candidate_price and candidate_price > 0:
                    price = candidate_price
                    break
            if price is not None:
                break

        rating = None
        rating_el = soup.select_one("#acrPopover")
        if rating_el and rating_el.get("title"):
            rating = parse_rating(rating_el["title"])
        if rating is None:
            alt = soup.select_one('span[data-hook="rating-out-of-text"]')
            if alt:
                rating = parse_rating(alt.get_text(strip=True))

        review_count = None
        review_el = soup.select_one("#acrCustomerReviewText")
        if review_el:
            review_count = parse_int(review_el.get_text(strip=True))

        return ProductFields(
            title=title,
            price=price,
            rating=rating,
            review_count=review_count,
        )


amazon = AmazonSite()
