#!/usr/bin/env python3
"""
WeatherWatch Agent — Live weather observation agent for the Trust Layer platform.

Usage:
    # Register on the platform and run as a live worker:
    python3 agent.py

    # Just check weather for a location (standalone mode):
    python3 agent.py --query "Boston"

    # Get 7-day forecast:
    python3 agent.py --forecast "Tokyo"

    # Register on the platform only:
    python3 agent.py --register

    # Run as live worker (poll for tasks):
    python3 agent.py --worker
"""

import argparse
import json
import sys
import time
import re

from weather_api import geocode, get_current_weather, get_forecast, get_hourly_forecast
from trust_client import (
    register_agent, get_agent_profile, check_inbox,
    submit_result, discover_agents, delegate_task, rate_task,
)
from config import AGENT_ID, POLL_INTERVAL


# ---------------------------------------------------------------------------
# Task processing — parse weather requests and return real data
# ---------------------------------------------------------------------------

def parse_location(text: str) -> str:
    """Extract a location name from a task description or payload."""
    # Try common patterns
    patterns = [
        r"(?:weather|forecast|conditions|temperature|climate)\s+(?:in|for|at|of)\s+([A-Za-z\s,]+)",
        r"(?:in|for|at)\s+([A-Z][a-zA-Z\s,]+?)(?:\.|$|\?|!|\n)",
        r"^([A-Z][a-zA-Z\s,]+?)(?:\.|$|\?|!|\n)",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(",. ")

    # Fallback: return the whole text trimmed
    return text.strip()[:50]


def process_weather_task(description: str, payload: str) -> str:
    """Process a weather-related task and return real weather data."""
    text = f"{description} {payload}".strip()
    location_name = parse_location(text)

    # Geocode the location
    geo = geocode(location_name)
    if not geo:
        return json.dumps({
            "status": "error",
            "message": f"Could not find location: '{location_name}'. Please provide a valid city or place name.",
        }, indent=2)

    location_label = f"{geo['name']}, {geo['admin1']}, {geo['country']}".strip(", ")

    # Determine what kind of weather info is needed
    text_lower = text.lower()
    wants_forecast = any(w in text_lower for w in ["forecast", "week", "7-day", "7 day", "next days", "upcoming"])
    wants_hourly = any(w in text_lower for w in ["hourly", "hour by hour", "next 24", "today"])
    wants_current = any(w in text_lower for w in ["current", "now", "right now", "conditions", "temperature"])

    # Default to current + forecast if ambiguous
    if not (wants_forecast or wants_hourly or wants_current):
        wants_current = True
        wants_forecast = True

    result = {
        "status": "success",
        "location": location_label,
        "coordinates": {"lat": geo["latitude"], "lon": geo["longitude"]},
    }

    if wants_current:
        current = get_current_weather(geo["latitude"], geo["longitude"], geo.get("timezone", "auto"))
        result["current_conditions"] = current

    if wants_forecast:
        fc = get_forecast(geo["latitude"], geo["longitude"], days=7, timezone=geo.get("timezone", "auto"))
        result["7_day_forecast"] = fc["forecast"]

    if wants_hourly:
        hf = get_hourly_forecast(geo["latitude"], geo["longitude"], hours=24, timezone=geo.get("timezone", "auto"))
        result["hourly_forecast_24h"] = hf["hourly"]

    # Add a human-readable summary
    if wants_current and "current_conditions" in result:
        c = result["current_conditions"]
        result["summary"] = (
            f"Current weather in {location_label}: {c['weather_description']}, "
            f"{c['temperature_c']}°C ({c['temperature_f']}°F), "
            f"feels like {c['feels_like_c']}°C. "
            f"Humidity {c['humidity_pct']}%, wind {c['wind_speed_kmh']} km/h. "
            f"UV index: {c['uv_index']}."
        )

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Worker mode — poll platform for tasks
# ---------------------------------------------------------------------------

def run_worker():
    """Run as a live worker, polling the trust layer for weather tasks."""
    # Ensure registered
    profile = get_agent_profile()
    if not profile:
        print("  Registering WeatherWatch on the platform...")
        resp = register_agent()
        if resp.get("error"):
            print(f"  Registration failed: {resp['error']}")
            return
        print(f"  Registered!")
        profile = get_agent_profile()

    trust = profile.get("trust_score", 0)
    print(f"\n  Agent: {profile['agent_name']} ({AGENT_ID})")
    print(f"  Trust: {trust*100:.0f}%")
    print(f"  Polling every {POLL_INTERVAL}s (Ctrl+C to stop)\n")

    while True:
        try:
            tasks = check_inbox()
            if tasks:
                print(f"  [{profile['agent_name']}] {len(tasks)} pending task(s):")
                for task in tasks:
                    task_id = task["task_id"]
                    desc = task.get("description", "")
                    payload = task.get("payload", "")
                    requester = task.get("requester_id", "?")
                    print(f"    -> Task {task_id}: \"{desc[:55]}\" (from {requester})")
                    print(f"       Processing...", end=" ", flush=True)

                    try:
                        result = process_weather_task(desc, payload)
                        resp = submit_result(task_id, result)
                        if resp.get("error"):
                            print(f"SUBMIT FAILED: {resp['error']}")
                        else:
                            print("Done!")
                    except Exception as e:
                        print(f"ERROR: {e}")
                        # Submit error result so task doesn't stay stuck
                        submit_result(task_id, json.dumps({
                            "status": "error",
                            "message": f"Weather lookup failed: {str(e)}",
                        }))

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n  Worker stopped.")
            break


# ---------------------------------------------------------------------------
# CLI — standalone weather queries
# ---------------------------------------------------------------------------

def query_weather(location: str):
    """Quick standalone weather check."""
    geo = geocode(location)
    if not geo:
        print(f"  Could not find location: '{location}'")
        return

    label = f"{geo['name']}, {geo['admin1']}, {geo['country']}".strip(", ")
    print(f"\n  Location: {label}")
    print(f"  Coordinates: {geo['latitude']}, {geo['longitude']}\n")

    current = get_current_weather(geo["latitude"], geo["longitude"], geo.get("timezone", "auto"))

    print(f"  Current Conditions:")
    print(f"    {current['weather_description']}")
    print(f"    Temperature: {current['temperature_c']}°C ({current['temperature_f']}°F)")
    print(f"    Feels like:  {current['feels_like_c']}°C ({current['feels_like_f']}°F)")
    print(f"    Humidity:    {current['humidity_pct']}%")
    print(f"    Wind:        {current['wind_speed_kmh']} km/h (gusts {current['wind_gusts_kmh']} km/h)")
    print(f"    Cloud cover: {current['cloud_cover_pct']}%")
    print(f"    Pressure:    {current['pressure_hpa']} hPa")
    print(f"    UV Index:    {current['uv_index']}")
    print(f"    Precip:      {current['precipitation_mm']} mm")
    print(f"    Observed:    {current['observation_time']}")


def show_forecast(location: str):
    """Show 7-day forecast for a location."""
    geo = geocode(location)
    if not geo:
        print(f"  Could not find location: '{location}'")
        return

    label = f"{geo['name']}, {geo['admin1']}, {geo['country']}".strip(", ")
    print(f"\n  7-Day Forecast for {label}\n")

    fc = get_forecast(geo["latitude"], geo["longitude"], days=7, timezone=geo.get("timezone", "auto"))

    print(f"  {'Date':<12} {'Conditions':<25} {'High':>6} {'Low':>6} {'Precip':>8} {'Wind':>8} {'UV':>4}")
    print(f"  {'-'*12} {'-'*25} {'-'*6} {'-'*6} {'-'*8} {'-'*8} {'-'*4}")

    for day in fc["forecast"]:
        print(
            f"  {day['date']:<12} "
            f"{day['weather_description']:<25} "
            f"{day['high_c']:>4.0f}°C "
            f"{day['low_c']:>4.0f}°C "
            f"{day['precipitation_mm']:>5.1f}mm "
            f"{day['wind_max_kmh']:>5.0f}kmh "
            f"{day['uv_index_max']:>4.0f}"
        )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="WeatherWatch Agent — Real-time weather for the Trust Layer platform"
    )
    parser.add_argument("--query", "-q", type=str, help="Quick weather check for a location")
    parser.add_argument("--forecast", "-f", type=str, help="7-day forecast for a location")
    parser.add_argument("--register", action="store_true", help="Register agent on the trust layer")
    parser.add_argument("--worker", "-w", action="store_true", help="Run as live worker (poll for tasks)")
    parser.add_argument("--status", "-s", action="store_true", help="Show agent trust status")

    args = parser.parse_args()

    print("\n" + "=" * 55)
    print("  WeatherWatch — Live Weather Observation Agent")
    print("=" * 55)

    if args.query:
        query_weather(args.query)
    elif args.forecast:
        show_forecast(args.forecast)
    elif args.register:
        print("\n  Registering on trust layer platform...")
        resp = register_agent()
        if resp.get("error"):
            print(f"  Error: {resp['error']}")
        else:
            print(f"  Registered! Agent ID: {AGENT_ID}")
            profile = get_agent_profile()
            if profile:
                print(f"  Trust Score: {profile['trust_score']*100:.0f}%")
    elif args.status:
        profile = get_agent_profile()
        if profile:
            print(f"\n  Agent: {profile['agent_name']}")
            print(f"  Trust Score: {profile['trust_score']*100:.0f}%")
            print(f"  Total Runs: {profile.get('total_runs', 0)}")
            print(f"  Tasks Completed: {profile.get('tasks_completed', 0)}")
        else:
            print(f"\n  WeatherWatch not registered yet. Run: python3 agent.py --register")
    elif args.worker:
        run_worker()
    else:
        # Default: register + start worker
        print()
        run_worker()


if __name__ == "__main__":
    main()
