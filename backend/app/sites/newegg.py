from urllib.parse import quote_plus

from app.sites.base import SiteConfig


class NeweggSite(SiteConfig):
    name = "Newegg.com"
    base_url = "https://www.newegg.com"

    def build_search_url(self, query: str) -> str:
        return f"{self.base_url}/p/pl?d={quote_plus(query)}"


newegg = NeweggSite()