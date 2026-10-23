"""Write tiny H&M-shaped CSVs for tests and for trying the job without the Kaggle download.

The numbers are synthetic and only exercise the pipeline; real pairings come from the Kaggle data.
"""

import argparse
import csv
import random
from pathlib import Path

ARTICLE_COLS = ["article_id", "product_type_name", "product_group_name", "graphical_appearance_name",
                "colour_group_name", "perceived_colour_master_name", "index_group_name"]

ARTICLES = [
    # id, type, group, appearance, colour_group, master, index
    (1, "T-shirt", "Garment Upper body", "Solid", "White", "White", "Ladieswear"),
    (2, "Sweater", "Garment Upper body", "Solid", "Black", "Black", "Ladieswear"),
    (3, "Trousers", "Garment Lower body", "Denim", "Blue", "Blue", "Ladieswear"),
    (4, "Trousers", "Garment Lower body", "Solid", "Dark Blue", "Blue", "Menswear"),
    (5, "Skirt", "Garment Lower body", "Solid", "Black", "Black", "Divided"),
    (6, "Sneakers", "Shoes", "Solid", "White", "White", "Ladieswear"),
    (7, "Coat", "Garment Upper body", "Solid", "Beige", "Beige", "Ladieswear"),
    (8, "Dress", "Garment Full body", "All over pattern", "Red", "Red", "Ladieswear"),
    (9, "Bra", "Underwear", "Solid", "Black", "Black", "Ladieswear"),
    (10, "T-shirt", "Garment Upper body", "Solid", "Pink", "Pink", "Baby/Children"),
    (11, "Shirt", "Garment Upper body", "Stripe", "Light Pink", "Pink", "Ladieswear"),
    (12, "Trousers", "Garment Lower body", "Solid", "Red", "Red", "Ladieswear"),
]

# Baskets with a strong signal: white tee + jeans + sneakers, black sweater + black skirt.
PATTERNS = [([1, 3, 6], 6), ([2, 5], 5), ([1, 3], 3), ([7, 4], 3), ([8, 6], 2), ([11, 12], 1),
            ([1], 4), ([9, 2], 2), ([10, 3], 2), ([1, 1, 2], 1)]


def write(out: Path, customers: int = 400, seed: int = 7) -> Path:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "articles.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(ARTICLE_COLS)
        w.writerows(ARTICLES)
    weights = [wt for _, wt in PATTERNS]
    with open(out / "transactions_train.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t_dat", "customer_id", "article_id", "price", "sales_channel_id"])
        for c in range(customers):
            for d in range(rng.randint(1, 3)):
                basket, _ = rng.choices(PATTERNS, weights)[0]
                for a in basket:
                    w.writerow([f"2020-0{d + 1}-1{c % 9}", f"cust{c:05d}", f"{a:010d}", "0.03", 2])
    return out


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("sample-data"))
    print("Wrote", write(p.parse_args().out))
