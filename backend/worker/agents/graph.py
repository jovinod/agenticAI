"""
The LangGraph orchestration wiring for Phase 5's multi-agent research
pipeline -- the ORCHESTRATOR in the Harness-vs-Orchestrator sense
(book/chapter-04-the-first-agent.md): decides which agent runs when and
what state passes between them, never reimplements the harness cycle
itself. Every node below just calls into one of agents/*.py, each of which
goes through the same shared agent_harness.py.

News, Fundamentals, and Technical run in parallel (none depend on each
other's output); Risk waits for all three; Devil's Advocate runs after Risk
(it needs Risk's summary to build counter-evidence against); Decision runs
last, replacing Synthesizer -- it owns both the BUY/HOLD/SELL verdict and
the final narrative, using Devil's Advocate's counter-thesis as one more
input alongside the other four agents' summaries.

Each node also writes its own result to short-term memory (memory/short_term.py)
as soon as it finishes -- so a still-running job has real partial progress to
show, not just silence until the whole graph completes.
"""
import operator
from typing import Annotated, TypedDict
from opentelemetry import trace
from langgraph.graph import StateGraph, START, END
from langgraph.types import RetryPolicy
from agents import fundamentals_agent, technical_agent, news_agent, risk_agent, devil_agent, decision_agent
from memory.short_term import write_progress

# Phase 10, Stage C -- one span per agent node, nested under process_ticker's
# root span (worker.py). This is what actually gives "each agent's duration"
# in a real trace, not just one undifferentiated blob per job.
tracer = trace.get_tracer(__name__)


class ResearchState(TypedDict):
    job_id: str
    ticker: str
    market: str
    fundamentals_data: dict
    fundamentals_summary: str
    technical_summary: str
    news_summary: str
    risk_summary: str
    risk_flags: list
    devil_advocate_summary: str
    devil_advocate_data: dict
    recommendation: str
    overall_score: float | None
    hard_stops_triggered: list
    intrinsic_value: dict
    final_report: str
    # Fundamentals/Technical/News run in PARALLEL and each contributes its own
    # usage -- if this were a single dict, whichever node finished last would
    # silently overwrite the others' totals instead of merging with them
    # (LangGraph's default is last-write-wins per key, not a merge). A list
    # with an `operator.add` reducer sidesteps that entirely: each node just
    # appends its own usage, concatenation is safe under concurrent writes,
    # and the real total gets summed once, after the graph finishes.
    usage_log: Annotated[list[dict], operator.add]


def _empty_usage() -> dict:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0}


async def _degraded_result(job_id: str, ticker: str, node_name: str, state_key: str, exc: Exception, extra: dict | None = None) -> dict:
    """Phase 7 (Resilience) -- a persistent failure (RetryPolicy's retries
    exhausted, or a non-retryable exception type entirely) degrades only
    THIS node's own state field instead of raising, so downstream nodes
    (Risk, Synthesizer) still run on whatever data IS real, and successful
    parallel siblings' usage_log entries survive intact.

    Deliberately a plain try/except INSIDE each node, not LangGraph's
    error_handler=. Verified directly, not assumed: error_handler does get
    called and does produce a fallback value, but the graph still re-raises
    the original exception anyway when the failing node is part of a
    concurrent parallel fan-out (Fundamentals/Technical/News, exactly this
    project's main failure surface) -- traced to LangGraph's async executor
    independently re-raising a submitted task's exception on exit, a
    separate code path from the one that's supposed to honor "this was
    handled." A solo/sequential node doesn't hit this, but relying on a
    mechanism that's inconsistent for our most important case isn't worth
    it when a plain try/except works identically everywhere. See
    book/chapter-07.
    """
    message = f"{node_name} unavailable: {exc}"
    await write_progress(job_id, ticker, node_name, message)
    result = {state_key: message, "usage_log": []}
    if extra:
        result.update(extra)
    return result


async def fundamentals_node(state: ResearchState) -> dict:
    with tracer.start_as_current_span("agent:fundamentals") as span:
        span.set_attribute("job_id", state["job_id"])
        span.set_attribute("ticker", state["ticker"])
        try:
            result = await fundamentals_agent.run(state["ticker"], state["market"])
        except Exception as exc:
            return await _degraded_result(
                state["job_id"], state["ticker"], "fundamentals", "fundamentals_summary", exc, {"fundamentals_data": {}}
            )
        span.set_attribute("total_tokens", result.get("usage", {}).get("total_tokens", 0))
        summary = result.get("answer") or result.get("error", "Fundamentals data unavailable.")
        await write_progress(state["job_id"], state["ticker"], "fundamentals", summary)
        return {
            "fundamentals_data": result.get("data", {}),
            "fundamentals_summary": summary,
            "usage_log": [result.get("usage", {})],
        }


