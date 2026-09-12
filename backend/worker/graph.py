import operator
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from typing import Any

import model_client
from decision import make_decision
from devil_advocate import run_devil_advocate
from extended_data import fetch_extended_data
from market_data import fetch_stock_data
from profile_store import record_research
from progress import write_progress
from publish_embedding_job import publish_embedding_job
from risk_rules import flag_risk_factors
from semantic_search import search_reports
from synthesis import run_synthesis
from tools import search

MARKET = "US"


class ResearchState(TypedDict, total=False):
    ticker: str
    job_id: str
    prior_context: str
    fundamentals_summary: str
    technical_summary: str
    news_summary: str
    risk_summary: str
    dissent: str
    final_report: str
    recommendation: str
    overall_score: float | None
    hard_stops_triggered: list[str]
    intrinsic_value: dict[str, Any]
    # Additive reducer: three parallel specialists each contribute one
    # independent usage record. Concatenation is correct because the
    # records are independent -- a shared running total would race.
    usage_log: Annotated[list[dict], operator.add]
    node_intervals: Annotated[list[dict], operator.add]


def _interval(name: str, start: float, end: float) -> dict:
    return {"node": name, "start": start, "end": end}


async def memory_node(state: ResearchState) -> dict:
    """Real memory, real infra: records this research in the durable
    ticker profile, then checks past reports for relevant prior context.
    A cold start (no prior reports, or the table not reachable yet) is
    not an error -- it just means there is nothing to recall."""
    ticker = state["ticker"]
    record_research(ticker, MARKET)

    try:
        prior = await search_reports(f"{ticker} stock research", limit=1)
    except Exception:
        prior = []

    if not prior:
        return {"prior_context": ""}
    return {"prior_context": prior[0]["report_text"]}


async def _write_progress(job_id: str, ticker: str, agent_name: str, summary: str) -> None:
    if not job_id:
        return
    try:
        await write_progress(job_id, ticker, agent_name, summary)
    except Exception:
        pass  # progress is observability, never a reason to fail the job


async def fundamentals_node(state: ResearchState) -> dict:
    start = time.monotonic()
    ticker = state["ticker"]
    data = fetch_stock_data(ticker)
    if "error" in data:
        summary = f"fundamentals unavailable ({data['error']})"
        usage: dict = {}
    else:
        result = await run_synthesis(
            model_client.chat,
            "You are a fundamentals analyst. In two sentences, assess the "
            "company's valuation and profitability from the data given.",
            f"Ticker {ticker}. Price {data.get('price')} {data.get('currency')}, "
            f"P/E {data.get('pe_ratio')}.",
        )
        summary = result["answer"]
        usage = result.get("usage", {})
    end = time.monotonic()
    await _write_progress(state.get("job_id", ""), ticker, "fundamentals", summary)
    return {
        "fundamentals_summary": summary,
        "usage_log": [{"node": "fundamentals", **usage}],
        "node_intervals": [_interval("fundamentals", start, end)],
    }


async def technical_node(state: ResearchState) -> dict:
    start = time.monotonic()
    ticker = state["ticker"]
    data = fetch_stock_data(ticker)
    if "error" in data:
        summary = f"technical view unavailable ({data['error']})"
        usage: dict = {}
    else:
        result = await run_synthesis(
            model_client.chat,
            "You are a technical analyst. In two sentences, assess where the "
            "current price sits within its 52-week range.",
            f"Ticker {ticker}. Price {data.get('price')}, "
            f"52-week low {data.get('fifty_two_week_low')}, "
            f"52-week high {data.get('fifty_two_week_high')}.",
        )
        summary = result["answer"]
        usage = result.get("usage", {})
    end = time.monotonic()
    await _write_progress(state.get("job_id", ""), ticker, "technical", summary)
    return {
        "technical_summary": summary,
        "usage_log": [{"node": "technical", **usage}],
        "node_intervals": [_interval("technical", start, end)],
    }


async def news_node(state: ResearchState) -> dict:
    start = time.monotonic()
    ticker = state["ticker"]
    try:
        headlines = await search(f"{ticker} stock news", max_results=3)
    except Exception as exc:  # provider unavailable, no key, MCP transport error
        headlines = [f"search unavailable ({exc})"]

    result = await run_synthesis(
        model_client.chat,
        "You are a news analyst. In two sentences, summarize the sentiment "
        "and materiality of the headlines given.",
        f"Ticker {ticker}. Headlines: {headlines}",
    )
    end = time.monotonic()
    await _write_progress(state.get("job_id", ""), ticker, "news", result["answer"])
    return {
        "news_summary": result["answer"],
        "usage_log": [{"node": "news", **result.get("usage", {})}],
        "node_intervals": [_interval("news", start, end)],
    }


