from urllib.parse import quote_plus

from app.sites.base import SiteConfig


class WalmartSite(SiteConfig):
    name = "Walmart.com"
    base_url = "https://www.walmart.com"

    def build_search_url(self, query: str) -> str:
        return f"{self.base_url}/search?q={quote_plus(query)}"


walmart = WalmartSite()