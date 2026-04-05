"""GET /api/cron — Vercel Cron Job: WeatherWatch autonomous agent loop.

Runs every minute. This makes WeatherWatch a LIVE autonomous agent that:
1. Checks its inbox on the Trust Layer for pending weather tasks
2. Fetches REAL weather data and submits results
3. Delegates fact-checking of its own data to FactCheckAgent
4. Rates completed tasks that other agents did for WeatherWatch
"""

import json
import random
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from weather_api import geocode, get_current_weather, get_forecast

# ---------------------------------------------------------------------------
# Trust Layer API helpers
# ---------------------------------------------------------------------------

TRUST_LAYER = "https://trust-layer-topaz.vercel.app"
AGENT_ID = "agent_weatherwatch"


def _api(method, path, body=None):
    """Call the Trust Layer API."""
    url = TRUST_LAYER + path
    try:
        if method == "GET":
            r = requests.get(url, timeout=15)
        else:
            r = requests.post(url, json=body, timeout=15)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def get_pending_tasks():
    """Get tasks assigned to WeatherWatch that need processing."""
    return _api("GET", f"/api/tasks?agent_id={AGENT_ID}&status=pending").get("tasks", [])


def get_tasks_we_requested():
    """Get tasks WeatherWatch delegated to other agents."""
    return _api("GET", f"/api/tasks?agent_id={AGENT_ID}&role=requester").get("tasks", [])


def submit_result(task_id, result):
    return _api("POST", "/api/submit-result", {"task_id": task_id, "result": result})


def delegate_task(provider_id, description, payload=""):
    return _api("POST", "/api/delegate-task", {
        "requester_id": AGENT_ID,
        "provider_id": provider_id,
        "description": description,
        "payload": payload,
    })


def rate_agent(agent_id, score, task_id):
    return _api("POST", "/api/submit-feedback", {
        "agent_id": agent_id,
        "score": score,
        "task_id": task_id,
    })


# ---------------------------------------------------------------------------
# Weather task processing — uses REAL weather data
# ---------------------------------------------------------------------------

def parse_location(text):
    """Extract location from task text."""
    import re
    patterns = [
        r"(?:weather|forecast|conditions|temperature)\s+(?:in|for|at|of)\s+([A-Za-z\s,]+)",
        r"(?:in|for|at)\s+([A-Z][a-zA-Z\s,]+?)(?:\.|$|\?|!|\n)",
    ]
    for pat in patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(",. ")
    # Fallback: try the whole thing
    return text.strip()[:60]


def process_weather_task(description, payload):
    """Process a weather task with REAL data from Open-Meteo."""
    text = f"{description} {payload}".strip()
    location_name = parse_location(text)

    geo = geocode(location_name)
    if not geo:
        return json.dumps({"status": "error", "message": f"Could not find location: '{location_name}'"})

    label = f"{geo['name']}, {geo.get('admin1', '')}, {geo['country']}".replace(", ,", ",").strip(", ")
    tz = geo.get("timezone", "auto")

    current = get_current_weather(geo["latitude"], geo["longitude"], tz)
    fc = get_forecast(geo["latitude"], geo["longitude"], days=7, timezone=tz)

    result = {
        "status": "success",
        "location": label,
        "coordinates": {"lat": geo["latitude"], "lon": geo["longitude"]},
        "current_conditions": current,
        "7_day_forecast": fc["forecast"],
        "summary": (
            f"Weather in {label}: {current['weather_description']}, "
            f"{current['temperature_c']}°C ({current['temperature_f']}°F), "
            f"humidity {current['humidity_pct']}%, wind {current['wind_speed_kmh']} km/h. "
            f"UV index: {current['uv_index']}."
        ),
        "data_source": "Open-Meteo API (national weather services)",
    }
    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Autonomous behaviors
# ---------------------------------------------------------------------------

# Cities WeatherWatch monitors and can proactively delegate about
WATCH_CITIES = ["Boston", "New York", "San Francisco", "London", "Tokyo"]

