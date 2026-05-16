"""Orchestrator tests with mocked tier functions — no network calls."""

import asyncio
from typing import Awaitable, Callable
from unittest.mock import patch

import pytest

from app import orchestrator
from app.models import Method, ScrapeResult, ScrapeStatus
from app.sites.base import SiteConfig


@pytest.fixture(autouse=True)
def _clear_pipeline_cache():
    """Cache persists across calls; reset between tests."""
    orchestrator.clear_cache()
    yield
    orchestrator.clear_cache()

QUERY = "Lenovo Tab P12-2024"
GOOD_TITLE = "Lenovo Tab P12-2024 - Expansive Touchscreen Tablet, 12.7 Inch"


class _SelectorSite(SiteConfig):
    name = "Test.com"
    base_url = "https://test.com"
    has_selectors = True

    def build_search_url(self, query: str) -> str:
        return self.base_url


class _ExternalOnlySite(SiteConfig):
    name = "Test.com"
    base_url = "https://test.com"
    has_selectors = False

    def build_search_url(self, query: str) -> str:
        return self.base_url


def _result(method: Method, **overrides) -> ScrapeResult:
    base = dict(
        site="Test.com",
        status=ScrapeStatus.SUCCESS,
        method=method,
        title=GOOD_TITLE,
        price=332.54,
        rating=4.7,
        review_count=315,
        product_url="https://test.com/p/1",
    )
    base.update(overrides)
    return ScrapeResult(**base)


def _failed_result(error: str = "tier failed") -> ScrapeResult:
    return ScrapeResult(site="Test.com", status=ScrapeStatus.FAILED, error=error)


def _mock_tier(result: ScrapeResult) -> Callable[[SiteConfig, str], Awaitable[ScrapeResult]]:
    async def fn(site, query):  # noqa: ARG001
        return result
    return fn


@pytest.mark.asyncio
async def test_pipeline_returns_first_valid_tier():
    site = _SelectorSite()
    with patch.object(orchestrator, "SELECTOR_TIERS", [
        ("basic", _mock_tier(_result(Method.BASIC))),
        ("browser", _mock_tier(_result(Method.BROWSER))),
    ]), patch.object(orchestrator, "EXTERNAL_TIERS", [
        ("firecrawl", _mock_tier(_result(Method.FIRECRAWL))),
    ]):
        result = await orchestrator.run_pipeline(site, QUERY)
    assert result.status is ScrapeStatus.SUCCESS
    assert result.method is Method.BASIC


@pytest.mark.asyncio
async def test_pipeline_falls_through_failed_tier():
    site = _SelectorSite()
    with patch.object(orchestrator, "SELECTOR_TIERS", [
        ("basic", _mock_tier(_failed_result("basic blocked"))),
        ("browser", _mock_tier(_result(Method.BROWSER))),
    ]), patch.object(orchestrator, "EXTERNAL_TIERS", []):
        result = await orchestrator.run_pipeline(site, QUERY)
    assert result.method is Method.BROWSER


@pytest.mark.asyncio
async def test_pipeline_falls_through_invalid_result():
    """A SUCCESS that doesn't pass the validator (bad price) should fall through."""
    site = _SelectorSite()
    bogus = _result(Method.BASIC, price=0.0)  # price <= 0 → invalid
    with patch.object(orchestrator, "SELECTOR_TIERS", [
        ("basic", _mock_tier(bogus)),
        ("browser", _mock_tier(_result(Method.BROWSER))),
    ]), patch.object(orchestrator, "EXTERNAL_TIERS", []):
        result = await orchestrator.run_pipeline(site, QUERY)
    assert result.method is Method.BROWSER


@pytest.mark.asyncio
async def test_pipeline_returns_failed_when_all_tiers_fail():
    site = _SelectorSite()
    with patch.object(orchestrator, "SELECTOR_TIERS", [
        ("basic", _mock_tier(_failed_result("a"))),
        ("browser", _mock_tier(_failed_result("b"))),
    ]), patch.object(orchestrator, "EXTERNAL_TIERS", [
        ("firecrawl", _mock_tier(_failed_result("c"))),
    ]):
        result = await orchestrator.run_pipeline(site, QUERY)
    assert result.status is ScrapeStatus.FAILED
    # The error message should reflect the *last* tier's failure.
    assert result.error == "c"


