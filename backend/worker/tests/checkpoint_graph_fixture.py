import asyncio
import operator
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph


class FixtureState(TypedDict, total=False):
    fundamentals_summary: str
    technical_summary: str
    news_summary: str
    risk_summary: str
    dissent: str
    final_report: str
    call_log: Annotated[list[str], operator.add]


def make_specialist(name: str, summary_key: str, call_counts: dict, fail_node: str | None):
    async def node(state: FixtureState) -> dict:
        call_counts[name] = call_counts.get(name, 0) + 1
        if fail_node == name and call_counts[name] == 1:
            raise RuntimeError(f"simulated crash in {name}")
        await asyncio.sleep(0.01)
        return {summary_key: f"{name} summary", "call_log": [name]}

    return node


def make_sequential_node(name: str, summary_key: str, call_counts: dict, fail_node: str | None):
    async def node(state: FixtureState) -> dict:
        call_counts[name] = call_counts.get(name, 0) + 1
        if fail_node == name and call_counts[name] == 1:
            raise RuntimeError(f"simulated crash in {name}")
        combined = (
            state.get("fundamentals_summary", "")
            + state.get("technical_summary", "")
            + state.get("news_summary", "")
        )
        return {summary_key: f"{name} over: {combined}", "call_log": [name]}

    return node


def build_fixture_graph(checkpointer, call_counts: dict, fail_node: str | None = None):
    """Mirrors the real worker graph's shape (three specialists fan out,
    converge on Risk, then Devil's Advocate, then Decision) with
    instrumented fake nodes -- proving the checkpoint commit-boundary
    mechanism against real Postgres without spending real model/search
    calls on it, the same trade-off Chapter 8's own topology tests made."""
    builder = StateGraph(FixtureState)
    builder.add_node(
        "fundamentals",
        make_specialist("fundamentals", "fundamentals_summary", call_counts, fail_node),
    )
    builder.add_node(
        "technical",
        make_specialist("technical", "technical_summary", call_counts, fail_node),
    )
    builder.add_node("news", make_specialist("news", "news_summary", call_counts, fail_node))
    builder.add_node(
        "risk", make_sequential_node("risk", "risk_summary", call_counts, fail_node)
    )
    builder.add_node(
        "devil_advocate",
        make_sequential_node("devil_advocate", "dissent", call_counts, fail_node),
    )
    builder.add_node(
        "decision",
        make_sequential_node("decision", "final_report", call_counts, fail_node),
    )

    builder.add_edge(START, "fundamentals")
    builder.add_edge(START, "technical")
    builder.add_edge(START, "news")
    builder.add_edge("fundamentals", "risk")
    builder.add_edge("technical", "risk")
    builder.add_edge("news", "risk")
    builder.add_edge("risk", "devil_advocate")
    builder.add_edge("devil_advocate", "decision")
    builder.add_edge("decision", END)

    return builder.compile(checkpointer=checkpointer)
