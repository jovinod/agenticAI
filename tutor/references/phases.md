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
   ├─▶ Durable workflow engine (checkpointed multi-agent execution)
   │      │
   │      ├─▶ Context Assembler (gathers memory + retrieved docs + tool results, fits context window)
   │      │      │
   │      │      ├─ Guardrails (input: injection/PII checks; output: content safety)
   │      │      ├─ calls Azure AI Foundry (model + tracing)
   │      │      ├─ calls MCP tools (stock data, news) — credentials from Azure Key Vault
   │      │      ├─ loads Skills (reusable capability modules)
   │      │      └─ reads/writes memory:
   │      │           ├─ Redis — short-term (this job/conversation)
   │      │           ├─ Vector DB (pgvector) — long-term/semantic (searchable facts/docs)
   │      │           └─ Postgres — profile memory (durable user/entity facts) + job status + token/cost logs
   │      │
   │      └─▶ Checkpoint Store (Postgres) — records completed steps, enables resume-not-restart
   │
   └─▶ App Insights / OpenTelemetry (logs, traces, metrics) ──▶ feedback loop → prompt/routing improvements

Return path: Worker → Postgres (status/result) → FastAPI (poll, or stream — see Phase 12) → frontend
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
Build: pick data sources (e.g. `yfinance` for price/fundamentals, a news API/search for news). Test as plain functions first, then via an MCP server (use an existing community MCP server if one exists before building custom). Real data sources need real credentials (e.g. a news API key) — introduce **Azure Key Vault** here for storing them, rather than plain env vars. This is the first genuine secret this project has that Managed Identity can't cover on its own (a third-party API doesn't know what Managed Identity is); Phase 8 formalizes the pattern.
**Deploy & verify:** MCP server runs alongside/within the worker's Container App (or as its own Container App if it makes sense to isolate it). Confirm the deployed worker can call the MCP tool and get real data back — check via logs, not just locally. Confirm the API key is read from Key Vault, not sitting in a Container App env var in plain text.

## Phase 4 — First agent: Azure AI Foundry + tool-calling + token/cost logging
Concepts: LLM tool-calling loop, Foundry model deployment, tracking tokens/cost per call, and the **Context Assembler** — before every LLM call, something has to gather memory + retrieved docs + tool results and trim it to fit the model's context window. Name and build this as its own explicit piece; don't let it become unexamined glue code that "just happens" between the tool call and the prompt.
Build: deploy a model in Azure AI Foundry. Write one agent: given a ticker, decide which tool(s) to call, get data, summarize. Build the Context Assembler as a distinct function/module the agent calls before each LLM invocation. Log token usage + estimated cost per call into Postgres.
**Deploy & verify:** replace the Phase 2 stub with this real agent in the deployed worker. Submit a job on the live URL, confirm a real Foundry-generated summary comes back, and confirm a cost/token row appears in Postgres.

## Phase 5 — Multi-agent + Skills + real three-tier memory
Concepts: multi-agent orchestration (LangGraph), Skills (reusable capability modules loaded by any agent, not duplicated per agent), and the real three-tier memory model production agent systems need — not just "Redis vs. Postgres":
- **Short-term (Redis)** — what's happening in this job/conversation right now, ephemeral, cleared after.
- **Long-term / semantic (Vector DB)** — facts and docs the agent can search *by meaning*, not by exact key lookup. We already chose Postgres partly for its `pgvector` extension support (see `decisions.md`) — use it here rather than standing up a separate vector database service.
- **Profile memory (Postgres, plain tables)** — durable facts about the user/entity, queried directly by key, not searched semantically. Distinct from job-status rows and distinct from the vector-indexed table above.
Build: split into agents (News, Fundamentals, Technical, Risk, Synthesizer or similar). Structure a `skills/` folder for shared reusable logic (see `project-structure.md`). Parallel branches feed a Risk agent → Synthesizer. Wire in **Azure Cache for Redis** for short-term in-job state, enable `pgvector` on the existing Postgres for semantic recall, and add a dedicated profile-memory table distinct from job status.
**Deploy & verify:** deployed worker now runs the full multi-agent graph. Confirm a live job produces a multi-section report, that a second request can semantically recall relevant facts from a prior run (not just an exact-match lookup), and that profile-style facts persist across unrelated jobs.

