import json
from datetime import date

import httpx
import pytest

from app import calendar_feed, tagger, weather

ICS = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//test//EN
BEGIN:VEVENT
UID:1
DTSTART:20261027T140000Z
DTEND:20261027T150000Z
SUMMARY:Interview with Deloitte
END:VEVENT
BEGIN:VEVENT
UID:2
DTSTART:20261020T130000Z
DTEND:20261020T141500Z
RRULE:FREQ=WEEKLY;BYDAY=TU
SUMMARY:COMP 210 lecture
END:VEVENT
BEGIN:VEVENT
UID:3
DTSTART;VALUE=DATE:20261030
SUMMARY:Date night
END:VEVENT
END:VCALENDAR
"""


def test_events_include_recurring_and_classify():
    evs = calendar_feed.events_on(ICS, date(2026, 10, 27))
    titles = [e.title for e in evs]
    assert titles == ["COMP 210 lecture", "Interview with Deloitte"]
    assert max(evs, key=lambda e: e.formality).formality == 4


def test_all_day_event():
    (ev,) = calendar_feed.events_on(ICS, date(2026, 10, 30))
    assert ev.all_day and ev.dress_code == "going out"


@pytest.mark.parametrize("title,formality", [
    ("Gym", 1), ("Brunch w/ roommates", 3), ("Wedding - cousin", 5),
    ("Career fair", 4), ("Random thing", 2), ("Update resume", 2),
])
def test_classify(title, formality):
    assert calendar_feed.classify(title)[0] == formality


def test_ics_url_allowlist():
    ok = "webcal://calendar.google.com/calendar/ical/x%40gmail.com/private-abc/basic.ics"
    assert calendar_feed.normalize_ics_url(ok).startswith("https://calendar.google.com/")
    for bad in ["http://calendar.google.com/x.ics", "https://169.254.169.254/latest",
                "https://evilcalendar.google.com.attacker.io/x.ics"]:
        with pytest.raises(ValueError):
            calendar_feed.normalize_ics_url(bad)


def test_fetch_ics_with_mock():
    url = "https://calendar.google.com/calendar/ical/a/private-b/basic.ics"
    client = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text=ICS)))
    assert "VCALENDAR" in calendar_feed.fetch_ics(url, client)
    bad = httpx.Client(transport=httpx.MockTransport(lambda req: httpx.Response(200, text="<html>")))
    with pytest.raises(ValueError):
        calendar_feed.fetch_ics(url + "?2", bad)


FORECAST = {"daily": {
    "time": ["2026-10-27", "2026-10-28"],
    "temperature_2m_max": [21.0, 8.0], "temperature_2m_min": [11.0, -1.0],
    "precipitation_probability_max": [10, 80], "weather_code": [1, 63],
}}


def test_forecast_parse_and_cache():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json=FORECAST)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    days = weather.forecast(35.9, -79.05, client)
    weather.forecast(35.9, -79.05, client)
    assert len(calls) == 1
    d = days[date(2026, 10, 28)]
    assert d.summary == "rain" and d.precip_chance == 80
    assert round(d.feels_c, 1) == 4.4


def test_geocode():
    payload = {"results": [{"name": "Chapel Hill", "admin1": "North Carolina", "country_code": "US",
                            "latitude": 35.91, "longitude": -79.05}]}
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    assert weather.geocode("chapel hill", client)["name"] == "Chapel Hill, North Carolina, US"


def test_gemini_request_and_parse(monkeypatch):
    monkeypatch.setattr(tagger, "get_settings", lambda: type("S", (), {"gemini_api_key": "k", "gemini_model": "m"})())
    seen = {}

    def handler(req):
        seen["url"] = str(req.url)
        seen["key"] = req.headers["x-goog-api-key"]
        seen["body"] = json.loads(req.content)
        model_json = {"name": "olive cargo pants", "category": "bottom", "color": "olive", "pattern": "solid",
                      "formality": 7, "warmth": 3, "seasons": ["fall", "bogus"], "secondary_color": "none"}
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(model_json)}]}}]})

    tags = tagger.gemini_tags(b"\xff\xd8fake", httpx.Client(transport=httpx.MockTransport(handler)))
    assert seen["url"].endswith("/models/m:generateContent") and seen["key"] == "k"
    assert seen["body"]["generationConfig"]["responseMimeType"] == "application/json"
    assert (tags.category, tags.color, tags.formality, tags.seasons, tags.secondary_color) == \
        ("bottom", "green", 5, ["fall"], None)


def test_fallback_detects_dominant_color():
    from tests.conftest import photo
    jpeg = tagger.prepare_image(photo((200, 30, 40)))
    assert tagger.fallback_tags(jpeg).color == "red"
