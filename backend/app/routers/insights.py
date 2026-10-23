from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import engine
from ..auth import current_user
from ..config import get_settings
from ..db import get_db
from ..models import Item, Outfit, User, Wear
from ..pairings import get_model
from .items import item_out, wear_stats
from .plan import to_pieces

router = APIRouter(prefix="/api", tags=["insights"])

UNWORN_GRACE_DAYS = 21   # new items get three weeks before we nag
STALE_DAYS = 90          # not worn in a season -> resale candidate


def _as_date(dt: datetime) -> date:
    return dt.date() if isinstance(dt, datetime) else dt


@router.get("/insights")
def insights(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Item).where(Item.user_id == user.id)).all()
    stats = wear_stats(db, [i.id for i in items])
    outs = [item_out(i, stats.get(i.id, (0, None))) for i in items]
    today = date.today()

    priced = [o for o in outs if o.price is not None]
    cost_per_wear = sorted(priced, key=lambda o: o.cost_per_wear or 0, reverse=True)

    resell = []
    for item, o in zip(items, outs):
        age = (today - _as_date(item.created_at)).days
        if o.wear_count == 0 and age >= UNWORN_GRACE_DAYS:
            resell.append({"item": o, "why": f"Never worn in {age} days"})
        elif o.last_worn and (today - o.last_worn).days >= STALE_DAYS:
            resell.append({"item": o, "why": f"Last worn {(today - o.last_worn).days} days ago"})

    pieces = to_pieces(items, stats)
    model = get_model()
    total_wears = sum(o.wear_count for o in outs)
    return {
        "totals": {
            "items": len(items),
            "closet_value": round(sum(o.price for o in priced), 2),
            "wears_logged": total_wears,
            # Mean of per-item cost per wear (an unworn item counts at full price).
            "avg_cost_per_wear": round(sum(o.cost_per_wear for o in priced) / len(priced), 2) if priced else None,
            "outfit_combos": len(engine.good_bases(pieces, model)),
        },
        "cost_per_wear": cost_per_wear,
        "never_worn": [o for o in outs if o.wear_count == 0],
        "resell": resell,
        "next_buys": engine.unlock_ranking(pieces, model),
        "pairing_source": model.meta.get("source", "rules"),
    }


@router.get("/admin/metrics")
def metrics(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Usage numbers for the README/resume. Only for emails in ADMIN_EMAILS."""
    if user.email not in get_settings().admin_email_set:
        raise HTTPException(403, "Admins only")
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    users = db.scalar(select(func.count(User.id)))
    active = db.scalar(select(func.count(User.id)).where(User.last_seen_at >= week_ago))
    with_items = db.scalar(select(func.count(func.distinct(Item.user_id))))
    rated = db.execute(select(func.count(Outfit.id), func.avg(Outfit.rating)).where(Outfit.rating.is_not(None))).one()
    top1 = db.execute(select(func.count(Outfit.id), func.avg(Outfit.rating))
                      .where(Outfit.rating.is_not(None), Outfit.rank == 1)).one()

    # Real-world tagging accuracy: AI tags vs. what users kept after reviewing.
    reviewed = db.scalars(select(Item).where(Item.reviewed.is_(True), Item.ai_tags.is_not(None))).all()
    reviewed = [i for i in reviewed if (i.ai_tags or {}).get("source") == "gemini"]
    acc = {}
    for field in ("category", "color", "formality", "warmth"):
        if reviewed:
            acc[field] = round(sum(1 for i in reviewed if i.ai_tags.get(field) == getattr(i, field)) / len(reviewed), 3)
    if reviewed:
        acc["formality_within_1"] = round(
            sum(1 for i in reviewed if abs(i.ai_tags.get("formality", 0) - i.formality) <= 1) / len(reviewed), 3)

    return {
        "users": users,
        "active_7d": active,
        "users_with_items": with_items,
        "items": db.scalar(select(func.count(Item.id))),
        "wears": db.scalar(select(func.count(Wear.id))),
        "outfits_worn": db.scalar(select(func.count(Outfit.id)).where(Outfit.worn.is_(True))),
        "ratings": rated[0],
        "avg_rating": round(float(rated[1]), 2) if rated[1] is not None else None,
        "top_pick_ratings": top1[0],
        "top_pick_avg_rating": round(float(top1[1]), 2) if top1[1] is not None else None,
        "tagging_reviewed_items": len(reviewed),
        "tagging_accuracy": acc,
    }
