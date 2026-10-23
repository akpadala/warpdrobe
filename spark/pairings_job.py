"""Learn which clothes go together from H&M purchase history.

Input (Kaggle "H&M Personalized Fashion Recommendations"):
  articles.csv            ~105k products with product type and colour
  transactions_train.csv  ~31.8M purchases (t_dat, customer_id, article_id, price, sales_channel_id)

Idea: items one customer buys on the same day are usually meant to be worn together. We map every
article to a Warpdrobe token "category|color" (e.g. "top|white"), build one basket per
(customer, day), and compute lift for every token pair:

    lift(a, b) = P(a and b in basket) / (P(a) * P(b))

lift > 1 means the pair is bought together more often than chance. The app reads the result from
data/pairings.json.

Usage:
  python pairings_job.py --data ~/Downloads/hm-data --out ../data/pairings.json
  python pairings_job.py --data ~/Downloads/hm-data --sample 0.1   # quick run on 10% of customers
  python pairings_job.py --data ~/Downloads/hm-data --holdout-from 2020-08-22   # for eval/outfit_eval.py
"""

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from category_map import category_expr, color_expr

MIN_PAIR_BASKETS = 50      # ignore pairs seen in fewer baskets (noise)
MAX_BASKET_TOKENS = 12     # very large baskets are bulk/haul orders, not outfits


def build_spark(app_name: str = "warpdrobe-pairings") -> SparkSession:
    spark = (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.shuffle.partitions", "64")
        .config("spark.driver.memory", "4g")
        .config("spark.ui.showConsoleProgress", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def article_tokens(articles: DataFrame) -> DataFrame:
    """article_id -> category, color, token. Drops underwear, swimwear, cosmetics, etc."""
    return (
        articles.select(
            F.col("article_id").cast("long").alias("article_id"),
            category_expr().alias("category"),
            color_expr().alias("color"),
        )
        .where(F.col("category").isNotNull() & F.col("color").isNotNull())
        .withColumn("token", F.concat_ws("|", "category", "color"))
    )


def baskets(transactions: DataFrame, tokens: DataFrame) -> DataFrame:
    """One row per (basket, distinct token)."""
    tx = transactions.select(
        F.col("customer_id"), F.col("t_dat"), F.col("article_id").cast("long").alias("article_id")
    )
    b = (
        tx.join(F.broadcast(tokens), "article_id")
        .select(F.xxhash64("customer_id", "t_dat").alias("basket"), "token", "category")
        .distinct()
    )
    # Keep baskets with at least two different categories (an outfit, not three of the same tee)
    # and not absurdly many items.
    stats = b.groupBy("basket").agg(
        F.countDistinct("category").alias("n_cat"), F.count("*").alias("n_tok")
    )
    keep = stats.where((F.col("n_cat") >= 2) & (F.col("n_tok") <= MAX_BASKET_TOKENS)).select("basket")
    return b.join(keep, "basket").select("basket", "token", "category")


def pair_lifts(b: DataFrame, min_baskets: int = MIN_PAIR_BASKETS) -> tuple[DataFrame, int]:
    n = b.select("basket").distinct().count()
    singles = b.groupBy("token").agg(F.count("*").alias("n_a"))
    left, right = b.alias("l"), b.alias("r")
    pairs = (
        left.join(right, (F.col("l.basket") == F.col("r.basket")) & (F.col("l.token") < F.col("r.token"))
                  # Two tops in one basket are alternatives, not an outfit.
                  & (F.col("l.category") != F.col("r.category")))
        .groupBy(F.col("l.token").alias("a"), F.col("r.token").alias("b"))
        .agg(F.count("*").alias("n_ab"))
        .where(F.col("n_ab") >= min_baskets)
    )
    sa, sb = singles.alias("sa"), singles.alias("sb")
    lifts = (
        pairs.join(sa, F.col("a") == F.col("sa.token"))
        .join(sb, F.col("b") == F.col("sb.token"))
        .select(
            "a", "b", "n_ab",
            (F.col("n_ab") * F.lit(n) / (F.col("sa.n_a") * F.col("sb.n_a"))).alias("lift"),
        )
    )
    return lifts, n


def color_lifts(lifts: DataFrame) -> DataFrame:
    """Collapse category: how well do two colors pair regardless of garment type."""
    return (
        lifts.select(
            F.split("a", r"\|").getItem(1).alias("c1"),
            F.split("b", r"\|").getItem(1).alias("c2"),
            "n_ab", "lift",
        )
        .select(F.least("c1", "c2").alias("c1"), F.greatest("c1", "c2").alias("c2"), "n_ab", "lift")
        .groupBy("c1", "c2")
        # Weighted by support so rare category combos don't dominate.
        .agg((F.sum(F.col("lift") * F.col("n_ab")) / F.sum("n_ab")).alias("lift"), F.sum("n_ab").alias("n_ab"))
    )


def export_holdout(test_baskets: DataFrame, path: Path, limit: int, seed: int = 42) -> int:
    """Write real held-out baskets (token lists) for eval/outfit_eval.py."""
    grouped = (
        test_baskets.groupBy("basket").agg(F.sort_array(F.collect_set("token")).alias("tokens"))
        .orderBy(F.xxhash64("basket", F.lit(seed))).limit(limit)
    )
    rows = [r["tokens"] for r in grouped.collect()]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"baskets": rows}))
    return len(rows)


