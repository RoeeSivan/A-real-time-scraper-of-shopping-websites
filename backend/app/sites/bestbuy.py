"""BestBuy site config.

**Geo caveat**: from a non-US IP, www.bestbuy.com redirects to a
"Select your Country" splash and never serves search results. The selectors
below are correct for the live US search-results page; tier 1/2 will only
succeed when run from a US-routed network. From elsewhere, the orchestrator
will fall through to tier 3 (LLM) or tier 4 (Firecrawl), both of which
egress through US infrastructure.

Search-card structure (US):
  - card root        : `li.sku-item`
  - title + URL      : `h4.sku-title a`  (href like `/site/.../...skuId.p?...`)
  - price            : `.priceView-customer-price span[aria-hidden="true"]`
                       e.g. "$278.00"
  - rating           : `.c-ratings-reviews .visually-hidden` text contains
                       "Rating 4.6 out of 5 stars"
  - review count     : same area, "(6,285 Reviews)" — captured via regex

Like Walmart, everything is on the card so we populate `Candidate` fully
and short-circuit the product-page fetch.
"""

import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from app.models import Candidate
from app.sites.base import ProductFields, SiteConfig, parse_int, parse_price


_RATING_RE = re.compile(r"(\d+(?:\.\d+)?)\s*out of\s*5", re.I)
_REVIEWS_RE = re.compile(r"\(\s*([\d,]+)\s*Reviews?\s*\)", re.I)


class BestBuySite(SiteConfig):
    name = "BestBuy.com"
    base_url = "https://www.bestbuy.com"
    has_selectors = True

    def build_search_url(self, query: str) -> str:
        return f"{self.base_url}/site/searchpage.jsp?st={quote_plus(query)}"

    def parse_search_candidates(self, html: str) -> list[Candidate]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("li.sku-item, [data-testid='product-list-item']")
        candidates: list[Candidate] = []
        seen: set[str] = set()

        for card in cards:
            link = card.select_one("h4.sku-title a, a.sku-title, a[href*='skuId=']")
            if not link:
                continue
            href = link.get("href", "")
            url = href if href.startswith("http") else f"{self.base_url}{href}"
            if url in seen:
                continue
            seen.add(url)

            title = link.get_text(strip=True)
            if not title:
                continue

            price_el = card.select_one(
                ".priceView-customer-price span[aria-hidden='true'], "
                ".priceView-hero-price span[aria-hidden='true']"
            )
            price = parse_price(price_el.get_text(strip=True)) if price_el else None

            ratings_block = card.select_one(".c-ratings-reviews")
            rating: float | None = None
            review_count: int | None = None
            if ratings_block:
                txt = ratings_block.get_text(" ", strip=True)
                rm = _RATING_RE.search(txt)
                if rm:
                    rating = float(rm.group(1))
                rcm = _REVIEWS_RE.search(txt)
                if rcm:
                    review_count = parse_int(rcm.group(1))

            candidates.append(
                Candidate(
                    title=title,
                    url=url,
                    price=price,
                    rating=rating,
                    review_count=review_count,
                )
            )

        return candidates

    def parse_product(self, html: str) -> ProductFields:
        # Fallback only — search cards already provide full data.
        soup = BeautifulSoup(html, "lxml")
        h1 = soup.select_one("h1.heading-5, h1")
        return ProductFields(title=h1.get_text(strip=True) if h1 else None)


bestbuy = BestBuySite()
