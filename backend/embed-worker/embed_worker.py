import asyncio
import json
import os
from dotenv import load_dotenv
from azure.servicebus.aio import ServiceBusClient
from sqlmodel import create_engine, Session
from models import ResearchReport
from embeddings_client import embed

# No-op in Azure (no .env.local file there) -- Container Apps sets real env vars directly.
load_dotenv(".env.local")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
)
engine = create_engine(DATABASE_URL)

SERVICEBUS_CONNECTION_STRING = os.environ.get("SERVICEBUS_CONNECTION_STRING")
SERVICEBUS_QUEUE_NAME = os.environ.get("SERVICEBUS_EMBEDDING_QUEUE_NAME", "embedding-jobs")


async def process_message(job_id: str, ticker: str, market: str, report_text: str):
    print(f"Embedding report for {ticker} ({market}), job {job_id}...")
    vector = await embed(report_text)

    with Session(engine) as session:
        session.add(ResearchReport(
            job_id=job_id, ticker=ticker, market=market,
            report_text=report_text, embedding=vector,
        ))
        session.commit()
    print(f"{ticker} report embedded and stored.")


async def main():
    client = ServiceBusClient.from_connection_string(SERVICEBUS_CONNECTION_STRING)
    async with client:
        async with client.get_queue_receiver(queue_name=SERVICEBUS_QUEUE_NAME) as receiver:
            print("Embed worker started, waiting for messages...")
            async for msg in receiver:
                data = json.loads(str(msg))
                await process_message(data["job_id"], data["ticker"], data["market"], data["report_text"])
                await receiver.complete_message(msg)


if __name__ == "__main__":
    asyncio.run(main())
