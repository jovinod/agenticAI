import asyncio
import json
import os
from dotenv import load_dotenv
from azure.servicebus.aio import ServiceBusClient
from azure.identity.aio import DefaultAzureCredential
from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential
import psycopg
from sqlmodel import create_engine, Session
from models import ResearchReport
from embeddings_client import embed

# No-op in Azure (no .env.local file there) -- Container Apps sets real env vars directly.
load_dotenv(".env.local")

# Phase 8, Stage B -- Managed Identity instead of a password secret, when
# running in Azure. Same reasoning as backend/api/main.py: the local Docker
# Postgres container has no AAD support at all, so this is a genuine second
# code path, not a same-code-either-way fallback like Service Bus's.
DATABASE_HOST = os.environ.get("DATABASE_HOST")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "alpha")
DATABASE_USER = os.environ.get("DATABASE_USER")  # must match the Managed Identity's Entra ID display name
PG_TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

if DATABASE_HOST:
    _pg_credential = SyncDefaultAzureCredential()

    def _get_pg_connection():
        token = _pg_credential.get_token(PG_TOKEN_SCOPE).token
        return psycopg.connect(
            host=DATABASE_HOST, port=5432, dbname=DATABASE_NAME,
            user=DATABASE_USER, password=token, sslmode="require",
        )

    engine = create_engine("postgresql+psycopg://", creator=_get_pg_connection)
else:
    DATABASE_URL = os.environ.get(
        "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
    )
    engine = create_engine(DATABASE_URL)

# Phase 8, Stage B -- Managed Identity (granted "Azure Service Bus Data
# Receiver" on embedding-jobs specifically) instead of a SAS connection string.
SERVICEBUS_FQDN = os.environ.get("SERVICEBUS_FQDN", "alpharesearchsb.servicebus.windows.net")
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
    credential = DefaultAzureCredential()
    client = ServiceBusClient(fully_qualified_namespace=SERVICEBUS_FQDN, credential=credential)
    async with client, credential:
        async with client.get_queue_receiver(queue_name=SERVICEBUS_QUEUE_NAME) as receiver:
            print("Embed worker started, waiting for messages...")
            async for msg in receiver:
                try:
                    data = json.loads(str(msg))
                    job_id, ticker, market, report_text = (
                        data["job_id"], data["ticker"], data["market"], data["report_text"]
                    )
                except Exception as exc:
                    # Same fix as worker.py's main() -- a malformed message
                    # must not crash-loop this process forever.
                    print(f"Malformed message, dropping: {exc}")
                    await receiver.complete_message(msg)
                    continue

                try:
                    await process_message(job_id, ticker, market, report_text)
                except Exception as exc:
                    # A real permission error here (found live, in production)
                    # propagated straight out of this loop and crashed the
                    # whole process -- every OTHER queued embedding job would
                    # have been taken down with it, the same class of bug as
                    # the message-parsing gap above. Deliberately NOT calling
                    # complete_message() here, unlike the parsing case: unlike
                    # a malformed message, this failure might be transient (or,
                    # as it was here, fixable) -- leaving the message
                    # uncompleted lets Service Bus's own lock-expiry and
                    # maxDeliveryCount redelivery retry it later, without this
                    # process dying and taking every other in-flight job with it.
                    print(f"{ticker} embedding failed, will be redelivered: {exc}")
                    continue

                await receiver.complete_message(msg)


if __name__ == "__main__":
    asyncio.run(main())
