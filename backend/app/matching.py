from rapidfuzz import fuzz

from app.models import Candidate

# A safe default — empirically clears "Lenovo Tab P12" vs
# "Lenovo Tab P12-2024 Touchscreen Tablet" but rejects clearly different items.
DEFAULT_THRESHOLD = 55.0


def score(query: str, title: str) -> float:
    """0..100 token-set similarity. Robust to word order and extra words."""
    if not query or not title:
        return 0.0
    return float(fuzz.token_set_ratio(query.lower(), title.lower()))


def pick_best_candidate(
    query: str,
    candidates: list[Candidate],
    threshold: float = DEFAULT_THRESHOLD,
) -> tuple[Candidate, float] | None:
    """Return the (candidate, score) above threshold, or None if nothing clears it."""
    if not candidates:
        return None
    scored = [(c, score(query, c.title)) for c in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    best, best_score = scored[0]
    if best_score < threshold:
        return None
    return best, best_score
