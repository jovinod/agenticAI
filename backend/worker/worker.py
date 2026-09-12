import asyncio
import json
import os

from azure.servicebus.aio import ServiceBusClient
from sqlmodel import Session, SQLModel, create_engine, select

from market_data import fetch_stock_data
from models import Job
from risk_rules import flag_risk_factors, format_ticker_result
from search_client import search_via_mcp

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
)
SERVICEBUS_CONNECTION_STRING = os.environ.get("SERVICEBUS_CONNECTION_STRING")
SERVICEBUS_QUEUE_NAME = os.environ.get("SERVICEBUS_QUEUE_NAME", "research-jobs")

engine = create_engine(DATABASE_URL)
SQLModel.metadata.create_all(engine)

# Gives the frontend's "running" state something to observe before real
# per-ticker work starts, independent of how long that work takes.
JOB_DELAY_SECONDS = 2.0


async def fetch_headline(ticker: str) -> str:
    """Crosses the MCP boundary for one real search; never fails the job."""
    try:
        results = await search_via_mcp(f"{ticker} stock news", max_results=1)
    except Exception as exc:  # provider unavailable, no key, MCP transport error
        return f"headline unavailable ({exc})"

    if not results:
        return "no recent headline found"

    try:
        parsed = json.loads(results[0])
        first = parsed[0] if isinstance(parsed, list) else parsed
        return first["title"] if first else "no recent headline found"
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return results[0]


async def summarize_ticker(ticker: str) -> str:
    data = fetch_stock_data(ticker)
    headline = await fetch_headline(ticker)

    if "error" in data:
        return f"{ticker}: data unavailable ({data['error']}); {headline}"

    flags = flag_risk_factors(data)
    result = format_ticker_result(data, flags)
    flag_text = ", ".join(flags) if flags else "none"
    currency = result.get("currency") or ""
    return (
        f"{ticker}: price {result['price']} {currency}, "
        f"P/E {result.get('pe_ratio')}, risk flags: {flag_text}; {headline}"
    )


async def process_message(
    job_id: str,
    tickers: list[str],
    delay_seconds: float = JOB_DELAY_SECONDS,
) -> None:
    with Session(engine) as session:
        job = session.exec(select(Job).where(Job.job_id == job_id)).first()
        job.status = "running"
        session.add(job)
        session.commit()

    await asyncio.sleep(delay_seconds)

    result = {
        "jobId": job_id,
        "summary": [await summarize_ticker(ticker) for ticker in tickers],
    }

    with Session(engine) as session:
        job = session.exec(select(Job).where(Job.job_id == job_id)).first()
        job.status = "done"
        job.result = json.dumps(result)
        session.add(job)
        session.commit()


async def main() -> None:
    client = ServiceBusClient.from_connection_string(SERVICEBUS_CONNECTION_STRING)
    async with client:
        async with client.get_queue_receiver(
            queue_name=SERVICEBUS_QUEUE_NAME
        ) as receiver:
            print("Worker started, waiting for messages...")
            async for message in receiver:
                data = json.loads(str(message))
                await process_message(data["job_id"], data["tickers"])
                await receiver.complete_message(message)


if __name__ == "__main__":
    asyncio.run(main())