@pytest.mark.asyncio
async def test_pipeline_skips_selector_tiers_for_external_only_site():
    """A site with `has_selectors=False` should jump straight to firecrawl."""
    site = _ExternalOnlySite()
    basic_called = False
    firecrawl_called = False

    async def basic(*_):
        nonlocal basic_called
        basic_called = True
        return _failed_result("should not run")

    async def firecrawl(*_):
        nonlocal firecrawl_called
        firecrawl_called = True
        return _result(Method.FIRECRAWL)

    with patch.object(orchestrator, "SELECTOR_TIERS", [("basic", basic)]), \
         patch.object(orchestrator, "EXTERNAL_TIERS", [("firecrawl", firecrawl)]):
        result = await orchestrator.run_pipeline(site, QUERY)

    assert basic_called is False
    assert firecrawl_called is True
    assert result.method is Method.FIRECRAWL


@pytest.mark.asyncio
async def test_run_all_sites_yields_results_in_completion_order():
    """Slow sites must not block fast sites — test by varying tier sleep times."""
    site_a = _ExternalOnlySite()
    site_a.name = "FastSite"
    site_b = _ExternalOnlySite()
    site_b.name = "SlowSite"

    async def fast_tier(site, query):  # noqa: ARG001
        await asyncio.sleep(0.01)
        return _result(Method.FIRECRAWL, site=site.name, title=GOOD_TITLE)

    async def slow_tier(site, query):  # noqa: ARG001
        await asyncio.sleep(0.1)
        return _result(Method.FIRECRAWL, site=site.name, title=GOOD_TITLE)

    async def per_site(site, query, **_):
        return await (fast_tier(site, query) if site.name == "FastSite" else slow_tier(site, query))

    with patch.object(orchestrator, "run_pipeline", per_site):
        completed: list[str] = []
        async for result in orchestrator.run_all_sites(QUERY, sites=[site_b, site_a]):
            completed.append(result.site)

    assert completed == ["FastSite", "SlowSite"], (
        "fast site should yield first regardless of input order"
    )


@pytest.mark.asyncio
async def test_run_all_sites_caches_successful_results():
    """Second call for the same (site, query) must hit cache, not the pipeline."""
    site = _ExternalOnlySite()
    site.name = "CachedSite"
    call_count = 0

    async def per_site(site, query, **_):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        return _result(Method.FIRECRAWL, site=site.name)

    with patch.object(orchestrator, "run_pipeline", per_site):
        first = [r async for r in orchestrator.run_all_sites(QUERY, sites=[site])]
        second = [r async for r in orchestrator.run_all_sites(QUERY, sites=[site])]

    assert call_count == 1, "second run must be served from cache"
    assert first[0].site == second[0].site
    assert first[0].title == second[0].title


@pytest.mark.asyncio
async def test_run_all_sites_does_not_cache_failures():
    """Cache only stores successes — failed sites must retry on next call."""
    site = _ExternalOnlySite()
    site.name = "FlakySite"
    call_count = 0

    async def per_site(site, query, **_):  # noqa: ARG001
        nonlocal call_count
        call_count += 1
        return _failed_result("transient")

    with patch.object(orchestrator, "run_pipeline", per_site):
        [r async for r in orchestrator.run_all_sites(QUERY, sites=[site])]
        [r async for r in orchestrator.run_all_sites(QUERY, sites=[site])]

    assert call_count == 2, "failed result must not be cached"


