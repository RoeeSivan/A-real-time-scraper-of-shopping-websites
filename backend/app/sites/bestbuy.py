from urllib.parse import quote_plus

from app.sites.base import SiteConfig


class BestBuySite(SiteConfig):
    name = "BestBuy.com"
    base_url = "https://www.bestbuy.com"

    def build_search_url(self, query: str) -> str:
        return f"{self.base_url}/site/searchpage.jsp?st={quote_plus(query)}"


bestbuy = BestBuySite()