"""
The LangGraph orchestration wiring for Phase 5's multi-agent research
pipeline -- the ORCHESTRATOR in the Harness-vs-Orchestrator sense
(book/chapter-04-the-first-agent.md): decides which agent runs when and
what state passes between them, never reimplements the harness cycle
itself. Every node below just calls into one of agents/*.py, each of which
goes through the same shared agent_harness.py.

News, Fundamentals, and Technical run in parallel (none depend on each
other's output); Risk waits for all three; Synthesizer runs last.

Each node also writes its own result to short-term memory (memory/short_term.py)
as soon as it finishes -- so a still-running job has real partial progress to
show, not just silence until the whole graph completes.
"""
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from agents import fundamentals_agent, technical_agent, news_agent, risk_agent, synthesizer_agent
from memory.short_term import write_progress


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


async def fundamentals_node(state: ResearchState) -> dict:
    result = await fundamentals_agent.run(state["ticker"], state["market"])
    summary = result.get("answer") or result.get("error", "Fundamentals data unavailable.")
    await write_progress(state["job_id"], state["ticker"], "fundamentals", summary)
    return {
        "fundamentals_data": result.get("data", {}),
        "fundamentals_summary": summary,
        "usage_log": [result.get("usage", {})],
    }


async def technical_node(state: ResearchState) -> dict:
    result = await technical_agent.run(state["ticker"], state["market"])
    summary = result.get("answer") or result.get("error", "Technical data unavailable.")
    await write_progress(state["job_id"], state["ticker"], "technical", summary)
    return {
        "technical_summary": summary,
        "usage_log": [result.get("usage", {})],
    }


async def news_node(state: ResearchState) -> dict:
    result = await news_agent.run(state["ticker"], state["market"])
    summary = result.get("answer", "News assessment unavailable.")
    await write_progress(state["job_id"], state["ticker"], "news", summary)
    return {
        "news_summary": summary,
        "usage_log": [result.get("usage", {})],
    }


async def risk_node(state: ResearchState) -> dict:
    result = await risk_agent.run(
        state.get("fundamentals_data", {}),
        state.get("fundamentals_summary", ""),
        state.get("technical_summary", ""),
        state.get("news_summary", ""),
    )
    summary = result.get("answer", "Risk assessment unavailable.")
    await write_progress(state["job_id"], state["ticker"], "risk", summary)
    return {
        "risk_summary": summary,
        "risk_flags": result.get("flags", []),
        "usage_log": [result.get("usage", {})],
    }


async def synthesizer_node(state: ResearchState) -> dict:
    result = await synthesizer_agent.run(
        state["ticker"],
        state.get("fundamentals_summary", ""),
        state.get("technical_summary", ""),
        state.get("news_summary", ""),
        state.get("risk_summary", ""),
    )
    summary = result.get("answer", "Report unavailable.")
    await write_progress(state["job_id"], state["ticker"], "synthesizer", summary)
    return {
        "final_report": summary,
        "usage_log": [result.get("usage", {})],
    }


def build_graph():
    builder = StateGraph(ResearchState)
    builder.add_node("fundamentals", fundamentals_node)
    builder.add_node("technical", technical_node)
    builder.add_node("news", news_node)
    builder.add_node("risk", risk_node)
    builder.add_node("synthesizer", synthesizer_node)

    # Fan-out: all three fire from START in parallel, none waits on the others.
    builder.add_edge(START, "fundamentals")
    builder.add_edge(START, "technical")
    builder.add_edge(START, "news")

    # Fan-in: risk only runs once ALL three parallel branches have finished.
    builder.add_edge("fundamentals", "risk")
    builder.add_edge("technical", "risk")
    builder.add_edge("news", "risk")

    builder.add_edge("risk", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile()


async def run_research(job_id: str, ticker: str, market: str) -> dict:
    graph = build_graph()
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
        "final_report": "",
        "usage_log": [],
    }
    result = await graph.ainvoke(initial_state)

    total_usage = _empty_usage()
    for usage in result["usage_log"]:
        for key in total_usage:
            total_usage[key] += usage.get(key, 0)
    result["total_usage"] = total_usage

    return result


if __name__ == "__main__":
    import asyncio
    final = asyncio.run(run_research("standalone-test-job", "AAPL", "US"))
    print(final["final_report"])
    print()
    print("Risk flags:", final["risk_flags"])
    print("Total usage:", final["total_usage"])
