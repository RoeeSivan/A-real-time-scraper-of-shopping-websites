"""Tier 4: Firecrawl. External scraping API — handles fetching, bot evasion,
and structured extraction in a single call. The "give up on our own infra" tier.

We hand Firecrawl the **search** URL and ask it to find the listing matching
the query, then extract title/price/rating/reviews. One round trip, no
selector or stealth-cookie work on our side.
"""

import json
import logging

from firecrawl import AsyncFirecrawl

from app.config import settings
from app.matching import score
from app.models import Method, ScrapeResult, ScrapeStatus
from app.sites.base import SiteConfig

log = logging.getLogger(__name__)



async def firecrawl_scrape(site: SiteConfig, query: str) -> ScrapeResult:
    if not settings.firecrawl_api_key:
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error="firecrawl: FIRECRAWL_API_KEY not configured",
        )

    fc = AsyncFirecrawl(api_key=settings.firecrawl_api_key)
    
    try:
        search_url = site.build_search_url(query)
        log.debug(f"Scraping {site.name} URL: {search_url}")
        
        # Use markdown format - most reliable
        doc = await fc.scrape(
            search_url,
            formats=["markdown"],
            location={"country": "US", "languages": ["en-US"]},
            only_main_content=True,
        )
        
        markdown_content = getattr(doc, 'markdown', None)
        log.debug(f"Markdown content length: {len(markdown_content) if markdown_content else 0}")
        
        if not markdown_content:
            log.warning(f"No markdown content from Firecrawl for {site.name}")
            return ScrapeResult(
                site=site.name,
                status=ScrapeStatus.FAILED,
                error="firecrawl: no markdown content",
            )
        
        # Simple heuristic parsing: look for links and extract text
        import re
        
        # Look for markdown links: [text](url)
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        matches = re.findall(link_pattern, markdown_content)
        
        log.debug(f"Found {len(matches)} links in markdown")
        
        if matches:
            # Find the best match - typically the first substantial product link
            # Filter out nav/header links (usually short)
            candidates = [
                (title, url) for title, url in matches 
                if len(title) > 10 and len(title) < 200
            ]
            
            if candidates:
                title, url = candidates[0]  # Take the first good candidate
                
                # Validate
                if title and len(title) > 5:
                    log.debug(f"Extracted from markdown: {title}")
                    return ScrapeResult(
                        site=site.name,
                        status=ScrapeStatus.SUCCESS,
                        method=Method.FIRECRAWL,
                        title=title,
                        price=None,  # Markdown doesn't preserve price easily
                        rating=None,
                        review_count=None,
                        product_url=url if url.startswith('http') else search_url,
                        similarity=score(query, title),
                    )
        
        # Fallback: try to extract the first heading as product name
        heading_pattern = r'^#+\s+(.+)$'
        heading_matches = re.findall(heading_pattern, markdown_content, re.MULTILINE)
        
        if heading_matches:
            title = heading_matches[0].strip()
            if title and len(title) > 5:
                log.debug(f"Extracted heading as title: {title}")
                return ScrapeResult(
                    site=site.name,
                    status=ScrapeStatus.SUCCESS,
                    method=Method.FIRECRAWL,
                    title=title,
                    price=None,
                    rating=None,
                    review_count=None,
                    product_url=search_url,
                    similarity=score(query, title),
                )
        
        log.warning(f"Firecrawl for {site.name}: could not extract product title from markdown")
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error="firecrawl: could not extract title from markdown",
        )
        
    except Exception as exc:
        log.error(f"Firecrawl scrape error for {site.name}: {type(exc).__name__}: {exc}")
        return ScrapeResult(
            site=site.name,
            status=ScrapeStatus.FAILED,
            error=f"firecrawl: {type(exc).__name__}: {str(exc)[:100]}",
        )
