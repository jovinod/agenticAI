# Alpha — Agentic Stock Research System

A distributed multi-agent stock research system: enter one or more tickers in a
React SPA, and a pipeline of agents (news, fundamentals, technical, risk) researches
them and returns a report. Built incrementally, deployed to Azure layer by layer.

Being built with guidance from the `tutor/` skill — see `tutor/references/phases.md`
for the full roadmap and `book/` for a curated, chapter-per-phase account of how it
was built (concept explanations now live there, not in a separate glossary file).

## Status

**Phase 1 — Frontend shell: complete.** **Phase 2 — Backend skeleton: complete.** **Phase 3 — MCP tools + real data: complete.** **Phase 4 — First agent (Azure AI Foundry + tool-calling + token/cost logging): complete.** **Phase 5 — Multi-agent + Skills + real three-tier memory: complete.** Five-agent LangGraph pipeline (Fundamentals/Technical/News/Risk/Synthesizer), genuinely concurrent execution, Azure API Management fronting Foundry, real KEDA autoscaling, Skills genuinely discoverable, and all three memory tiers (short-term/Redis, profile/Postgres, semantic/pgvector via a standalone `/search` feature) — all deployed and verified live. **Phase 6 — Checkpointing & durable workflows: complete.** LangGraph's built-in Postgres checkpointing wired into the research graph, verified against a genuine `az containerapp revision restart` mid-job on the live deployment, not a simulated crash. Next: Phase 7 — Resilience.

## Architecture

```
Web page (React SPA, Azure Static Web Apps)        ← ✅ live
   │ (JWT/API key auth)                             ← not built yet (Phase 8)
   ▼
FastAPI (Container App, autoscale on HTTP)          ← ✅ live (alpha-api, external ingress)
   │  writes job → Azure Service Bus queue
   ▼
Worker (Container App, autoscale on queue depth)    ← ✅ live (alpha-worker, no ingress, min 1 / max 10 replicas) — real KEDA azure-servicebus scale rule, ~1 replica per queued message (messageCount=1, deliberately aggressive — will be reverted closer to 5 near project completion), verified via `az containerapp show` (not just the update command's success)
   │
   ├─▶ Single agent (LangGraph multi-agent flow is Phase 5) ← ✅ live — real bounded async tool-calling loop, deterministic checks run alongside it, not replaced by it
   │      ├─ calls Azure AI Foundry (gpt-5-mini) via Azure API Management ← ✅ live — APIM (Consumption tier) fronts Foundry, authenticates via its own managed identity (worker never holds the raw Foundry key); tracing still Phase 8
   │      ├─ calls MCP tools (stock data, news)           ← both ✅ live — stock data (direct call, yfinance) and Tavily search (real MCP server), model decides when search is worth it
   │      ├─ loads Skills (reusable capability modules)   ← flag_risk_factors ✅ live (deterministic); assess_news_sentiment ✅ live — genuine LLM-discoverable Skill, model discovers + chooses to apply it
   │      └─ reads/writes Redis + Postgres                ← both ✅ live (Redis: per-ticker result cache; Postgres: job status + token/cost log; agent memory proper is still Phase 5)
   │
   └─▶ App Insights / OpenTelemetry                 ← not built yet (Phase 10)
```

