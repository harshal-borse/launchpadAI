# Implementation Spec — HeliosHR Onboarding Automation

> Deliverable 3, **Option B**. This document is the step-by-step build plan for the
> core onboarding workflow: the trigger, the LLM orchestration, the per-system
> provisioning calls (concrete API endpoints), the authentication approach, and the
> shape of the MCP server. It complements the working prototype in `main.py` and the
> n8n export in `helioshr-onboarding-workflow.json`.

---

## 1. Core workflow, step by step

```
Workday "hire active" event
        │  (1) webhook / scheduled HRIS poll
        ▼
Ingestion + validation  ──► reject if domain/role invalid, emit audit event
        │  (2)
        ▼
LLM Decision Agent (Claude)  ──► {email, systems[], onboarding_message, risk_notes}
        │  (3) validate + apply policy guardrails (least-privilege, approval gate)
        ▼
Fan-out provisioning (parallel, idempotent, per-system retry)
   ├─ Okta            (4a) create user + assign groups
   ├─ Google Workspace(4b) create user
   ├─ Slack           (4c) invite to workspace + channels
   └─ Jira            (4d) create/active account + project role
        │  (5) collect results, write audit log per system
        ▼
Notify (Slack/FreshService ticket) + persist audit  ──► (6) escalate failures to human
```

**Step 1 — Trigger.** Preferred: Workday **Business Process** outbound webhook on the
"Hire" event, or an EIB/RaaS report polled every N minutes as a fallback when outbound
webhooks aren't enabled. The webhook posts a minimal payload:

```jsonc
{ "worker_id": "21001", "first_name": "Alice", "last_name": "Anderson",
  "department": "Engineering", "title": "Software Engineer", "start_date": "2026-07-01" }
```

**Step 2 — Ingestion + validation.** Verify the request signature, normalize names,
derive `firstname.lastname@helioshr.com`, and reject anything that isn't an internal
domain. Persist the raw event to the audit store before doing anything else.

**Step 3 — LLM decision.** Claude receives the hire context plus the department→systems
access matrix and returns a structured decision (see §3). Output is schema-validated;
on any parse/validation failure we fall back to the static access matrix (never block
onboarding on a bad LLM response). Decisions that flag elevated access (`risk_notes`)
are routed to a human approval gate before provisioning.

**Step 4 — Provisioning.** Each system call is **idempotent** (look up by email first,
create only if absent) and wrapped in a retry with exponential backoff (§5). Calls run
in parallel; one system failing does not block the others.

**Steps 5–6 — Audit + notify.** Every attempt (success or failure) appends an audit
record. A summary is posted to the IT Slack channel; persistent failures open a
FreshService ticket assigned to IT for manual completion.

---

## 2. API endpoints per system

> All examples assume least-privilege service accounts (see §4). Bodies are trimmed to
> the essential fields.

### Okta — create user and assign group
- `POST /api/v1/users?activate=true`
  ```jsonc
  { "profile": { "firstName": "Alice", "lastName": "Anderson",
                 "email": "alice.anderson@helioshr.com",
                 "login": "alice.anderson@helioshr.com" },
    "credentials": { "password": { "hook": { "type": "default" } } } }
  ```
- Idempotency check first: `GET /api/v1/users/alice.anderson@helioshr.com`
- Assign to a group (drives downstream SSO app access):
  `PUT /api/v1/groups/{groupId}/users/{userId}`
- Auth header: `Authorization: SSWS {api_token}` (or OAuth2 for Okta — see §4).

### Google Workspace (Admin SDK Directory API) — create user
- Idempotency check: `GET https://admin.googleapis.com/admin/directory/v1/users/{email}`
- Create: `POST https://admin.googleapis.com/admin/directory/v1/users`
  ```jsonc
  { "primaryEmail": "alice.anderson@helioshr.com",
    "name": { "givenName": "Alice", "familyName": "Anderson" },
    "password": "<random-32-char>", "changePasswordAtNextLogin": true }
  ```
- Auth: OAuth2 service account with **domain-wide delegation**, scope
  `https://www.googleapis.com/auth/admin.directory.user`, impersonating an admin.

### Slack (Admin APIs — Enterprise Grid) — invite + add to channels
- Invite to workspace:
  `POST https://slack.com/api/admin.users.invite`
  `{ "team_id": "T123", "email": "alice.anderson@helioshr.com", "channel_ids": "C0ENG,C0ALL" }`
- (Standard plan fallback) email-invite via SCIM, or post a join request to IT.
- Notify channel: `POST https://slack.com/api/chat.postMessage`
- Auth: `Authorization: Bearer xoxb-…` (bot token) with `admin.users:write`,
  `chat:write` scopes.

### Jira (Atlassian Cloud) — create user + assign project role
- Create: `POST https://{site}.atlassian.net/rest/api/3/user`
  `{ "emailAddress": "alice.anderson@helioshr.com", "displayName": "Alice Anderson", "products": ["jira-software"] }`
- Add to project role:
  `POST /rest/api/3/project/{projectKey}/role/{roleId}` `{ "user": ["{accountId}"] }`
- Auth: HTTP Basic with `email:api_token` (base64), or an OAuth2 (3LO) app.

### FreshService (ticketing) — fallback / escalation
- `POST https://{domain}.freshservice.com/api/v2/tickets` to open a manual-provisioning
  ticket when a system fails after all retries.
