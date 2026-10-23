"""Outfit suggestions and closet analysis.

Works on plain `Piece` objects rather than database rows, so it can be unit tested and can reason
about hypothetical items (for "which new item unlocks the most outfits").
"""

from dataclasses import dataclass, field
from datetime import date
from itertools import combinations

from .pairings import PairingModel
from .taxonomy import FORMALITY_LABELS

W_FORMALITY, W_WEATHER, W_PAIRING, W_FRESH = 0.35, 0.25, 0.30, 0.10
GOOD_BASE = 0.6  # minimum "looks good together" score for counting an outfit as wearable


@dataclass(frozen=True)
class Piece:
    id: int
    name: str
    category: str
    color: str
    formality: int = 2
    warmth: int = 3
    seasons: tuple[str, ...] = ()
    last_worn: date | None = None


@dataclass
class Context:
    day: date
    target_formality: int = 2
    feels_c: float | None = None  # None = weather unknown
    temp_min_c: float | None = None
    precip_chance: int = 0
    occasion: str | None = None


@dataclass
class Suggestion:
    pieces: list[Piece]
    score: float
    parts: dict[str, float]
    reasons: list[str] = field(default_factory=list)


def season_of(day: date) -> str:
    return {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
            6: "summer", 7: "summer", 8: "summer"}.get(day.month, "fall")


def ideal_warmth(feels_c: float) -> int:
    if feels_c >= 26:
        return 1
    if feels_c >= 20:
        return 2
    if feels_c >= 13:
        return 3
    if feels_c >= 6:
        return 4
    return 5


def needs_outerwear(ctx: Context) -> bool | None:
    if ctx.feels_c is None:
        return None
    return ctx.feels_c < 15 or (ctx.temp_min_c is not None and ctx.temp_min_c < 10)


def pairing_score(pieces: list[Piece], model: PairingModel) -> float:
    pairs = list(combinations(pieces, 2))
    if not pairs:
        return 0.6  # a dress on its own is a complete look
    return sum(model.score(a.category, a.color, b.category, b.color) for a, b in pairs) / len(pairs)


def formality_score(pieces: list[Piece], target: int) -> float:
    gap = sum(abs(p.formality - target) for p in pieces) / len(pieces)
    spread = max(p.formality for p in pieces) - min(p.formality for p in pieces)
    # Under-dressing for an interview is worse than over-dressing for class.
    under = sum(max(0, target - p.formality) for p in pieces) / len(pieces)
    return max(0.0, 1 - gap / 4 - spread / 8 - under / 8)


def weather_score(pieces: list[Piece], ctx: Context) -> float:
    if ctx.feels_c is None:
        return 0.7
    ideal = ideal_warmth(ctx.feels_c)
    core = [p for p in pieces if p.category not in {"outerwear", "accessory"}]
    s = 1 - sum(abs(p.warmth - ideal) for p in core) / (4 * len(core)) if core else 0.7
    season = season_of(ctx.day)
    off_season = sum(1 for p in pieces if p.seasons and season not in p.seasons)
    s -= 0.1 * off_season
    has_coat = any(p.category == "outerwear" for p in pieces)
    if needs_outerwear(ctx) and not has_coat:
        s -= 0.25
    return max(0.0, s)


def fresh_score(pieces: list[Piece], day: date) -> float:
    vals = []
    for p in pieces:
        if p.last_worn is None:
            vals.append(1.0)
            continue
        ago = (day - p.last_worn).days
        vals.append(0.2 if 0 <= ago <= 2 else 0.6 if 0 <= ago <= 6 else 1.0)
    return sum(vals) / len(vals)


def score_outfit(pieces: list[Piece], ctx: Context, model: PairingModel) -> Suggestion:
    parts = {
        "formality": formality_score(pieces, ctx.target_formality),
        "weather": weather_score(pieces, ctx),
        "pairing": pairing_score(pieces, model),
        "freshness": fresh_score(pieces, ctx.day),
    }
    total = (W_FORMALITY * parts["formality"] + W_WEATHER * parts["weather"]
             + W_PAIRING * parts["pairing"] + W_FRESH * parts["freshness"])
    return Suggestion(pieces, round(total, 4), {k: round(v, 3) for k, v in parts.items()})


def _bases(pieces: list[Piece]) -> list[list[Piece]]:
    tops = [p for p in pieces if p.category == "top"]
    bottoms = [p for p in pieces if p.category == "bottom"]
    dresses = [p for p in pieces if p.category == "dress"]
    return [[t, b] for t in tops for b in bottoms] + [[d] for d in dresses]


def _best_addon(base: list[Piece], options: list[Piece], ctx: Context, model: PairingModel) -> Piece | None:
    best, best_score = None, -1.0
    for o in options:
        s = score_outfit(base + [o], ctx, model).score
        if s > best_score:
            best, best_score = o, s
    return best


