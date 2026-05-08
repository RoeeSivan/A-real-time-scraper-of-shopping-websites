"""Orchestrator tests with mocked tier functions — no network calls."""

import asyncio
from typing import Awaitable, Callable
from unittest.mock import patch

import pytest

from app import orchestrator
from app.models import Method, ScrapeResult, ScrapeStatus
from app.sites.base import SiteConfig

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

    async def per_site(site, query):
        return await (fast_tier(site, query) if site.name == "FastSite" else slow_tier(site, query))

    with patch.object(orchestrator, "run_pipeline", per_site):
        completed: list[str] = []
        async for result in orchestrator.run_all_sites(QUERY, sites=[site_b, site_a]):
            completed.append(result.site)

    assert completed == ["FastSite", "SlowSite"], (
        "fast site should yield first regardless of input order"
    )


@pytest.mark.asyncio
async def test_run_all_sites_isolates_per_site_failures():
    """One site raising must not break the run for the others."""
    site_a = _ExternalOnlySite()
    site_a.name = "GoodSite"
    site_b = _ExternalOnlySite()
    site_b.name = "BrokenSite"

    async def per_site(site, query):  # noqa: ARG001
        if site.name == "BrokenSite":
            raise RuntimeError("kaboom")
        return _result(Method.FIRECRAWL, site=site.name, title=GOOD_TITLE)

    with patch.object(orchestrator, "run_pipeline", per_site):
        results = [r async for r in orchestrator.run_all_sites(QUERY, sites=[site_a, site_b])]

    by_site = {r.site: r for r in results}
    assert by_site["GoodSite"].status is ScrapeStatus.SUCCESS
    assert by_site["BrokenSite"].status is ScrapeStatus.FAILED
    assert "kaboom" in (by_site["BrokenSite"].error or "")
