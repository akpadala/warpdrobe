import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON, Date, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_key() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Google Calendar "secret address in iCal format". Treated like a password.
    ics_url: Mapped[str | None] = mapped_column(Text, default=None)
    latitude: Mapped[float | None] = mapped_column(Float, default=None)
    longitude: Mapped[float | None] = mapped_column(Float, default=None)
    location_name: Mapped[str | None] = mapped_column(String(120), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)

    items: Mapped[list["Item"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class AuthToken(Base):
    __tablename__ = "auth_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(20))
    color: Mapped[str] = mapped_column(String(20))
    secondary_color: Mapped[str | None] = mapped_column(String(20), default=None)
    pattern: Mapped[str] = mapped_column(String(20), default="solid")
    formality: Mapped[int] = mapped_column(Integer, default=2)
    warmth: Mapped[int] = mapped_column(Integer, default=3)
    seasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    price: Mapped[float | None] = mapped_column(Float, default=None)
    purchased_on: Mapped[date | None] = mapped_column(Date, default=None)
    # "gemini" when tags came from the model, "fallback" from the offline tagger, "user" once edited.
    tag_source: Mapped[str] = mapped_column(String(20), default="user")
    # What the model originally said, kept so tagging accuracy can be measured against user fixes.
    ai_tags: Mapped[dict | None] = mapped_column(JSON, default=None)
    # Set once the user confirms or fixes the tags; reviewed items measure real-world accuracy.
    reviewed: Mapped[bool] = mapped_column(default=False)
    image_key: Mapped[str | None] = mapped_column(String(32), unique=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User] = relationship(back_populates="items")
    image: Mapped["ItemImage | None"] = relationship(cascade="all, delete-orphan", uselist=False)
    wears: Mapped[list["Wear"]] = relationship(cascade="all, delete-orphan")


class ItemImage(Base):
    # Photos live in the database so the app deploys without a persistent disk.
    __tablename__ = "item_images"

    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), primary_key=True)
    content_type: Mapped[str] = mapped_column(String(40), default="image/jpeg")
    data: Mapped[bytes] = mapped_column(LargeBinary)


class Outfit(Base):
    __tablename__ = "outfits"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    for_date: Mapped[date] = mapped_column(Date)
    item_ids: Mapped[list[int]] = mapped_column(JSON)
    occasion: Mapped[str | None] = mapped_column(String(200), default=None)
    engine_score: Mapped[float | None] = mapped_column(Float, default=None)
    rank: Mapped[int | None] = mapped_column(Integer, default=None)
    rating: Mapped[int | None] = mapped_column(Integer, default=None)  # 1..5
    worn: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Wear(Base):
    __tablename__ = "wears"
    __table_args__ = (UniqueConstraint("item_id", "worn_on"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    worn_on: Mapped[date] = mapped_column(Date)
    outfit_id: Mapped[int | None] = mapped_column(ForeignKey("outfits.id", ondelete="SET NULL"), default=None)
