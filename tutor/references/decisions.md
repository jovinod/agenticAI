# Decision Cheat Sheet

For each fork, options + trade-offs + default recommendation. Always re-check against the user's actual existing code before applying a recommendation blindly — these are starting points, not overrides.

## Frontend framework
- **Plain HTML/CSS/JS** — right for trivial, no-state apps; wrong here because polling/loading-state/report-rendering gets messy fast without component state.
- **React + Vite** (recommended) — teaches real frontend state management (submit → poll → result), minimal build tooling, deploys easily as a static build. Use plain `useState`, no Redux/Router needed for a single-page flow.
- **Streamlit/Gradio** — fastest to a working UI, but not a real SPA and limits learning frontend/backend separation, which is a stated goal here.
- **Next.js** — more than needed for a single input page; adds SSR/routing complexity with no payoff at this scale.

## Backend queue
- **Local Redis list / simple Python queue lib (e.g. `arq`)** for Phase 2 dev — recommended starting point, swap later.
- **Azure Service Bus** — production target for Phase 9, once containerized.
- Avoid Celery unless the user already knows it — `arq` (asyncio-based) fits FastAPI more naturally.

## Agent orchestration framework
- **LangGraph** (recommended) — strongest current support for stateful, multi-node, parallel-branch agent graphs; explicit state object matches the "shared memory between agents" need.
- **CrewAI** — simpler mental model for role-based agents, less control over graph structure/parallelism.
- **Raw Python (no framework)** — most learning value on the "how orchestration actually works" front, but slower to build; consider if the user wants to understand internals before adopting an abstraction.

## LLM hosting
- **Azure AI Foundry** (user's explicit choice) — model deployment, prompt management, tracing/evaluation in one place; use its built-in tracing for Phase 8 rather than bolting on a separate tracer initially.

## Auth
- **User-facing:** API key for simplest MVP; JWT if the user wants real login/session semantics later.
- **Service-to-service (backend → Azure services):** Managed Identity — no secrets/keys in code or env files.

## Local dev ports (machine-specific)
- Redis: **`localhost:6380`**, not the standard 6379 — an unrelated container (`infra-redis-1`, different project) already holds 6379 on this machine. Discovered late: `alpha-redis` had silently failed to bind 6379 the whole time (requested vs. actual port bindings didn't match — `docker inspect`'s `NetworkSettings.Ports` was empty despite `HostConfig.PortBindings` looking correct), so the backend had actually been talking to `infra-redis-1` all along without erroring. Fixed by moving to 6380 and passing `RedisSettings(port=6380)` explicitly in both `backend/api/main.py` and `backend/worker/worker.py` instead of relying on the default. **Lesson: after any `docker run -p`, verify with `docker inspect <name> --format '{{json .NetworkSettings.Ports}}'` that the binding actually took — `docker ps`/`docker start` succeeding is not proof the port bound.**
- Postgres: **`localhost:5433`**, not the standard 5432 — an unrelated container (`infra-postgres-1`, different project) already holds 5432 on this machine. Don't "fix" this to 5432 without checking that container is still there.

## Database library
- **SQLModel** (recommended, in use) — combines Pydantic (already used for `ResearchRequest`) with SQLAlchemy underneath; one class can define both API shape and DB table. Built by FastAPI's author, standard pairing for FastAPI apps.
- Alternatives considered: raw `psycopg` + hand-written SQL (most transparent, more boilerplate); plain SQLAlchemy (mature, more verbose setup than SQLModel). Not chosen — SQLModel builds on what's already known rather than introducing a separate modeling system.

## Why Postgres (not SQLite/MySQL/MongoDB)
- Relational data (jobs/tickers/reports/costs, all connected) + multiple independent processes (API, worker) needing safe concurrent access → rules out SQLite (single-writer, file-based, not multi-process safe).
- Data is naturally tabular, not document-shaped → rules out MongoDB/NoSQL.
- Postgres over MySQL mainly for its stronger extension ecosystem (e.g. `pgvector` for future agent-memory/embedding use) — otherwise roughly equivalent; this was already the architecture's locked-in choice from `phases.md`, not a fresh decision.

## Azure regions & resource groups
- **Resource groups:** one shared RG per environment (`alpha-rg` for now), not one per component (frontend-rg/backend-rg/db-rg). Per-component RGs are an enterprise/multi-team pattern (separate billing/RBAC boundaries) — unnecessary overhead for a single-team project; RG is a lifecycle boundary ("created/torn down together"), not a component boundary.
- **Static Web Apps region:** doesn't meaningfully affect latency — content is served via global CDN regardless of the region picked at creation (that setting is really just deployment metadata location). Using **East Asia** (closest of SWA's short fixed region list to India).
- **Everything else (Container Apps, Postgres, Service Bus, Redis) from Phase 2 on:** region matters here for real — use **Central India (Pune)**, most fully-featured India region for these services. South/West India support fewer service types.

## Hosting/scaling
- **Azure Container Apps** (recommended over VM Scale Sets) — built-in autoscaling on HTTP or queue-depth triggers, less infra to manage than raw VMs/K8s, fits a two-service (API + worker) architecture well.
- VM Scale Sets / AKS — more control, much more operational overhead; not needed at this project's scale and adds learning surface area that isn't on the user's stated list.
