from datetime import date

from app import engine
from app.engine import Context, Piece
from app.pairings import PairingModel

RULES = PairingModel()
DAY = date(2026, 10, 27)


def closet():
    return [
        Piece(1, "grey hoodie", "top", "grey", formality=1, warmth=3),
        Piece(2, "white button-down", "top", "white", formality=4, warmth=2),
        Piece(3, "sweatpants", "bottom", "grey", formality=1, warmth=3),
        Piece(4, "navy trousers", "bottom", "navy", formality=4, warmth=3),
        Piece(5, "sneakers", "shoes", "white", formality=2, warmth=2),
        Piece(6, "loafers", "shoes", "black", formality=4, warmth=2),
        Piece(7, "wool coat", "outerwear", "beige", formality=4, warmth=5),
    ]


def ids(s):
    return {p.id for p in s.pieces}


def test_interview_day_picks_business_pieces():
    ctx = Context(day=DAY, target_formality=4, feels_c=18, temp_min_c=12, occasion="Interview")
    best = engine.suggest(closet(), ctx, RULES, k=1)[0]
    assert {2, 4, 6} <= ids(best)
    assert any("Interview" in r for r in best.reasons)


def test_lounge_day_picks_casual_pieces():
    ctx = Context(day=DAY, target_formality=1, feels_c=18, temp_min_c=12)
    best = engine.suggest(closet(), ctx, RULES, k=1)[0]
    assert {1, 3} <= ids(best)


def test_cold_day_adds_coat_and_hot_day_does_not():
    cold = engine.suggest(closet(), Context(day=DAY, target_formality=4, feels_c=2, temp_min_c=-3), RULES, k=1)[0]
    hot = engine.suggest(closet(), Context(day=DAY, target_formality=4, feels_c=30, temp_min_c=22), RULES, k=1)[0]
    assert 7 in ids(cold)
    assert 7 not in ids(hot)


def test_suggestions_are_varied():
    ctx = Context(day=DAY, target_formality=2)
    out = engine.suggest(closet(), ctx, RULES, k=3)
    cores = [frozenset(p.id for p in s.pieces if p.category in {"top", "bottom"}) for s in out]
    seen = set()
    for c in cores:
        assert not (c & seen)
        seen |= c


def test_recently_worn_items_rank_lower():
    pieces = [
        Piece(1, "black tee", "top", "black", last_worn=DAY),
        Piece(2, "white tee", "top", "white"),
        Piece(3, "jeans", "bottom", "blue"),
    ]
    best = engine.suggest(pieces, Context(day=DAY), RULES, k=1)[0]
    assert 2 in ids(best)


def test_dress_only_closet_works():
    out = engine.suggest([Piece(1, "black dress", "dress", "black", formality=3)], Context(day=DAY, target_formality=3), RULES)
    assert len(out) == 1


def test_unlock_ranking_recommends_missing_category():
    tops = [Piece(i, f"top {i}", "top", c, formality=2) for i, c in enumerate(["white", "black", "grey", "navy"], 1)]
    ranking = engine.unlock_ranking(tops, RULES)
    assert ranking[0]["category"] == "bottom"
    assert ranking[0]["new_outfits"] == 4
    assert len({(r["category"], r["color"]) for r in ranking}) == len(ranking)


def test_learned_pairings_override_rules():
    learned = PairingModel(pairs={"bottom|red::top|pink": 3.0})
    assert learned.score("top", "pink", "bottom", "red") > RULES.score("top", "pink", "bottom", "red")
    assert learned.score("bottom", "red", "top", "pink") == learned.score("top", "pink", "bottom", "red")
