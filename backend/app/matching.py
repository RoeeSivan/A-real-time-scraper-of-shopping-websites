import re

from rapidfuzz import fuzz

from app.models import Candidate

# Variant suffixes that meaningfully change the product (Apple/Samsung style).
# If a title contains one of these as a whole word and the query doesn't,
# it's a different SKU — reject regardless of substring similarity. This
# stops "iPhone 16" from matching "iPhone 16 Pro Max" at sim=100.
VARIANT_TOKENS = ("pro", "max", "ultra", "plus", "mini")
_VARIANT_PATTERNS = {tok: re.compile(rf"\b{tok}\b", re.IGNORECASE) for tok in VARIANT_TOKENS}


def _title_has_extra_variant(query: str, title: str) -> bool:
    """True if `title` contains a variant token that's absent from `query`."""
    for tok, rx in _VARIANT_PATTERNS.items():
        if rx.search(title) and not rx.search(query):
            return True
    return False

# `partial_ratio` (best-substring match) discriminates much better than
# `token_set_ratio` on real product titles, which are typically short queries
# vs verbose titles padded with specs/SKUs/colors. Live benchmark on the
# query "Lenovo Tab P12-2024":
#   real product ("Lenovo Tab P12 128 GB Mediatek …")   → 84.8  ✓ accept
#   wrong product ("Lenovo Idea Tab Pro 12.7")          → 66.7  ✗ reject
#   accessory     ("BONAEVER Keyboard Case for ... P12") → 78.9  ⚠ borderline
#   unrelated     ("Apple iPad Pro M4")                  → ~25   ✗ reject
# 75 splits real-vs-wrong cleanly. Same-family overlaps (XM4 vs XM5,
# iPhone 16 vs Pro Max, accessories) score similarly high — no similarity
# metric alone can resolve those; see CLAUDE.md follow-ups.
DEFAULT_THRESHOLD = 75.0


def score(query: str, title: str) -> float:
    """0..100 best-substring similarity. Robust to verbose titles."""
    if not query or not title:
        return 0.0
    if _title_has_extra_variant(query, title):
        return 0.0
    return float(fuzz.partial_ratio(query.lower(), title.lower()))


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