def run(data_dir: Path, out_path: Path, sample: float | None = None, min_baskets: int = MIN_PAIR_BASKETS,
        spark: SparkSession | None = None, holdout_from: str | None = None,
        holdout_path: Path | None = None, holdout_limit: int = 20000) -> dict:
    spark = spark or build_spark()
    t0 = time.time()
    articles = spark.read.csv(str(data_dir / "articles.csv"), header=True)
    transactions = spark.read.csv(str(data_dir / "transactions_train.csv"), header=True)
    if sample:
        # Sample customers (not rows) so baskets stay whole.
        transactions = transactions.where((F.abs(F.xxhash64("customer_id")) % 1000) < int(sample * 1000))

    tokens = article_tokens(articles)
    n_holdout = None
    if holdout_from:
        # Learn from purchases before the date; evaluate on baskets from after it.
        test = baskets(transactions.where(F.col("t_dat") >= holdout_from), tokens)
        n_holdout = export_holdout(test, holdout_path or out_path.with_name("holdout_baskets.json"), holdout_limit)
        transactions = transactions.where(F.col("t_dat") < holdout_from)
    b = baskets(transactions, tokens).cache()
    lifts, n_baskets = pair_lifts(b, min_baskets)
    lifts = lifts.cache()
    colors = color_lifts(lifts)

    pair_rows = lifts.collect()
    color_rows = colors.collect()
    result = {
        "meta": {
            "source": "hm",
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "baskets": n_baskets,
            "pairs": len(pair_rows),
            "min_pair_baskets": min_baskets,
            "sample": sample,
            "holdout_from": holdout_from,
            "holdout_baskets": n_holdout,
            "seconds": round(time.time() - t0, 1),
        },
        "pairs": {f"{r['a']}::{r['b']}": round(float(r["lift"]), 4) for r in pair_rows},
        "color_pairs": {f"{r['c1']}::{r['c2']}": round(float(r["lift"]), 4) for r in color_rows},
        "support": {f"{r['a']}::{r['b']}": int(r["n_ab"]) for r in pair_rows},
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=1, sort_keys=True))
    b.unpersist()
    lifts.unpersist()
    return result


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, required=True, help="folder with articles.csv and transactions_train.csv")
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "pairings.json")
    p.add_argument("--sample", type=float, default=None, help="fraction of customers, e.g. 0.1")
    p.add_argument("--min-baskets", type=int, default=MIN_PAIR_BASKETS)
    p.add_argument("--holdout-from", default=None,
                   help="YYYY-MM-DD: train on earlier purchases, export later baskets for evaluation")
    args = p.parse_args()
    res = run(args.data.expanduser(), args.out, args.sample, args.min_baskets, holdout_from=args.holdout_from)
    m = res["meta"]
    print(f"Wrote {args.out}: {m['pairs']} pairs from {m['baskets']:,} baskets in {m['seconds']}s")
    top = sorted(res["pairs"].items(), key=lambda kv: -kv[1])[:10]
    for k, v in top:
        print(f"  lift {v:5.2f}  {k}  ({res['support'][k]:,} baskets)")


if __name__ == "__main__":
    main()
