"""USD → other-currency exchange rate, fetched from Frankfurter.

Frankfurter is a free, key-less wrapper around ECB reference rates. The
backend fetches once per hour and caches in memory; the frontend's USD/ILS
toggle will hit `/rate?target=ILS` once on mount and reuse the value.
"""

import time

import httpx

FRANKFURTER_URL = "https://api.frankfurter.dev/v1/latest"
CACHE_TTL_SECONDS = 3600

# currency code -> (fetched_at_unix_seconds, rate_per_usd)
_cache: dict[str, tuple[float, float]] = {}


async def fetch_usd_rate(target: str) -> float:
    """Return how many `target` units one USD buys (e.g. ILS≈3.74)."""
    target = target.upper()
    now = time.time()

    cached = _cache.get(target)
    if cached and (now - cached[0]) < CACHE_TTL_SECONDS:
        return cached[1]

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            FRANKFURTER_URL,
            params={"base": "USD", "symbols": target},
        )
        resp.raise_for_status()
        payload = resp.json()

    rate = payload.get("rates", {}).get(target)
    if rate is None:
        raise ValueError(f"frankfurter response missing rate for {target}: {payload}")

    _cache[target] = (now, float(rate))
    return float(rate)
