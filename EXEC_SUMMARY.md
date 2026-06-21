Executive Summary — HeliosHR Onboarding Automation

What it does (plain language)
- Automatically provisions new hires with the right accounts and tools shortly after HR marks them active in Workday. Reduces manual steps and start-day friction.

What it will improve & metrics
- Time-to-first-access: target reduce from 3–5 business days to <1 business day (measure via metrics endpoint).
- Error rate: lower provisioning failures via automated retries and LLM triage.
- Operational load: fewer manual tickets and faster onboarding completion.

Risks & limitations
- Needs secure credentials for real systems; prototype uses simulated connectors.
- LLM decisions require guardrails — outputs must be validated and auditable.
- Edge-case approvals may still need human review.

What People Ops needs to know
- This integrates with Workday and automates account creation for core systems. People Ops can review failed events via the audit endpoint and set policy in the RBAC service.
- The prototype includes both a Python/MCP implementation and an n8n workflow spec (`helioshr-onboarding-workflow.json`) for low-code deployment.
- The Python code and n8n workflow describe the same onboarding process in two forms: backend orchestration and low-code automation.
- To deploy to production: provide service accounts, approve scopes, and define access templates per role/department.

Call to action
- Approve a small pilot (Engineering hires) and provide test service accounts for Okta, Google Workspace, and Slack.
