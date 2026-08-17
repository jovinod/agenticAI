# Alpha — The Book

A curated, chapter-per-phase account of building this project: what was decided, why, what was learned, and how it actually works — written from the real project history, with code drawn from the actual repo.

Format/approach decisions are logged in `tutor/references/decisions.md` under "The book."

## Chapters

1. [The Frontend Shell](chapter-01-frontend-shell.md) — Phase 0 (audit) + Phase 1 (React + Vite frontend, fully mocked, first live Azure deploy)
2. [The Backend Skeleton](chapter-02-backend-skeleton.md) — Phase 2 (FastAPI, arq→Service Bus, Postgres, worker, deployed to Azure Container Apps)
3. [MCP Tools and Real Data](chapter-03-mcp-and-real-data.md) — Phase 3 (fan-out/caching redesign, real yfinance data, a rule-based Skill, an MCP search tool)
4. [The First Agent](chapter-04-the-first-agent.md) — Phase 4 (Context Assembler, a swappable model client, a genuine LLM-discoverable Skill, and the Azure AI Foundry swap with token/cost logging — deployed and verified live)
5. [Multi-Agent](chapter-05-multi-agent.md) — Phase 5, in progress (a real LangGraph multi-agent pipeline — Fundamentals/Technical/News in parallel, Risk, Synthesizer — proven end to end locally; Skills restructuring, real three-tier memory, and deploy still ahead)
