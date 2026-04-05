"""Client for interacting with the Trust Layer platform API."""

import json
import requests
from config import TRUST_LAYER_URL, AGENT_ID, AGENT_NAME, SKILL_MD


def _safe_json(resp):
    """Parse JSON from response, return error dict on failure."""
    try:
        return resp.json()
    except Exception:
        return {"error": f"HTTP {resp.status_code}: {resp.text[:200]}"}


def register_agent() -> dict:
    """Register WeatherWatch agent on the trust layer platform.

    Returns the agent profile or error dict.
    """
    resp = requests.post(f"{TRUST_LAYER_URL}/api/agents", json={
        "agent_id": AGENT_ID,
        "agent_name": AGENT_NAME,
        "skill_md": SKILL_MD,
    }, timeout=15)
    return _safe_json(resp)


def get_agent_profile():
    """Get WeatherWatch's current profile and trust score."""
    resp = requests.get(f"{TRUST_LAYER_URL}/api/agents", timeout=15)
    data = _safe_json(resp)
    for agent in data.get("agents", []):
        if agent["agent_id"] == AGENT_ID:
            return agent
    return None


def check_inbox() -> list:
    """Check for pending tasks assigned to WeatherWatch."""
    resp = requests.get(
        f"{TRUST_LAYER_URL}/api/tasks",
        params={"agent_id": AGENT_ID, "status": "pending"},
        timeout=15,
    )
    return _safe_json(resp).get("tasks", [])


def submit_result(task_id: str, result: str) -> dict:
    """Submit a completed task result back to the platform."""
    resp = requests.post(f"{TRUST_LAYER_URL}/api/submit-result", json={
        "task_id": task_id,
        "result": result,
    }, timeout=15)
    return _safe_json(resp)


def delegate_task(provider_id: str, description: str, payload: str = "") -> dict:
    """Delegate a task to another agent via the trust layer.

    WeatherWatch can delegate fact-checking or research tasks to other agents.
    """
    resp = requests.post(f"{TRUST_LAYER_URL}/api/tasks", json={
        "requester_id": AGENT_ID,
        "provider_id": provider_id,
        "description": description,
        "payload": payload,
    }, timeout=15)
    return _safe_json(resp)


def discover_agents(query: str) -> list:
    """Search for agents on the platform by skill keyword."""
    resp = requests.get(
        f"{TRUST_LAYER_URL}/api/discover",
        params={"q": query},
        timeout=15,
    )
    return _safe_json(resp).get("agents", [])


def rate_task(task_id: str, provider_id: str, score: float) -> dict:
    """Rate a completed task."""
    resp = requests.post(f"{TRUST_LAYER_URL}/api/feedback", json={
        "provider_id": provider_id,
        "score": score,
        "task_id": task_id,
    }, timeout=15)
    return _safe_json(resp)
