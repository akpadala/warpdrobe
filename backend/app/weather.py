"""Daily forecast from Open-Meteo (free, no API key)."""

import time
from dataclasses import asdict, dataclass
from datetime import date

import httpx

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# WMO weather codes -> short text.
_CODES = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "cloudy", 45: "fog", 48: "fog",
    51: "drizzle", 53: "drizzle", 55: "drizzle", 61: "rain", 63: "rain", 65: "heavy rain",
    71: "snow", 73: "snow", 75: "heavy snow", 80: "showers", 81: "showers", 82: "heavy showers",
    95: "thunderstorms", 96: "thunderstorms", 99: "thunderstorms",
}

_cache: dict[tuple, tuple[float, dict]] = {}
_TTL = 30 * 60


@dataclass
class DayWeather:
    date: date
    temp_max_c: float
    temp_min_c: float
    precip_chance: int
    summary: str

    @property
    def feels_c(self) -> float:
        # Weighted toward the high: you are out during the day.
        return 0.6 * self.temp_max_c + 0.4 * self.temp_min_c

    def as_dict(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        return d


def parse_forecast(payload: dict) -> dict[date, DayWeather]:
    daily = payload["daily"]
    n = len(daily["time"])

    def col(name: str) -> list:
        return daily.get(name) or [None] * n

    out = {}
    for i, day in enumerate(daily["time"]):
        hi, lo = col("temperature_2m_max")[i], col("temperature_2m_min")[i]
        if hi is None or lo is None:
            # The far end of the forecast window is sometimes empty; skip it rather than fail.
            continue
        d = date.fromisoformat(day)
        code = col("weather_code")[i]
        out[d] = DayWeather(
            date=d,
            temp_max_c=float(hi),
            temp_min_c=float(lo),
            precip_chance=int(col("precipitation_probability_max")[i] or 0),
            summary=_CODES.get(int(code), "mixed") if code is not None else "mixed",
        )
    return out


def forecast(lat: float, lon: float, client: httpx.Client | None = None) -> dict[date, DayWeather]:
    key = (round(lat, 2), round(lon, 2))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _TTL:
        return hit[1]
    params = {
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": 8,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
    }
    own = client is None
    client = client or httpx.Client(timeout=15)
    try:
        resp = client.get(FORECAST_URL, params=params)
        resp.raise_for_status()
        days = parse_forecast(resp.json())
    finally:
        if own:
            client.close()
    _cache[key] = (time.time(), days)
    return days


def geocode(query: str, client: httpx.Client | None = None) -> dict | None:
    own = client is None
    client = client or httpx.Client(timeout=15)
    try:
        resp = client.get(GEOCODE_URL, params={"name": query, "count": 1, "language": "en"})
        resp.raise_for_status()
        results = resp.json().get("results") or []
    finally:
        if own:
            client.close()
    if not results:
        return None
    r = results[0]
    label = ", ".join(p for p in (r.get("name"), r.get("admin1"), r.get("country_code")) if p)
    return {"latitude": r["latitude"], "longitude": r["longitude"], "name": label}
