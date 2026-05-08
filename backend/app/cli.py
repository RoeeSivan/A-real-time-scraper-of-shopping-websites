"""Tiny CLI for running one site through one tier without the FastAPI server.

Usage:
    uv run python -m app.cli "Lenovo Tab P12-2024"
    uv run python -m app.cli "Lenovo Tab P12-2024" amazon basic
    uv run python -m app.cli "Lenovo Tab P12-2024" bestbuy firecrawl
"""

import asyncio
import json
import logging
import sys

from app.sites.amazon import amazon
from app.sites.base import SiteConfig
from app.sites.bestbuy import bestbuy
from app.sites.newegg import newegg
from app.sites.walmart import walmart
from app.tiers.basic import basic_scrape
from app.tiers.browser import browser_scrape
from app.tiers.firecrawl import firecrawl_scrape

# Set up logging to see debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s | %(levelname)s | %(message)s"
)

SITES: dict[str, SiteConfig] = {
    "amazon": amazon,
    "bestbuy": bestbuy,
    "walmart": walmart,
    "newegg": newegg,
}

TIERS = {
    "basic": basic_scrape,
    "browser": browser_scrape,
    "firecrawl": firecrawl_scrape,
    # tier 3 (llm) plugs in here next.
}


async def run(query: str, site_name: str, tier_name: str) -> None:
    if site_name not in SITES:
        raise SystemExit(f"unknown site: {site_name} (have: {list(SITES)})")
    if tier_name not in TIERS:
        raise SystemExit(f"unknown tier: {tier_name} (have: {list(TIERS)})")

    site = SITES[site_name]
    tier = TIERS[tier_name]

    result = await tier(site, query)
    print(json.dumps(result.model_dump(mode="json"), indent=2))


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)

    query = sys.argv[1]
    site_name = sys.argv[2] if len(sys.argv) > 2 else "amazon"
    tier_name = sys.argv[3] if len(sys.argv) > 3 else "basic"
    asyncio.run(run(query, site_name, tier_name))


if __name__ == "__main__":
    main()
