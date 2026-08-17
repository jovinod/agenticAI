# Chapter 5 — Multi-Agent

*Phase 5 is in progress. This chapter covers the multi-agent graph — built, wired into the worker, and proven end to end locally. Skills restructuring, real three-tier memory, and the deploy are still ahead.*

## From One Agent to Five

Phase 4 ended with a single flat agent — one loop, one system prompt, a handful of tools it could reach for. Phase 5's whole premise is that a real research report benefits from several *narrower* agents working in parallel rather than one generalist trying to reason about everything at once — the same shape `buynobuy` (a prior related project) already used for real, and the shape this project's own roadmap named from the start: News, Fundamentals, Technical, Risk, Synthesizer.

## Learning From buynobuy Again, More Precisely This Time

Before building anything, the actual `buynobuy` orchestration config was read directly rather than worked from memory — worth doing properly, since the real shape turned out richer than a rough recollection suggested. It runs **15 domain agents plus a synthesizer**, not a flat dozen: `fundamentals`, `technical_analysis`, `news_sentiment`, `macro_trends`, `employee_feedback`, `institutional_flows`, `insider_promoter`, `competitive_landscape`, `esg_governance`, `quarterly_reports`, `leadership`, `regulatory_legal`, `dividend_capital`, a dedicated `devil` (Devil's Advocate) agent, and `valuation` — organized into real dependency phases, including a **hard-stop gate**: if Fundamentals triggers a genuine disqualifier (debt rising three years straight, ROE and ROCE both under 12%), the whole pipeline short-circuits straight to a `DO NOT BUY` synthesis instead of spending the other 14 agents' worth of calls on a stock that already failed.

Only three of those 15 map directly onto this project's plan — Fundamentals, Technical, News — because only those three have data sources this project actually has (`yfinance`, Tavily). The other 11 are missing not because the ideas are wrong, but because their real value comes from data sources this project deliberately didn't reuse: Trendlyne scraping, NSE insider filings, AmbitionBox employee reviews — all India-only, with no US equivalent, a decision already logged when `buynobuy` was first assessed back in Phase 3 ("reuse the patterns, not the scaffolding"). A real, explicit scoping call was made here: build the 5-agent core market-agnostic, as already planned, and treat any *additional* India-sourced agents as their own later, explicitly India-only addition — not a "phase 1 of a US rollout," since finding a genuine US equivalent for something like NSE insider-trading disclosures is a real, separate integration, not a lightweight follow-up.

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

Not a guess — checking `buynobuy`'s own Fundamentals agent found it does exactly this, with a real number attached: *"Direct (non-ReAct) approach: Python functions do the data fetching, then a single llm_generate() call analyses the data and returns structured JSON. This avoids LangGraph tool-schema overhead (~8K tokens saved per call)."*

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

## Where Phase 5 Actually Stands

The multi-agent graph is real, proven, and wired into the worker — genuine parallel execution, a genuine cross-signal Risk judgment, a real concurrency bug caught before it shipped rather than discovered in production. Still ahead: restructuring Skills to be genuinely shared and discoverable across agents rather than each agent hardcoding its own tool list (today's News agent still imports `assess_news_sentiment` directly — nothing scans a `skills/` folder and offers it dynamically), the real three-tier memory model (short-term Redis, semantic `pgvector`, profile Postgres tables), and — as always in this project — an actual deploy and a live check before this chapter is called finished.

## What Came Out of This Chapter (So Far)

- A precise, source-checked understanding of `buynobuy`'s real 15-agent structure — and an honest, explicit decision to build a smaller 5-agent core now, deferring the India-sourced agents as their own later, explicitly-scoped addition rather than pretending they're a lightweight follow-up.
- A real technical-indicators tool, with SMA and RSI genuinely understood — not just called, but the actual math worked through by hand, including why the RS-ratio-to-0–100 transform behaves the way it does at its extremes.
- A generalized harness (`run_agent` vs. `run_synthesis`) drawing a real, principled line between "genuine tool-choice" and "always-fetch-then-synthesize" — validated against `buynobuy`'s own equivalent design choice, not invented in isolation.
- Five real agents, each proven standalone before being wired together — including the first agent in this project (Risk) where an LLM's synthesis is genuinely load-bearing, not a narrative layer on top of numbers that already spoke for themselves.
- A real LangGraph `StateGraph` with genuine parallel execution, and a real concurrency bug (last-write-wins silently discarding parallel contributions to a shared key) caught and fixed with a proper reducer before it ever produced a wrong number silently.
- The Phase 4 hybrid design retired for a principled reason, not just because more code existed: once the graph's own agents did the same deterministic work internally, keeping a separate copy in `worker.py` stopped being cheap insurance and became genuine waste.
- Phase 5 still open: Skills restructuring, real three-tier memory, and the first live deploy of any of it.
