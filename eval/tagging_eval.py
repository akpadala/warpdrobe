"""Measure photo-tagging accuracy against hand labels.

1. Put photos in a folder (your closet, friends' closets; aim for ~200).
2. Write labels.csv with columns: filename,category,color,formality
   (category/color must use the values in backend/app/taxonomy.py; formality 1-5).
   `--template` writes a starter CSV listing every photo in the folder.
3. Run with GEMINI_API_KEY set (in .env at the repo root):
   backend/.venv/bin/python eval/tagging_eval.py --images ~/closet-photos --labels ~/closet-photos/labels.csv

Writes per-photo predictions next to the labels (predictions.csv) so you can look at the misses.
"""

import argparse
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app import tagger  # noqa: E402
from app.config import get_settings  # noqa: E402

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


def score(rows: list[dict]) -> dict:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    res = {"n": n}
    for field in ("category", "color", "formality"):
        res[f"{field}_acc"] = round(sum(r[field] == r[f"pred_{field}"] for r in rows) / n, 3)
    res["formality_within_1"] = round(sum(abs(int(r["formality"]) - int(r["pred_formality"])) <= 1
                                          for r in rows) / n, 3)
    res["all_three_correct"] = round(sum(
        r["category"] == r["pred_category"] and r["color"] == r["pred_color"]
        and abs(int(r["formality"]) - int(r["pred_formality"])) <= 1 for r in rows) / n, 3)
    res["category_confusions"] = Counter(
        f"{r['category']}->{r['pred_category']}" for r in rows if r["category"] != r["pred_category"]
    ).most_common(5)
    res["color_confusions"] = Counter(
        f"{r['color']}->{r['pred_color']}" for r in rows if r["color"] != r["pred_color"]
    ).most_common(5)
    return res


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--images", type=Path, required=True)
    p.add_argument("--labels", type=Path)
    p.add_argument("--template", action="store_true", help="write labels.csv listing every photo, then stop")
    args = p.parse_args()
    images = args.images.expanduser()

    if args.template:
        out = images / "labels.csv"
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["filename", "category", "color", "formality"])
            for img in sorted(x for x in images.iterdir() if x.suffix.lower() in IMAGE_EXT):
                w.writerow([img.name, "", "", ""])
        print(f"Wrote {out}. Fill in the blanks, then rerun with --labels {out}")
        return

    if not get_settings().gemini_api_key:
        sys.exit("GEMINI_API_KEY is not set (put it in .env at the repo root).")
    labels = list(csv.DictReader(open(args.labels.expanduser())))
    rows = []
    for i, lab in enumerate(labels, 1):
        if not lab.get("category"):
            continue
        jpeg = tagger.prepare_image((images / lab["filename"]).read_bytes())
        for attempt in range(3):
            try:
                t = tagger.gemini_tags(jpeg)
                break
            except Exception as exc:  # rate limits on the free tier
                if attempt == 2:
                    raise
                print(f"  retrying {lab['filename']}: {exc}")
                time.sleep(5 * (attempt + 1))
        rows.append({**lab, "pred_category": t.category, "pred_color": t.color,
                     "pred_formality": str(t.formality), "pred_name": t.name})
        print(f"[{i}/{len(labels)}] {lab['filename']}: {t.category}/{t.color}/{t.formality}")

    out = args.labels.expanduser().with_name("predictions.csv")
    if rows:
        with open(out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(json.dumps(score(rows), indent=2))
    print(f"Per-photo predictions: {out}")


if __name__ == "__main__":
    main()
