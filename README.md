# Stock Research Assistant

An agentic AI application that researches stocks: a frontend, a backend API,
a queue-based worker, an embedding worker, and an MCP search service, deployed
to Azure via the infra scripts.

- `frontend/` — the web UI
- `backend/api` — the backend API
- `backend/worker` — background job processing
- `backend/embed-worker` — embedding generation
- `backend/mcp-search` — MCP-based search tool
- `infra/` — Azure deployment scripts (Bicep)
