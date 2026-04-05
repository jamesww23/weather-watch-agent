"""GET /api/forecast?location=Tokyo&days=7 — Multi-day weather forecast."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from weather_api import geocode, get_forecast, get_hourly_forecast


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            location = params.get("location", [None])[0]
            days = int(params.get("days", ["7"])[0])
            hourly = params.get("hourly", ["false"])[0].lower() == "true"

            if not location:
                self._json(400, {"error": "location parameter is required (e.g. ?location=Tokyo)"})
                return

            geo = geocode(location)
            if not geo:
                self._json(404, {"error": f"Could not find location: '{location}'"})
                return

            label = f"{geo['name']}, {geo.get('admin1', '')}, {geo['country']}".replace(", ,", ",").strip(", ")
            tz = geo.get("timezone", "auto")

            result = {
                "location": label,
                "coordinates": {"lat": geo["latitude"], "lon": geo["longitude"]},
            }

            fc = get_forecast(geo["latitude"], geo["longitude"], days=days, timezone=tz)
            result["daily_forecast"] = fc["forecast"]

            if hourly:
                hf = get_hourly_forecast(geo["latitude"], geo["longitude"], hours=days * 24, timezone=tz)
                result["hourly_forecast"] = hf["hourly"]

            self._json(200, result)

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
