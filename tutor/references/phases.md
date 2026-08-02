# Build Phases — Stock Research Multi-Agent System

**Core rule for this project: build one layer → deploy it to Azure → see it work live → THEN move to the next layer.**
Do not batch multiple layers before deploying. Each phase below ends with a "Deploy & verify" step — never skip it, even though it's slower. This is intentional: the user is learning cloud deployment incrementally, not just building locally and shipping once at the end.

This maps directly to the target architecture:

```
Web page (React SPA, Azure Static Web Apps)
   │ (JWT/API key auth)
   ▼
FastAPI (Container App, autoscale on HTTP)
   │  writes job → Azure Service Bus queue
   ▼
Worker (Container App, autoscale on queue depth)
   │
   ├─▶ LangGraph multi-agent flow
   │      ├─ calls Azure AI Foundry (model + tracing)
   │      ├─ calls MCP tools (stock data, news)
   │      ├─ loads Skills (reusable capability modules)
   │      └─ reads/writes Redis (short-term memory) + Postgres (long-term memory, job status, token/cost logs)
   │
   └─▶ App Insights / OpenTelemetry (logs, traces, metrics)
```

Every box in that diagram is a phase below. Every arrow gets tested live on Azure before moving to the next box.

---

## Phase 0 — Audit existing project
Understand current structure, language/framework, any existing LLM/agent code, what's reusable. Set up (or confirm) the target folder structure — see `references/project-structure.md`.
**Done when:** written summary of current state + repo matches the target structure skeleton (empty folders are fine at this point).

## Phase 1 — Frontend shell (local only, no backend yet)
Concepts: SPA state (input → loading → result), why React+Vite over alternatives (see `decisions.md`).
Build: ticker input (multi-ticker support) → submit → fake job_id → fake polling → fake report view. Everything hardcoded/mocked, no network calls yet.
**Deploy & verify:** deploy this static build to **Azure Static Web Apps** now, even though it's fake. Get a live URL. Confirm the mocked flow works from that public URL. This is the user's first real Azure deploy — keep it simple, this is the point.

## Phase 2 — Backend skeleton: FastAPI + queue + Postgres (distributed system core)
Concepts: queues, workers, async job processing, why a queue instead of direct request/response for slow work.
Build locally first: FastAPI `POST /research` → pushes job to a queue → worker process pulls it → writes status to Postgres → `GET /research/{job_id}` for polling. Worker logic is a stub (fake delay + fake text).
**Deploy & verify:** containerize FastAPI + worker, stand up **Azure Service Bus** (queue) and **Azure Database for PostgreSQL**, deploy both containers to **Azure Container Apps**. Point the Phase 1 frontend's mocked calls at this real API instead. Confirm end-to-end on the live URL: submit → real job_id → real status transition → fake result, all over the internet, not localhost.

## Phase 3 — MCP tools + real data
Concepts: MCP (Model Context Protocol) — standard way for an agent to call external tools/data without hardcoding each integration.
Build: pick data sources (e.g. `yfinance` for price/fundamentals, a news API/search for news). Test as plain functions first, then via an MCP server (use an existing community MCP server if one exists before building custom).
**Deploy & verify:** MCP server runs alongside/within the worker's Container App (or as its own Container App if it makes sense to isolate it). Confirm the deployed worker can call the MCP tool and get real data back — check via logs, not just locally.

## Phase 4 — First agent: Azure AI Foundry + tool-calling + token/cost logging
Concepts: LLM tool-calling loop, Foundry model deployment, tracking tokens/cost per call.
Build: deploy a model in Azure AI Foundry. Write one agent: given a ticker, decide which tool(s) to call, get data, summarize. Log token usage + estimated cost per call into Postgres.
**Deploy & verify:** replace the Phase 2 stub with this real agent in the deployed worker. Submit a job on the live URL, confirm a real Foundry-generated summary comes back, and confirm a cost/token row appears in Postgres.

## Phase 5 — Multi-agent + Skills + memory
Concepts: multi-agent orchestration (LangGraph), Skills (reusable capability modules loaded by any agent, not duplicated per agent), short-term memory (Redis, within a job) vs. long-term memory (Postgres, across jobs).
Build: split into agents (News, Fundamentals, Technical, Risk, Synthesizer or similar). Structure a `skills/` folder for shared reusable logic (see `project-structure.md`). Parallel branches feed a Risk agent → Synthesizer. Wire in **Azure Cache for Redis** for in-job state.
**Deploy & verify:** deployed worker now runs the full multi-agent graph. Confirm a live job produces a multi-section report and that a second request for the same ticker can reference Postgres-stored history from the first.

## Phase 6 — Resilience
Concepts: retries/backoff, partial failure, dead-letter handling.
Build: retry logic around tool/agent calls; simulate a failure (bad ticker, kill a dependency) and confirm graceful partial results instead of a crash; failed-job tracking.
**Deploy & verify:** on the live deployment, deliberately break one data source (e.g. bad API key temporarily) and confirm the deployed system still returns a partial report, not a 500 or a stuck job.

## Phase 7 — Auth & trust boundaries
Concepts: user-facing auth (API key/JWT) vs. service-to-service auth (Managed Identity), trust boundary — what the browser is allowed to touch vs. what only the backend touches.
Build: add auth to the FastAPI endpoints; switch backend→Azure service calls (Postgres, Service Bus, Foundry, Redis) to **Managed Identity**, removing any secrets from code/env files; document the trust boundary.
**Deploy & verify:** confirm the deployed frontend must authenticate to call the API; confirm (e.g. via Azure portal / logs) the backend containers are using Managed Identity, not embedded keys.

## Phase 8 — Observability
Concepts: tracing, structured logging, metrics.
Build: enable Azure AI Foundry tracing; add Application Insights + OpenTelemetry to FastAPI/worker.
**Deploy & verify:** on the live system, pick a real job_id and reconstruct its full lifecycle from Azure Portal/App Insights — queue time, each agent's duration, tokens used, total cost.

## Phase 9 — Scaling validation
Concepts: autoscaling triggers (HTTP traffic vs. queue depth) — already deployed on Container Apps since Phase 2, this phase is about *proving* it scales, and tuning it.
Build: load-test by submitting many jobs at once (script it, or several tickers rapid-fire).
**Deploy & verify:** watch worker container count scale up in Azure Portal under load, then scale back down after. Tune min/max replica settings if needed.

## Phase 10 — Polish & final wiring
Build: final UI polish, error states in the frontend for failed jobs, README documenting the deployed architecture.
**Deploy & verify:** full live demo, start to finish, from the public Static Web App URL — enter ticker(s), see a real multi-agent report, backed by everything above.

---

## Mapping back to the original goals (confirm nothing is missing)

| Goal | Covered in phase |
|---|---|
| Distributed system (FastAPI + Service Bus + Postgres) | Phase 2 |
| MCP + tool calls | Phase 3 |
| Scaling via containers | Phase 2 (deploy), Phase 9 (validate) |
| Context & memory (Redis + Postgres) | Phase 5 |
| Pricing & tokens | Phase 4 |
| Trust boundaries & auth (Managed Identity + JWT) | Phase 7 |
| Skills (reusable modules) | Phase 5 |
| Observability (Foundry tracing + App Insights) | Phase 8 |
| LLM via Azure AI Foundry | Phase 4 |
| Entire workflow server-side (thin client) | Enforced from Phase 2 onward — frontend never talks to anything but FastAPI |
| Hosted + scaled FastAPI | Phase 2 (deploy), Phase 9 (scale validation) |
