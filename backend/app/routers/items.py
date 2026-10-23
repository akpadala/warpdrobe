from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from PIL import UnidentifiedImageError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import tagger
from ..auth import current_user
from ..db import get_db
from ..models import Item, ItemImage, User, Wear, new_key
from ..schemas import ItemIn, ItemOut

router = APIRouter(prefix="/api", tags=["items"])

MAX_UPLOAD = 15 * 1024 * 1024


def wear_stats(db: Session, item_ids: list[int]) -> dict[int, tuple[int, date | None]]:
    if not item_ids:
        return {}
    rows = db.execute(
        select(Wear.item_id, func.count(), func.max(Wear.worn_on))
        .where(Wear.item_id.in_(item_ids)).group_by(Wear.item_id)
    ).all()
    return {r[0]: (r[1], r[2]) for r in rows}


def item_out(item: Item, stats: tuple[int, date | None] = (0, None)) -> ItemOut:
    count, last = stats
    return ItemOut(
        id=item.id, name=item.name, category=item.category, color=item.color,
        secondary_color=item.secondary_color, pattern=item.pattern, formality=item.formality,
        warmth=item.warmth, seasons=item.seasons or [], price=item.price,
        purchased_on=item.purchased_on, tag_source=item.tag_source,
        image_url=f"/api/images/{item.image_key}" if item.image_key else None,
        wear_count=count, last_worn=last,
        cost_per_wear=round(item.price / max(count, 1), 2) if item.price is not None else None,
    )


def get_own_item(db: Session, user: User, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(404, "Item not found")
    return item


@router.get("/items", response_model=list[ItemOut])
def list_items(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = db.scalars(select(Item).where(Item.user_id == user.id).order_by(Item.created_at.desc())).all()
    stats = wear_stats(db, [i.id for i in items])
    return [item_out(i, stats.get(i.id, (0, None))) for i in items]


@router.post("/items", response_model=ItemOut)
async def upload_item(
    photo: UploadFile = File(...),
    price: float | None = Form(default=None),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    raw = await photo.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "Photo is too large (max 15 MB)")
    try:
        jpeg = tagger.prepare_image(raw)
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(400, "That file isn't a photo we can read (try JPEG or PNG)") from exc
    tags = await run_in_threadpool(tagger.tag_image, jpeg)
    item = Item(
        user_id=user.id, name=tags.name, category=tags.category, color=tags.color,
        secondary_color=tags.secondary_color, pattern=tags.pattern, formality=tags.formality,
        warmth=tags.warmth, seasons=tags.seasons, price=price, tag_source=tags.source,
        ai_tags=tags.as_dict(), image_key=new_key(),
    )
    item.image = ItemImage(data=jpeg)
    db.add(item)
    db.commit()
    return item_out(item)


@router.post("/items/manual", response_model=ItemOut)
def create_manual(body: ItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not body.category or not body.color:
        raise HTTPException(422, "category and color are required")
    item = Item(user_id=user.id, name=body.name or f"{body.color} {body.category}", tag_source="user",
                reviewed=True, **body.model_dump(exclude={"name"}, exclude_none=True))
    db.add(item)
    db.commit()
    return item_out(item)


@router.patch("/items/{item_id}", response_model=ItemOut)
def update_item(item_id: int, body: ItemIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    item = get_own_item(db, user, item_id)
    changes = body.model_dump(exclude_unset=True)
    tag_fields = {"category", "color", "formality", "warmth", "seasons", "pattern", "secondary_color"}
    for key, value in changes.items():
        setattr(item, key, value)
    if any(k in tag_fields and changes[k] != (item.ai_tags or {}).get(k) for k in changes):
        item.tag_source = "user"
    item.reviewed = True
    db.commit()
    return item_out(item, wear_stats(db, [item.id]).get(item.id, (0, None)))


@router.delete("/items/{item_id}")
def delete_item(item_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(get_own_item(db, user, item_id))
    db.commit()
    return {"ok": True}


@router.post("/items/{item_id}/wear", response_model=ItemOut)
def log_wear(item_id: int, on: date | None = None, user: User = Depends(current_user),
             db: Session = Depends(get_db)):
    item = get_own_item(db, user, item_id)
    day = on or date.today()
    if not db.scalar(select(Wear).where(Wear.item_id == item.id, Wear.worn_on == day)):
        db.add(Wear(item_id=item.id, worn_on=day))
        db.commit()
    return item_out(item, wear_stats(db, [item.id]).get(item.id, (0, None)))


@router.get("/images/{key}")
def get_image(key: str, db: Session = Depends(get_db)):
    # Keys are random 128-bit ids, so <img src> works without an auth header.
    item = db.scalar(select(Item).where(Item.image_key == key))
    if item is None or item.image is None:
        raise HTTPException(404, "Not found")
    return Response(item.image.data, media_type=item.image.content_type,
                    headers={"Cache-Control": "private, max-age=86400"})