async def risk_node(state: ResearchState) -> dict:
    """Waits for all three specialists (the fan-in barrier), then
    combines their results. Deterministic: risk flags come from Chapter
    4's real, inspectable rules, not model judgment."""
    start = time.monotonic()
    ticker = state["ticker"]
    data = fetch_stock_data(ticker)
    flags = flag_risk_factors(data) if "error" not in data else []
    flag_text = ", ".join(flags) if flags else "none"
    combined = ", ".join(
        state[key]
        for key in ("fundamentals_summary", "technical_summary", "news_summary")
        if key in state
    )
    end = time.monotonic()
    return {
        "risk_summary": f"risk flags: {flag_text}; based on: {combined}",
        "node_intervals": [_interval("risk", start, end)],
    }


async def _search_web(query: str) -> list[str]:
    return await search(query, max_results=3)


async def devil_advocate_node(state: ResearchState) -> dict:
    start = time.monotonic()
    summaries = {
        "fundamentals": state.get("fundamentals_summary", ""),
        "technical": state.get("technical_summary", ""),
        "news": state.get("news_summary", ""),
        "risk": state.get("risk_summary", ""),
    }
    result = await run_devil_advocate(model_client.chat, summaries, _search_web)
    end = time.monotonic()
    return {
        "dissent": result["dissent"],
        "node_intervals": [_interval("devil_advocate", start, end)],
    }


async def decision_node(state: ResearchState) -> dict:
    """Terminal node: the model proposes a recommendation, then Python
    overwrites the deterministic fields (hard stops, intrinsic value)
    from real fetched data -- the model never controls those numbers."""
    start = time.monotonic()
    ticker = state["ticker"]
    extended_data = fetch_extended_data(ticker)

    prior_context = state.get("prior_context", "")
    user_message = (
        f"Risk assessment: {state.get('risk_summary', '')}\n"
        f"Dissent: {state.get('dissent', '')}"
    )
    if prior_context:
        user_message += f"\nPrior research on this ticker: {prior_context}"

    messages = [
        {
            "role": "system",
            "content": "You are the decision agent. Respond with JSON: "
            '{"recommendation": "BUY|WAIT|HOLD|OVERPRICED", '
            '"overall_score": number, "summary": string}',
        },
        {"role": "user", "content": user_message},
    ]
    result = await model_client.chat(messages, [])
    decision = make_decision(result["message"]["content"], extended_data)
    end = time.monotonic()

    final_report = decision["summary"]
    await _write_progress(state.get("job_id", ""), ticker, "decision", final_report)
    try:
        await publish_embedding_job(state.get("job_id", ""), ticker, MARKET, final_report)
    except Exception:
        pass  # embedding is out of the research critical path

    return {
        "recommendation": decision["recommendation"],
        "overall_score": decision["overall_score"],
        "hard_stops_triggered": decision["hard_stops_triggered"],
        "intrinsic_value": decision["intrinsic_value"],
        "final_report": final_report,
        "usage_log": [{"node": "decision", **result.get("usage", {})}],
        "node_intervals": [_interval("decision", start, end)],
    }


def build_graph():
    """The chapter-stage topology: a memory node records and recalls
    context, then three independent specialists fan out, converge on
    Risk, then Risk feeds Devil's Advocate, then Decision -- Synthesizer
    is removed, not retained beside them, so only one component ever
    owns the final report."""
    builder = StateGraph(ResearchState)
    builder.add_node("memory", memory_node)
    builder.add_node("fundamentals", fundamentals_node)
    builder.add_node("technical", technical_node)
    builder.add_node("news", news_node)
    builder.add_node("risk", risk_node)
    builder.add_node("devil_advocate", devil_advocate_node)
    builder.add_node("decision", decision_node)

    builder.add_edge(START, "memory")
    builder.add_edge("memory", "fundamentals")
    builder.add_edge("memory", "technical")
    builder.add_edge("memory", "news")

    builder.add_edge("fundamentals", "risk")
    builder.add_edge("technical", "risk")
    builder.add_edge("news", "risk")

    builder.add_edge("risk", "devil_advocate")
    builder.add_edge("devil_advocate", "decision")
    builder.add_edge("decision", END)

    return builder.compile()
