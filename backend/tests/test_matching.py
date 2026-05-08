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
