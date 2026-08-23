"""weather-mcp (chat_spec.md §4.2). Separate process, no DB access — backed by Open-Meteo (no API
key needed) with a 30-minute in-memory TTL cache. Runs as its own always-on Railway service (not a
scale-to-zero function), so a plain module-level dict cache persists across calls within the
process exactly the way spec intends, no Redis required.

Field names below were verified against Open-Meteo's real response (both the forecast and
geocoding endpoints), not assumed from memory.
"""

from __future__ import annotations

import time

import httpx
from mcp.server.fastmcp import FastMCP

from app.core.config import get_settings
from app.mcp.common import to_jsonable

mcp = FastMCP(name="weather-mcp", instructions="Current conditions and forecast, with derived styling flags.")

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"

# WMO weather codes -> a short condition slug. Not exhaustive of every WMO code, just the bands
# that matter for "what should I wear" framing.
_WMO_CONDITIONS: dict[int, str] = {
    0: "clear",
    1: "mostly-clear",
    2: "partly-cloudy",
    3: "overcast",
    45: "fog",
    48: "fog",
    51: "light-drizzle",
    53: "drizzle",
    55: "heavy-drizzle",
    61: "light-rain",
    63: "rain",
    65: "heavy-rain",
    66: "freezing-rain",
    67: "freezing-rain",
    71: "light-snow",
    73: "snow",
    75: "heavy-snow",
    80: "rain-showers",
    81: "rain-showers",
    82: "violent-rain-showers",
    95: "thunderstorm",
    96: "thunderstorm-hail",
    99: "thunderstorm-hail",
}


def _condition(code: int) -> str:
    return _WMO_CONDITIONS.get(code, "unknown")


def _heat_band(feels_like_c: float) -> str:
    if feels_like_c < 18:
        return "cold"
    if feels_like_c < 24:
        return "cool"
    if feels_like_c < 30:
        return "mild"
    if feels_like_c < 40:
        return "hot"
    return "very-hot"


def _humidity_band(humidity_pct: float) -> str:
    if humidity_pct < 40:
        return "dry"
    if humidity_pct < 60:
        return "moderate"
    if humidity_pct < 75:
        return "humid"
    return "very-humid"


def _rain_risk(precip_prob_pct: float) -> str:
    if precip_prob_pct < 20:
        return "low"
    if precip_prob_pct < 50:
        return "moderate"
    if precip_prob_pct < 75:
        return "high"
    return "very-high"


def _uv_band(uv_index: float) -> str:
    if uv_index < 3:
        return "low"
    if uv_index < 6:
        return "moderate"
    if uv_index < 8:
        return "high"
    if uv_index < 11:
        return "very-high"
    return "extreme"


def _styling_flags(heat_band: str, humidity_band: str, rain_risk: str, uv_band: str) -> list[str]:
    flags: list[str] = []
    if heat_band in ("hot", "very-hot"):
        flags.append("breathable-fabrics")
    if humidity_band in ("humid", "very-humid"):
        flags.append("quick-dry")
    if uv_band in ("high", "very-high", "extreme"):
        flags.append("sun-protection")
    if rain_risk in ("high", "very-high"):
        flags.append("packable-rain-layer")
    if heat_band in ("hot", "very-hot") and humidity_band in ("humid", "very-humid"):
        flags.append("avoid-heavy-layers")
    return flags


# {cache_key: (fetched_at_epoch, response_dict)}
_cache: dict[tuple, tuple[float, dict]] = {}


async def _geocode(place: str) -> tuple[float, float, str, str | None] | None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(_GEOCODE_URL, params={"name": place, "count": 1})
        resp.raise_for_status()
        results = resp.json().get("results") or []
        if not results:
            return None
        return results[0]["latitude"], results[0]["longitude"], results[0]["name"], results[0].get("country_code")


@mcp.tool()
async def get_weather_forecast(
    lat: float | None = None,
    lon: float | None = None,
    place: str | None = None,
    days: int = 5,
) -> dict:
    """Current conditions and daily forecast for a location. Use the lat/lon returned by
    catalog-mcp's get_climate_profile when available; falls back to geocoding `place` otherwise.
    On any upstream failure, returns {"available": false, "reason": ...} rather than a guessed
    forecast — the caller must proceed on get_climate_profile alone and say so."""
    days = max(1, min(days, 10))
    settings = get_settings()
    label = place

    try:
        if lat is None or lon is None:
            if not place:
                return {"available": False, "reason": "Need either lat/lon or a place name."}
            geocoded = await _geocode(place)
            if geocoded is None:
                return {"available": False, "reason": f"Couldn't geocode '{place}'."}
            lat, lon, resolved_name, country_code = geocoded
            label = f"{resolved_name}, {country_code}" if country_code else resolved_name

        cache_key = (round(lat, 2), round(lon, 2), days)
        cached = _cache.get(cache_key)
        now = time.monotonic()
        if cached and (now - cached[0]) < settings.weather_cache_ttl_seconds:
            return cached[1]

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                _FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,apparent_temperature,uv_index,weather_code",
                    "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
                    "timezone": "auto",
                    "forecast_days": days,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        current = data["current"]
        daily = data["daily"]
        heat_band = _heat_band(current["apparent_temperature"])
        humidity_band = _humidity_band(current["relative_humidity_2m"])
        today_rain_risk = _rain_risk(daily["precipitation_probability_max"][0])
        uv_band = _uv_band(current["uv_index"])

        result = to_jsonable(
            {
                "available": True,
                "place": label or f"{lat},{lon}",
                "current": {
                    "temp_c": current["temperature_2m"],
                    "feels_like_c": current["apparent_temperature"],
                    "humidity": current["relative_humidity_2m"],
                    "uv_index": current["uv_index"],
                    "condition": _condition(current["weather_code"]),
                },
                "daily": [
                    {
                        "date": daily["time"][i],
                        "min_c": daily["temperature_2m_min"][i],
                        "max_c": daily["temperature_2m_max"][i],
                        "precip_prob": daily["precipitation_probability_max"][i],
                        "condition": _condition(daily["weather_code"][i]),
                    }
                    for i in range(len(daily["time"]))
                ],
                "derived": {
                    "heat_band": heat_band,
                    "humidity_band": humidity_band,
                    "rain_risk": today_rain_risk,
                    "uv_band": uv_band,
                    "styling_flags": _styling_flags(heat_band, humidity_band, today_rain_risk, uv_band),
                },
            }
        )
        _cache[cache_key] = (now, result)
        return result
    except httpx.HTTPError as exc:
        return {"available": False, "reason": f"Weather service unavailable: {exc}"}
