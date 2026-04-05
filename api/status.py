"""GET /api/status — WeatherWatch trust profile + recent activity from Trust Layer."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

TRUST_LAYER = "https://trust-layer-topaz.vercel.app"
AGENT_ID = "agent_weatherwatch"


def _fetch(path):
    try:
        r = requests.get(TRUST_LAYER + path, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # 1. Get agent profile
            agents_data = _fetch("/api/agents")
            profile = None
            for a in agents_data.get("agents", []):
                if a["agent_id"] == AGENT_ID:
                    profile = a
                    break

            if not profile:
                self._json(200, {
                    "registered": False,
                    "message": "WeatherWatch not yet registered on Trust Layer. Hit Reset on the platform to seed agents.",
                })
                return

            # 2. Get tasks where WeatherWatch is the provider (work we did)
            tasks_provider = _fetch(f"/api/tasks?agent_id={AGENT_ID}&status=all&role=provider")
            tasks_done = tasks_provider.get("tasks", [])

            # 3. Get tasks where WeatherWatch is the requester (work we delegated)
            tasks_requester = _fetch(f"/api/tasks?agent_id={AGENT_ID}&role=requester")
            tasks_delegated = tasks_requester.get("tasks", [])

            # 4. Get recent activity from the platform
            activity = _fetch("/api/activity")
            all_activity = activity.get("events", [])

            # Filter activity involving WeatherWatch
            my_activity = [
                e for e in all_activity
                if e.get("provider_id") == AGENT_ID or e.get("requester_id") == AGENT_ID
            ]

            self._json(200, {
                "registered": True,
                "profile": {
                    "agent_id": profile["agent_id"],
                    "agent_name": profile["agent_name"],
                    "trust_score": profile.get("trust_score", 0),
                    "total_runs": profile.get("total_runs", 0),
                    "tasks_received": profile.get("tasks_received", 0),
                    "tasks_completed": profile.get("tasks_completed", 0),
                    "avg_latency_ms": profile.get("avg_latency_ms", 0),
                },
                "tasks_completed_for_others": [
                    {
                        "task_id": t["task_id"],
                        "requester": t.get("requester_id", "?"),
                        "description": t.get("description", "")[:80],
                        "status": t.get("status"),
                        "rating": t.get("rating"),
                        "completed_at": t.get("completed_at"),
                    }
                    for t in tasks_done
                    if t.get("status") in ("completed", "rated")
                ][:10],
                "tasks_delegated_to_others": [
                    {
                        "task_id": t["task_id"],
                        "provider": t.get("provider_id", "?"),
                        "description": t.get("description", "")[:80],
                        "status": t.get("status"),
                        "rating": t.get("rating"),
                    }
                    for t in tasks_delegated
                ][:10],
                "recent_activity": my_activity[:10],
            })

        except Exception as e:
            self._json(500, {"error": str(e)})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
