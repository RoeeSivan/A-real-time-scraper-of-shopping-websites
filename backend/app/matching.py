from rapidfuzz import fuzz

from app.models import Candidate

# Empirically chosen: a clean subset match (e.g. query tokens ⊂ title tokens)
# scores 100; an "almost-but-different" pairing like "Lenovo Tab P12-2024" vs
# "Lenovo Idea Tab Pro …" scores ~69. 70 splits those cleanly while still
# accepting expanded titles ("iPhone 15" → "Apple iPhone 15 Pro Max …" = 100).
DEFAULT_THRESHOLD = 70.0


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
