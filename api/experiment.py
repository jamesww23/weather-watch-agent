"""GET /api/experiment — Cloud Experiment: Real Data vs Simulated.

Assignment 7, Experiment 2: Proves the Trust Layer rewards accuracy.

Registers 3 weather agents (real, fake, stale) + a judge, runs 5 rounds
across different cities, scores accuracy against Open-Meteo ground truth,
and submits ratings through the Trust Layer.

Returns full JSON results showing trust score divergence.
"""

import json
import random
import urllib.request
import urllib.error
import urllib.parse
from http.server import BaseHTTPRequestHandler
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TRUST_LAYER = "https://trust-layer-topaz.vercel.app"

CITIES = ["Boston", "Tokyo", "London", "Sydney", "Paris"]

AGENTS = {
    "real":  {"id": "agent_weatherwatch",   "name": "WeatherWatch"},
    "fake":  {"id": "agent_weather_fake",   "name": "FakeWeatherBot"},
    "stale": {"id": "agent_weather_stale",  "name": "StaleWeatherBot"},
    "judge": {"id": "agent_weather_judge",  "name": "WeatherJudge"},
}

WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "depositing rime fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    56: "light freezing drizzle", 57: "dense freezing drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    66: "light freezing rain", 67: "heavy freezing rain",
    71: "slight snow fall", 73: "moderate snow fall", 75: "heavy snow fall",
    77: "snow grains",
    80: "slight rain showers", 81: "moderate rain showers", 82: "violent rain showers",
    85: "slight snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
}

CONDITION_GROUPS = {
    "clear":   [0, 1],
    "cloudy":  [2, 3],
    "fog":     [45, 48],
    "drizzle": [51, 53, 55, 56, 57],
    "rain":    [61, 63, 65, 66, 67, 80, 81, 82],
    "snow":    [71, 73, 75, 77, 85, 86],
    "storm":   [95, 96, 99],
}

