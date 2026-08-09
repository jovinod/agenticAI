# Alpha — Agentic Stock Research System

A distributed multi-agent stock research system: enter one or more tickers in a
React SPA, and a pipeline of agents (news, fundamentals, technical, risk) researches
them and returns a report. Built incrementally, deployed to Azure layer by layer.

Being built with guidance from the `tutor/` skill — see `tutor/references/phases.md`
for the full roadmap and `tutor/references/concepts.md` for concepts explained along
the way.

## Status

**Phase 1 — Frontend shell: complete.** Deployed and verified live on Azure Static Web Apps. Next: Phase 2 — backend skeleton (FastAPI + queue + Postgres).

## Architecture

```
Web page (React SPA, Azure Static Web Apps)        ← ✅ live
   │ (JWT/API key auth)                             ← not built yet
   ▼
FastAPI (Container App, autoscale on HTTP)          ← not built yet
   │  writes job → Azure Service Bus queue
   ▼
Worker (Container App, autoscale on queue depth)    ← not built yet
   │
   ├─▶ LangGraph multi-agent flow                   ← not built yet
   │      ├─ calls Azure AI Foundry (model + tracing)
   │      ├─ calls MCP tools (stock data, news)
   │      ├─ loads Skills (reusable capability modules)
   │      └─ reads/writes Redis + Postgres
   │
   └─▶ App Insights / OpenTelemetry                 ← not built yet
```

## Live URLs

- Frontend: https://nice-water-0e7781500.7.azurestaticapps.net/ (Azure Static Web Apps, `alpha-rg`, East Asia)

## What's working right now

- Ticker input (comma-separated, multi-ticker), with format validation.
- Fully mocked flow: submit → fake job id → fake "analyzing" state → fake report.
- No backend, no real data, no network calls yet — everything in `frontend/` is
  hardcoded/mocked by design for this phase.

## Running locally

```bash
cd frontend
npm install
npm run dev
```
