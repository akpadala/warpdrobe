"""Does the outfit scorer prefer real outfits over random ones?

Uses held-out H&M baskets (bought after the training cutoff, see spark/pairings_job.py
--holdout-from). Each real basket is paired with a fake one where every piece is swapped for a random
piece of the same category, so the fake differs only in *which* pieces were combined. AUC is the
chance the scorer ranks the real basket above its fake. 0.5 = coin flip.

Run from the repo root with the backend environment:
  backend/.venv/bin/python eval/outfit_eval.py --pairings data/pairings.json --holdout data/holdout_baskets.json
"""

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.pairings import PairingModel  # noqa: E402


def parse(token: str) -> tuple[str, str]:
    cat, color = token.split("|")
    return cat, color


def basket_score(tokens: list[str], model: PairingModel) -> float:
    pieces = [parse(t) for t in tokens]
    pairs = [(a, b) for a, b in combinations(pieces, 2) if a[0] != b[0]]
    if not pairs:
        return 0.5
    return sum(model.score(a[0], a[1], b[0], b[1]) for a, b in pairs) / len(pairs)


def make_fake(tokens: list[str], pool: dict[str, list[str]], weights: dict[str, list[int]],
              rng: random.Random) -> list[str]:
    return [rng.choices(pool[parse(t)[0]], weights[parse(t)[0]])[0] for t in tokens]


def auc(real: list[float], fake: list[float]) -> float:
    """Paired AUC: fraction of (real, its fake) where real scores higher; ties count half."""
    wins = sum(1.0 if r > f else 0.5 if r == f else 0.0 for r, f in zip(real, fake))
    return wins / len(real)


def evaluate(baskets: list[list[str]], models: dict[str, PairingModel], seed: int = 0) -> dict:
    # Fakes draw from the same category marginals as the real data, so popularity alone can't win.
    counts: dict[str, Counter] = defaultdict(Counter)
    for b in baskets:
        for t in b:
            counts[parse(t)[0]][t] += 1
    pool = {c: list(cnt) for c, cnt in counts.items()}
    weights = {c: list(cnt.values()) for c, cnt in counts.items()}
    rng = random.Random(seed)
    fakes = [make_fake(b, pool, weights, rng) for b in baskets]
    # Drop pairs where the fake came out identical to the real one.
    kept = [(r, f) for r, f in zip(baskets, fakes) if sorted(r) != sorted(f)]
    out = {"baskets": len(kept)}
    for name, model in models.items():
        out[name] = round(auc([basket_score(r, model) for r, _ in kept],
                              [basket_score(f, model) for _, f in kept]), 4)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pairings", type=Path, default=Path("data/pairings.json"))
    p.add_argument("--holdout", type=Path, default=Path("data/holdout_baskets.json"))
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()
    baskets = json.loads(args.holdout.read_text())["baskets"]
    res = evaluate(baskets, {"learned_auc": PairingModel.load(args.pairings), "rules_only_auc": PairingModel()},
                   args.seed)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
