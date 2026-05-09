"""Newegg site config.

**Cloudflare caveat**: tier 1 (httpx) is hit with a 403/CAPTCHA; tier 2
(Playwright stealth) often gets through but Newegg sometimes serves a
CAPTCHA challenge instead of the search page. When tier 1/2 fail, the
orchestrator falls through to tier 4 (Firecrawl), whose servers are
allow-listed.

Search-card structure (when the page actually loads):
  - card root        : `.item-cell` (or `.item-container` on some layouts)
  - title + URL      : `a.item-title`
  - price            : `.price-current` — text usually `$278.99`, sometimes
                       `$278<sup>99</sup>` so we collapse text and parse
                       the first decimal/integer
  - rating + reviews : `<a class="item-rating" title="Rating + N">` with an
                       inner `<span class="item-rating-num">(N)</span>`. The
                       `title` attribute contains the star count, the inner
                       span the review count.

All fields available on the card — same short-circuit pattern as Walmart.
"""

import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from app.models import Candidate
from app.sites.base import ProductFields, SiteConfig, parse_int, parse_price


_RATING_FROM_TITLE_RE = re.compile(r"Rating\s*\+\s*(\d+(?:\.\d+)?)", re.I)


class NeweggSite(SiteConfig):
    name = "Newegg.com"
    base_url = "https://www.newegg.com"
    has_selectors = True

    def build_search_url(self, query: str) -> str:
        return f"{self.base_url}/p/pl?d={quote_plus(query)}"

    def parse_search_candidates(self, html: str) -> list[Candidate]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select(".item-cell, .item-container")
        candidates: list[Candidate] = []
        seen: set[str] = set()

        for card in cards:
            link = card.select_one("a.item-title")
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

            price_el = card.select_one(".price-current")
            price = parse_price(price_el.get_text(" ", strip=True)) if price_el else None

            rating: float | None = None
            review_count: int | None = None
            rating_anchor = card.select_one("a.item-rating")
            if rating_anchor:
                # Rating from title attribute (e.g. "Rating + 4 out of 5").
                # Newegg encodes whole-star ratings as "Rating + 4", half as
                # "Rating + 4.5".
                title_attr = rating_anchor.get("title", "")
                rm = _RATING_FROM_TITLE_RE.search(title_attr)
                if rm:
                    rating = float(rm.group(1))

                # Review count from inner span.
                count_span = rating_anchor.select_one(".item-rating-num")
                if count_span:
                    review_count = parse_int(count_span.get_text(strip=True))

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
        h1 = soup.select_one("h1.product-title, h1")
        return ProductFields(title=h1.get_text(strip=True) if h1 else None)


newegg = NeweggSite()
