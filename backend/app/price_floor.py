"""Plausible-price floor per product category.

Without this gate, Amazon's multi-offer search results sometimes surface
accessory or refurbished prices (a $9.99 phone case in the "frequently
bought together" rail) and Walmart's installment widgets occasionally
slip through as headline figures. The category floor rejects any price
that's an order of magnitude below the lowest plausible new-unit price
for that product class.

Categories are matched by keyword presence in the user's query (lowercase
substring). First match wins; falls back to ``DEFAULT_FLOOR`` so we still
catch obvious $1 garbage on uncategorised queries.
"""

# (category keywords, min USD for a legit new unit)
# Keep keywords narrow — a too-loose match ("pro" → all laptops) would
# reject legitimate cheaper-tier products in adjacent categories.
_CATEGORIES: tuple[tuple[tuple[str, ...], float], ...] = (
    (("iphone", "galaxy s", "pixel ", "smartphone", "oneplus"), 200.0),
    (("macbook", "laptop", "thinkpad", "zenbook", "chromebook"), 250.0),
    (("ipad", "tablet", "galaxy tab", "lenovo tab", "surface pro"), 80.0),
    (("airpods", "earbuds", "headphones", "wh-1000", "buds pro"), 30.0),
    (("playstation", "ps5", "xbox", "nintendo switch"), 150.0),
    (("rtx ", "radeon", "geforce", "graphics card"), 150.0),
    (("apple watch", "galaxy watch", "smartwatch"), 100.0),
    (("camera", "dslr", "mirrorless"), 200.0),
    (("oled tv", "qled", "smart tv", "4k tv"), 100.0),
)

# Floor when nothing matched. Pure trash filter — $1 iPhones, $0.50 GPUs.
DEFAULT_FLOOR = 5.0


def floor_for(query: str) -> float:
    """Return the lowest plausible USD price for the category implied by ``query``."""
    q = query.lower()
    for keywords, floor in _CATEGORIES:
        if any(k in q for k in keywords):
            return floor
    return DEFAULT_FLOOR
