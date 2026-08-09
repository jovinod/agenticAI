import asyncio
import json
import os
from azure.servicebus.aio import ServiceBusClient
from sqlmodel import create_engine, Session, select
from models import Job

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
)
engine = create_engine(DATABASE_URL)

SERVICEBUS_CONNECTION_STRING = os.environ.get("SERVICEBUS_CONNECTION_STRING")
SERVICEBUS_QUEUE_NAME = os.environ.get("SERVICEBUS_QUEUE_NAME", "research-jobs")


async def process_research(job_id: str, tickers: list[str]):
    with Session(engine) as session:
        job = session.exec(select(Job).where(Job.job_id == job_id)).first()
        job.status = "running"
        session.add(job)
        session.commit()

    print(f"Processing job {job_id} for {tickers}...")
    await asyncio.sleep(3)  # fake delay — stands in for real agent work, later phases
    print(f"Job {job_id} done.")

    result = {
        "tickers": tickers,
        "summary": [f"{t}: looks solid, no major red flags." for t in tickers],
    }

    with Session(engine) as session:
        job = session.exec(select(Job).where(Job.job_id == job_id)).first()
        job.status = "done"
        job.result = json.dumps(result)
        session.add(job)
        session.commit()


async def main():
    client = ServiceBusClient.from_connection_string(SERVICEBUS_CONNECTION_STRING)
    async with client:
        async with client.get_queue_receiver(queue_name=SERVICEBUS_QUEUE_NAME) as receiver:
            print("Worker started, waiting for messages...")
            async for msg in receiver:
                data = json.loads(str(msg))
                await process_research(data["job_id"], data["tickers"])
                await receiver.complete_message(msg)  # acknowledge — without this, Service Bus redelivers it


if __name__ == "__main__":
    asyncio.run(main())