async def technical_node(state: ResearchState) -> dict:
    with tracer.start_as_current_span("agent:technical") as span:
        span.set_attribute("job_id", state["job_id"])
        span.set_attribute("ticker", state["ticker"])
        try:
            result = await technical_agent.run(state["ticker"], state["market"])
        except Exception as exc:
            return await _degraded_result(state["job_id"], state["ticker"], "technical", "technical_summary", exc)
        span.set_attribute("total_tokens", result.get("usage", {}).get("total_tokens", 0))
        summary = result.get("answer") or result.get("error", "Technical data unavailable.")
        await write_progress(state["job_id"], state["ticker"], "technical", summary)
        return {
            "technical_summary": summary,
            "usage_log": [result.get("usage", {})],
        }


async def news_node(state: ResearchState) -> dict:
    with tracer.start_as_current_span("agent:news") as span:
        span.set_attribute("job_id", state["job_id"])
        span.set_attribute("ticker", state["ticker"])
        try:
            result = await news_agent.run(state["ticker"], state["market"])
        except Exception as exc:
            return await _degraded_result(state["job_id"], state["ticker"], "news", "news_summary", exc)
        span.set_attribute("total_tokens", result.get("usage", {}).get("total_tokens", 0))
        summary = result.get("answer", "News assessment unavailable.")
        await write_progress(state["job_id"], state["ticker"], "news", summary)
        return {
            "news_summary": summary,
            "usage_log": [result.get("usage", {})],
        }


async def risk_node(state: ResearchState) -> dict:
    with tracer.start_as_current_span("agent:risk") as span:
        span.set_attribute("job_id", state["job_id"])
        span.set_attribute("ticker", state["ticker"])
        try:
            result = await risk_agent.run(
                state.get("fundamentals_data", {}),
                state.get("fundamentals_summary", ""),
                state.get("technical_summary", ""),
                state.get("news_summary", ""),
            )
        except Exception as exc:
            return await _degraded_result(
                state["job_id"], state["ticker"], "risk", "risk_summary", exc, {"risk_flags": []}
            )
        span.set_attribute("total_tokens", result.get("usage", {}).get("total_tokens", 0))
        summary = result.get("answer", "Risk assessment unavailable.")
        await write_progress(state["job_id"], state["ticker"], "risk", summary)
        return {
            "risk_summary": summary,
            "risk_flags": result.get("flags", []),
            "usage_log": [result.get("usage", {})],
        }


async def devil_advocate_node(state: ResearchState) -> dict:
    with tracer.start_as_current_span("agent:devil_advocate") as span:
        span.set_attribute("job_id", state["job_id"])
        span.set_attribute("ticker", state["ticker"])
        try:
            result = await devil_agent.run(
                state["ticker"],
                state["market"],
                state.get("fundamentals_summary", ""),
                state.get("technical_summary", ""),
                state.get("news_summary", ""),
                state.get("risk_summary", ""),
            )
        except Exception as exc:
            return await _degraded_result(
                state["job_id"], state["ticker"], "devil_advocate", "devil_advocate_summary", exc, {"devil_advocate_data": {}}
            )
        span.set_attribute("total_tokens", result.get("usage", {}).get("total_tokens", 0))
        summary = result.get("answer", "Devil's Advocate assessment unavailable.")
        await write_progress(state["job_id"], state["ticker"], "devil_advocate", summary)
        return {
            "devil_advocate_summary": summary,
            "devil_advocate_data": result,
            "usage_log": [result.get("usage", {})],
        }


async def decision_node(state: ResearchState) -> dict:
    with tracer.start_as_current_span("agent:decision") as span:
        span.set_attribute("job_id", state["job_id"])
        span.set_attribute("ticker", state["ticker"])
        try:
            result = await decision_agent.run(
                state["ticker"],
                state["market"],
                state.get("fundamentals_summary", ""),
                state.get("technical_summary", ""),
                state.get("news_summary", ""),
                state.get("risk_summary", ""),
                state.get("devil_advocate_summary", ""),
            )
        except Exception as exc:
            return await _degraded_result(
                state["job_id"], state["ticker"], "decision", "final_report", exc,
                {"recommendation": "HOLD", "overall_score": None, "hard_stops_triggered": [], "intrinsic_value": {}},
            )
        span.set_attribute("total_tokens", result.get("usage", {}).get("total_tokens", 0))
        summary = result.get("answer", "Report unavailable.")
        await write_progress(state["job_id"], state["ticker"], "decision", summary)
        return {
            "final_report": summary,
            "recommendation": result.get("recommendation", "HOLD"),
            "overall_score": result.get("overall_score"),
            "hard_stops_triggered": result.get("hard_stops_triggered", []),
            "intrinsic_value": result.get("intrinsic_value", {}),
            "usage_log": [result.get("usage", {})],
        }


