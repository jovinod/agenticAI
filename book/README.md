# Alpha — The Book

A curated, chapter-per-phase account of building this project: what was decided, why, what was learned, and how it actually works — written from the real project history, with code drawn from the actual repo.

Format/approach decisions are logged in `tutor/references/decisions.md` under "The book."

## Chapters

1. [The Frontend Shell](chapter-01-frontend-shell.md) — Phase 0 (audit) + Phase 1 (React + Vite frontend, fully mocked, first live Azure deploy)
2. [The Backend Skeleton](chapter-02-backend-skeleton.md) — Phase 2 (FastAPI, arq→Service Bus, Postgres, worker, deployed to Azure Container Apps)
3. [MCP Tools and Real Data](chapter-03-mcp-and-real-data.md) — Phase 3 (fan-out/caching redesign, real yfinance data, a rule-based Skill, an MCP search tool)
4. [The First Agent](chapter-04-the-first-agent.md) — Phase 4 (Context Assembler, a swappable model client, a genuine LLM-discoverable Skill, and the Azure AI Foundry swap with token/cost logging — deployed and verified live)
5. [Multi-Agent](chapter-05-multi-agent.md) — Phase 5 (a real LangGraph multi-agent pipeline — Fundamentals/Technical/News in parallel, Risk, Synthesizer — plus real three-tier memory; later grown a Decision and Devil's Advocate agent, replacing Synthesizer entirely)
6. [Checkpointing](chapter-06-checkpointing.md) — Phase 6 (LangGraph's built-in Postgres checkpointing, proven against a genuine mid-job container restart, not a simulated crash)
7. [Resilience](chapter-07-resilience.md) — Phase 7 (`RetryPolicy` for transient failures, in-function graceful degradation for persistent ones, verified via a real failure injection)
8. [Auth & Trust Boundaries](chapter-08-auth.md) — Phase 8, all 5 stages (Entra ID sign-in, Managed Identity across Service Bus/Postgres/Redis, Key Vault for the one remaining third-party secret, an honest trust-boundary writeup, and a full checklist for constraining agents specifically)
9. [Guardrails](chapter-09-guardrails.md) — Phase 9 (Azure AI Content Safety's Prompt Shields against indirect prompt injection, basic PII scrubbing, verified live against a real crafted attack)
10. [Observability](chapter-10-observability.md) — Phase 10 (Azure OpenAI diagnostic logs, real OpenTelemetry tracing across `alpha-api`/`alpha-worker`; the tracing itself surfaced a real blocking-call bug, fixed for a measured ~58% speedup)
11. [Scaling Validation](chapter-11-scaling.md) — Phase 11 (a real, fully-captured autoscaling cycle for `alpha-worker`; the MCP search server graduated to its own Container App, including a genuine Azure ingress/`httpx` redirect gotcha)
12. [Polish & Final Wiring](chapter-12-polish.md) — Phase 12 (explicit per-ticker failure states, a History tab, a fully current README, a live-caught KEDA regression, and a full visual redesign iterated with the user before shipping)
