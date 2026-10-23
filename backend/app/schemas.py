from datetime import date

from pydantic import BaseModel, Field, field_validator

from .taxonomy import CATEGORIES, COLORS, SEASONS


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("Enter a valid email")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


class SettingsIn(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    ics_url: str | None = None  # "" clears it
    location_query: str | None = None  # city name, geocoded server-side
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class MeOut(BaseModel):
    id: int
    email: str
    name: str
    has_calendar: bool
    location_name: str | None
    latitude: float | None
    longitude: float | None
    is_admin: bool


class AuthOut(BaseModel):
    token: str
    user: MeOut


class ItemIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    category: str | None = None
    color: str | None = None
    secondary_color: str | None = None
    pattern: str | None = None
    formality: int | None = Field(default=None, ge=1, le=5)
    warmth: int | None = Field(default=None, ge=1, le=5)
    seasons: list[str] | None = None
    price: float | None = Field(default=None, ge=0, le=100000)
    purchased_on: date | None = None

    @field_validator("category")
    @classmethod
    def _cat(cls, v):
        if v is not None and v not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}")
        return v

    @field_validator("color", "secondary_color")
    @classmethod
    def _color(cls, v):
        if v is not None and v not in COLORS:
            raise ValueError(f"color must be one of {COLORS}")
        return v

    @field_validator("seasons")
    @classmethod
    def _seasons(cls, v):
        if v is not None and any(s not in SEASONS for s in v):
            raise ValueError(f"seasons must be from {SEASONS}")
        return v


class ItemOut(BaseModel):
    id: int
    name: str
    category: str
    color: str
    secondary_color: str | None
    pattern: str
    formality: int
    warmth: int
    seasons: list[str]
    price: float | None
    purchased_on: date | None
    tag_source: str
    image_url: str | None
    wear_count: int
    last_worn: date | None
    cost_per_wear: float | None


class OutfitIn(BaseModel):
    for_date: date
    item_ids: list[int] = Field(min_length=1, max_length=8)
    occasion: str | None = Field(default=None, max_length=200)
    engine_score: float | None = None
    rank: int | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    worn: bool = False


class OutfitPatch(BaseModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    worn: bool | None = None


class OutfitOut(BaseModel):
    id: int
    for_date: date
    item_ids: list[int]
    occasion: str | None
    engine_score: float | None
    rank: int | None
    rating: int | None
    worn: bool
