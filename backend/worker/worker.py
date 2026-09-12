import asyncio
import json
import os

from azure.servicebus.aio import ServiceBusClient
from sqlmodel import Session, SQLModel, create_engine, select

from market_data import fetch_stock_data
from models import Job
from risk_rules import flag_risk_factors, format_ticker_result

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


def summarize_ticker(ticker: str) -> str:
    data = fetch_stock_data(ticker)
    if "error" in data:
        return f"{ticker}: data unavailable ({data['error']})"

    flags = flag_risk_factors(data)
    result = format_ticker_result(data, flags)
    flag_text = ", ".join(flags) if flags else "none"
    currency = result.get("currency") or ""
    return (
        f"{ticker}: price {result['price']} {currency}, "
        f"P/E {result.get('pe_ratio')}, risk flags: {flag_text}"
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
        "summary": [summarize_ticker(ticker) for ticker in tickers],
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