def _reasons(s: Suggestion, ctx: Context) -> list[str]:
    out = []
    if ctx.occasion:
        out.append(f"Dressed for {ctx.occasion} ({FORMALITY_LABELS[ctx.target_formality]}).")
    if ctx.feels_c is not None:
        f = round(ctx.feels_c * 9 / 5 + 32)
        if any(p.category == "outerwear" for p in s.pieces):
            out.append(f"Layer up: it feels like about {f}°F.")
        else:
            out.append(f"Warmth matched to about {f}°F.")
    if ctx.precip_chance >= 50:
        out.append(f"{ctx.precip_chance}% chance of rain; bring an umbrella.")
    if s.parts["pairing"] >= 0.65:
        out.append("These colors and pieces are often worn together.")
    stale = [p.name for p in s.pieces if p.last_worn and 0 <= (ctx.day - p.last_worn).days <= 2]
    if stale:
        out.append(f"Heads up: you wore {', '.join(stale)} recently.")
    return out


def suggest(pieces: list[Piece], ctx: Context, model: PairingModel, k: int = 3) -> list[Suggestion]:
    shoes = [p for p in pieces if p.category == "shoes"]
    coats = [p for p in pieces if p.category == "outerwear"]
    want_coat = needs_outerwear(ctx)
    scored = []
    for base in _bases(pieces):
        outfit = list(base)
        if shoes:
            outfit.append(_best_addon(outfit, shoes, ctx, model))
        if coats and want_coat:
            outfit.append(_best_addon(outfit, coats, ctx, model))
        scored.append(score_outfit(outfit, ctx, model))
    scored.sort(key=lambda s: s.score, reverse=True)

    # Greedy pick for variety: no piece other than shoes/coats in more than one suggestion.
    picked: list[Suggestion] = []
    used: set[int] = set()
    for s in scored:
        core = {p.id for p in s.pieces if p.category not in {"shoes", "outerwear"}}
        if core & used:
            continue
        picked.append(s)
        used |= core
        if len(picked) == k:
            break
    for s in picked:
        s.reasons = _reasons(s, ctx)
    return picked


def base_quality(base: list[Piece], model: PairingModel) -> float:
    """Context-free 'do these look good together' score used for closet analysis."""
    spread = max(p.formality for p in base) - min(p.formality for p in base)
    return 0.5 * (1 - spread / 4) + 0.5 * pairing_score(base, model)


def good_bases(pieces: list[Piece], model: PairingModel) -> list[list[Piece]]:
    return [b for b in _bases(pieces) if base_quality(b, model) >= GOOD_BASE]


def _compatible_addon(base: list[Piece], addon: Piece, model: PairingModel) -> bool:
    return base_quality(base + [addon], model) >= GOOD_BASE


ARCHETYPE_COLORS = ["black", "white", "grey", "beige", "navy", "blue", "brown", "green", "red", "pink"]
ARCHETYPE_CATEGORIES = ["top", "bottom", "dress", "outerwear", "shoes"]


def unlock_ranking(pieces: list[Piece], model: PairingModel, limit: int = 3) -> list[dict]:
    """Which single hypothetical new item would add the most new wearable outfits."""
    current = good_bases(pieces, model)
    # Bases that already have a matching pair of shoes / coat in the closet.
    covered = {
        cat: {i for i, b in enumerate(current)
              if any(_compatible_addon(b, h, model) for h in pieces if h.category == cat)}
        for cat in ("shoes", "outerwear")
    }
    results = []
    next_id = -1
    for cat in ARCHETYPE_CATEGORIES:
        for color in ARCHETYPE_COLORS:
            for formality in (2, 3, 4):
                x = Piece(id=next_id, name=f"{color} {FORMALITY_LABELS[formality]} {cat}",
                          category=cat, color=color, formality=formality)
                next_id -= 1
                if cat in {"top", "bottom", "dress"}:
                    unlocked = len(good_bases(pieces + [x], model)) - len(current)
                else:
                    unlocked = sum(
                        1 for i, b in enumerate(current)
                        if i not in covered[cat] and _compatible_addon(b, x, model)
                    )
                if unlocked > 0:
                    results.append({"name": x.name, "category": cat, "color": color,
                                    "formality": formality, "new_outfits": unlocked})
    results.sort(key=lambda r: (-r["new_outfits"], r["color"] not in {"black", "white", "navy", "grey"}))
    # One entry per (category, color): "black top" at three dressiness levels is one suggestion.
    seen, unique = set(), []
    for r in results:
        if (r["category"], r["color"]) not in seen:
            seen.add((r["category"], r["color"]))
            unique.append(r)
    return unique[:limit]
