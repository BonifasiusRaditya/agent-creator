"""WorkBuddy's stdio connector. The website service must be running."""
import os

import httpx
from mcp.server.fastmcp import FastMCP
from .models import REFERENCE_CONTEXT_FIELDS


mcp = FastMCP("TrendForge", instructions="Run the source-grounded Planner, Writer and Reviewer workflow. Follow the returned role schema. Only the human can approve or export in TrendForge.")
base = os.environ.get("TRENDFORGE_URL", "http://127.0.0.1:8765").rstrip("/")


def call(method, path, body=None, request_key=None):
    # A personal connector token from Connections; it acts only on its owner's projects.
    token = os.environ.get("TRENDFORGE_TOKEN", "").strip()
    if not token:
        return {"error": {"code": "CONNECTOR_TOKEN_MISSING", "message": "Set TRENDFORGE_TOKEN. Create a connector configuration in TrendForge Connections and use it in WorkBuddy."}}
    headers = {"Authorization": "Bearer " + token}
    if request_key:
        headers["Idempotency-Key"] = request_key
    try:
        with httpx.Client(timeout=28) as client:
            r = client.request(method, base + "/api/v1" + path, json=body, headers=headers)
        if r.status_code >= 400:
            return {"error": r.json().get("error", {"message": "The action could not be completed."})}
        return r.json() if r.content else {"ok": True}
    except (httpx.HTTPError, ValueError):
        return {"error": {"code": "SERVICE_UNAVAILABLE", "message": "Start the TrendForge website service, then try again."}}


def get_project(project_id: str) -> dict:
    """Compatibility helper for older video clients; deliberately not an exposed agent tool."""
    project = call("GET", f"/projects/{project_id}")
    for run in project.get("research", []) if isinstance(project, dict) else []:
        run["items"] = [{k: x.get(k) for k in REFERENCE_CONTEXT_FIELDS} for x in run.get("items", [])]
    return project


@mcp.tool()
def trendforge_health() -> dict:
    """Read the selected engine and safe configuration status. Does not test provider credentials."""
    return call("GET", "/creator/status")


@mcp.tool()
def list_projects() -> list | dict:
    """List only the connector owner's saved projects. Never invent an ID."""
    return call("GET", "/projects")


@mcp.tool()
def creator_workspace(project_id: str) -> dict:
    """Read supplied facts, current run, rules, revision history and human approval status."""
    return call("GET", f"/projects/{project_id}/creator")


@mcp.tool()
def creator_next_step(project_id: str, run_id: str) -> dict:
    """Get the current role, revision, system instructions, untrusted context and exact JSON schema. Starts the 80-second WorkBuddy run budget. Stop when no role is returned."""
    return call("GET", f"/projects/{project_id}/creator/runs/{run_id}/next")


@mcp.tool()
def creator_submit_step(project_id: str, run_id: str, revision: int, role: str, result: dict) -> dict:
    """Submit only the requested role's schema-compliant output. A stale revision is rejected. Reviewer must inspect every line and cite documented rules. Never submit human approval."""
    return call("POST", f"/projects/{project_id}/creator/runs/{run_id}/step",
                {"revision": revision, "role": role, "result": result})


if __name__ == "__main__":
    mcp.run(transport="stdio")
