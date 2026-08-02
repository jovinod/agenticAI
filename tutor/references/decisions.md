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

## Hosting/scaling
- **Azure Container Apps** (recommended over VM Scale Sets) — built-in autoscaling on HTTP or queue-depth triggers, less infra to manage than raw VMs/K8s, fits a two-service (API + worker) architecture well.
- VM Scale Sets / AKS — more control, much more operational overhead; not needed at this project's scale and adds learning surface area that isn't on the user's stated list.
