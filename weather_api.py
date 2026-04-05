"""Weather data fetching via Open-Meteo API (free, no API key needed)."""

from typing import Optional

import requests
from config import WEATHER_API_BASE, GEOCODING_API_BASE


# WMO Weather interpretation codes
WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Foggy", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snowfall", 73: "Moderate snowfall", 75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


def geocode(location_name: str) -> Optional[dict]:
    """Convert a location name to latitude/longitude using Open-Meteo Geocoding API.

    Returns dict with {name, latitude, longitude, country, admin1} or None.
    """
    # Try with more results to handle "Cambridge, MA" style queries
    resp = requests.get(f"{GEOCODING_API_BASE}/search", params={
        "name": location_name.split(",")[0].strip(),
        "count": 10,
        "language": "en",
        "format": "json",
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if not results:
        return None

    # If a region/state hint is provided (e.g. "Cambridge, MA"), try to match it
    parts = [p.strip() for p in location_name.split(",")]
    if len(parts) > 1:
        hint = parts[-1].lower()
        for r in results:
            admin = (r.get("admin1", "") or "").lower()
            country = (r.get("country", "") or "").lower()
            cc = (r.get("country_code", "") or "").lower()
            if hint in admin or hint in country or hint == cc:
                break
        else:
            r = results[0]  # fallback to top result
    else:
        r = results[0]
    return {
        "name": r.get("name", location_name),
        "latitude": r["latitude"],
        "longitude": r["longitude"],
        "country": r.get("country", ""),
        "admin1": r.get("admin1", ""),  # state/province
        "timezone": r.get("timezone", "auto"),
    }


def get_current_weather(lat: float, lon: float, timezone: str = "auto") -> dict:
    """Fetch current weather conditions for a coordinate pair.

    Returns dict with temperature, humidity, wind, conditions, etc.
    """
    resp = requests.get(f"{WEATHER_API_BASE}/forecast", params={
        "latitude": lat,
        "longitude": lon,
        "current": ",".join([
            "temperature_2m", "relative_humidity_2m", "apparent_temperature",
            "precipitation", "rain", "snowfall", "weather_code",
            "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
            "cloud_cover", "surface_pressure", "uv_index",
        ]),
        "timezone": timezone,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    current = data.get("current", {})

    weather_code = current.get("weather_code", 0)

    return {
        "temperature_c": current.get("temperature_2m"),
        "temperature_f": round(current.get("temperature_2m", 0) * 9 / 5 + 32, 1) if current.get("temperature_2m") is not None else None,
        "feels_like_c": current.get("apparent_temperature"),
        "feels_like_f": round(current.get("apparent_temperature", 0) * 9 / 5 + 32, 1) if current.get("apparent_temperature") is not None else None,
        "humidity_pct": current.get("relative_humidity_2m"),
        "precipitation_mm": current.get("precipitation"),
        "rain_mm": current.get("rain"),
        "snowfall_cm": current.get("snowfall"),
        "weather_code": weather_code,
        "weather_description": WMO_CODES.get(weather_code, "Unknown"),
        "wind_speed_kmh": current.get("wind_speed_10m"),
        "wind_direction_deg": current.get("wind_direction_10m"),
        "wind_gusts_kmh": current.get("wind_gusts_10m"),
        "cloud_cover_pct": current.get("cloud_cover"),
        "pressure_hpa": current.get("surface_pressure"),
        "uv_index": current.get("uv_index"),
        "observation_time": current.get("time"),
    }


def get_forecast(lat: float, lon: float, days: int = 7, timezone: str = "auto") -> dict:
    """Fetch multi-day forecast.

    Returns dict with daily forecast data including highs, lows, precip, etc.
    """
    resp = requests.get(f"{WEATHER_API_BASE}/forecast", params={
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join([
            "temperature_2m_max", "temperature_2m_min",
            "apparent_temperature_max", "apparent_temperature_min",
            "precipitation_sum", "rain_sum", "snowfall_sum",
            "precipitation_probability_max",
            "weather_code", "wind_speed_10m_max", "wind_gusts_10m_max",
            "uv_index_max", "sunrise", "sunset",
        ]),
        "timezone": timezone,
        "forecast_days": min(days, 16),
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    daily = data.get("daily", {})

    forecast_days = []
    dates = daily.get("time", [])
    for i, date in enumerate(dates):
        wcode = (daily.get("weather_code") or [0])[i] if i < len(daily.get("weather_code", [])) else 0
        forecast_days.append({
            "date": date,
            "high_c": daily.get("temperature_2m_max", [None])[i],
            "low_c": daily.get("temperature_2m_min", [None])[i],
            "high_f": round(daily["temperature_2m_max"][i] * 9 / 5 + 32, 1) if daily.get("temperature_2m_max") and daily["temperature_2m_max"][i] is not None else None,
            "low_f": round(daily["temperature_2m_min"][i] * 9 / 5 + 32, 1) if daily.get("temperature_2m_min") and daily["temperature_2m_min"][i] is not None else None,
            "precipitation_mm": (daily.get("precipitation_sum") or [0])[i],
            "precip_probability_pct": (daily.get("precipitation_probability_max") or [0])[i],
            "weather_code": wcode,
            "weather_description": WMO_CODES.get(wcode, "Unknown"),
            "wind_max_kmh": (daily.get("wind_speed_10m_max") or [0])[i],
            "wind_gust_max_kmh": (daily.get("wind_gusts_10m_max") or [0])[i],
            "uv_index_max": (daily.get("uv_index_max") or [0])[i],
            "sunrise": (daily.get("sunrise") or [""])[i],
            "sunset": (daily.get("sunset") or [""])[i],
        })

    return {"forecast": forecast_days}


def get_hourly_forecast(lat: float, lon: float, hours: int = 24, timezone: str = "auto") -> dict:
    """Fetch hourly forecast for the next N hours."""
    resp = requests.get(f"{WEATHER_API_BASE}/forecast", params={
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "temperature_2m", "relative_humidity_2m", "precipitation_probability",
            "precipitation", "weather_code", "wind_speed_10m",
            "cloud_cover", "uv_index",
        ]),
        "timezone": timezone,
        "forecast_hours": min(hours, 168),
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    hourly = data.get("hourly", {})

    hours_data = []
    times = hourly.get("time", [])
    for i, t in enumerate(times):
        wcode = (hourly.get("weather_code") or [0])[i] if i < len(hourly.get("weather_code", [])) else 0
        hours_data.append({
            "time": t,
            "temperature_c": (hourly.get("temperature_2m") or [None])[i],
            "humidity_pct": (hourly.get("relative_humidity_2m") or [None])[i],
            "precip_probability_pct": (hourly.get("precipitation_probability") or [0])[i],
            "precipitation_mm": (hourly.get("precipitation") or [0])[i],
            "weather_description": WMO_CODES.get(wcode, "Unknown"),
            "wind_speed_kmh": (hourly.get("wind_speed_10m") or [0])[i],
            "cloud_cover_pct": (hourly.get("cloud_cover") or [0])[i],
            "uv_index": (hourly.get("uv_index") or [0])[i],
        })

    return {"hourly": hours_data}
