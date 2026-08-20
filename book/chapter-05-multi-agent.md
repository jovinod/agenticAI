# Chapter 5 — Multi-Agent

*Phase 5 is in progress. This chapter covers the multi-agent graph — built, wired into the worker, and proven end to end locally. Skills restructuring, real three-tier memory, and the deploy are still ahead.*

## From One Agent to Five

Phase 4 ended with a single flat agent — one loop, one system prompt, a handful of tools it could reach for. Phase 5's whole premise is that a real research report benefits from several *narrower* agents working in parallel rather than one generalist trying to reason about everything at once — the same shape the prior related project assessed back in Chapter 3 already used for real, and the shape this project's own roadmap named from the start: News, Fundamentals, Technical, Risk, Synthesizer.

## Learning From the Prior Project Again, More Precisely This Time

Before building anything, that prior project's actual orchestration config was read directly rather than worked from memory — worth doing properly, since the real shape turned out richer than a rough recollection suggested. It runs **15 domain agents plus a synthesizer**, not a flat dozen: fundamentals, technical analysis, news sentiment, macro trends, employee feedback, institutional flows, insider/promoter activity, competitive landscape, ESG/governance, quarterly reports, leadership, regulatory/legal, dividend/capital, a dedicated Devil's Advocate agent, and valuation — organized into real dependency phases, including a **hard-stop gate**: if Fundamentals triggers a genuine disqualifier (debt rising three years straight, ROE and ROCE both under 12%), the whole pipeline short-circuits straight to a `DO NOT BUY` synthesis instead of spending the other 14 agents' worth of calls on a stock that already failed.

Only three of those 15 map directly onto this project's plan — Fundamentals, Technical, News — because only those three have data sources this project actually has (`yfinance`, Tavily). The other 11 are missing not because the ideas are wrong, but because their real value comes from data sources this project deliberately didn't reuse: a proprietary financial-data site's scraping, NSE insider filings, employee-review-site scraping — all India-only, with no US equivalent, a decision already logged when that project was first assessed back in Phase 3 ("reuse the patterns, not the scaffolding"). A real, explicit scoping call was made here: build the 5-agent core market-agnostic, as already planned, and treat any *additional* India-sourced agents as their own later, explicitly India-only addition — not a "phase 1 of a US rollout," since finding a genuine US equivalent for something like NSE insider-trading disclosures is a real, separate integration, not a lightweight follow-up.

One pattern worth remembering even though it wasn't built this pass: the **Devil's Advocate agent** — a dedicated node whose entire job is arguing against the bullish case. Genuinely interesting, deliberately deferred.

## The Missing Piece: A Real Technical Data Source

Before any agent could be split out, a real gap surfaced: `fetch_stock_data` covers Fundamentals, `search_web`/`assess_news_sentiment` covers News, but **Technical analysis had no data source at all**. Rather than fake it, a real one got built first.

**Simple Moving Average (SMA)** — the average closing price over the last N days, recalculated fresh each day as the window slides forward. Smooths out daily noise to reveal whether a price is meaningfully above or below where it's recently been settling.

**RSI (Relative Strength Index)** — a 0–100 measure of whether a stock has been bought or sold more aggressively than usual over a lookback window (14 days is standard). The actual math:

```python
rs = avg_gain / avg_loss
rsi = 100 - (100 / (1 + rs))
```

`RS` on its own isn't bounded — average gain divided by average loss can range from 0 (no gains at all) to infinity (no losses at all). The `100 - 100/(1+RS)` transform is what squeezes that unbounded ratio onto a fixed 0–100 scale: if there were no losses at all, `100/(1+RS)` → 0 so RSI → 100; if there were no gains at all, RS = 0 so RSI = `100 - 100 = 0`; if gains and losses were exactly equal, RS = 1 so RSI = `100 - 50 = 50`, the neutral midpoint. A worked example: average gain $2, average loss $1 → RS = 2 → `100/(1+2) = 33.3` → RSI = `100 - 33.3 = 66.7` — gains outweighing losses 2-to-1 lands around 67, leaning toward the commonly-cited ">70 = overbought" territory without quite reaching it.

