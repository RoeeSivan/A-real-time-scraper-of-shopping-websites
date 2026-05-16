from app.matching import DEFAULT_THRESHOLD, pick_best_candidate, score
from app.models import Candidate


def test_score_exact_match_is_100():
    assert score("Lenovo Tab P12", "Lenovo Tab P12") == 100.0


def test_score_close_variant_clears_threshold():
    # A real-world Amazon-style title for the same product.
    s = score(
        "Lenovo Tab P12-2024",
        "Lenovo Tab P12-2024 - Expansive Touchscreen Tablet, 12.7 Inch",
    )
    assert s >= DEFAULT_THRESHOLD


def test_score_unrelated_product_is_far_below_threshold():
    s = score("Lenovo Tab P12-2024", "Apple iPad Pro 11-inch (M4)")
    assert s < DEFAULT_THRESHOLD


def test_score_handles_empty_inputs():
    assert score("", "anything") == 0.0
    assert score("anything", "") == 0.0


def test_score_is_case_insensitive():
    assert score("LENOVO tab", "lenovo TAB") == 100.0


def test_pick_best_returns_none_for_empty_list():
    assert pick_best_candidate("Lenovo Tab", []) is None


def test_pick_best_returns_none_when_all_below_threshold():
    candidates = [
        Candidate(title="Apple iPad Pro", url="https://example.com/a"),
        Candidate(title="Samsung Galaxy S24", url="https://example.com/b"),
    ]
    assert pick_best_candidate("Lenovo Tab P12-2024", candidates) is None


def test_variant_filter_ignores_cpu_keyword_in_spec_text():
    # Regression: "Ultra" is a variant token (Galaxy S24 Ultra) but also
    # appears inside Intel "Core Ultra 7" CPU branding. The variant filter
    # must only consider tokens in the title's name prefix, not deep in
    # spec text — otherwise every modern Lenovo Yoga listing scored 0.
    s = score(
        "Lenovo - Yoga Slim 7i Aura Edition",
        "Lenovo Yoga Slim 7i Aura Edition Laptop, 15.3 inch, Intel Core Ultra 7",
    )
    assert s >= DEFAULT_THRESHOLD


def test_variant_filter_still_rejects_iphone_pro_max():
    # The variant filter's original purpose still holds: querying "iPhone 16"
    # must not match "iPhone 16 Pro Max" — those are different SKUs.
    assert score("iPhone 16", "Apple iPhone 16 Pro Max 256GB") == 0.0


def test_variant_filter_still_rejects_galaxy_ultra():
    assert score("Samsung Galaxy S24", "Samsung Galaxy S24 Ultra 256GB") == 0.0


def test_model_anchor_rejects_xm4_when_query_is_xm5():
    """The headline pre-existing bug: 'Sony WH-1000XM5' vs 'WH-1000XM4' scored
    96 on `partial_ratio` because everything except one digit overlaps. Model
    anchor must zero this out."""
    assert score("Sony WH-1000XM5", "Sony WH-1000XM4 Wireless Bluetooth Headphones") == 0.0


def test_model_anchor_accepts_same_model_with_extra_text():
    """The anchor must not over-reject: the same model with marketing copy
    after it should still score high."""
    s = score(
        "Sony WH-1000XM5",
        "Sony WH-1000XM5 Wireless Industry Leading Noise Cancelling Headphones",
    )
    assert s >= DEFAULT_THRESHOLD


def test_model_anchor_iphone_version_mismatch():
    """iPhone 16 must not match iPhone 15 (already rejected by partial_ratio
    too, but the anchor makes it deterministic)."""
    assert score("iPhone 16", "Apple iPhone 15 128GB Black") == 0.0


def test_model_anchor_ignores_year_only_tokens():
    """A bare year like '2024' should NOT count as a model identifier — most
    retailer titles drop the year, and forcing it would zero everything."""
    s = score(
        "Lenovo Tab P12-2024",
        "Lenovo Tab P12 Touchscreen Tablet, 12.7 Inch",
    )
    # P12 is the model anchor (matches), 2024 is treated as a year (ignored).
    assert s >= DEFAULT_THRESHOLD


def test_model_anchor_no_op_when_query_has_no_model():
    """Brand-only queries ('sony headphones') have no model token, so the
    anchor should be a no-op and let `partial_ratio` decide."""
    s = score("sony headphones", "Sony Premium Wireless Headphones")
    assert s >= DEFAULT_THRESHOLD


def test_pick_best_returns_highest_scorer_above_threshold():
    candidates = [
        Candidate(title="Apple iPad Pro", url="https://example.com/a"),
        Candidate(
            title="Lenovo Tab P12-2024 Touchscreen Tablet 12.7 inch",
            url="https://example.com/b",
        ),
        Candidate(title="Lenovo ThinkPad X1 Carbon", url="https://example.com/c"),
    ]
    result = pick_best_candidate("Lenovo Tab P12-2024", candidates)
    assert result is not None
    best, sim = result
    assert best.url == "https://example.com/b"
    assert sim >= DEFAULT_THRESHOLD
