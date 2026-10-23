"""Map H&M article metadata onto the app's vocabulary (backend/app/taxonomy.py)."""

from pyspark.sql import Column
from pyspark.sql import functions as F

OUTERWEAR_TYPES = ["Jacket", "Coat", "Blazer", "Outdoor Waistcoat"]
DRESS_TYPES = ["Dress", "Jumpsuit/Playsuit"]
BOTTOM_TYPES_IN_FULL_BODY = ["Dungarees"]
SHOE_GROUPS = ["Shoes"]
ACCESSORY_GROUPS = ["Accessories", "Bags"]
ACCESSORY_TYPES = ["Bag", "Belt", "Hat/beanie", "Cap/peaked", "Hat/brim", "Scarf", "Sunglasses",
                   "Earring", "Necklace", "Bracelet", "Ring", "Watch", "Earrings"]
# Parents shopping for kids would create fake "outfits" with their own clothes.
EXCLUDED_INDEX_GROUPS = ["Baby/Children"]

# perceived_colour_master_name -> app color
COLOR_MAP = {
    "Black": "black", "White": "white", "Grey": "grey", "Beige": "beige", "Brown": "brown",
    "Mole": "brown", "Yellowish Brown": "brown", "Red": "red", "Orange": "orange", "Yellow": "yellow",
    "Green": "green", "Khaki green": "green", "Yellowish Green": "green", "Bluish Green": "green",
    "Blue": "blue", "Turquoise": "blue", "Lilac Purple": "purple", "Pink": "pink", "Metal": "metallic",
}
MULTI_PATTERNS = ["All over pattern", "Check", "Colour blocking", "Other pattern", "Dot"]


def category_expr() -> Column:
    group, ptype, index = F.col("product_group_name"), F.col("product_type_name"), F.col("index_group_name")
    cat = (
        F.when(group == "Garment Upper body",
               F.when(ptype.isin(OUTERWEAR_TYPES), F.lit("outerwear")).otherwise(F.lit("top")))
        .when(group == "Garment Lower body", F.lit("bottom"))
        .when(group == "Garment Full body",
              F.when(ptype.isin(DRESS_TYPES), F.lit("dress"))
              .when(ptype.isin(BOTTOM_TYPES_IN_FULL_BODY), F.lit("bottom")))
        .when(group.isin(SHOE_GROUPS), F.lit("shoes"))
        .when(group.isin(ACCESSORY_GROUPS) & ptype.isin(ACCESSORY_TYPES), F.lit("accessory"))
    )
    return F.when(~index.isin(EXCLUDED_INDEX_GROUPS), cat)


def color_expr() -> Column:
    master = F.col("perceived_colour_master_name")
    mapping = F.create_map(*[F.lit(x) for kv in COLOR_MAP.items() for x in kv])
    base = (
        F.when(F.col("graphical_appearance_name").isin(MULTI_PATTERNS), F.lit("multi"))
        # H&M lumps navy into Blue; colour_group_name keeps "Dark Blue".
        .when((master == "Blue") & (F.col("colour_group_name") == "Dark Blue"), F.lit("navy"))
        .otherwise(mapping[master])
    )
    return base
