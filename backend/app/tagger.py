"""Photo -> clothing tags.

Uses Gemini (vision + structured JSON output) when GEMINI_API_KEY is set. Without a key it falls
back to an offline tagger that only detects the dominant color, so the app still works locally and
in tests; the user then fixes the category and formality by hand.
"""

import base64
import io
import json
import logging
from dataclasses import asdict, dataclass, field

import httpx
from PIL import Image, ImageOps

from .config import get_settings
from .taxonomy import (
    CATEGORIES, COLORS, SEASONS, clamp_int, normalize_category, normalize_color,
)

log = logging.getLogger(__name__)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT = """You are tagging one clothing item photographed by a college student for a digital closet app.
Describe the single main garment in the photo (ignore the background, hangers, and the person wearing it).
- category: top (shirts, sweaters, hoodies), bottom (pants, jeans, skirts, shorts), dress (dresses, jumpsuits),
  outerwear (jackets, coats, blazers), shoes, or accessory (bags, belts, hats, jewelry).
- color: the dominant color. Use navy for dark blue, beige for cream/tan/khaki, multi for strong prints.
- formality from 1 to 5: 1 lounge/gym, 2 casual, 3 smart casual (date night, class presentation),
  4 business (internship, interview), 5 formal (gala, wedding).
- warmth from 1 to 5: 1 very light (tank top, linen shorts) to 5 very warm (wool coat, snow boots).
- seasons: every season it is comfortable to wear in.
- name: a short 2-4 word name a person would use, e.g. "black denim jacket"."""

RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "name": {"type": "STRING"},
        "category": {"type": "STRING", "enum": CATEGORIES},
        "color": {"type": "STRING", "enum": COLORS},
        "secondary_color": {"type": "STRING", "enum": COLORS + ["none"]},
        "pattern": {"type": "STRING", "enum": ["solid", "striped", "plaid", "floral", "graphic", "other"]},
        "formality": {"type": "INTEGER"},
        "warmth": {"type": "INTEGER"},
        "seasons": {"type": "ARRAY", "items": {"type": "STRING", "enum": SEASONS}},
    },
    "required": ["name", "category", "color", "pattern", "formality", "warmth", "seasons"],
}

# Reference RGB values for the offline fallback.
_PALETTE = {
    "black": (25, 25, 25), "white": (240, 240, 240), "grey": (128, 128, 128),
    "beige": (215, 195, 160), "brown": (110, 70, 40), "red": (190, 30, 40),
    "orange": (235, 125, 35), "yellow": (240, 210, 50), "green": (60, 130, 60),
    "blue": (70, 120, 200), "navy": (30, 40, 80), "purple": (120, 70, 150), "pink": (235, 150, 180),
}


@dataclass
class Tags:
    name: str
    category: str
    color: str
    secondary_color: str | None = None
    pattern: str = "solid"
    formality: int = 2
    warmth: int = 3
    seasons: list[str] = field(default_factory=lambda: list(SEASONS))
    source: str = "fallback"

    def as_dict(self) -> dict:
        return asdict(self)


def prepare_image(raw: bytes, max_side: int = 768) -> bytes:
    """Fix phone rotation, strip metadata (incl. GPS), shrink, and re-encode as JPEG."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True)
    return out.getvalue()


def dominant_color(jpeg: bytes) -> str:
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    w, h = img.size
    # The garment is usually centred; the edges are usually background.
    img = img.crop((w // 5, h // 5, w - w // 5, h - h // 5)).resize((48, 48))
    counts: dict[str, int] = {}
    for r, g, b in img.get_flattened_data():
        name = min(_PALETTE, key=lambda c: sum((x - y) ** 2 for x, y in zip((r, g, b), _PALETTE[c])))
        counts[name] = counts.get(name, 0) + 1
    return max(counts, key=counts.get)


def fallback_tags(jpeg: bytes) -> Tags:
    color = dominant_color(jpeg)
    return Tags(name=f"{color} item", category="top", color=color, source="fallback")


def parse_model_json(payload: dict) -> Tags:
    secondary = payload.get("secondary_color")
    return Tags(
        name=str(payload.get("name") or "item")[:120],
        category=normalize_category(payload.get("category")),
        color=normalize_color(payload.get("color")),
        secondary_color=None if secondary in (None, "", "none") else normalize_color(secondary),
        pattern=str(payload.get("pattern") or "solid"),
        formality=clamp_int(payload.get("formality"), 1, 5, 2),
        warmth=clamp_int(payload.get("warmth"), 1, 5, 3),
        seasons=[s for s in payload.get("seasons") or [] if s in SEASONS] or list(SEASONS),
        source="gemini",
    )


def gemini_tags(jpeg: bytes, client: httpx.Client | None = None) -> Tags:
    settings = get_settings()
    body = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpeg).decode()}},
                {"text": PROMPT},
            ]
        }],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }
    own = client is None
    client = client or httpx.Client(timeout=45)
    try:
        resp = client.post(
            GEMINI_URL.format(model=settings.gemini_model),
            headers={"x-goog-api-key": settings.gemini_api_key},
            json=body,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        return parse_model_json(json.loads(text))
    finally:
        if own:
            client.close()


def tag_image(jpeg: bytes) -> Tags:
    if get_settings().gemini_api_key:
        try:
            return gemini_tags(jpeg)
        except Exception as exc:  # network, quota, or malformed response
            log.warning("Gemini tagging failed, using fallback: %s", exc)
    return fallback_tags(jpeg)