- Auth: HTTP Basic `api_key:X`.

---

## 3. LLM agent contract (Claude)

**System prompt (essence):** "You are HeliosHR's onboarding orchestration agent. Apply
least-privilege. Return ONLY minified JSON with keys `email`, `systems` (subset of the
allowed catalog), `onboarding_message`, `risk_notes`."

**Output schema (validated before use):**
```jsonc
{ "email": "string (must end @helioshr.com)",
  "systems": ["Okta","Google Workspace","Slack","Jira"],  // subset of allowed catalog
  "onboarding_message": "string",
  "risk_notes": "string ('none' if no governance concerns)" }
```

**Where the LLM adds value beyond a static map:**
- Maps fuzzy/new titles (e.g. "Staff ML Engineer", "GTM Ops") to the right access set.
- Flags elevated access (`AWS`, `Okta` admin) in `risk_notes` → triggers human approval.
- Triages exceptions: on a provisioning failure it can be re-invoked to suggest a
  remediation (retry vs. open ticket vs. alternate group).

**Guardrails:** strict JSON-schema validation; `systems` intersected with the allowed
catalog (the model can never invent a system); deterministic fallback to the static
matrix on any failure. Prompts and responses are logged (PII-aware) for auditability.

---

## 4. Authentication approach

| System | Mechanism | Stored where |
| --- | --- | --- |
| Okta | API token (SSWS) or OAuth2 service app, scoped to user/group admin | Secrets manager |
| Google Workspace | OAuth2 service account + domain-wide delegation, single directory scope | Secrets manager (JSON key) |
| Slack | Bot token (`xoxb`), minimal `admin.users:write`/`chat:write` scopes | Secrets manager |
| Jira | API token (Basic) or OAuth2 3LO | Secrets manager |
| Claude | Anthropic API key | Secrets manager |

Principles: **dedicated least-privilege service accounts per system** (never a human's
creds); secrets in AWS Secrets Manager / HashiCorp Vault fetched at runtime with
short-lived credentials (IAM role / Vault lease); secrets never committed or logged;
rotation on a schedule. The MCP server authenticates **callers** separately (§5).

---

## 5. MCP server definition

The MCP server is the secure, narrow boundary that exposes the onboarding capability to
AI tooling (Claude Desktop, internal agents). It exposes a small, audited tool/resource
set — it does **not** hand raw system credentials to the model. Implemented with
FastMCP in `main.py`; the contract:

**Tools (actions):**
```jsonc
{
  "prepare_employee_payload": {
    "in":  { "first_name": "str", "last_name": "str", "department": "str", "title": "str" },
    "out": { "employee_id": "uuid", "email": "str", "department": "str", "title": "str", "status": "str" }
  },
  "get_access_template": {
    "in":  { "department": "str" },
    "out": { "department": "str", "recommended_access": ["str"] }
  },
  "create_provisioning_plan": {
    "in":  { "first_name": "str", "last_name": "str", "department": "str", "title": "str" },
    "out": { "email": "str", "systems": ["str"], "priority": "str", "created_at": "iso8601" }
  },
  "orchestrate_onboarding": {
    "in":  { "workday_event": { "first_name": "str", "last_name": "str", "department": "str", "title": "str" } },
    "out": { "employee": {}, "plan": {}, "results": [ { "system": "str", "status": "str", "attempts": "int" } ] }
  },
  "log_transaction": {
    "in":  { "employee_email": "str", "target_system": "str", "status": "str", "error_message": "str?" },
    "out": { "logged": "bool" }
  },
  "get_failed_provisioning_events": { "in": {}, "out": [ { "...": "audit record" } ] }
}
```

**Resources (read-only observability):**
```jsonc
{
  "onboarding://metrics":       { "total_transactions": "int", "failures": "int", "success_rate": "float" },
  "onboarding://failed-events": [ { "timestamp": "...", "email": "...", "system": "...", "status": "FAILED", "error": "..." } ]
}
```

**Security of the MCP layer:** authenticate callers via mTLS or signed API keys; expose
the **minimum** tool surface; enforce per-tool authorization (e.g. only the onboarding
agent may call `orchestrate_onboarding`); validate every argument (the `log_transaction`
tool rejects non-`@helioshr.com` emails today); rate-limit; and write an audit record
for every tool invocation.

---

## 6. Failure handling, retries, edge cases

- **Per-system retry:** up to 3 attempts with exponential backoff + jitter; each attempt
  is logged. Today's prototype uses a fixed-attempt loop in `orchestrate_onboarding`.
- **Idempotency:** every create is preceded by a lookup; re-running an event never
  creates duplicates (safe to replay from the audit log).
- **Partial failure:** other systems still provision; failed ones open a FreshService
  ticket and surface in `onboarding://failed-events`.
- **Bad LLM output:** schema validation → deterministic fallback to the static matrix.
- **Duplicate / rehire:** detect existing Okta/Google account → reactivate instead of create.
- **Dead-letter / replay:** failed events are retained so IT (or a scheduled job) can
  retry just the failed systems.

---

## 7. What I'd build next
- Replace mock connectors with the real API clients above behind a `Connector` interface.
- Persist audit to an append-only store (S3 + Object Lock/KMS, or a WORM DB).
- Add a human-approval step (Slack interactive / FreshService) for `risk_notes != none`.
- Add unit + integration tests and CI; contract-test each connector against sandboxes.
