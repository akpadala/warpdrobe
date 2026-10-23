import logging
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import calendar_feed, engine, weather
from ..auth import current_user
from ..db import get_db
from ..models import Item, Outfit, User, Wear
from ..pairings import get_model
from ..schemas import OutfitIn, OutfitOut, OutfitPatch
from .items import item_out, wear_stats

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["plan"])


def to_pieces(items: list[Item], stats: dict) -> list[engine.Piece]:
    return [
        engine.Piece(id=i.id, name=i.name, category=i.category, color=i.color, formality=i.formality,
                     warmth=i.warmth, seasons=tuple(i.seasons or ()), last_worn=stats.get(i.id, (0, None))[1])
        for i in items
    ]


def day_context(user: User, day: date) -> tuple[engine.Context, dict | None, list[dict], list[str]]:
    """Weather + calendar for one day. Failures become warnings, never errors."""
    warnings: list[str] = []
    ctx = engine.Context(day=day)
    wx = None
    if user.latitude is not None and user.longitude is not None:
        try:
            dw = weather.forecast(user.latitude, user.longitude).get(day)
            if dw:
                ctx.feels_c, ctx.temp_min_c, ctx.precip_chance = dw.feels_c, dw.temp_min_c, dw.precip_chance
                wx = dw.as_dict()
            else:
                warnings.append("No forecast that far out yet.")
        except Exception as exc:
            log.warning("weather failed for (%s, %s): %r", user.latitude, user.longitude, exc)
            warnings.append("Weather is unavailable right now.")
    else:
        warnings.append("Add your city in Settings to plan around the weather.")

    events: list[dict] = []
    if user.ics_url:
        try:
            evs = calendar_feed.events_on(calendar_feed.fetch_ics(user.ics_url), day)
            events = [e.as_dict() for e in evs]
            if evs:
                top = max(evs, key=lambda e: e.formality)
                ctx.target_formality, ctx.occasion = top.formality, top.title
        except Exception as exc:
            log.warning("calendar failed: %r", exc)
            warnings.append("Couldn't read your calendar right now.")
    else:
        warnings.append("Connect your calendar in Settings to dress for your events.")
    return ctx, wx, events, warnings


@router.get("/plan")
def plan(
    day: date | None = None,
    formality: int | None = Query(default=None, ge=1, le=5, description="Override the dress code"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    day = day or date.today()
    ctx, wx, events, warnings = day_context(user, day)
    if formality is not None:
        ctx.target_formality, ctx.occasion = formality, None
    items = db.scalars(select(Item).where(Item.user_id == user.id)).all()
    stats = wear_stats(db, [i.id for i in items])
    by_id = {i.id: i for i in items}
    suggestions = engine.suggest(to_pieces(items, stats), ctx, get_model(), k=3)
    if not suggestions:
        warnings.append("Add at least one top and one bottom (or a dress) to get outfits.")
    return {
        "date": day.isoformat(),
        "weather": wx,
        "events": events,
        "target_formality": ctx.target_formality,
        "occasion": ctx.occasion,
        "warnings": warnings,
        "suggestions": [
            {
                "rank": rank,
                "score": s.score,
                "parts": s.parts,
                "reasons": s.reasons,
                "items": [item_out(by_id[p.id], stats.get(p.id, (0, None))) for p in s.pieces],
            }
            for rank, s in enumerate(suggestions, start=1)
        ],
    }


@router.get("/week")
def week(user: User = Depends(current_user)):
    out = []
    for day in calendar_feed.upcoming_window(date.today(), 7):
        ctx, wx, events, _ = day_context(user, day)
        out.append({"date": day.isoformat(), "weather": wx, "events": events,
                    "target_formality": ctx.target_formality, "occasion": ctx.occasion})
    return out


def outfit_out(o: Outfit) -> OutfitOut:
    return OutfitOut(id=o.id, for_date=o.for_date, item_ids=o.item_ids, occasion=o.occasion,
                     engine_score=o.engine_score, rank=o.rank, rating=o.rating, worn=o.worn)


def _record_wears(db: Session, outfit: Outfit) -> None:
    existing = set(db.scalars(select(Wear.item_id).where(
        Wear.item_id.in_(outfit.item_ids), Wear.worn_on == outfit.for_date)))
    for item_id in outfit.item_ids:
        if item_id not in existing:
            db.add(Wear(item_id=item_id, worn_on=outfit.for_date, outfit_id=outfit.id))


@router.post("/outfits", response_model=OutfitOut)
def save_outfit(body: OutfitIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned = set(db.scalars(select(Item.id).where(Item.user_id == user.id, Item.id.in_(body.item_ids))))
    if owned != set(body.item_ids):
        raise HTTPException(404, "Some of those items aren't in your closet")
    outfit = Outfit(user_id=user.id, **body.model_dump())
    db.add(outfit)
    db.flush()
    if outfit.worn:
        _record_wears(db, outfit)
    db.commit()
    return outfit_out(outfit)


@router.patch("/outfits/{outfit_id}", response_model=OutfitOut)
def update_outfit(outfit_id: int, body: OutfitPatch, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    outfit = db.get(Outfit, outfit_id)
    if outfit is None or outfit.user_id != user.id:
        raise HTTPException(404, "Outfit not found")
    if body.rating is not None:
        outfit.rating = body.rating
    if body.worn and not outfit.worn:
        outfit.worn = True
        _record_wears(db, outfit)
    db.commit()
    return outfit_out(outfit)


@router.get("/outfits", response_model=list[OutfitOut])
def list_outfits(days: int = Query(default=30, ge=1, le=365), user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    since = date.today() - timedelta(days=days)
    rows = db.scalars(select(Outfit).where(Outfit.user_id == user.id, Outfit.for_date >= since)
                      .order_by(Outfit.for_date.desc(), Outfit.id.desc())).all()
    return [outfit_out(o) for o in rows]
