import asyncio
import json
import os

import httpx
from azure.servicebus.aio import ServiceBusClient
from sqlmodel import Session, SQLModel, create_engine

from models import ResearchReport

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
)
SERVICEBUS_CONNECTION_STRING = os.environ.get("SERVICEBUS_CONNECTION_STRING")
SERVICEBUS_EMBEDDING_QUEUE_NAME = os.environ.get(
    "SERVICEBUS_EMBEDDING_QUEUE_NAME", "embedding-jobs"
)

APIM_BASE_URL = os.environ.get("APIM_BASE_URL", "")
APIM_SUBSCRIPTION_KEY = os.environ.get("APIM_SUBSCRIPTION_KEY", "")
API_VERSION = os.environ.get("APIM_API_VERSION", "2024-10-21")
EMBED_URL = f"{APIM_BASE_URL}/openai/deployments/embed/embeddings"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SQLModel.metadata.create_all(engine)


async def embed_text(text: str) -> list[float]:
    """Embeds report text through the same Azure API Management boundary
    the chat model uses -- one gateway, one managed identity, two
    deployments (chat and embed) behind it."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            EMBED_URL,
            params={"api-version": API_VERSION},
            headers={
                "Ocp-Apim-Subscription-Key": APIM_SUBSCRIPTION_KEY,
                "Content-Type": "application/json",
            },
            json={"input": text},
        )
        response.raise_for_status()
        body = response.json()
    return body["data"][0]["embedding"]


async def process_message(data: dict) -> None:
    """Embeds one completed report and writes the durable row. Embedding
    stays outside the research critical path -- this runs only after a
    report already exists, on its own queue and its own consumer."""
    embedding = await embed_text(data["report_text"])

    with Session(engine) as session:
        session.add(
            ResearchReport(
                job_id=data["job_id"],
                ticker=data["ticker"],
                market=data["market"],
                report_text=data["report_text"],
                embedding=embedding,
            )
        )
        session.commit()


async def main() -> None:
    client = ServiceBusClient.from_connection_string(SERVICEBUS_CONNECTION_STRING)
    async with client:
        async with client.get_queue_receiver(
            queue_name=SERVICEBUS_EMBEDDING_QUEUE_NAME
        ) as receiver:
            print("Embed worker started, waiting for completed reports...")
            async for message in receiver:
                data = json.loads(str(message))
                await process_message(data)
                await receiver.complete_message(message)


if __name__ == "__main__":
    asyncio.run(main())
