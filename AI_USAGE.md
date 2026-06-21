AI Usage Statement

This project was completed using a mix of manual work and AI-assisted drafting.

What I used AI for:
- Copilot CLI / ChatGPT: generated Python scaffolding, FastMCP tool structure, and mock orchestration logic.
- Copilot CLI / ChatGPT: suggested phrasing and helped with README content.
- Google AI: helped create the architecture diagram image by describing the complete onboarding architecture and data flows.

What I wrote myself:
- The overall solution design and architecture decisions.
- The main Python prototype logic in `main.py`, including Workday event simulation, LLM integration hook, retry/error handling, audit logging, and MCP resource definitions.
- The n8n workflow file `helioshr-onboarding-workflow.json` and its sequence of trigger, LLM, provisioning, and notification steps.
- The Python prototype in `main.py` and the explanation of how it complements the n8n workflow.
- The technical writeup and executive summary content in TECHNICAL_WRITEUP.md and EXEC_SUMMARY.md.
- The README setup and run instructions.
- The final review and editing to make the deliverables sound natural and human-written.

Validation and judgment:
- I reviewed and refined all AI-generated content manually.
- I made sure the project stayed credential-free and used deterministic fallbacks where needed.
- I chose not to use AI for credential-sensitive or production-specific connector implementation, because the assignment assumes no live credentials are available.

Notes:
- The architecture image was created with Google AI after I explained the full architecture, including Workday, MCP server, LLM, onboarding orchestration, target systems, and audit review flow.