"""How well two pieces go together.

Learned scores come from spark/pairings_job.py (H&M baskets: what people buy together). Lift > 1
means two (category, color) pieces co-occur more than chance. When a pair is missing from the
learned table we fall back to simple color rules.
"""

import json
from functools import lru_cache
from pathlib import Path

from .config import get_settings
from .taxonomy import NEUTRALS

_GOOD_COLOR_PAIRS = {
    frozenset(p) for p in [
        ("blue", "pink"), ("blue", "yellow"), ("green", "pink"), ("purple", "yellow"),
        ("blue", "orange"), ("green", "brown"), ("red", "blue"), ("pink", "purple"),
    ]
}
_CLASHING_COLOR_PAIRS = {
    frozenset(p) for p in [
        ("red", "pink"), ("orange", "pink"), ("red", "green"), ("purple", "orange"),
        ("red", "orange"), ("orange", "purple"),
    ]
}


def token(category: str, color: str) -> str:
    return f"{category}|{color}"


def pair_key(a: str, b: str) -> str:
    return "::".join(sorted((a, b)))


class PairingModel:
    def __init__(self, pairs: dict[str, float] | None = None, color_pairs: dict[str, float] | None = None,
                 meta: dict | None = None):
        self.pairs = pairs or {}
        self.color_pairs = color_pairs or {}
        self.meta = meta or {"source": "rules"}

    @classmethod
    def load(cls, path: Path) -> "PairingModel":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        return cls(data.get("pairs", {}), data.get("color_pairs", {}), data.get("meta", {}))

    @staticmethod
    def rule_score(c1: str, c2: str) -> float:
        if c1 == "multi" and c2 == "multi":
            return 0.2
        if c1 in NEUTRALS and c2 in NEUTRALS:
            return 0.7 if c1 != c2 or c1 in {"black", "navy", "white"} else 0.6
        if c1 in NEUTRALS or c2 in NEUTRALS:
            return 0.65
        pair = frozenset((c1, c2))
        if c1 == c2:
            return 0.45
        if pair in _GOOD_COLOR_PAIRS:
            return 0.6
        if pair in _CLASHING_COLOR_PAIRS:
            return 0.2
        return 0.4

    def score(self, cat1: str, col1: str, cat2: str, col2: str) -> float:
        """0..1, where 0.5 means 'no better than chance'."""
        rule = self.rule_score(col1, col2)
        lift = self.pairs.get(pair_key(token(cat1, col1), token(cat2, col2)))
        if lift is None:
            lift = self.color_pairs.get(pair_key(col1, col2))
            if lift is None:
                return rule
            # Color-only evidence is weaker: blend with the rules.
            return 0.5 * (lift / (1 + lift)) + 0.5 * rule
        return 0.7 * (lift / (1 + lift)) + 0.3 * rule


@lru_cache
def get_model() -> PairingModel:
    return PairingModel.load(get_settings().pairings_path)