```python
# tools/technical_indicators.py
def fetch_technical_indicators(ticker: str, market: str) -> dict:
    symbols_to_try = resolve_symbol_candidates(ticker, market)
    for symbol in symbols_to_try:
        history = yf.Ticker(symbol).history(period="6mo")
        if not history.empty:
            closes = history["Close"]
            return {
                "ticker": ticker, "resolved_symbol": symbol, "market": market,
                "current_price": round(closes.iloc[-1], 2),
                "sma_20": _simple_moving_average(closes, 20),
                "sma_50": _simple_moving_average(closes, 50),
                "rsi_14": _rsi(closes, 14),
            }
    ...
```

Verified with real data on both markets: AAPL came back with RSI 26.09 — below 30, "possibly oversold" — with its price sitting below its own 20-day average, an internally consistent read. RELIANCE.NS came back with RSI 57.8, roughly neutral, price close to both moving averages.

One small, genuine refactor came out of this: both `fetch_stock_data` and the new tool need the identical "which real exchange symbol does this ticker map to" logic. With two real callers now, `resolve_symbol_candidates(ticker, market)` was extracted out of `stock_data.py` rather than duplicated — worth doing now that duplication was real, not before.

## Generalizing the Harness

Phase 4's `agent.py` and `context_assembler.py` were hardcoded to one fixed system prompt and one fixed toolset — fine for one agent, wrong the moment there are five. The fix split the reusable *mechanism* from the agent-specific *parameters*: `context_assembler.py`'s `system_prompt` became an argument instead of a module constant, and the loop itself moved into a new `agent_harness.py`.

A second, more interesting refinement came out of thinking honestly about which agents have genuine tool-choice at all. Fundamentals and Technical should *always* fetch their data — there's no scenario where they wouldn't, which is exactly the "direct call, not a tool" distinction from Chapter 3, one level up. Giving them the full tool-calling loop would mean paying real overhead (tool schemas sent every turn, an LLM "deciding" something that was never actually in question) for zero benefit. So `agent_harness.py` now exports two functions:

```python
async def run_agent(system_prompt, user_message, tool_schemas, tool_registry, max_turns=5) -> dict:
    """The full loop -- for genuine tool-choice cases."""
    ...

async def run_synthesis(system_prompt, user_message) -> dict:
    """One LLM call, no tools, no loop -- for direct-fetch-then-synthesize cases."""
    messages = assemble_context([{"role": "user", "content": user_message}], system_prompt)
    result = chat(messages, tools=[])
    return {"status": "success", "answer": result["message"]["content"], "usage": result["usage"]}
```

Not a guess — checking the prior project's own Fundamentals agent found it does exactly this, with a real number attached in its own code comments: *"Direct (non-ReAct) approach: Python functions do the data fetching, then a single llm_generate() call analyses the data and returns structured JSON. This avoids LangGraph tool-schema overhead (~8K tokens saved per call)."*

## The Five Agents

**Fundamentals and Technical** are near-identical in shape: fetch directly, synthesize once.

```python
# agents/fundamentals_agent.py
async def run(ticker: str, market: str) -> dict:
    data = fetch_stock_data(ticker, market)
    if "error" in data:
        return {"status": "error", "error": data["error"], "data": data}
    user_message = f"Ticker: {data['ticker']} ({data['resolved_symbol']})\nPrice: ...\n..."
    result = await run_synthesis(SYSTEM_PROMPT, user_message)
    result["data"] = data
    return result
```

Run standalone against real AAPL data, the result was noticeably better-reasoned than anything Phase 4 produced: *"trading above the midpoint of its 52-week range... roughly 11% below its 52-week high"* — correct, where Chapter 4's single flat agent twice got this exact kind of range-position judgment wrong. Worth naming honestly rather than claiming a clean explanation: this could be `gpt-5-mini` simply being a stronger model than the `qwen3:8b` runs in Chapter 4, or it could be that handing an agent clean, already-fetched numbers to reason over produces more reliable arithmetic than making it juggle a tool-calling decision and the math in the same turn. Both are plausible; nothing here isolates which one actually mattered more — an honest open question, not a solved one.

