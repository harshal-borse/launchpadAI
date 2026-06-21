# HeliosHR Onboarding Automation (Prototype)

This repo contains a prototype MCP-based onboarding orchestrator that simulates provisioning new hires across core systems (Okta, Google Workspace, Slack, Jira, FreshService).

Features

- FastMCP server exposing tools/resources for metrics and failed events
- Orchestrator: Workday-like event → provisioning plan → LLM decision hook → per-system provisioning with retries
- Audit logs and failed-event collection for governance and auditability

Prerequisites

- Python 3.10+
- (Optional) Virtualenv

Setup

1. python -m venv .venv && source .venv/bin/activate
2. pip install --upgrade pip
3. pip install fastmcp
   - If you have additional requirements, add a requirements.txt and run `pip install -r requirements.txt`

Configuration

- Optional environment variables:
  - LLM_URL: URL of LLM endpoint (Claude/other)
  - LLM_API_KEY: API key for LLM
- Do NOT commit secrets to git. Use a secrets manager in prod.

Running

- Demo run (simulated Workday event + start server):
  python main.py
  - This runs a simulated onboarding (simulate_workday_activation) and starts the MCP server.

Using the prototype

- Orchestrator entrypoint: orchestrate_onboarding(workday_event)
- Observability resources exposed via MCP:
  - onboarding://metrics — returns total/success rate
  - onboarding://failed-events — returns failed provisioning events

How the Python prototype and n8n workflow relate

- `main.py` is the code-first prototype: it simulates a Workday activation, calls an LLM decision helper, performs provisioning logic, and exposes audit/metrics endpoints via MCP.
- `helioshr-onboarding-workflow.json` / `sample.json` are n8n workflow exports that model the same onboarding flow in a low-code automation tool: webhook trigger → AI node → provisioning nodes → Slack notification.
- They are complementary, not the same runtime: one proves the backend orchestration and governance layer in Python, the other proves the same business process in n8n.

n8n workflow import

- Import `helioshr-onboarding-workflow.json` from the n8n workflow import menu.
- The file has explicit workflow connections and workflow metadata to preserve node wiring.
- If nodes display with `?`, your n8n instance may not have the required node packages installed (AdvancedAI, Okta, Google Workspace, Slack).
- If the workflow still appears with detached nodes, make sure you are using the Workflow import feature, not the node-level import into an existing workflow.
- Use the workflow as a template: connect real API credentials and enable the appropriate nodes in n8n.

Install required n8n nodes

- For self-hosted n8n with the UI: go to **Settings > Community Nodes** and install the connector packages.
- If your instance supports manual npm installation, run in the n8n user node directory:
  ```bash
  cd ~/.n8n/nodes
  npm install n8n-nodes-okta n8n-nodes-google-workspace n8n-nodes-slack n8n-nodes-advanced-ai
  ```
  then restart n8n.
- If you are using n8n Cloud, use the Community Nodes install screen or upgrade to a current n8n version so the built-in `Slack`, `Okta`, `Google Workspace`, and `Advanced AI` nodes are available.
- If these nodes are still missing after install, upgrade n8n to the latest stable version and re-import the workflow.

What this repo delivers (assignment mapping)

- Trigger: simulate_workday_activation() demonstrates automatic trigger
- Provisioning: ACCESS_MATRIX covers ≥3 systems; mock_provision_system simulates connectors
- LLM: call_llm() is the decision hook; safe fallback used when not configured
- MCP: FastMCP exposes resources/tools securely
- Governance: log_transaction(), AUDIT_LOGS, FAILED_EVENTS for auditability

Files added

- ARCHITECTURE.md — Mermaid diagram + notes
- TECHNICAL_WRITEUP.md — design, failure handling, governance, next steps
- EXEC_SUMMARY.md — plain-language summary for People Ops
- helioshr-onboarding-workflow.json — working n8n workflow import template with built-in nodes
- AI_USAGE.md — detailed AI usage statement and manual contribution summary

AI Usage Statement (expanded)

- See `AI_USAGE.md` for the full AI usage statement and details on what was authored manually vs AI-assisted.

Next steps (optional)

- Wire real connectors (Okta, Google Workspace, Slack) using service accounts and least-privilege scopes
- Persist audit logs to secure store (S3 + KMS or DB)
- Add unit/integration tests and CI checks
