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

## The book (standing project, started 2026-08-15)
- Format: markdown files in this repo, `book/` directory, one chapter per Phase — not a separate tool (mdBook/Docusaurus) or external doc system, at least to start.
- Code references: inline snippets + plain file path mentions (e.g. "see `frontend/src/App.jsx`"), not GitHub permalinks to specific commit SHAs — simpler, doesn't break if files later change, chosen over more rigorous permalinks for now.
- Depth: curated narrative, not a transcript — concepts, decisions + reasoning, code, gotchas, written as a coherent chapter. Actively synthesized, not a reformatted copy-paste of the actual back-and-forth.
- Starting point: one full sample chapter (Phase 1) first, for review/approval before writing the rest — avoids redoing a lot of work if the first attempt misses what the user actually wants.
- Phase 0 (the audit — minimal content, repo was empty) folded into Chapter 1's opening rather than given its own chapter.
- **Two recurring sections, required in every chapter from now on, added after Chapter 1's first draft was reviewed:**
  1. **"Azure Components Used This Chapter"** — what Azure resources got introduced this chapter specifically, what each one is, and why it fits. Keep scoped to *this chapter's* new resources, not a recap of everything so far.
  2. **"The Architecture So Far"** — **corrected after a second round of feedback**: this diagram must show *only what's actually been built by that point in the story* — no preview of future pieces, not even grayed out. Each chapter *adds* new nodes for whatever it actually built (don't redesign/reshuffle what already existed in earlier chapters — grow it). From Chapter 2 onward, distinguish nodes carried over from earlier chapters vs. genuinely new this chapter (two `classDef` styles — e.g. `existing` solid green, `new` a brighter/highlighted green — both still "live," just visually marking what's fresh). By the final chapter, the diagram should look like the real target architecture, arrived at incrementally, not revealed all at once in Chapter 1 with placeholders.

## Reusing `/Users/vinodjoshi/Work/Repos/buynobuy` for Phase 3+
- Prior project: agentic stock analysis, LangGraph + local LLMs (Ollama/Groq) + yfinance + Tavily + BeautifulSoup scraping. No MCP used (confirmed via full codebase survey).
- **Reuse the patterns and the working pieces, not the scaffolding**: `skills/utils/search.py`'s Tavily→DuckDuckGo→Playwright/Bing fallback chain and `agents/utils.py`'s LLM-JSON-cleanup helpers are genuinely portable. The Trendlyne/NSE/AmbitionBox scrapers are India-specific and not reused as-is (though useful reference if India-market depth beyond `yfinance` is ever needed). The sync Flask + local file-based caching/run-storage model is superseded entirely by our Postgres/Redis/Service Bus architecture.
- **Market scope**: `alpha` covers both US and India. User explicitly chose an **explicit market selector** (US/India, user-picked) over auto-detection/fallback-across-regions — cleaner, fails clearly on a mismatch instead of silently guessing. `yfinance` alone covers both (`.NS`/`.BO` suffixes for NSE/BSE) — start there; only reach for something like StockAnalysis.com or India-specific scraping if `yfinance`'s Indian data proves too thin (not decided yet, no need to build ahead of that).
- **`yfinance` reliability note**: free, but unofficial (reverse-engineers Yahoo's own site) — no SLA, no documented rate limits, real risk of breaking or being throttled at scale, especially from a shared cloud IP. Flagged, accepted for now, revisit in Phase 7 if it becomes a real problem.
- **LangGraph/orchestration**: buynobuy genuinely does use LangGraph for real phase-level multi-agent orchestration (which agents run when, parallel fan-out/fan-in) — confirmed, not a wrong impression. What's *not* live is a finer-grained ReAct tool-selection loop *within* an individual agent (present in the codebase but vestigial/unused). Deliberately **not** pulling full multi-agent orchestration learning forward into Phase 3 — it needs multiple real agents to exist first (Phase 4), so doing it now would be the actual force-fit. Sequenced properly into Phase 5, where `phases.md` already named it, using buynobuy's real `StateGraph` pattern as reference at that point.
- **Terminology, precise**: a "tool"/"function call" specifically means an LLM decides at runtime to invoke it. A "direct API call" (our `fetch_stock_data`) is called deterministically by our own code — no LLM decision involved, appropriate when there's no real judgment call about *whether* to fetch (we always want price data). A "Skill" (our project's own vocabulary) is a reusable capability module loadable by any agent — distinct from both.

## ⚠️ Container Apps + `:latest` tag — silent stale-deployment trap (real incident, 2026-08-15)
- `az containerapp update --image ...:latest` does **not** reliably create a new revision when the image *reference string* is unchanged, even though the actual image *content* behind that mutable tag changed (new digest pushed to ACR). Azure appears to treat "same image string" as "no configuration change" and skips creating a new revision — the old container keeps running, never re-pulling.
- **What actually happened**: rebuilt + pushed both images with real Phase 3 code (yfinance, market selector, risk-flag skill), ran the normal `az containerapp update --image ...:latest` for both, got a success response — but both apps kept running their **Aug 12 revision** (Phase 2-era fake-stub code) for 3 days of "deployed" work. Only caught because live test results showed the old fake "looks solid, no major red flags" text instead of real data — **would have silently declared Phase 3 deployed while it wasn't**, had the output not been checked carefully against what was actually expected.
- **Standing practice from now on, every deploy**: always pass `--revision-suffix <something-unique>` (e.g. a timestamp) on `az containerapp update --image` calls — forces a genuinely new revision regardless of whether the tag string looks unchanged. **And always verify** via `az containerapp revision list` that (a) a new revision with a recent `CreatedTime` actually appears, and (b) the old revision's replica count drops to 0 / it deactivates, before trusting a "deployed" claim — don't just trust the update command's success response.
- Also worth remembering: for the **worker** specifically (no ingress, no traffic-weight concept), briefly having both old and new revisions with active replicas means both are competing for the same Service Bus messages simultaneously — a real source of "which code actually processed this" confusion if not caught quickly. Container Apps did scale the old one down automatically within a few seconds in this incident, but don't assume that's instant — verify.

## MCP Python SDK naming — `FastMCP` renamed to `MCPServer`
- The installed `mcp` package (v2.0.0+) has no `mcp.server.fastmcp.FastMCP` — that's the name used in older docs/tutorials. Current path: `from mcp.server.mcpserver import MCPServer`. Same decorator-based API otherwise (`.tool()`, `.run()`). No backward-compat alias exists — if following older MCP examples, expect this exact import to fail.
- `load_dotenv()` inside an MCP server meant to be spawned as a subprocess needs a **file-relative** path (`pathlib.Path(__file__).parent / ".env.local"`), not a bare relative one — the subprocess's working directory isn't guaranteed to match wherever the client happens to be run from. Same fix `buynobuy` already used for the identical problem.

## MCP search server — local shape now, real shape later
- Chose Option A (stdio transport, spawned in-process by the worker) for the Phase 3 build — simplest, keeps focus on protocol mechanics rather than deployment topology.
- **Deliberately deferred to Phase 11 (Scaling validation)**: graduate to Option B — its own Container App, HTTP transport, independently autoscaled. User explicitly asked this not be forgotten.

## Local env vars — `.env.local` + `python-dotenv` (backend/worker)
- Adopted once the list of required local env vars grew past "just type them by hand each time" (`DATABASE_URL`, `SERVICEBUS_CONNECTION_STRING`, `REDIS_*`, `TAVILY_API_KEY`). Matches `buynobuy`'s own convention.
- Gitignored, never committed. `load_dotenv(".env.local")` at the top of `worker.py` — no-ops harmlessly if the file doesn't exist (i.e. in Azure, where Container Apps sets real env vars directly) and doesn't override an already-set env var if one exists.
- Not yet added to `backend/api` — only introduced where the immediate need (Tavily key) was, not scope-crept to the other service.

## Human-in-the-loop (not built — documented for later)
- Concept: a pause/approval gate before an agent takes a risky or irreversible action (payments, deletions, sending something on the user's behalf, etc.).
- **Not needed for this app's current scope** — stock research is read-only; there's no risky action for anything to gate. Not a phase, not built.
- Revisit if the app's scope ever grows to include an agent *acting* on the user's behalf (e.g. placing a trade), not just reporting.

## Azure Cache for Redis is retiring — use Azure Managed Redis instead
- `az redis create` now fails outright: "Azure Cache for Redis is retiring, create Azure Managed Redis instance instead." Use `az redisenterprise create` (cluster) + `az redisenterprise database create` (a separate sub-resource, same two-step shape as Postgres server + database).
- Real differences from the classic service, all of which cost debugging time the first time: default port is **10000**, not 6379/6380; `accessKeysAuthentication` defaults to **Disabled** (pushes toward Azure AD/Managed Identity auth) — enable explicitly with `az redisenterprise database update --access-keys-authentication Enabled` if using key-based auth for now, matching how Postgres is currently handled (password now, Managed Identity formalized together in Phase 8 — kept consistent rather than introducing a one-off Entra ID token-refresh flow for just this one resource).
- Cheapest SKU is `Balanced_B0` (not a "Basic" tier name like the classic service).

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
