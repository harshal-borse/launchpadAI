import re
import uuid
import logging
import os
import json
import random
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib import request, parse

try:
    from fastmcp import FastMCP
except Exception:
    raise

mcp = FastMCP(
    name="HeliosHR Onboarding Gateway",
    version="2.1.0",
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("helioshr")

AUDIT_LOGS: List[Dict[str, Any]] = []
FAILED_EVENTS: List[Dict[str, Any]] = []

ACCESS_MATRIX = {
    "Engineering": ["Google Workspace", "Slack", "Jira", "AWS"],
    "Sales": ["Google Workspace", "Slack", "Salesforce"],
    "PeopleOps": ["Google Workspace", "Slack", "Workday"],
    "IT": ["Google Workspace", "Slack", "Jira", "AWS", "Okta", "FreshService"],
}


def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@helioshr\.com$"
    return bool(re.match(pattern, email))


def create_employee_email(first_name: str, last_name: str) -> str:
    return f"{first_name.lower().strip()}.{last_name.lower().strip()}@helioshr.com"


# -- MCP resources/tools for observability --
@mcp.resource("onboarding://metrics")
def onboarding_metrics() -> Dict[str, Any]:
    total = len(AUDIT_LOGS)
    failures = len([log for log in AUDIT_LOGS if log.get("status") == "FAILED"])
    return {
        "total_transactions": total,
        "failures": failures,
        "success_rate": ((total - failures) / total) * 100 if total else 100,
    }


@mcp.resource("onboarding://failed-events")
def failed_events() -> List[Dict[str, Any]]:
    return FAILED_EVENTS


# Basic tools
@mcp.tool
def prepare_employee_payload(first_name: str, last_name: str, department: str, title: str) -> Dict[str, Any]:
    email = create_employee_email(first_name, last_name)
    return {
        "employee_id": str(uuid.uuid4()),
        "email": email,
        "department": department,
        "title": title,
        "status": "VALIDATED",
    }


@mcp.tool
def get_access_template(department: str) -> Dict[str, Any]:
    return {"department": department, "recommended_access": ACCESS_MATRIX.get(department, ["Google Workspace", "Slack"]) }


@mcp.tool
def create_provisioning_plan(first_name: str, last_name: str, department: str, title: str) -> Dict[str, Any]:
    email = create_employee_email(first_name, last_name)
    return {
        "email": email,
        "systems": ACCESS_MATRIX.get(department, ["Google Workspace", "Slack"]),
        "priority": "HIGH",
        "created_at": datetime.utcnow().isoformat(),
    }


@mcp.tool
def log_transaction(employee_email: str, target_system: str, status: str, error_message: str = "") -> Dict[str, Any]:
    if not validate_email(employee_email):
        raise ValueError("External domains not allowed")
    log = {"timestamp": datetime.utcnow().isoformat(), "email": employee_email, "system": target_system, "status": status, "error": error_message}
    AUDIT_LOGS.append(log)
    if status == "FAILED":
        FAILED_EVENTS.append(log)
    logger.info(json.dumps(log))
    return {"logged": True}


@mcp.tool
def get_failed_provisioning_events() -> List[Dict[str, Any]]:
    return FAILED_EVENTS


# -- LLM decision helper (optional) --
def call_llm(prompt: str, timeout: int = 5) -> Optional[str]:
    """
    Call an external LLM endpoint if configured via environment variables.
    Falls back to a deterministic heuristic when not configured.
    """
    llm_url = os.environ.get("LLM_URL")
    api_key = os.environ.get("LLM_API_KEY")
    if not llm_url or not api_key:
        # Simple heuristic: map department mentions in prompt to systems
        if "engineering" in prompt.lower():
            return json.dumps({"systems": ACCESS_MATRIX.get("Engineering")})
        if "sales" in prompt.lower():
            return json.dumps({"systems": ACCESS_MATRIX.get("Sales")})
        return json.dumps({"systems": ["Google Workspace", "Slack"]})
    try:
        data = json.dumps({"prompt": prompt}).encode()
        req = request.Request(llm_url, data=data, headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode()
    except Exception as e:
        logger.warning("LLM call failed: %s", e)
        return None


# -- Mock provisioning (replace with real API calls in prod) --
def mock_provision_system(email: str, system: str) -> Dict[str, Any]:
    """Simulate a provisioning call; randomly fail to exercise retries."""
    time.sleep(0.1)
    # deterministic pseudo-random based on email+system to keep runs stable
    seed = sum(ord(c) for c in (email + system)) % 10
    success = seed >= 2  # ~80% success
    if success:
        return {"system": system, "status": "SUCCESS"}
    return {"system": system, "status": "FAILED", "error": "simulated error"}


# -- Orchestrator tool: LLM participates in decisions and exception handling --
@mcp.tool
def orchestrate_onboarding(workday_event: Dict[str, Any]) -> Dict[str, Any]:
    """Accepts a Workday-like event and provisions accounts across systems.
    Uses an LLM to adjust access decisions and handles retries/auditing.
    """
    try:
        first_name = workday_event.get("first_name")
        last_name = workday_event.get("last_name")
        department = workday_event.get("department")
        title = workday_event.get("title")
        if not all([first_name, last_name, department]):
            raise ValueError("Missing required fields in event")

        payload = prepare_employee_payload(first_name, last_name, department, title)
        plan = create_provisioning_plan(first_name, last_name, department, title)

        # Ask LLM to refine systems (provides explainability and policy checks)
        prompt = f"Recommend systems for a new hire in {department} with title {title}. Base recommendation: {plan['systems']}"
        llm_raw = call_llm(prompt)
        llm_decision = None
        if llm_raw:
            try:
                llm_decision = json.loads(llm_raw)
            except Exception:
                logger.info("LLM returned non-JSON; ignoring: %s", llm_raw)
        systems_to_provision = llm_decision.get("systems") if llm_decision and isinstance(llm_decision.get("systems"), list) else plan["systems"]

        results = []
        for system in systems_to_provision:
            # retry pattern
            attempts = 0
            max_attempts = 3
            while attempts < max_attempts:
                attempts += 1
                res = mock_provision_system(payload["email"], system)
                if res["status"] == "SUCCESS":
                    log_transaction(payload["email"], system, "SUCCESS")
                    results.append({"system": system, "status": "SUCCESS", "attempts": attempts})
                    break
                else:
                    logger.warning("Provision to %s failed on attempt %d", system, attempts)
                    if attempts >= max_attempts:
                        log_transaction(payload["email"], system, "FAILED", res.get("error", "unknown"))
                        results.append({"system": system, "status": "FAILED", "attempts": attempts, "error": res.get("error")})
        return {"employee": payload, "plan": plan, "results": results}
    except Exception as e:
        logger.exception("Orchestration failed")
        return {"error": str(e)}


# -- Helper to simulate an incoming Workday activation webhook --
def simulate_workday_activation():
    event = {"first_name": "Alice", "last_name": "Anderson", "department": "Engineering", "title": "Software Engineer"}
    return orchestrate_onboarding(event)


if __name__ == "__main__":
    logger.info("Starting HeliosHR MCP Server (simulator)")
    # When running locally, demonstrate a simulated run and then start the MCP server
    demo = simulate_workday_activation()
    logger.info("Demo result: %s", json.dumps(demo, indent=2))
    mcp.run()
