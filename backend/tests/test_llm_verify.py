"""Tests for the LLM verification layer.

`rewrite_queries` and `verify_title` are network-bound; we mock the
`get_openai_client` factory so no actual API call is made. `flag_price_outliers`
is pure and tested directly.

Default-off behaviour (no API key / flag=False) is also covered to confirm the
graceful-degradation contract: helpers must return safe identities so the rest
of the cascade keeps working without an OpenAI account.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import llm_verify
from app.models import ScrapeResult, ScrapeStatus


# ---------------------------------------------------------------------------
# rewrite_queries
# ---------------------------------------------------------------------------

def _mock_rewrite_completion(entries: list[tuple[str, str]]) -> MagicMock:
    """Build a fake OpenAI completion that mimics the `.parsed` shape."""
    parsed = llm_verify._RewriteResponse(
        rewrites=[
            llm_verify._RewriteEntry(site=s, rewritten_query=q)
            for s, q in entries
        ]
    )
    choice = MagicMock()
    choice.message.parsed = parsed
    completion = MagicMock()
    completion.choices = [choice]
    return completion


@pytest.mark.asyncio
async def test_rewrite_queries_returns_per_site_map(monkeypatch):
    monkeypatch.setattr(llm_verify.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(llm_verify.settings, "enable_llm_verification", True)

    client = MagicMock()
    client.beta.chat.completions.parse = AsyncMock(
        return_value=_mock_rewrite_completion([
            ("Amazon", "Bose QuietComfort Ultra Headphones"),
            ("BestBuy", "Bose QuietComfort Ultra Wireless Headphones"),
        ])
    )
    with patch.object(llm_verify, "get_openai_client", return_value=client):
        out = await llm_verify.rewrite_queries("bose qc ultra", ["Amazon", "BestBuy"])

    assert out == {
        "Amazon": "Bose QuietComfort Ultra Headphones",
        "BestBuy": "Bose QuietComfort Ultra Wireless Headphones",
    }


@pytest.mark.asyncio
async def test_rewrite_queries_fills_missing_sites_with_original(monkeypatch):
    monkeypatch.setattr(llm_verify.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(llm_verify.settings, "enable_llm_verification", True)

    client = MagicMock()
    client.beta.chat.completions.parse = AsyncMock(
        return_value=_mock_rewrite_completion([("Amazon", "Sony WH-1000XM5")])
    )
    with patch.object(llm_verify, "get_openai_client", return_value=client):
        out = await llm_verify.rewrite_queries("sony xm5", ["Amazon", "Walmart"])

    assert out == {"Amazon": "Sony WH-1000XM5", "Walmart": "sony xm5"}


@pytest.mark.asyncio
async def test_rewrite_queries_returns_identity_when_disabled(monkeypatch):
    monkeypatch.setattr(llm_verify.settings, "enable_llm_verification", False)
    out = await llm_verify.rewrite_queries("anything", ["Amazon", "Walmart"])
    assert out == {"Amazon": "anything", "Walmart": "anything"}


@pytest.mark.asyncio
async def test_rewrite_queries_returns_identity_when_no_key(monkeypatch):
    monkeypatch.setattr(llm_verify.settings, "openai_api_key", None)
    monkeypatch.setattr(llm_verify.settings, "enable_llm_verification", True)
    out = await llm_verify.rewrite_queries("q", ["Amazon"])
    assert out == {"Amazon": "q"}


@pytest.mark.asyncio
async def test_rewrite_queries_empty_site_list_is_no_op(monkeypatch):
    monkeypatch.setattr(llm_verify.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(llm_verify.settings, "enable_llm_verification", True)
    # Even with the key set, an empty list must short-circuit without an API call.
    with patch.object(llm_verify, "get_openai_client") as mock_factory:
        out = await llm_verify.rewrite_queries("q", [])
    assert out == {}
    mock_factory.assert_not_called()


@pytest.mark.asyncio
async def test_rewrite_queries_falls_back_on_api_error(monkeypatch):
    monkeypatch.setattr(llm_verify.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(llm_verify.settings, "enable_llm_verification", True)

    client = MagicMock()
    client.beta.chat.completions.parse = AsyncMock(side_effect=RuntimeError("boom"))
    with patch.object(llm_verify, "get_openai_client", return_value=client):
        out = await llm_verify.rewrite_queries("q", ["Amazon"])
    assert out == {"Amazon": "q"}


# ---------------------------------------------------------------------------
# verify_title
# ---------------------------------------------------------------------------

def _mock_verify_completion(matches: bool, reason: str) -> MagicMock:
    parsed = llm_verify._VerifyResponse(matches=matches, reason=reason)
    choice = MagicMock()
    choice.message.parsed = parsed
    completion = MagicMock()
    completion.choices = [choice]
    return completion


@pytest.mark.asyncio
async def test_verify_title_true(monkeypatch):
    monkeypatch.setattr(llm_verify.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(llm_verify.settings, "enable_llm_verification", True)
    client = MagicMock()
    client.beta.chat.completions.parse = AsyncMock(
        return_value=_mock_verify_completion(True, "exact line match")
    )
    with patch.object(llm_verify, "get_openai_client", return_value=client):
        ok, reason = await llm_verify.verify_title("Sony WH-1000XM5", "Sony WH-1000XM5 Wireless Headphones")
    assert ok is True
    assert "exact" in reason


@pytest.mark.asyncio
async def test_verify_title_false(monkeypatch):
    monkeypatch.setattr(llm_verify.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(llm_verify.settings, "enable_llm_verification", True)
    client = MagicMock()
    client.beta.chat.completions.parse = AsyncMock(
        return_value=_mock_verify_completion(False, "XM4 not XM5")
    )
    with patch.object(llm_verify, "get_openai_client", return_value=client):
        ok, reason = await llm_verify.verify_title("Sony WH-1000XM5", "Sony WH-1000XM4 Headphones")
    assert ok is False
    assert "XM4" in reason


@pytest.mark.asyncio
async def test_verify_title_empty_rejects():
    ok, reason = await llm_verify.verify_title("anything", "")
    assert ok is False
    assert "empty" in reason


@pytest.mark.asyncio
async def test_verify_title_skipped_when_disabled(monkeypatch):
    monkeypatch.setattr(llm_verify.settings, "enable_llm_verification", False)
    ok, reason = await llm_verify.verify_title("query", "title")
    assert ok is True
    assert reason == "skipped"


@pytest.mark.asyncio
async def test_verify_title_passes_through_on_api_error(monkeypatch):
    """Fail-open: don't reject good results just because the OpenAI call hiccupped."""
    monkeypatch.setattr(llm_verify.settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(llm_verify.settings, "enable_llm_verification", True)
    client = MagicMock()
    client.beta.chat.completions.parse = AsyncMock(side_effect=TimeoutError("slow"))
    with patch.object(llm_verify, "get_openai_client", return_value=client):
        ok, reason = await llm_verify.verify_title("q", "t")
    assert ok is True
    assert "fail" in reason or "call" in reason


# ---------------------------------------------------------------------------
# flag_price_outliers (pure function)
# ---------------------------------------------------------------------------

def _success(site: str, price: float | None) -> ScrapeResult:
    return ScrapeResult(
        site=site,
        status=ScrapeStatus.SUCCESS,
        title=f"{site} product title",
        price=price,
        product_url=f"https://{site.lower()}.example/p/1",
    )


def _failed(site: str) -> ScrapeResult:
    return ScrapeResult(site=site, status=ScrapeStatus.FAILED, error="x")


def test_flag_outliers_skipped_below_three_samples():
    results = [_success("A", 100.0), _success("B", 105.0)]
    outliers, median = llm_verify.flag_price_outliers(results)
    assert outliers == []
    assert median == 102.5  # still computed, just not used for flagging


def test_flag_outliers_no_priced_results():
    outliers, median = llm_verify.flag_price_outliers([_failed("A"), _failed("B")])
    assert outliers == []
    assert median is None


def test_flag_outliers_within_threshold():
    """All prices within 30% of median → no flags."""
    results = [
        _success("A", 100.0),
        _success("B", 110.0),
        _success("C", 90.0),
        _success("D", 120.0),
    ]
    outliers, median = llm_verify.flag_price_outliers(results)
    assert outliers == []
    assert median == 105.0


def test_flag_outliers_detects_high_outlier():
    """One sky-high price > 30% of median should be flagged."""
    results = [
        _success("A", 400.0),
        _success("B", 380.0),
        _success("C", 390.0),
        _success("D", 1200.0),  # 3x median = outlier
    ]
    outliers, median = llm_verify.flag_price_outliers(results)
    assert outliers == ["D"]
    assert median == 395.0


def test_flag_outliers_detects_low_outlier():
    """A suspiciously cheap price (e.g. case/accessory leak) should be flagged too."""
    results = [
        _success("A", 400.0),
        _success("B", 390.0),
        _success("C", 410.0),
        _success("D", 30.0),  # way below median → outlier
    ]
    outliers, median = llm_verify.flag_price_outliers(results)
    assert outliers == ["D"]
    # median of sorted (30, 390, 400, 410) = (390 + 400) / 2
    assert median == 395.0


def test_flag_outliers_ignores_failed_and_priceless():
    """Failed results and None prices must not influence the median."""
    results = [
        _success("A", 100.0),
        _success("B", 105.0),
        _success("C", 95.0),
        _success("D", None),       # priceless → ignored
        _failed("E"),               # failed → ignored
    ]
    outliers, median = llm_verify.flag_price_outliers(results)
    assert outliers == []
    assert median == 100.0


def test_flag_outliers_custom_deviation():
    """Tighter threshold should flag near-edge prices."""
    results = [
        _success("A", 100.0),
        _success("B", 100.0),
        _success("C", 100.0),
        _success("D", 130.0),  # 30% deviation exactly
    ]
    # default: not strictly > 30% → no flag
    outliers, _ = llm_verify.flag_price_outliers(results)
    assert outliers == []
    # tightened to 20% → D is flagged
    outliers, _ = llm_verify.flag_price_outliers(results, deviation=0.20)
    assert outliers == ["D"]


# ---------------------------------------------------------------------------
# client singleton plumbing
# ---------------------------------------------------------------------------

def test_get_openai_client_none_when_no_key(monkeypatch):
    monkeypatch.setattr(llm_verify.settings, "openai_api_key", None)
    llm_verify.reset_client()
    assert llm_verify.get_openai_client() is None


def test_get_openai_client_caches(monkeypatch):
    monkeypatch.setattr(llm_verify.settings, "openai_api_key", "sk-test")
    llm_verify.reset_client()
    first = llm_verify.get_openai_client()
    second = llm_verify.get_openai_client()
    assert first is not None
    assert first is second  # singleton, not rebuilt on each call
    llm_verify.reset_client()