@pytest.mark.asyncio
async def test_run_all_sites_isolates_per_site_failures():
    """One site raising must not break the run for the others."""
    site_a = _ExternalOnlySite()
    site_a.name = "GoodSite"
    site_b = _ExternalOnlySite()
    site_b.name = "BrokenSite"

    async def per_site(site, query, **_):  # noqa: ARG001
        if site.name == "BrokenSite":
            raise RuntimeError("kaboom")
        return _result(Method.FIRECRAWL, site=site.name, title=GOOD_TITLE)

    with patch.object(orchestrator, "run_pipeline", per_site):
        results = [r async for r in orchestrator.run_all_sites(QUERY, sites=[site_a, site_b])]

    by_site = {r.site: r for r in results}
    assert by_site["GoodSite"].status is ScrapeStatus.SUCCESS
    assert by_site["BrokenSite"].status is ScrapeStatus.FAILED
    assert "kaboom" in (by_site["BrokenSite"].error or "")


# --- LLM verification wiring -------------------------------------------------

@pytest.mark.asyncio
async def test_run_pipeline_falls_through_when_llm_verify_rejects():
    """A title rejected by the LLM judge must trigger the next tier, same as a
    validator failure."""
    site = _SelectorSite()
    # Both tiers return validator-passing results; LLM rejects only the first.
    first = _result(Method.BASIC)
    second = _result(Method.BROWSER)
    calls = 0

    async def fake_verify(query, title):  # noqa: ARG001
        nonlocal calls
        calls += 1
        if calls == 1:
            return False, "different product line"
        return True, "ok"

    with patch.object(orchestrator, "SELECTOR_TIERS", [
        ("basic", _mock_tier(first)),
        ("browser", _mock_tier(second)),
    ]), patch.object(orchestrator, "EXTERNAL_TIERS", []), \
         patch.object(orchestrator, "verify_title", fake_verify):
        result = await orchestrator.run_pipeline(site, QUERY)

    assert result.method is Method.BROWSER
    assert any(
        a.outcome == "rejected" and a.error and "llm-verify" in a.error
        for a in result.tier_trace
    )


@pytest.mark.asyncio
async def test_run_all_sites_applies_query_rewrite():
    """Per-site rewrites must reach the tier as the effective search string and
    propagate to ScrapeResult.query_used."""
    site = _ExternalOnlySite()
    site.name = "ReroutedSite"
    seen_queries: list[str] = []

    async def per_site(site, query, **_):
        seen_queries.append(query)
        return _result(Method.FIRECRAWL, site=site.name)

    async def fake_rewrite(q, sites):
        return {s: f"canonical {q}" for s in sites}

    with patch.object(orchestrator, "run_pipeline", per_site), \
         patch.object(orchestrator, "rewrite_queries", fake_rewrite):
        results = [r async for r in orchestrator.run_all_sites(QUERY, sites=[site])]

    assert seen_queries == [f"canonical {QUERY}"]
    assert results[0].query_used == f"canonical {QUERY}"


@pytest.mark.asyncio
async def test_run_all_sites_flips_price_outlier():
    """A site whose price is far from the cross-site median must be re-emitted
    as FAILED after the initial gather completes."""
    sites = []
    for name in ("S1", "S2", "S3", "S4"):
        s = _ExternalOnlySite()
        s.name = name
        sites.append(s)
    prices = {"S1": 400.0, "S2": 380.0, "S3": 390.0, "S4": 9999.0}

    async def per_site(site, query, **_):
        return _result(Method.FIRECRAWL, site=site.name, price=prices[site.name])

    with patch.object(orchestrator, "run_pipeline", per_site):
        emitted = [r async for r in orchestrator.run_all_sites(QUERY, sites=sites)]

    final_by_site: dict[str, ScrapeResult] = {}
    for r in emitted:
        final_by_site[r.site] = r  # later emission overwrites — outlier flip lands last

    assert final_by_site["S4"].status is ScrapeStatus.FAILED
    assert "price-outlier" in (final_by_site["S4"].error or "")
    assert final_by_site["S1"].status is ScrapeStatus.SUCCESS
    assert final_by_site["S2"].status is ScrapeStatus.SUCCESS
    assert final_by_site["S3"].status is ScrapeStatus.SUCCESS
