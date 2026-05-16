import re

from rapidfuzz import fuzz

from app.models import Candidate

# Variant suffixes that meaningfully change the product (Apple/Samsung style).
# If a title contains one of these as a whole word in the *name prefix* and
# the query doesn't, it's a different SKU — reject regardless of substring
# similarity. This stops "iPhone 16" from matching "iPhone 16 Pro Max" at
# sim=100, while still allowing "Lenovo Yoga Slim 7i Aura Edition" to match
# titles whose spec text mentions "Intel Core Ultra 7" (the CPU, not a
# variant suffix).
VARIANT_TOKENS = ("pro", "max", "ultra", "plus", "mini")
_VARIANT_PATTERNS = {tok: re.compile(rf"\b{tok}\b", re.IGNORECASE) for tok in VARIANT_TOKENS}

# Boundary markers that separate a product's *name* from its *spec text* in
# typical retailer titles. Once we hit one of these, anything after it is
# specs/marketing copy, not a variant suffix.
_SPEC_SEPARATORS = re.compile(
    r"[,\(\[]"            # commas, opening parens/brackets
    r"|[–—]"    # en/em dashes
    r"| - "                # hyphen with surrounding spaces
    r"|\bIntel\b|\bAMD\b|\bSnapdragon\b|\bQualcomm\b"
    r"|\bRyzen\b|\bCore\b|\bApple M\d\b|\bM\d\s*(Pro|Max|Ultra)?\b"
    r"|\bGeForce\b|\bRadeon\b|\bNvidia\b"
    r"|\bGB\b|\bTB\b|\bRAM\b|\bSSD\b|\bHDD\b"
    r"|\bWi-?Fi\b|\bBluetooth\b",
    re.IGNORECASE,
)


def _name_prefix(title: str) -> str:
    """Return the slice of `title` before the first spec separator. Falls back
    to the whole string if no separator is found."""
    m = _SPEC_SEPARATORS.search(title)
    return title[: m.start()] if m else title


def _title_has_extra_variant(query: str, title: str) -> bool:
    """True if the title's name prefix contains a variant token absent from
    the query. Variant tokens deep in spec text (e.g. "Intel Core Ultra 7"
    inside a Lenovo Yoga listing) are intentionally ignored."""
    prefix = _name_prefix(title)
    for tok, rx in _VARIANT_PATTERNS.items():
        if rx.search(prefix) and not rx.search(query):
            return True
    return False


# Tokens containing at least one digit — these are model/version identifiers
# (WH-1000XM5 → "1000xm5", iPhone 16 → "16", P12-2024 → "p12" + "2024", M3).
# A query that names a specific model MUST match a title that names the same
# model; otherwise `partial_ratio` will happily give 96 to "WH-1000XM4" vs
# "WH-1000XM5" because the surrounding text overlaps.
# Hyphens are NOT included in the character class so compound identifiers like
# "P12-2024" split into ["P12", "2024"]; "2024" then gets filtered as a year.
_MODEL_TOKEN = re.compile(r"[a-z0-9]*\d[a-z0-9]*", re.IGNORECASE)
# Pure-year tokens (4 digits between 1990 and 2099) are too generic — most
# titles drop the release year, and forcing it would zero every match. Filtered
# out of the anchor set; `partial_ratio` still penalizes year mismatches.
_YEAR_TOKEN = re.compile(r"^(19|20)\d{2}$")


def _model_tokens(text: str) -> list[str]:
    """Extract digit-bearing identifiers from `text`. Drops bare years
    (1990–2099) because they're too generic to anchor on."""
    out: list[str] = []
    for m in _MODEL_TOKEN.finditer(text):
        tok = m.group().lower()
        if not tok or _YEAR_TOKEN.match(tok):
            continue
        out.append(tok)
    return out


def _query_model_mismatch(query: str, title: str) -> bool:
    """True iff `query` names model identifiers that NONE of `title`'s
    text contains. Substring containment (not equality) so "1000xm5" matches
    a title that mentions "WH-1000XM5" anywhere. When the query has no model
    identifier, returns False (no constraint applied)."""
    qtokens = _model_tokens(query)
    if not qtokens:
        return False
    title_lower = title.lower()
    return not any(t in title_lower for t in qtokens)

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
    if _query_model_mismatch(query, title):
        # "Sony WH-1000XM5" must not match "WH-1000XM4" just because the
        # surrounding tokens (Sony, headphones) overlap.
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