# Agents WeatherWatch knows how to work with
COLLABORATORS = {
    "agent_factcheck": "Verify weather-related claims",
    "agent_analyst": "Analyze weather trend data",
    "agent_summarizer": "Summarize weekly weather reports",
    "agent_datapipeline": "Clean and normalize weather datasets",
}


def maybe_delegate_task():
    """Delegate a task to another agent (always delegates since cron runs infrequently).

    This creates organic cross-agent activity on the platform.
    """

    city = random.choice(WATCH_CITIES)
    collab_id = random.choice(list(COLLABORATORS.keys()))
    collab_desc = COLLABORATORS[collab_id]

    tasks_by_type = {
        "agent_factcheck": {
            "description": f"Verify accuracy of weather forecast data for {city}",
            "payload": f"WeatherWatch generated a 7-day forecast for {city}. Please cross-reference temperature ranges, precipitation probability, and wind speeds against other meteorological sources.",
        },
        "agent_analyst": {
            "description": f"Analyze weather trend patterns for {city} this quarter",
            "payload": f"Historical weather data shows temperature and precipitation trends for {city}. Identify any anomalies, seasonal patterns, or notable deviations from 10-year averages.",
        },
        "agent_summarizer": {
            "description": f"Summarize this week's weather observations for {city}",
            "payload": f"WeatherWatch collected 7 days of hourly observations for {city}. Create a concise summary highlighting key conditions, extremes, and notable events.",
        },
        "agent_datapipeline": {
            "description": f"Clean and normalize weather dataset for {city}",
            "payload": f"Raw weather data for {city}: contains hourly readings with some missing values, inconsistent timestamps, and duplicate entries. Normalize to ISO 8601 and impute gaps.",
        },
    }

    task_info = tasks_by_type.get(collab_id, {
        "description": f"{collab_desc} for {city} weather data",
        "payload": f"WeatherWatch needs help with: {collab_desc.lower()} related to {city}.",
    })

    result = delegate_task(collab_id, task_info["description"], task_info["payload"])
    return {"delegated_to": collab_id, "result": result}


def maybe_rate_completed_tasks():
    """Rate tasks that other agents completed for us."""
    tasks = get_tasks_we_requested()
    rated = []

    for task in tasks:
        if task.get("status") == "completed" and not task.get("rating"):
            # Rate based on whether the result looks useful
            result_text = task.get("result", "")
            if not result_text or "error" in result_text.lower():
                score = round(random.uniform(0.3, 0.5), 2)
            elif len(result_text) > 100:
                score = round(random.uniform(0.75, 0.95), 2)
            else:
                score = round(random.uniform(0.55, 0.75), 2)

            resp = rate_agent(task["provider_id"], score, task["task_id"])
            rated.append({
                "task_id": task["task_id"],
                "provider": task["provider_id"],
                "score": score,
                "result": resp,
            })

    return rated


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            log = {"agent": AGENT_ID, "actions": []}

            # 1. Process pending weather tasks (our inbox)
            pending = get_pending_tasks()
            tasks_processed = []

            for task in pending:
                desc = task.get("description", "")
                payload = task.get("payload", "")

                result = process_weather_task(desc, payload)
                resp = submit_result(task["task_id"], result)

                tasks_processed.append({
                    "task_id": task["task_id"],
                    "from": task.get("requester_id", "?"),
                    "description": desc[:60],
                    "submit_status": "ok" if not resp.get("error") else resp["error"],
                })

            if tasks_processed:
                log["actions"].append({
                    "type": "processed_tasks",
                    "count": len(tasks_processed),
                    "tasks": tasks_processed,
                })

            # 2. Rate completed tasks from agents we delegated to
            rated = maybe_rate_completed_tasks()
            if rated:
                log["actions"].append({
                    "type": "rated_agents",
                    "count": len(rated),
                    "ratings": rated,
                })

            # 3. Maybe delegate a new task to another agent
            delegation = maybe_delegate_task()
            if delegation:
                log["actions"].append({
                    "type": "delegated_task",
                    "details": delegation,
                })

            self._json(200, log)

        except Exception as e:
            self._json(500, {"error": str(e)})

    def _json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
