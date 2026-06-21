Technical Writeup — HeliosHR Onboarding Automation

Overview
This prototype demonstrates an MCP-hosted orchestration that simulates onboarding triggered by Workday. The orchestrator provisions accounts across multiple systems, uses an LLM as a decision agent, records audit logs, and exposes observability endpoints.

The repository includes both a Python prototype and a low-code workflow spec. `main.py` shows the orchestration, LLM decision hook, retry handling, and audit resources in code. `helioshr-onboarding-workflow.json` models the same business process in n8n as a webhook-triggered workflow with AI, provisioning, and notification nodes.

Design decisions

- FastMCP: lightweight way to expose tools/resources to LLMs securely.
- LLM as decision agent: LLM refines recommended systems, triages exceptions, and generates human-facing messages; deterministic fallback prevents outage without keys.
- Simulated connectors: mock_provision_system() stands in for Okta/Slack/GWorkspace APIs to keep repo credential-free.

Failure handling and retries

- Per-system retry loop (3 attempts) with logging on every attempt.
- Failed attempts are captured in FAILED_EVENTS and surfaced via MCP resource.
- LLM is consulted for exception triage; human escalation recommended after persistent failures.

Access governance & auditability

- validate_email enforces company domain for operations.
- log_transaction appends structured audit entries (timestamp, system, status, error).
- Audit store (in-memory here) designed to be backed by an append-only secure log (S3+KMS or WORM DB) in prod.
- Role-based actions: in production, orchestrator would consult an RBAC service or Okta groups before granting elevated access.

MCP & security

- MCP server limits surface area: expose narrow tools/resources; authenticate requests via mTLS or API keys; allow LLMs/agents only the permitted tool set.
- Secrets are never stored here; connectors use short-lived credentials via a secrets manager (AWS Secrets Manager / HashiCorp Vault).

LLM usage

- Prompt includes context: department, title, baseline access template to allow policy-aware decisions.
- Validation: LLM outputs parsed and validated; non-JSON or unexpected outputs are ignored and fall back to safe defaults.

Next steps (if time permits)

- Implement real connectors for Okta, Slack, Google Workspace using service accounts and least-privilege scopes.
- Add persistent audit storage, webhook retry queues, and a UI for People Ops to review/approve edge cases.
- Add unit/integration tests and CI checks.

Assumptions

- No live credentials provided; prototype simulates connectors.
- Workday triggers are modeled as incoming events to orchestrate_onboarding().
