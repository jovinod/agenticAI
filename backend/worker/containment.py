from typing import Any, Awaitable, Callable

TickerCall = Callable[[], Awaitable[str]]


async def run_ticker_safely(ticker: str, call: TickerCall) -> str:
    """The worker containment boundary for one ticker within a job.

    A graph node's RetryPolicy already retries a transient failure
    in-process; this is what happens after retries are exhausted and the
    exception still escapes graph.ainvoke(). One ticker's permanent
    failure degrades that ticker's line and lets the rest of the job's
    tickers, and the worker's message loop, keep going -- it is never a
    reason to leave the job stuck in "running" or to crash the process.
    """
    try:
        return await call()
    except Exception as exc:
        return f"{ticker}: research unavailable after retries ({exc})"
