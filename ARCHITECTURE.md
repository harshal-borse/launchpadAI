Architecture diagram (Mermaid) and notes

Mermaid diagram:

```mermaid
flowchart LR
  Workday[Workday (HRIS)] -->|Activation webhook| MCP[MCP Server (FastMCP)]
  MCP --> LLM[LLM (Claude / external)]
  MCP --> Orchestrator[Onboarding Orchestrator]
  Orchestrator -->|Provision API calls| Okta[Okta]
  Orchestrator -->|Provision API calls| GWS[Google Workspace]
  Orchestrator -->|Provision API calls| Slack[Slack]
  Orchestrator -->|Provision API calls| Jira[Jira]
  Orchestrator -->|Provision API calls| Fresh[FreshService]
  Orchestrator --> Audit[Audit store / logs]
  LLM -->|policy decisions & exceptions| Orchestrator
  Admin[Admin Console / People Ops] -->|review/audit| Audit
```

Notes:

- MCP server exposes tools/resources to LLM and automation tooling securely (tool endpoints, metrics, failed-events).
- LLM used for access decisions, exception triage, and generating human-facing messages.
- Orchestrator handles retries, error handling, and writes to audit logs; real connectors would be implemented as isolated microservices, n8n workflows, or dedicated integration services.
- The included `helioshr-onboarding-workflow.json` represents an n8n implementation option for the same onboarding flow.
- The Python prototype and the n8n workflow are complementary implementations: the Python code proves the orchestration and audit design, while the n8n JSON proves the flow can be expressed in a low-code automation platform.