FAKE_CONDITIONS = [
    "clear sky", "partly cloudy", "moderate rain", "slight snow fall",
    "overcast", "fog", "thunderstorm", "light drizzle",
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _post(path, body):
    url = TRUST_LAYER + path
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        try:
            return json.loads(err)
        except Exception:
            return {"error": err or str(e)}


def _get(path):
    url = TRUST_LAYER + path
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        try:
            return json.loads(err)
        except Exception:
            return {"error": err or str(e)}


def _get_external(url):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


# ---------------------------------------------------------------------------
# Open-Meteo helpers
# ---------------------------------------------------------------------------

def geocode(city):
    url = (
        f"https://geocoding-api.open-meteo.com/v1/search?"
        f"name={urllib.parse.quote(city)}&count=1"
    )
    data = _get_external(url)
    result = data["results"][0]
    return result["latitude"], result["longitude"]


def fetch_real_weather(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,weather_code"
    )
    data = _get_external(url)
    current = data["current"]
    code = current["weather_code"]
    return {
        "temperature_c": current["temperature_2m"],
        "humidity_pct":  current["relative_humidity_2m"],
        "weather_code":  code,
        "condition":     WMO_CODES.get(code, f"code {code}"),
    }


# ---------------------------------------------------------------------------
# Agent response generators
# ---------------------------------------------------------------------------

def generate_real_response(city, lat, lon):
    w = fetch_real_weather(lat, lon)
    return {
        "agent": "WeatherWatch",
        "city": city,
        "temperature_c": w["temperature_c"],
        "humidity_pct":  w["humidity_pct"],
        "condition":     w["condition"],
        "source": "Open-Meteo API (live)",
    }


def generate_fake_response(city):
    return {
        "agent": "FakeWeatherBot",
        "city": city,
        "temperature_c": round(random.uniform(-10, 45), 1),
        "humidity_pct":  random.randint(10, 100),
        "condition":     random.choice(FAKE_CONDITIONS),
        "source": "randomly generated",
    }


def generate_stale_response(city):
    return {
        "agent": "StaleWeatherBot",
        "city": city,
        "temperature_c": 22.0,
        "humidity_pct":  45,
        "condition":     "clear sky",
        "source": "hardcoded stale data",
    }


# ---------------------------------------------------------------------------
# Accuracy scoring
# ---------------------------------------------------------------------------

def _condition_group(condition):
    for group, codes in CONDITION_GROUPS.items():
        for code in codes:
            if WMO_CODES.get(code, "") == condition:
                return group
    return "unknown"


def score_accuracy(reported, ground_truth):
    temp_diff = abs(reported["temperature_c"] - ground_truth["temperature_c"])
    temp_score = max(0.0, 1.0 - temp_diff / 15.0)

    humid_diff = abs(reported["humidity_pct"] - ground_truth["humidity_pct"])
    humid_score = max(0.0, 1.0 - humid_diff / 50.0)

    rep_group = _condition_group(reported["condition"])
    truth_group = _condition_group(ground_truth["condition"])
    if rep_group == truth_group:
        cond_score = 1.0
    elif rep_group in ("rain", "drizzle", "storm") and truth_group in ("rain", "drizzle", "storm"):
        cond_score = 0.3
    elif rep_group in ("rain", "drizzle", "storm") and truth_group in ("snow",):
        cond_score = 0.15
    else:
        cond_score = 0.0

    overall = 0.45 * temp_score + 0.25 * humid_score + 0.30 * cond_score
    details = {
        "temp_diff": round(temp_diff, 1),
        "temp_score": round(temp_score, 3),
        "humid_diff": round(humid_diff, 1),
        "humid_score": round(humid_score, 3),
        "condition_match": rep_group == truth_group,
        "cond_score": round(cond_score, 3),
        "overall": round(overall, 3),
    }
    return overall, details


def accuracy_to_rating(accuracy):
    if accuracy >= 0.75:
        return round(random.uniform(0.85, 0.95), 2)
    elif accuracy >= 0.45:
        return round(random.uniform(0.50, 0.70), 2)
    else:
        return round(random.uniform(0.20, 0.40), 2)


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------

def register_agents():
    results = []
    specs = [
        ("judge", "agent_weather_judge", "WeatherJudge",
         "# WeatherJudge\nEvaluates weather forecast accuracy by comparing "
         "agent responses against Open-Meteo ground truth data."),
        ("fake", "agent_weather_fake", "FakeWeatherBot",
         "# FakeWeatherBot\nReturns weather forecasts for any city. "
         "Provides temperature, humidity, and sky condition data."),
        ("stale", "agent_weather_stale", "StaleWeatherBot",
         "# StaleWeatherBot\nReturns weather forecasts for any city. "
         "Provides temperature, humidity, and sky condition data."),
        ("real", "agent_weatherwatch", "WeatherWatch",
         "# WeatherWatch\nProvides real-time weather data from Open-Meteo API. "
         "Returns current temperature, humidity, and conditions for any city."),
    ]
    for label, aid, name, skill in specs:
        resp = _post("/api/register-agent", {
            "agent_id": aid,
            "agent_name": name,
            "skill_md": skill,
        })
        results.append({
            "agent": name,
            "agent_id": aid,
            "status": resp.get("status", resp.get("error", "unknown")),
        })
    return results


def run_round(round_num, city):
    log = {"round": round_num, "city": city, "agents": {}}

    # Geocode
    lat, lon = geocode(city)
    log["coordinates"] = {"lat": lat, "lon": lon}

    # Ground truth
    ground_truth = fetch_real_weather(lat, lon)
    log["ground_truth"] = ground_truth

    # Generate responses
    responses = {
        "real":  generate_real_response(city, lat, lon),
        "fake":  generate_fake_response(city),
        "stale": generate_stale_response(city),
    }

    # Process each agent
    for label in ["real", "fake", "stale"]:
        agent = AGENTS[label]
        resp = responses[label]
        agent_log = {
            "agent_name": agent["name"],
            "response": resp,
        }

        # Delegate task
        delegate_resp = _post("/api/delegate-task", {
            "requester_id": AGENTS["judge"]["id"],
            "provider_id":  agent["id"],
            "description":  f"Provide current weather for {city}",
            "payload":      json.dumps({"city": city, "lat": lat, "lon": lon}),
        })

        task_id = delegate_resp.get("task", {}).get("task_id")
        agent_log["task_id"] = task_id

        if not task_id:
            agent_log["delegation_error"] = delegate_resp.get("error", "unknown")
            # Score anyway
            accuracy, details = score_accuracy(resp, ground_truth)
            rating = accuracy_to_rating(accuracy)
            agent_log["accuracy"] = details
            agent_log["rating"] = rating
            agent_log["note"] = "Trust gate blocked delegation — rated without task"
            # Submit feedback without task_id
            _post("/api/submit-feedback", {
                "agent_id": agent["id"],
                "score":    rating,
                "rated_by": AGENTS["judge"]["id"],
            })
            log["agents"][label] = agent_log
            continue

        # Submit result
        submit_resp = _post("/api/submit-result", {
            "task_id": task_id,
            "result":  json.dumps(resp),
        })
        agent_log["submit_status"] = submit_resp.get("status", "ok")

        # Score accuracy
        accuracy, details = score_accuracy(resp, ground_truth)
        rating = accuracy_to_rating(accuracy)
        agent_log["accuracy"] = details
        agent_log["rating"] = rating

        # Submit feedback
        feedback_resp = _post("/api/submit-feedback", {
            "agent_id": agent["id"],
            "score":    rating,
            "task_id":  task_id,
            "rated_by": AGENTS["judge"]["id"],
        })
        agent_log["feedback_result"] = {
            "trust_before": feedback_resp.get("result", {}).get("trust_before"),
            "trust_after": feedback_resp.get("result", {}).get("trust_after"),
        }

        log["agents"][label] = agent_log

    return log


def fetch_final_scores():
    all_agents = _get("/api/agents").get("agents", [])
    scores = {}
    for a in all_agents:
        scores[a["agent_id"]] = {
            "agent_name": a.get("agent_name", a["agent_id"]),
            "trust_score": a.get("trust_score", 0),
            "tasks_completed": a.get("tasks_completed", 0),
        }
    return scores


# ---------------------------------------------------------------------------
# Vercel Handler
# ---------------------------------------------------------------------------

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            started = datetime.now(timezone.utc)
            experiment = {
                "experiment": "Experiment 2: Real Data vs Simulated",
                "question": "Does the Trust Layer reward accuracy?",
                "started_at": started.isoformat(),
                "platform": TRUST_LAYER,
                "cities": CITIES,
            }

            # Parse query params
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(self.path).query)
            num_rounds = min(int(qs.get("rounds", ["5"])[0]), 10)

            # Step 1: Register agents
            experiment["registration"] = register_agents()

            # Step 2: Run rounds
            rounds = []
            cumulative_ratings = {"real": [], "fake": [], "stale": []}
            cities_to_use = (CITIES * 2)[:num_rounds]  # cycle cities if > 5

            for i, city in enumerate(cities_to_use, 1):
                round_log = run_round(i, city)
                rounds.append(round_log)

                # Collect ratings
                for label in ["real", "fake", "stale"]:
                    if label in round_log["agents"]:
                        rating = round_log["agents"][label].get("rating")
                        if rating is not None:
                            cumulative_ratings[label].append(rating)

            experiment["rounds"] = rounds

            # Step 3: Final analysis
            final_scores = fetch_final_scores()
            experiment["final_trust_scores"] = final_scores

            # Build summary
            summary = {}
            for label in ["real", "fake", "stale"]:
                agent = AGENTS[label]
                ratings = cumulative_ratings[label]
                avg = sum(ratings) / len(ratings) if ratings else 0
                ts_info = final_scores.get(agent["id"], {})
                summary[label] = {
                    "agent_name": agent["name"],
                    "agent_id": agent["id"],
                    "avg_rating": round(avg, 3),
                    "trust_score": ts_info.get("trust_score", 0),
                    "rounds_completed": len(ratings),
                    "all_ratings": ratings,
                }

            experiment["summary"] = summary

            # Determine winner
            best_trust = max(summary.values(), key=lambda x: x["trust_score"])
            best_rating = max(summary.values(), key=lambda x: x["avg_rating"])

            if best_trust["agent_id"] == AGENTS["real"]["id"]:
                conclusion = (
                    f"SUCCESS: The Trust Layer correctly surfaced {best_trust['agent_name']} "
                    f"(real data) as the most trustworthy agent with trust score "
                    f"{best_trust['trust_score']:.4f}. Accuracy IS rewarded."
                )
            elif best_rating["agent_id"] == AGENTS["real"]["id"]:
                conclusion = (
                    f"PARTIAL: {best_rating['agent_name']} had the best ratings "
                    f"({best_rating['avg_rating']:.3f}) but {best_trust['agent_name']} "
                    f"has higher trust due to prior history. More rounds may converge."
                )
            else:
                conclusion = (
                    f"NEEDS MORE ROUNDS: Trust scores haven't converged yet. "
                    f"Best trust: {best_trust['agent_name']}, "
                    f"Best rating: {best_rating['agent_name']}."
                )

            experiment["conclusion"] = conclusion
            experiment["completed_at"] = datetime.now(timezone.utc).isoformat()
            elapsed = (datetime.now(timezone.utc) - started).total_seconds()
            experiment["elapsed_seconds"] = round(elapsed, 1)

            self._json(200, experiment)

        except Exception as e:
            import traceback
            self._json(500, {
                "error": str(e),
                "traceback": traceback.format_exc(),
            })

    def _json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
