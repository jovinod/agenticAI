import asyncio
import json
import os
from datetime import date, datetime, timedelta
from azure.servicebus.aio import ServiceBusClient
import redis.asyncio as redis
from sqlmodel import create_engine, Session, select
from models import TickerJob
from tools.stock_data import fetch_stock_data

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
)
engine = create_engine(DATABASE_URL)

SERVICEBUS_CONNECTION_STRING = os.environ.get("SERVICEBUS_CONNECTION_STRING")
SERVICEBUS_QUEUE_NAME = os.environ.get("SERVICEBUS_QUEUE_NAME", "research-jobs")

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6380"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")  # unset locally; required for Azure Managed Redis
REDIS_SSL = os.environ.get("REDIS_SSL", "false").lower() == "true"

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    ssl=REDIS_SSL,
    decode_responses=True,
)


def seconds_until_midnight():
    now = datetime.now()
    midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return int((midnight - now).total_seconds())


async def process_ticker(job_id: str, ticker: str, market: str):
    with Session(engine) as session:
        task = session.exec(
            select(TickerJob).where(TickerJob.job_id == job_id, TickerJob.ticker == ticker)
        ).first()
        task.status = "running"
        session.add(task)
        session.commit()

    print(f"Processing {ticker} ({market}) for job {job_id}...")
    # Real data now — direct API call, no MCP/LLM involved (see tools/stock_data.py docstring).
    data = fetch_stock_data(ticker, market)

    if "error" in data:
        summary_line = data["error"]
    else:
        summary_line = (
            f"{ticker}: {data['currency']} {data['price']}, "
            f"P/E {data['pe_ratio']}, 52w range {data['fifty_two_week_low']}-{data['fifty_two_week_high']}"
        )
    print(f"{ticker} done.")

    result = {"tickers": [ticker], "summary": [summary_line]}
    result_json = json.dumps(result)

    cache_key = f"research:{market}:{ticker}:{date.today().isoformat()}"
    await redis_client.set(cache_key, result_json, ex=seconds_until_midnight())

    with Session(engine) as session:
        task = session.exec(
            select(TickerJob).where(TickerJob.job_id == job_id, TickerJob.ticker == ticker)
        ).first()
        task.status = "done"
        task.result = result_json
        session.add(task)
        session.commit()


async def main():
    client = ServiceBusClient.from_connection_string(SERVICEBUS_CONNECTION_STRING)
    async with client:
        async with client.get_queue_receiver(queue_name=SERVICEBUS_QUEUE_NAME) as receiver:
            print("Worker started, waiting for messages...")
            async for msg in receiver:
                data = json.loads(str(msg))
                await process_ticker(data["job_id"], data["ticker"], data["market"])
                await receiver.complete_message(msg)  # acknowledge — without this, Service Bus redelivers it


if __name__ == "__main__":
    asyncio.run(main())
