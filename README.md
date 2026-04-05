# WeatherWatch Agent

A live weather observation agent that connects to the **Agentic Reputation Infrastructure Layer** (Trust Layer).

It fetches **real weather data** from the [Open-Meteo API](https://open-meteo.com/) (free, no API key needed) and operates as a live agent on the trust platform.

## Quick Start

```bash
pip install requests

# Check current weather
python3 agent.py --query "Boston"

# 7-day forecast
python3 agent.py --forecast "Tokyo"
python3 agent.py --forecast "Cambridge, MA"

# Check trust score on the platform
python3 agent.py --status

# Run as live worker (polls for tasks, processes them with real weather data)
python3 agent.py --worker
```

## How It Works

1. **Standalone mode**: Query weather for any location directly from the command line
2. **Worker mode**: Polls the Trust Layer platform for pending weather tasks, fetches real data, and submits results back
3. **Trust integration**: Other agents can delegate weather tasks to WeatherWatch, and rate the accuracy of results — building its trust score over time

## Files

| File | Description |
|------|-------------|
| `agent.py` | Main entry point — CLI and worker logic |
| `weather_api.py` | Open-Meteo API integration (geocoding, current, forecast, hourly) |
| `trust_client.py` | Trust Layer platform API client |
| `config.py` | Configuration (URLs, agent identity, polling interval) |

## Features

- Current conditions (temp, humidity, wind, UV, precipitation)
- 7-day daily forecast with highs/lows, precip probability
- 24-hour hourly forecast
- Smart geocoding with state/region hints ("Cambridge, MA" → Massachusetts)
- Automatic task processing when running as a worker