This first diagram is the conceptual/application view (matches `phases.md`'s target). Below is a
second, literal view — actual Azure resource names and how they really connect, updated every
phase as real infrastructure gets added. This is the one to check if you want to know "what's
actually deployed right now," rather than "what's the app logically made of."

## Azure Deployment Topology (real resource names — updated every phase)

```mermaid
flowchart TD
    User(["Visitor's browser"])

    subgraph SWA["Static Web App: alpha  (East Asia)"]
        Frontend["React SPA (built files)"]
    end

    subgraph RG["Resource Group: alpha-rg  (Central India unless noted)"]
        subgraph ENV["Container Apps Environment: alpha-env"]
            API["Container App: alpha-api\n(external ingress, port 8000)"]
            subgraph WorkerGroup["Container App: alpha-worker\n(no ingress) — KEDA-scaled: 1-10 replicas,\n1 replica per queued msg"]
                direction LR
                W1["replica"]
                W2["replica"]
                Wdots["···\nup to 10"]
            end
            EmbedWorker["Container App: alpha-embed-worker\n(no ingress) — KEDA-scaled: 0-3 replicas,\n1 replica per 5 queued msgs — separate from\nalpha-worker so a slow/failing embedding call\nnever blocks the research pipeline"]
        end
        ACR["Container Registry: alpharesearchacr\n(images pulled via Managed Identity)"]
        SB["Service Bus Namespace: alpharesearchsb\nqueues: research-jobs, embedding-jobs"]
        PG[("Postgres Flexible Server:\nalpha-research-pg\ndb: alpha — tickerjob, tokenusage,\ntickerprofile, researchreport (pgvector),\ncheckpoints (LangGraph)")]
        Redis[("Managed Redis:\nalpha-research-cache\nport 10000, TLS, key auth")]
        LAW["Log Analytics workspace:\nworkspace-alphargK2N9\n(auto-created by alpha-env)"]
        APIM["API Management: alpha-research-apim\n(Consumption tier, managed identity)"]
        OpenAI["Azure OpenAI: alpha-research-openai (South India)\ndeployments: gpt-5-mini, text-embedding-3-small"]
    end

    User -->|HTTPS| Frontend
    Frontend -->|"HTTPS (VITE_API_URL, baked in at build)"| API
    API -->|"send (send-only key)"| SB
    SB -->|"listen (listen-only key), one msg per replica"| WorkerGroup
    SB -->|"listen (listen-only key), embedding-jobs"| EmbedWorker
    API -->|"read/write (admin user+pass)"| PG
    WorkerGroup -->|"read/write (admin user+pass)"| PG
    WorkerGroup -->|"checkpoint check + write per<br/>super-step (thread_id = job_id:ticker)"| PG
    EmbedWorker -->|"write — vector embedding\n(admin user+pass)"| PG
    API -->|"cache check (read) — access key"| Redis
    WorkerGroup -->|"cache write — access key"| Redis
    WorkerGroup -->|"tool-calling + token/cost logging\nOcp-Apim-Subscription-Key"| APIM
    WorkerGroup -->|"publish report text\n(send-only key), embedding-jobs"| SB
    EmbedWorker -->|"embed report text\nOcp-Apim-Subscription-Key"| APIM
    API -->|"embed search query\nOcp-Apim-Subscription-Key"| APIM
    APIM -->|"managed identity (AAD token)\nno stored key"| OpenAI
    SB -.->|"KEDA polls queue depth\n(same servicebus-conn secret)"| WorkerGroup
    SB -.->|"KEDA polls queue depth"| EmbedWorker
    ENV -.->|pulls images| ACR
    ENV -.->|logs/metrics| LAW
```

## Live URLs

- Frontend: https://nice-water-0e7781500.7.azurestaticapps.net/ (Azure Static Web Apps, `alpha-rg`, East Asia)
- Backend API: https://alpha-api.orangesky-1a62d756.centralindia.azurecontainerapps.io (Azure Container Apps, `alpha-rg`, Central India)

## What's working right now

- Ticker input (comma-separated, multi-ticker) with an explicit US/India market selector — a ticker
  is only looked up in the chosen market, with a clear error on a mismatch rather than guessing.
- Real end-to-end flow: each ticker in a request fans out independently — submit → per-ticker cache
  check (Azure Managed Redis) → cache hit returns instantly, cache miss queues via Azure Service Bus →
  real worker picks it up → status written to Azure Database for PostgreSQL → frontend polls and
  aggregates all tickers' results once every one is done.
- A same-day repeat request for a ticker already computed returns instantly from cache, skipping the
  queue entirely; a request mixing a cached ticker with a fresh one correctly returns the cached one
  immediately while only the fresh one is computed.
- Real stock data (price, P/E, 52-week range) from `yfinance`, plus a rule-based risk-flag Skill
  (near 52-week low, high/negative P/E) — both deterministic, run on every ticker regardless of
  what the agent below decides.
- A real single agent (Azure OpenAI `gpt-5-mini`) that decides, at runtime, which tools to call:
  the same stock-data lookup, a real MCP-backed web search (Tavily), and one genuine
  LLM-discoverable Skill (`assess_news_sentiment`) it can choose to load and apply with its own
  judgment — distinct from the deterministic risk-flag Skill, which it always runs regardless.
- Real narrative summarization: the agent's own synthesized answer is appended to the deterministic
  report as an "AI summary" line — both run side by side, deliberately, not one replacing the other.
- Every real call's token usage and an estimated cost are logged to Postgres (`token_usage` table),
  one row per ticker per job.

## Running locally

```bash
# frontend
cd frontend
npm install
npm run dev

# backend api (needs local Postgres + a Service Bus connection string — see tutor/references/decisions.md)
cd backend/api
uv run uvicorn main:app --reload

# worker
cd backend/worker
uv run python worker.py
```
