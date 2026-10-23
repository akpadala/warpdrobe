from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import calendar_feed, weather
from ..auth import current_user, hash_password, issue_token, verify_password
from ..config import get_settings
from ..db import get_db
from ..models import AuthToken, User
from ..schemas import AuthOut, LoginIn, MeOut, RegisterIn, SettingsIn

router = APIRouter(prefix="/api", tags=["account"])


def me_out(user: User) -> MeOut:
    return MeOut(
        id=user.id, email=user.email, name=user.name, has_calendar=bool(user.ics_url),
        location_name=user.location_name, latitude=user.latitude, longitude=user.longitude,
        is_admin=user.email in get_settings().admin_email_set,
    )


@router.post("/auth/register", response_model=AuthOut)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "An account with that email already exists")
    user = User(email=body.email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    return AuthOut(token=issue_token(db, user), user=me_out(user))


@router.post("/auth/login", response_model=AuthOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password")
    return AuthOut(token=issue_token(db, user), user=me_out(user))


@router.post("/auth/logout")
def logout(request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    token = request.headers.get("authorization", "").split(" ", 1)[-1].strip()
    row = db.get(AuthToken, token)
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(current_user)):
    return me_out(user)


@router.patch("/me", response_model=MeOut)
def update_me(body: SettingsIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.name:
        user.name = body.name.strip()
    if body.ics_url is not None:
        if body.ics_url.strip() == "":
            user.ics_url = None
        else:
            try:
                text = calendar_feed.fetch_ics(body.ics_url)
                calendar_feed.icalendar.Calendar.from_ical(text)
            except Exception as exc:
                raise HTTPException(400, f"Couldn't read that calendar link: {exc}") from exc
            user.ics_url = calendar_feed.normalize_ics_url(body.ics_url)
    if body.location_query:
        try:
            place = weather.geocode(body.location_query)
        except Exception as exc:
            raise HTTPException(502, "Location lookup is unavailable right now") from exc
        if place is None:
            raise HTTPException(404, f"Couldn't find '{body.location_query}'")
        user.latitude, user.longitude, user.location_name = place["latitude"], place["longitude"], place["name"]
    elif body.latitude is not None and body.longitude is not None:
        user.latitude, user.longitude = body.latitude, body.longitude
        user.location_name = "Current location"
    db.commit()
    return me_out(user)