**News** kept the full `run_agent` loop unchanged from Phase 4 — real judgment is genuinely involved here (what to search for, whether the sentiment skill applies to what's found), so the overhead `run_synthesis` avoids is exactly what this agent needs. Run standalone, it correctly searched, correctly loaded the `assess_news_sentiment` skill, and produced a real, well-reasoned judgment: a trade-secrets lawsuit and an earnings guidance miss both correctly flagged as genuine near-term risk, while explicitly noting *"No evidence was found of sudden executive departures under a cloud, accounting irregularities, major recalls, or data breaches"* — the rubric's own distinctions, genuinely applied, not just a wall of everything found.

**Risk** is the first agent in this project where an LLM's synthesis is actually load-bearing, not a nice-to-have narrative layer on top of numbers that already spoke for themselves:

```python
# agents/risk_agent.py
async def run(fundamentals_data, fundamentals_summary, technical_summary, news_summary) -> dict:
    flags = flag_risk_factors(fundamentals_data) if "error" not in fundamentals_data else []
    user_message = f"Deterministic risk flags: {flags}\n\nFundamentals: ...\n\nTechnical: ...\n\nNews: ..."
    result = await run_synthesis(SYSTEM_PROMPT, user_message)
    result["flags"] = flags
    return result
```

Tested with real outputs from the other three agents, it correctly noticed *"both fundamentals (valuation/guidance) and news point the same (negative) direction"* — genuine cross-signal reasoning, not three summaries pasted together — and added a nuance none of the inputs stated explicitly: a low RSI *"signals a possible short-lived oversold bounce,"* distinguishing "falling" from "oversold-and-likely-to-bounce," a real, valid technical-analysis distinction.

**Synthesizer** closes the loop — no new data, no tool choice, purely combining the other four into one report a person could actually read. Its system prompt explicitly says *"Do not repeat numbers verbatim across sections — synthesize, don't paste,"* and the real output honored that: exact P/E and price figures from Fundamentals became *"priced with growth expectations baked in"* in the final report — real instruction-following, not just tolerance for it.

## The Graph, and a Real Concurrency Bug Caught Before It Shipped

```mermaid
flowchart LR
    Start(["ticker + market"]) --> News[News Agent]
    Start --> Fundamentals[Fundamentals Agent]
    Start --> Technical[Technical Agent]
    News --> Risk[Risk Agent]
    Fundamentals --> Risk
    Technical --> Risk
    Risk --> Synth[Synthesizer Agent]
    Synth --> Report(["final multi-section report"])
```

LangGraph's `StateGraph` is the **orchestrator** in the exact sense Chapter 4 defined it: it decides which agent runs when and what state passes between them, and never reimplements the harness cycle itself — every node below just calls one of `agents/*.py`, each of which goes through the same shared `agent_harness.py`.

One real, non-obvious bug surfaced during design, not discovered by accident in testing: LangGraph's default state merge is **last-write-wins per key, not a sum**. Fundamentals, Technical, and News all run in parallel and each wanted to contribute its own token usage to a running total — but if all three read the *same* starting state (all zero) and each independently computed "zero plus my own usage," the final result would just be whichever node finished *last*, silently discarding the other two's contributions. A real concurrency trap, not a hypothetical one.

```python
class ResearchState(TypedDict):
    ...
    # A list with an `operator.add` reducer sidesteps the read-modify-write race
    # entirely: each node just appends its own usage, concatenation is safe
    # under concurrent writes, and the real total gets summed once, after the
    # graph finishes.
    usage_log: Annotated[list[dict], operator.add]
```

Every other field in the state (`fundamentals_summary`, `technical_summary`, `news_summary`) is safe under plain last-write-wins, because each one has exactly **one** writer — the concurrency problem only exists where multiple parallel nodes genuinely want to contribute to the *same* key.

Run end to end, the fix proved itself: a correctly-summed total across all five real LLM calls (`$0.00557` for the full AAPL run), not just one agent's worth silently standing in for the whole.

## Wiring It Into the Worker — the Phase 4 Hybrid Retired

Phase 4's `process_ticker` called `fetch_stock_data` and `flag_risk_factors` directly, *and separately* ran a single flat agent — a deliberate hybrid, accepted at the time because the duplication was cheap. That reasoning no longer applies: the graph's own Fundamentals agent already calls `fetch_stock_data`, and the graph's own Risk agent already calls `flag_risk_factors`. Keeping worker.py's separate direct calls would now be genuinely redundant work, not cheap insurance.

```python
# worker.py
graph_result = await run_research(ticker, market)
data = graph_result.get("fundamentals_data", {})
...
flags = graph_result.get("risk_flags", [])
summary_line += " | Report: " + graph_result.get("final_report", "")
```

Verified fully end to end locally against a real `TickerJob` row (MSFT/US): a real multi-section report — fundamentals, technical, news, risk, and a synthesized headline — landed in Postgres, alongside a correctly-summed `TokenUsage` row for the full five-agent run.

## A Correction: The Graph Wasn't Actually Running in Parallel

This needs to be said plainly rather than quietly fixed and left unmentioned: the graph above was described as running Fundamentals, Technical, and News "in parallel" — and the *wiring* was correct — but the actual execution wasn't genuinely concurrent until this got checked directly. Asked what scaling further would take, the honest first step was measuring, not assuming: instrumenting the real graph run with timestamps around each node.

```
fundamentals START  t=430913.67
fundamentals END    t=430923.63  (took 9.97s)
news START           t=430923.63    <- starts the INSTANT fundamentals ends
technical START       t=430926.77
news END             t=430942.46  (took 18.83s)
TOTAL wall-clock: 45.26s
```

`news` didn't start until `fundamentals` had *completely* finished. Total wall-clock (45s) was close to the *sum* of each agent's own time, not the *max* — the opposite of what real concurrency should look like.

**The cause**: `llm/model_client.py`'s `chat()` used `requests.post()` — a synchronous, blocking call — and wasn't even declared `async def`. Every agent's harness function is `async def` and calls `chat()` without `await`, because it was never a coroutine to begin with. The mechanics matter here: `asyncio` only lets other tasks run when a coroutine hits a genuine `await` on something async. A blocking synchronous call inside an `async def` function doesn't yield control at all — it freezes the *entire* event loop until it returns. Wiring parallel edges in a graph says nothing about whether the work inside those edges can actually overlap; that depends entirely on whether the I/O underneath is genuinely async.

The fix: switch to `httpx.AsyncClient`, make `chat()` itself `async def`, and add `await` at every call site:

```python
# llm/model_client.py
async def chat(messages: list[dict], tools: list[dict]) -> dict:
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(CHAT_URL, headers=..., json=...)
    ...
```

Re-measured with the same instrumentation, the fix proved itself:

```
fundamentals START  t=431250.92
news START           t=431252.02    <- now within 1 second of fundamentals
technical START       t=431252.03
TOTAL wall-clock: 33.49s   (bound by the SLOWEST branch, not the sum)
```

**A second real gotcha, surfaced by the fix itself, not separately discovered**: the very first re-test failed outright with `httpx.ReadTimeout`. `httpx` defaults to a 5-second timeout; `requests` (used before) has no default timeout at all, so this was never a problem until switching libraries. Three agents now genuinely competing for the same rate-limited Azure OpenAI capacity concurrently made responses legitimately slower than 5 seconds under real load. Fixed with an explicit `timeout=90.0`.

> 🏭 **Production Lens:** "The graph diagram shows parallel edges" and "the work actually overlaps in wall-clock time" are two different claims, and only measuring proves the second one. This is exactly the kind of thing easy to assume is true because the code *looks* concurrent (every function is `async def`, the graph draws parallel arrows) — and exactly why this project has leaned on "verify actual behavior, don't trust what a command or a diagram implies" as a standing discipline since the Container Apps stale-deploy incident back in Chapter 3.

**Scaling further has two more real dimensions beyond this fix, worth naming rather than assuming this fix alone means "solved":**
1. **Azure OpenAI's rate limit becomes the real ceiling as concurrency increases.** The current deployment's `GlobalStandard` capacity (10K tokens/minute) is a genuine, non-code limit — more parallel agents or more concurrent tickers will eventually hit real `429` responses, fixable only by raising capacity or adding client-side backoff, not more `asyncio`.
2. **Multiple *tickers* running concurrently is a different axis than one ticker's graph running concurrently.** `worker.py`'s `async for msg in receiver` loop still processes Service Bus messages one at a time — two different tickers in the same request still run their graphs sequentially, even after this fix. The real production answer for that is more `alpha-worker` Container App replicas, autoscaled on queue depth — horizontal scaling, not parallelizing further inside one process.

## Skills, Actually Discoverable Now

One real gap sat unaddressed since the News agent was first built: `assess_news_sentiment` was genuinely LLM-discoverable *within* `news_agent.py`, but only because that one file happened to hardcode it into its own `TOOL_SCHEMAS`/`TOOL_REGISTRY`. Nothing scanned the `skills/` folder itself; nothing made a skill available to any agent other than the one that happened to import it by name. `flag_risk_factors` — no `SKILL.md`, never meant to be a model's choice — correctly stayed outside this entirely.

```python
# skills/discovery.py
def discover_skills() -> tuple[list[dict], dict]:
    """Built fresh from disk every call -- not a fixed list maintained by
    hand, so a new skill folder is picked up without touching this file
    or any agent that uses it."""
    tool_schemas, tool_registry = [], {}
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_dir.is_dir() or not skill_md.exists():
            continue
        fields = _parse_frontmatter(skill_md)
        module = importlib.import_module(f"skills.{skill_dir.name}.skill")
        tool_schemas.append({"type": "function", "function": {
            "name": fields["name"], "description": fields["description"],
            "parameters": {"type": "object", "properties": {}},
        }})
        tool_registry[fields["name"]] = module.load_instructions
    return tool_schemas, tool_registry
```

`news_agent.py` now calls this instead of hardcoding the one skill it happens to know about:

```python
_skill_schemas, _skill_registry = discover_skills()

TOOL_SCHEMAS = [{ ... "search_web" ... }, *_skill_schemas]
TOOL_REGISTRY = {"search_web": search_via_mcp, **_skill_registry}
```

**The real proof this is genuine discovery, not just moved hardcoding, isn't that two skills exist today — there's still only one.** It's that adding a *second* discoverable skill later requires editing exactly one thing: a new folder under `skills/` with its own `SKILL.md`. No agent's code changes at all, `news_agent.py` included. Verified standalone first (`discover_skills()` correctly finds `assess_news_sentiment`, correctly skips `flag_risk_factors`), then end to end (`news_agent.run("AAPL", "US")` — real search, the skill genuinely discovered and applied, identical quality of reasoning to before, now reached through a mechanism instead of an import).

## Key Files From This Chapter

| File | What it does |
|---|---|
| `backend/worker/tools/technical_indicators.py` | `fetch_technical_indicators()` — real SMA-20, SMA-50, RSI-14 from `yfinance` price history. |
| `backend/worker/tools/stock_data.py` | `resolve_symbol_candidates()` extracted out — now shared by this tool and the technical indicators tool. |
| `backend/worker/agent_harness.py` | The generalized engine: `run_agent()` (full tool-calling loop) and `run_synthesis()` (single call, no tools) — every agent below is built on one of these two. |
| `backend/worker/context_assembler.py` | `system_prompt` changed from a fixed constant to a parameter — the precondition for five agents each having their own. |
| `backend/worker/agents/fundamentals_agent.py` | Direct fetch + `run_synthesis` — fundamentals narrative. |
| `backend/worker/agents/technical_agent.py` | Direct fetch + `run_synthesis` — momentum narrative. |
| `backend/worker/agents/news_agent.py` | `run_agent`'s full loop — search + whatever `discover_skills()` finds, genuine judgment preserved from Chapter 4. |
| `backend/worker/skills/discovery.py` | `discover_skills()` — scans `skills/` for any folder with a `SKILL.md`, builds tool schemas + a registry dynamically. Adding a new discoverable skill needs zero agent code changes. |
| `backend/worker/agents/risk_agent.py` | Deterministic `flag_risk_factors` + cross-signal synthesis over the other three agents' outputs. |
| `backend/worker/agents/synthesizer_agent.py` | Combines all four into the final report. |
| `backend/worker/agents/graph.py` | The real LangGraph `StateGraph` — parallel fan-out, fan-in to Risk, then Synthesizer; the `usage_log` reducer fix lives here. |
| `backend/worker/worker.py` | `process_ticker` now calls the graph directly, retiring the Phase 4 hybrid. |
| `backend/worker/llm/model_client.py` | `chat()` switched from blocking `requests` to genuinely async `httpx.AsyncClient` — the fix that made the graph's parallel wiring actually run in parallel. Also later routed through APIM (subscription key auth) instead of calling Foundry directly. |

## The Flow So Far

```mermaid
flowchart TD
    WorkerPy["worker.py:<br/>process_ticker()"] --> Graph["agents/graph.py:<br/>run_research()"]

    Graph -->|"START, parallel"| Fund["agents/fundamentals_agent.py"]
    Graph -->|"START, parallel"| Tech["agents/technical_agent.py"]
    Graph -->|"START, parallel"| News["agents/news_agent.py"]
    News -->|"discover_skills()"| Discovery["skills/discovery.py"]
    Discovery -->|"scans for SKILL.md"| SkillFile["skills/assess_news_sentiment/"]

    Fund -->|"run_synthesis"| Harness["agent_harness.py"]
    Tech -->|"run_synthesis"| Harness
    News -->|"run_agent (full loop)"| Harness
    Harness --> ModelClient["llm/model_client.py:<br/>chat() -- async httpx"]
    ModelClient --> APIM["alpha-research-apim<br/>(Ocp-Apim-Subscription-Key)"]
    APIM --> Foundry["alpha-research-openai<br/>(managed identity auth)"]

    Fund --> Risk["agents/risk_agent.py"]
    Tech --> Risk
    News --> Risk
    Risk -->|"run_synthesis"| Harness

    Risk --> Synth["agents/synthesizer_agent.py"]
    Synth -->|"run_synthesis"| Harness
    Synth --> Report["final_report + usage_log"]
    Report -->|"write"| PG[("Postgres:<br/>TickerJob + TokenUsage")]

    classDef file fill:#e3f2fd,stroke:#1565c0,color:#0d47a1
    class WorkerPy,Graph,Fund,Tech,News,Risk,Synth,Harness,ModelClient,Discovery,SkillFile file
```

## Azure Architecture — Two Real Scaling Pieces Now Deployed

Unlike most of this chapter, this section documents changes made in a later session, prompted directly by the reader's own follow-up questions about scaling — not a separate build pass, but real infrastructure added while working through exactly the scaling questions raised below. Both pieces are live, verified, not exploratory.

**Azure API Management (Consumption tier)** now fronts the Foundry deployment, replacing the direct worker→Foundry call from earlier in this chapter:

```mermaid
flowchart LR
    Worker["alpha-worker"] -->|"Ocp-Apim-Subscription-Key"| APIM["alpha-research-apim<br/>(Consumption tier)"]
    APIM -->|"managed identity (AAD token)<br/>no stored key"| OpenAI["alpha-research-openai<br/>(South India)"]
```

Provisioned with a system-assigned managed identity, granted the `Cognitive Services OpenAI User` role directly on the Foundry resource — APIM authenticates to Foundry itself via a real Azure AD token, acquired fresh per request via the `authentication-managed-identity` policy. The worker no longer holds the raw Foundry API key at all; it only ever sees an APIM subscription key, itself scoped to just this one API. A real, non-obvious gotcha hit setting this up: the API's own client-facing path (`openai`) was being *stripped* by APIM before forwarding to the backend — but Azure OpenAI's actual REST path also starts with `/openai/deployments/...`, so the forwarded request was silently missing that segment, producing a `404` that looked like a routing failure but was actually a path-construction bug. Fixed by giving the API an empty client-facing path, so the full incoming path forwards to the backend unchanged. Verified with a direct `curl` through the whole chain (subscription key → APIM → managed identity token → Foundry → real response) before touching any application code — the same discipline used for every other piece in this project.

**The KEDA scale rule's `messageCount` dropped from 5 to 1** — deliberately aggressive, aiming for roughly one worker replica per queued ticker rather than one per five. Working through the actual formula (`replicas = ceil(queue_length / messageCount)`) surfaced a real, worth-remembering correction: a *higher* `messageCount` means *less* aggressive scaling, not more — the number means "how many messages one replica is expected to handle," so getting "one replica per ticker" required setting it to 1, not to a number that sounded like "2 tickers, 2 replicas." A real, acknowledged tradeoff comes with this: more replicas now compete harder for the same Foundry capacity behind APIM, which doesn't add capacity on its own — just a gateway layer in front of the same 10K TPM. This value is intentionally temporary — the plan is to revert it closer to 5 once the project nears completion, once aggressive per-ticker scaling has served its purpose of exercising the autoscaling path directly.

## Scaling Options — What's Built, What's Still Exploratory

**Option A — Raise capacity on the existing deployment.** Still not done; the simplest lever if the new APIM-fronted setup starts hitting real rate limits.

```mermaid
flowchart LR
    Worker["alpha-worker"] --> APIM["alpha-research-apim"] --> OpenAI["alpha-research-openai<br/>capacity: 10 -> N"]
```

**Option B — Multiple deployments, load-balanced in our own code.** Still not built — superseded in intent by Option C below, since APIM is now the actual gateway layer; hand-rolling load-balancing logic in `model_client.py` would duplicate what APIM already exists to do.

**Option C — APIM fronting a pool of multiple Foundry backends.** **Partially real now.** APIM fronting *one* backend is built and live, described above — the mechanism (backend resource, managed-identity auth, policy-based routing) is proven. What's still exploratory is the *pool* part: a second Foundry deployment and a load-balancing policy across both. One real constraint worth remembering if this gets built: genuine round-robin/weighted routing works on the Consumption tier we're using, but the *circuit-breaker* policy (automatically detecting a throttling backend and rerouting around it) does **not** — that needs a paid dedicated tier (Basic+, ~$150+/month), confirmed by checking Microsoft's own documentation rather than assumed.

```mermaid
flowchart LR
    Worker["alpha-worker"] --> APIM["alpha-research-apim<br/>(round-robin possible on Consumption;<br/>circuit-breaker needs a paid tier)"]
    APIM --> A["alpha-research-openai<br/>(South India) -- REAL"]
    APIM -.->|"not built"| B["alpha-research-openai-2<br/>(another region)"]
```

## The Architecture So Far

This is the diagram every chapter has grown, one real piece at a time, since Chapter 1's single box. Everything from Chapters 1–4 stays exactly as it was; this chapter adds one new node (`alpha-research-apim`) and changes one edge — `Worker` no longer calls `alpha-research-openai` directly, it now goes through APIM, which authenticates to Foundry itself via managed identity. The worker is also no longer drawn as a single fixed box: it's a real KEDA-scaled group now, 1 to 10 replicas depending on queue depth, not a single always-one instance the way it was through Chapter 4.

```mermaid
flowchart TB
    User(["Visitor's browser"])
    SWA["Azure Static Web Apps<br/>React SPA"]
    API["Container App: alpha-api<br/>FastAPI (external ingress)"]
    SB["Service Bus: alpharesearchsb<br/>queue: research-jobs"]

    subgraph WorkerGroup["Container App: alpha-worker<br/>KEDA-scaled: 1-10 replicas<br/>(1 replica per queued msg)"]
        direction LR
        W1["replica"]
        W2["replica"]
        Wdots["···<br/>up to 10"]
    end

    PG[("Postgres Flexible Server:<br/>alpha-research-pg<br/>+ token_usage table")]
    Redis[("Managed Redis:<br/>alpha-research-cache<br/>per-ticker cache")]
    APIM["API Management: alpha-research-apim<br/>(Consumption tier, managed identity)"]
    OpenAI["Azure OpenAI: alpha-research-openai<br/>(South India) — deployment: gpt-5-mini"]

    User --> SWA
    SWA -->|HTTPS| API
    API -->|send job, per ticker on miss| SB
    SB -->|deliver job, one per replica| WorkerGroup
    API -->|read status| PG
    WorkerGroup -->|write status/result/token-cost| PG
    API -->|cache check| Redis
    WorkerGroup -->|cache write| Redis
    WorkerGroup -->|"Ocp-Apim-Subscription-Key"| APIM
    APIM -->|"managed identity (AAD token)"| OpenAI

    classDef existing fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20
    classDef new fill:#69f0ae,stroke:#00c853,stroke-width:3px,color:#004d26
    classDef replica fill:#e8f5e9,stroke:#66bb6a,stroke-width:1px,color:#2e7d32
    class SWA,API,SB,PG,Redis,OpenAI existing
    class WorkerGroup existing
    class W1,W2,Wdots replica
    class APIM new
```

## Where Phase 5 Actually Stands

**A correction worth stating plainly rather than burying**: deploying the APIM change turned out to also be the *first real deploy of the entire multi-agent graph itself*. `worker.py` had been calling `agents.graph.run_research()` for a while, entirely proven locally — but the live worker was still running the Phase 4 single-agent code until this session's rebuild picked up everything that had accumulated since. The real live test that proved APIM worked (`GOOGL`, a genuine four-section report — fundamentals, technical, news, risk, synthesized — returned through the real deployed API) was, at the same time, the first live proof of this whole chapter's actual subject.

So: the multi-agent graph is real, proven, **and now genuinely deployed and verified live** — not just locally. Genuinely concurrent execution (measured, not assumed), a genuine cross-signal Risk judgment, two real concurrency bugs caught before either shipped silently wrong, real worker autoscaling, a real APIM layer in front of Foundry, and Skills genuinely discoverable rather than hardcoded per-agent — all confirmed against actual running Azure infrastructure, including a real live regression check after the Skills deploy. Only one real piece of the original Phase 5 roadmap remains: the real three-tier memory model (short-term Redis, semantic `pgvector`, profile Postgres tables).

## What Came Out of This Chapter (So Far)

- A precise, source-checked understanding of the prior project's real 15-agent structure — and an honest, explicit decision to build a smaller 5-agent core now, deferring the India-sourced agents as their own later, explicitly-scoped addition rather than pretending they're a lightweight follow-up.
- A real technical-indicators tool, with SMA and RSI genuinely understood — not just called, but the actual math worked through by hand, including why the RS-ratio-to-0–100 transform behaves the way it does at its extremes.
- A generalized harness (`run_agent` vs. `run_synthesis`) drawing a real, principled line between "genuine tool-choice" and "always-fetch-then-synthesize" — validated against the prior project's own equivalent design choice, not invented in isolation.
- Five real agents, each proven standalone before being wired together — including the first agent in this project (Risk) where an LLM's synthesis is genuinely load-bearing, not a narrative layer on top of numbers that already spoke for themselves.
- A real LangGraph `StateGraph`, and two real concurrency bugs caught rather than shipped silently wrong: a last-write-wins state-merge trap (fixed with a proper reducer) and a blocking synchronous HTTP call that made "parallel" graph wiring not actually mean parallel execution (fixed by switching to a genuinely async HTTP client) — plus the follow-on timeout gotcha that fix itself surfaced. A concrete lesson that "the code looks concurrent" and "the code IS concurrent" are different claims, and only measuring proves the second one.
- The Phase 4 hybrid design retired for a principled reason, not just because more code existed: once the graph's own agents did the same deterministic work internally, keeping a separate copy in `worker.py` stopped being cheap insurance and became genuine waste.
- A real, verified KEDA autoscaling rule on `alpha-worker`, closing a gap this same chapter had only flagged a day earlier — checked with `az containerapp show`, not trusted from a diagram label, the same discipline the concurrency bug itself was caught with. Deliberately tuned aggressive (`messageCount=1`) for now, with an explicit, logged plan to revert closer to 5 nearer project completion.
- A real Azure API Management deployment fronting Foundry via managed identity — the worker no longer holds a raw Foundry key at all — including a genuine gotcha (a stripped path prefix silently breaking the forwarded request) caught by testing the whole chain with `curl` before writing any application code, the exact discipline this project has used for every prior piece.
- A precise correction to KEDA's own scaling formula, caught before the wrong number shipped: `messageCount` means messages *per replica*, so a lower number scales *more* aggressively, not less — the opposite of what the number's shape suggests at a glance.
- **A genuinely important correction**: the APIM deploy turned out to also be the first real deployment of this entire chapter's multi-agent graph — it had been proven locally for a while, but had never actually been redeployed to the live worker until this session's rebuild. Worth naming directly rather than letting a milestone hide inside an unrelated change.
- Skills, genuinely discoverable now instead of hardcoded per-agent — `discover_skills()` scans `skills/` for anything with a `SKILL.md`, and the real proof it's genuine discovery rather than relocated hardcoding is that a second skill added later needs zero agent code changes, not that two skills exist today.
- Skills discovery deployed and verified live (real `TSLA` job, News correctly flagging genuine safety recalls via the dynamically-discovered skill, not the old hardcoded import) — a real regression check confirming identical behavior through a completely different discovery mechanism.
- Phase 5 down to one real remaining piece: the three-tier memory model.
