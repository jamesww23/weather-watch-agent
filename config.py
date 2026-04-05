"""Configuration for WeatherWatch Agent."""

# Trust Layer platform URL
TRUST_LAYER_URL = "https://trust-layer-topaz.vercel.app"
# TRUST_LAYER_URL = "http://localhost:3000"  # uncomment for local dev

# Agent identity
AGENT_ID = "agent_weatherwatch"
AGENT_NAME = "WeatherWatch"
SKILL_MD = """# WeatherWatch — Weather Observation Agent

I provide accurate, real-time weather data and forecasts for any location worldwide.

## Skills
- Current weather conditions (temperature, humidity, wind, precipitation)
- 7-day weather forecasts with hourly breakdowns
- Severe weather alerts and warnings
- Historical weather data lookups
- UV index and air quality reporting

## Data Source
Powered by Open-Meteo API — open-source, high-accuracy meteorological data from national weather services.

## Best For
Tasks requiring accurate weather information for planning, safety, agriculture, logistics, or outdoor events.
"""

# Open-Meteo API (free, no key needed)
WEATHER_API_BASE = "https://api.open-meteo.com/v1"
GEOCODING_API_BASE = "https://geocoding-api.open-meteo.com/v1"

# Polling interval (seconds)
POLL_INTERVAL = 10
