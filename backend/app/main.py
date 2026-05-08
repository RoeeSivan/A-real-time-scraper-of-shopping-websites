import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.exchange import fetch_usd_rate
from app.orchestrator import run_all_sites

app = FastAPI(title="Real-Time Product Scraper", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "openai_configured": bool(settings.openai_api_key),
        "firecrawl_configured": bool(settings.firecrawl_api_key),
    }


@app.get("/rate")
async def get_rate(target: str = "ILS") -> dict[str, str | float]:
    """USD → `target` exchange rate. 1-hour in-memory cache, ECB data via Frankfurter."""
    try:
        rate = await fetch_usd_rate(target)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"failed to fetch exchange rate: {type(exc).__name__}: {exc}",
        )
    return {"base": "USD", "target": target.upper(), "rate": rate}


@app.get("/search")
async def search(q: str) -> EventSourceResponse:
    """Stream per-site scrape results to the client as each one finishes.

    Events:
      - `event: result` — one ScrapeResult JSON per site (4 total)
      - `event: done`   — sent once all sites have completed
    """
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="query parameter 'q' is required")

    async def event_stream():
        async for result in run_all_sites(q.strip()):
            yield {
                "event": "result",
                "data": json.dumps(result.model_dump(mode="json")),
            }
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_stream())
