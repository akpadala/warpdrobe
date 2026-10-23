"""Shared vocabulary for clothing tags. The tagger, engine and Spark job all use these values."""

CATEGORIES = ["top", "bottom", "dress", "outerwear", "shoes", "accessory"]

COLORS = [
    "black", "white", "grey", "beige", "brown", "red", "orange", "yellow",
    "green", "blue", "navy", "purple", "pink", "metallic", "multi",
]

NEUTRALS = {"black", "white", "grey", "beige", "brown", "navy"}

SEASONS = ["spring", "summer", "fall", "winter"]

# 1 = lounge/gym, 2 = casual, 3 = smart casual, 4 = business, 5 = formal
FORMALITY_LABELS = {1: "lounge", 2: "casual", 3: "smart casual", 4: "business", 5: "formal"}

# 1 = very light (tank top, shorts) ... 5 = very warm (wool coat, boots)
WARMTH_LABELS = {1: "very light", 2: "light", 3: "medium", 4: "warm", 5: "very warm"}


def clamp_int(value, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(round(float(value)))))
    except (TypeError, ValueError):
        return default


def normalize_color(value: str | None) -> str:
    v = (value or "").strip().lower()
    aliases = {
        "gray": "grey", "cream": "beige", "tan": "beige", "khaki": "beige", "camel": "brown",
        "dark blue": "navy", "light blue": "blue", "denim": "blue", "burgundy": "red",
        "maroon": "red", "olive": "green", "lilac": "purple", "lavender": "purple",
        "gold": "metallic", "silver": "metallic", "patterned": "multi", "print": "multi",
    }
    v = aliases.get(v, v)
    return v if v in COLORS else "multi"


def normalize_category(value: str | None) -> str:
    v = (value or "").strip().lower()
    aliases = {
        "shirt": "top", "t-shirt": "top", "blouse": "top", "sweater": "top", "hoodie": "top",
        "pants": "bottom", "jeans": "bottom", "skirt": "bottom", "shorts": "bottom",
        "trousers": "bottom", "jacket": "outerwear", "coat": "outerwear", "blazer": "outerwear",
        "jumpsuit": "dress", "romper": "dress", "shoe": "shoes", "sneakers": "shoes",
        "boots": "shoes", "bag": "accessory", "jewelry": "accessory", "hat": "accessory",
    }
    v = aliases.get(v, v)
    return v if v in CATEGORIES else "top"
