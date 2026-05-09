"""Walmart site config.

Walmart's search-results page is fully server-rendered with all the fields
we need on each card:
  - card root        : `[data-item-id]`
  - title            : `[data-automation-id="product-title"]`
  - price            : `[data-automation-id="product-price"]` (text contains
                       "$259.00", sometimes "Now $259.00, Was $398.00" — first
                       parsed number is the current price)
  - rating           : not exposed structurally, but the card text contains
                       "X.X out of 5 Stars" — extracted via regex
  - review count     : `[data-testid="product-reviews"]`
  - product link     : `a[href*="/ip/"]` inside the card. Sponsored cards
                       have a tracking link instead — we filter those out.

Because everything is on the search card, we populate `Candidate` with the
full set of fields and the basic/browser tiers short-circuit the product-page
fetch.
"""

import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from app.models import Candidate
from app.sites.base import ProductFields, SiteConfig, parse_int, parse_price


_RATING_RE = re.compile(r"(\d+(?:\.\d+)?)\s*out of\s*5", re.I)


class WalmartSite(SiteConfig):
    name = "Walmart.com"
    base_url = "https://www.walmart.com"
    has_selectors = True

    def build_search_url(self, query: str) -> str:
        return f"{self.base_url}/search?q={quote_plus(query)}"

    def parse_search_candidates(self, html: str) -> list[Candidate]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("[data-item-id]")
        candidates: list[Candidate] = []
        seen: set[str] = set()

        for card in cards:
            # Organic cards link directly to /ip/...; sponsored cards link
            # to a /sp/track tracking URL instead. Skip sponsored.
            link = card.select_one('a[href*="/ip/"]')
            if not link:
                continue
            href = link.get("href", "")
            url = href if href.startswith("http") else f"{self.base_url}{href}"
            if url in seen:
                continue
            seen.add(url)

            title_el = card.select_one('[data-automation-id="product-title"]')
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                continue

            price_el = card.select_one('[data-automation-id="product-price"]')
            price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None

            text = card.get_text(" ", strip=True)
            rating_match = _RATING_RE.search(text)
            rating = float(rating_match.group(1)) if rating_match else None

            reviews_el = card.select_one('[data-testid="product-reviews"]')
            review_count = parse_int(reviews_el.get_text(strip=True)) if reviews_el else None

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
        # Reached only if `parse_search_candidates` returned a Candidate
        # without `price` populated — should not happen in practice. Walmart
        # PDPs are heavy SPAs and most fields aren't reliably parseable from
        # raw HTML, so we just pull a best-effort title and let the validator
        # decide.
        soup = BeautifulSoup(html, "lxml")
        h1 = soup.select_one("h1")
        return ProductFields(title=h1.get_text(strip=True) if h1 else None)


walmart = WalmartSite()