def build_graph(checkpointer=None):
    builder = StateGraph(ResearchState)
    # Phase 7 (Resilience) -- proven first on just "news", the exact node a
    # real httpx.ReadError hit during Phase 6 testing (see book/chapter-06):
    # a simulated version of that same error was retried automatically, the
    # super-step never failed, and Fundamentals/Technical (its parallel
    # siblings) were completely unaffected. Every node here calls the model
    # client and is exposed to the same class of transient failure, so the
    # same default RetryPolicy() (3 attempts, exponential backoff + jitter)
    # now applies uniformly, not just to the one node that happened to fail.
    # Persistent-failure degradation now lives INSIDE each node itself (see
    # _degraded_result above) -- not via error_handler=, for the reason
    # documented there.
    builder.add_node("fundamentals", fundamentals_node, retry_policy=RetryPolicy())
    builder.add_node("technical", technical_node, retry_policy=RetryPolicy())
    builder.add_node("news", news_node, retry_policy=RetryPolicy())
    builder.add_node("risk", risk_node, retry_policy=RetryPolicy())
    builder.add_node("devil_advocate", devil_advocate_node, retry_policy=RetryPolicy())
    builder.add_node("decision", decision_node, retry_policy=RetryPolicy())

    # Fan-out: all three fire from START in parallel, none waits on the others.
    builder.add_edge(START, "fundamentals")
    builder.add_edge(START, "technical")
    builder.add_edge(START, "news")

    # Fan-in: risk only runs once ALL three parallel branches have finished.
    builder.add_edge("fundamentals", "risk")
    builder.add_edge("technical", "risk")
    builder.add_edge("news", "risk")

    # Devil's Advocate needs Risk's summary to build counter-evidence against,
    # so it runs after Risk rather than in parallel with it. Decision runs
    # last, using Devil's Advocate's counter-thesis as one more input.
    builder.add_edge("risk", "devil_advocate")
    builder.add_edge("devil_advocate", "decision")
    builder.add_edge("decision", END)

    return builder.compile(checkpointer=checkpointer)


async def run_research(job_id: str, ticker: str, market: str, checkpointer=None) -> dict:
    graph = build_graph(checkpointer)
    initial_state: ResearchState = {
        "job_id": job_id,
        "ticker": ticker,
        "market": market,
        "fundamentals_data": {},
        "fundamentals_summary": "",
        "technical_summary": "",
        "news_summary": "",
        "risk_summary": "",
        "risk_flags": [],
        "devil_advocate_summary": "",
        "devil_advocate_data": {},
        "recommendation": "",
        "overall_score": None,
        "hard_stops_triggered": [],
        "intrinsic_value": {},
        "final_report": "",
        "usage_log": [],
    }

    if checkpointer is None:
        # No durability requested (e.g. the standalone __main__ test below) --
        # exact previous behavior, no thread_id/config needed at all.
        result = await graph.ainvoke(initial_state)
    else:
        # thread_id is OUR chosen identity for "this ticker's run within this
        # job" -- job_id alone isn't enough, since one job fans out into
        # independent per-ticker graph runs (same reasoning as short-term
        # memory's Redis keys). checkpointer.aget_tuple() is the cheap check
        # that tells us whether this is a fresh run or a crash survivor:
        # None -> nothing checkpointed yet, pass real initial state; a real
        # tuple -> a checkpoint already exists, pass None so LangGraph resumes
        # from the last completed super-step instead of redoing everything.
        thread_id = f"{job_id}:{ticker}"
        config = {"configurable": {"thread_id": thread_id}}
        existing = await checkpointer.aget_tuple(config)
        resume_input = None if existing else initial_state
        result = await graph.ainvoke(resume_input, config)

    total_usage = _empty_usage()
    for usage in result["usage_log"]:
        for key in total_usage:
            total_usage[key] += usage.get(key, 0)
    result["total_usage"] = total_usage

    return result


if __name__ == "__main__":
    import asyncio
    final = asyncio.run(run_research("standalone-test-job", "AAPL", "US"))
    print(f"Recommendation: {final['recommendation']} (score {final['overall_score']})")
    print(final["final_report"])
    print()
    print("Hard stops:", final["hard_stops_triggered"])
    print("Devil's Advocate:", final["devil_advocate_summary"])
    print()
    print("Risk flags:", final["risk_flags"])
    print("Total usage:", final["total_usage"])
