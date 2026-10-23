import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eval"))

import outfit_eval  # noqa: E402
import tagging_eval  # noqa: E402
from app.pairings import PairingModel  # noqa: E402


def test_outfit_eval_rewards_model_that_knows_real_pairs():
    real = [["bottom|blue", "top|white"]] * 30 + [["bottom|black", "top|black"]] * 30
    learned = PairingModel(pairs={"bottom|blue::top|white": 4.0, "bottom|black::top|black": 4.0,
                                  "bottom|black::top|white": 0.3, "bottom|blue::top|black": 0.3})
    res = outfit_eval.evaluate(real, {"learned": learned, "rules": PairingModel()})
    assert res["baskets"] > 0
    # Some fakes recombine into the other real outfit (a tie), so not a perfect 1.0.
    assert res["learned"] >= 0.7
    assert res["learned"] > res["rules"]


def test_tagging_score():
    rows = [
        {"category": "top", "color": "navy", "formality": "4", "pred_category": "top", "pred_color": "navy", "pred_formality": "3"},
        {"category": "shoes", "color": "white", "formality": "2", "pred_category": "shoes", "pred_color": "grey", "pred_formality": "2"},
    ]
    s = tagging_eval.score(rows)
    assert s["category_acc"] == 1.0 and s["color_acc"] == 0.5
    assert s["formality_acc"] == 0.5 and s["formality_within_1"] == 1.0
    assert s["color_confusions"] == [("white->grey", 1)]
