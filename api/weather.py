"""GET /api/weather?location=Boston — Current weather conditions."""

import json
import sys
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from weather_api import geocode, get_current_weather


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            location = params.get("location", [None])[0]

            if not location:
                self._json(400, {"error": "location parameter is required (e.g. ?location=Boston)"})
                return

            geo = geocode(location)
            if not geo:
                self._json(404, {"error": f"Could not find location: '{location}'"})
                return

            label = f"{geo['name']}, {geo.get('admin1', '')}, {geo['country']}".replace(", ,", ",").strip(", ")
            current = get_current_weather(geo["latitude"], geo["longitude"], geo.get("timezone", "auto"))

            self._json(200, {
                "location": label,
                "coordinates": {"lat": geo["latitude"], "lon": geo["longitude"]},
                "current": current,
                "summary": (
                    f"{current['weather_description']}, "
                    f"{current['temperature_c']}°C ({current['temperature_f']}°F), "
                    f"feels like {current['feels_like_c']}°C. "
                    f"Humidity {current['humidity_pct']}%, "
                    f"wind {current['wind_speed_kmh']} km/h. "
                    f"UV index: {current['uv_index']}."
                ),
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
