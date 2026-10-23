"""Reads a Google Calendar 'secret address in iCal format' and turns events into dress codes.

Using the private iCal link avoids Google OAuth app verification, which takes weeks.
"""

import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import httpx
import icalendar
import recurring_ical_events

# (pattern, formality 1-5, label). First match wins, so stricter codes come first.
_RULES: list[tuple[str, int, str]] = [
    (r"\b(gala|wedding|formal|banquet|black tie|ball)\b", 5, "formal"),
    (r"\b(interview|career fair|networking|presentation|pitch|conference|internship|office|"
     r"business|recruit|info session|coffee chat|client)\b", 4, "business"),
    (r"\b(date|dinner|brunch|party|birthday|concert|theat(er|re)|church|mixer|chapter|social)\b",
     3, "going out"),
    (r"\b(class|lecture|lab|study|office hours|recitation|meeting|club|errand|lunch)\b", 2, "casual"),
    (r"\b(gym|workout|run|yoga|pilates|practice|intramural|hike|climb|lift|swim)\b", 1, "active"),
]


@dataclass
class DressEvent:
    title: str
    start: datetime | None
    all_day: bool
    formality: int
    dress_code: str

    def as_dict(self) -> dict:
        return {
            "title": self.title,
            "start": self.start.isoformat() if self.start else None,
            "all_day": self.all_day,
            "formality": self.formality,
            "dress_code": self.dress_code,
        }


def classify(title: str) -> tuple[int, str]:
    text = title.lower()
    for pattern, formality, label in _RULES:
        if re.search(pattern, text):
            return formality, label
    return 2, "casual"


def events_on(ics_text: str, day: date) -> list[DressEvent]:
    cal = icalendar.Calendar.from_ical(ics_text)
    out = []
    for ev in recurring_ical_events.of(cal).at(day):
        title = str(ev.get("SUMMARY") or "").strip()
        if not title:
            continue
        start = ev.get("DTSTART").dt if ev.get("DTSTART") else None
        all_day = isinstance(start, date) and not isinstance(start, datetime)
        formality, label = classify(title)
        out.append(DressEvent(title, start if isinstance(start, datetime) else None, all_day, formality, label))
    out.sort(key=lambda e: (e.start is None, e.start.timestamp() if e.start else 0))
    return out


_cache: dict[str, tuple[float, str]] = {}
_TTL = 10 * 60


# The server fetches these URLs, so only allow known calendar hosts (no internal addresses).
ALLOWED_HOSTS = ("calendar.google.com", "outlook.office365.com", "outlook.live.com", ".icloud.com")


def normalize_ics_url(url: str) -> str:
    url = url.strip()
    if url.startswith("webcal://"):
        url = "https://" + url[len("webcal://") :]
    parsed = httpx.URL(url)
    host = parsed.host or ""
    if parsed.scheme != "https" or not any(
        host == h or (h.startswith(".") and host.endswith(h)) for h in ALLOWED_HOSTS
    ):
        raise ValueError("Use the calendar's https iCal link from Google, Outlook, or iCloud.")
    return url


def fetch_ics(url: str, client: httpx.Client | None = None) -> str:
    url = normalize_ics_url(url)
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    own = client is None
    client = client or httpx.Client(timeout=15)
    try:
        resp = client.get(url)
        resp.raise_for_status()
        text = resp.text
    finally:
        if own:
            client.close()
    if "BEGIN:VCALENDAR" not in text:
        raise ValueError("That link didn't return a calendar. Use the 'Secret address in iCal format'.")
    _cache[url] = (time.time(), text)
    return text


def upcoming_window(start: date, days: int = 7) -> list[date]:
    return [start + timedelta(days=i) for i in range(days)]
