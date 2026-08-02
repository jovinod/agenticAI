# Target Project Structure

Keep this structure consistent as the project grows. It doesn't all need to exist on day one — create folders as the relevant phase introduces them (noted below), not all upfront. Always check the user's existing repo layout first and adapt names to match existing conventions rather than forcing a rename.

```
project-root/
├── frontend/                      # Phase 1
│   ├── src/
│   │   ├── components/            # TickerInput, ReportView, StatusPoller, etc.
│   │   ├── api/                   # thin client calling FastAPI only
│   │   └── App.jsx
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── backend/                       # Phase 2 onward
│   ├── api/                       # FastAPI app (public-facing Container App)
│   │   ├── main.py
│   │   ├── routes/
│   │   │   └── research.py        # POST /research, GET /research/{id}
│   │   ├── auth/                  # Phase 7
│   │   └── Dockerfile
│   │
│   ├── worker/                    # Worker process (separate Container App)
│   │   ├── main.py                # pulls from queue, runs agent graph
│   │   ├── agents/                # Phase 5
│   │   │   ├── news_agent.py
│   │   │   ├── fundamentals_agent.py
│   │   │   ├── technical_agent.py
│   │   │   ├── risk_agent.py
│   │   │   ├── synthesizer_agent.py
│   │   │   └── graph.py           # LangGraph wiring
│   │   ├── skills/                # Phase 5 — reusable capability modules
│   │   │   ├── summarize_sentiment/
│   │   │   ├── flag_risk_factors/
│   │   │   └── ...
│   │   ├── tools/                 # Phase 3 — MCP client wrappers per data source
│   │   │   ├── mcp_client.py
│   │   │   └── stock_data.py
│   │   ├── memory/                # Phase 5
│   │   │   ├── redis_store.py     # short-term
│   │   │   └── postgres_store.py  # long-term
│   │   ├── llm/                   # Phase 4
│   │   │   └── foundry_client.py
│   │   ├── observability/         # Phase 8
│   │   │   └── tracing.py
│   │   └── Dockerfile
│   │
│   ├── db/                        # Phase 2
│   │   ├── models.py               # jobs, reports, token_costs tables
│   │   └── migrations/
│   │
│   └── shared/                    # code shared between api/ and worker/
│       └── schemas.py             # pydantic models for job payloads etc.
│
├── mcp-server/                    # Phase 3 — only if building a custom MCP server
│   ├── server.py
│   └── Dockerfile
│
├── infra/                         # Phase 2 onward — Azure deployment configs
│   ├── containerapps/
│   ├── bicep/ (or terraform/)     # infra-as-code, optional but recommended
│   └── deploy.md                  # manual deploy steps if not using IaC yet
│
├── references/                    # this skill's own reference material — do not touch during build
│
└── README.md                      # updated each phase with current architecture + live URLs
```

## Notes

- **`backend/api` vs `backend/worker` are separate Container Apps** — different Dockerfiles, different scaling triggers (HTTP vs. queue depth). Don't merge them into one deployable unit even though they share code via `shared/`.
- **`skills/` folder** — each skill is a self-contained folder (prompt/instructions + any code it needs), loaded dynamically by agents rather than copy-pasted into each agent file. This is what "Skills" means in the architecture table — keep it separate from `agents/`.
- **`infra/`** — start with `deploy.md` (manual `az` CLI steps) in early phases; introduce Bicep/Terraform later if the user wants to learn infra-as-code, but don't force it before it's needed.
- Update the root `README.md` at the end of each phase with: what's deployed, live URLs, and a copy of the current architecture diagram state (which boxes are live vs. not yet built).