## Phase 6 — Checkpointing & durable workflows
Concepts: when a multi-step agent task crashes partway through, it needs to **resume from where it left off, not restart from scratch**. This requires a dedicated **Checkpoint Store** (recording each step's completed state as the graph progresses) and evolving the current fire-and-forget Service Bus + Worker model into something closer to a durable workflow engine (e.g. Temporal, or an Azure-native equivalent) that can pause, persist, and resume mid-execution — not just "retry the whole job," which is Phase 7's concern.
Build: add checkpointing to the Phase 5 multi-agent graph — after each agent node completes, persist its output/state to Postgres (the Checkpoint Store). Simulate a mid-graph crash (kill the worker process deliberately after one agent finishes) and confirm a restarted worker resumes from the last completed step, not the beginning.
**Deploy & verify:** on the live deployment, deliberately kill the worker mid-job and confirm the job resumes and completes correctly from its last checkpoint, rather than being lost or restarted from scratch.

## Phase 7 — Resilience
Concepts: retries/backoff, partial failure, dead-letter handling. Distinct from Phase 6: checkpointing is about not losing *all* progress when something crashes mid-workflow; resilience is about individual tool/agent calls failing and the system degrading gracefully rather than crashing outright.
Build: retry logic around tool/agent calls; simulate a failure (bad ticker, kill a dependency) and confirm graceful partial results instead of a crash; failed-job tracking.
**Deploy & verify:** on the live deployment, deliberately break one data source (e.g. bad API key temporarily) and confirm the deployed system still returns a partial report, not a 500 or a stuck job.

## Phase 8 — Auth & trust boundaries
Concepts: user-facing auth (API key/JWT) vs. service-to-service auth (Managed Identity), trust boundary — what the browser is allowed to touch vs. what only the backend touches. Also formalizes **Azure Key Vault** (first introduced in Phase 3): Managed Identity covers everything that supports it (Postgres, Service Bus, Foundry, Redis); Key Vault covers everything that doesn't (third-party API keys for MCP tools). Together, no secret should exist in code or plain env vars anywhere in the system.
Build: add auth to the FastAPI endpoints; switch backend→Azure service calls to **Managed Identity**; move any remaining third-party credentials into **Key Vault**, granted to the Container Apps via their Managed Identity; document the trust boundary.
**Deploy & verify:** confirm the deployed frontend must authenticate to call the API; confirm (via Azure portal/logs) the backend containers use Managed Identity, not embedded keys, for both Azure services and Key Vault access.

## Phase 9 — Guardrails
Concepts: checks on what goes *into* the LLM (prompt injection attempts, PII in user input) and what comes *out* (unsafe or incorrect content) before it ever reaches the user. Distinct from Phase 8: that phase is an access-control boundary (who's allowed to call what); this phase is a content-safety boundary (what's allowed to flow through, regardless of who sent it).
Build: input-side checks before a request reaches an agent (basic prompt-injection pattern detection, PII scrubbing); output-side checks before a report reaches the user (Azure AI Foundry has built-in content safety features — use those rather than hand-rolling a filter).
**Deploy & verify:** on the live deployment, deliberately submit a prompt-injection-shaped input and confirm it's caught/neutralized before reaching the agent, not silently passed through.

## Phase 10 — Observability
Concepts: tracing, structured logging, metrics — and closing the loop. Observability that's purely one-way (write logs, nobody reads them back into decisions) is only half the system.
Build: enable Azure AI Foundry tracing; add Application Insights + OpenTelemetry to FastAPI/worker. As a closing step, use the gathered traces/metrics to inform at least one real improvement (e.g. a prompt tweak or routing change based on observed failure patterns) — a small, concrete feedback-loop example, not just a dashboard nobody acts on.
**Deploy & verify:** on the live system, pick a real job_id and reconstruct its full lifecycle from Azure Portal/App Insights — queue time, each agent's duration, tokens used, total cost. Document the one improvement made from this data.

## Phase 11 — Scaling validation
Concepts: autoscaling triggers (HTTP traffic vs. queue depth) — already deployed on Container Apps since Phase 2, this phase is about *proving* it scales, and tuning it.
Build: load-test by submitting many jobs at once (script it, or several tickers rapid-fire). **Also graduate the Phase 3 MCP search server** from Option A (stdio, spawned in-process by the worker — chosen deliberately in Phase 3 to focus on protocol mechanics first) to Option B (its own Container App, HTTP transport, independently autoscaled) — this is the natural point to prove it scales independently from ticker-processing load, and to make it reusable by any future consumer without duplicating the subprocess-spawning logic.
**Deploy & verify:** watch worker container count scale up in Azure Portal under load, then scale back down after. Tune min/max replica settings if needed. Confirm the MCP search server (now its own Container App) scales independently too.

## Phase 12 — Polish & final wiring
Build: final UI polish, error states in the frontend for failed jobs, README documenting the deployed architecture. Consider upgrading the current polling-based return path (frontend repeatedly asking "done yet?") to a streaming one (see results incrementally as each agent finishes, not all-or-nothing) — worth being precise that this is an *enhancement*, not a gap-fill, since polling already provides a working return path from day one.
**Deploy & verify:** full live demo, start to finish, from the public Static Web App URL — enter ticker(s), see a real multi-agent report, backed by everything above.

---

## Mapping back to the original goals (confirm nothing is missing)

| Goal | Covered in phase |
|---|---|
| Distributed system (FastAPI + Service Bus + Postgres) | Phase 2 |
| MCP + tool calls | Phase 3 |
| Scaling via containers | Phase 2 (deploy), Phase 11 (validate) |
| Context & memory — short-term (Redis), semantic (pgvector), profile (Postgres) | Phase 5 |
| Context Assembler | Phase 4 |
| Checkpointing / durable workflows | Phase 6 |
| Pricing & tokens | Phase 4 |
| Trust boundaries & auth (Managed Identity + JWT) | Phase 8 |
| Secrets Vault (third-party API keys) | Phase 3 (introduced), Phase 8 (formalized) |
| Guardrails (input/output safety) | Phase 9 |
| Skills (reusable modules) | Phase 5 |
| Observability + feedback loop | Phase 10 |
| LLM via Azure AI Foundry | Phase 4 |
| Entire workflow server-side (thin client) | Enforced from Phase 2 onward — frontend never talks to anything but FastAPI |
| Hosted + scaled FastAPI | Phase 2 (deploy), Phase 11 (scale validation) |
| Return path (streaming) | Phase 12 (enhancement over the working polling return path) |
| Human-in-the-loop | Not built — no risky/irreversible action exists in this app's current scope (read-only research). Documented as a concept in `decisions.md`; revisit if scope grows to include actions taken on the user's behalf. |
