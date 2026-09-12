import json
import os

from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage

SERVICEBUS_CONNECTION_STRING = os.environ.get("SERVICEBUS_CONNECTION_STRING")
SERVICEBUS_EMBEDDING_QUEUE_NAME = os.environ.get(
    "SERVICEBUS_EMBEDDING_QUEUE_NAME", "embedding-jobs"
)


async def publish_embedding_job(
    job_id: str, ticker: str, market: str, report_text: str
) -> None:
    """The research worker does not wait for this. Publishing a compact
    event and moving on keeps embedding outside the research critical
    path -- if the embed worker is stopped, this message just waits."""
    message = ServiceBusMessage(
        json.dumps(
            {
                "job_id": job_id,
                "ticker": ticker,
                "market": market,
                "report_text": report_text,
            }
        )
    )
    client = ServiceBusClient.from_connection_string(SERVICEBUS_CONNECTION_STRING)
    async with client:
        async with client.get_queue_sender(
            queue_name=SERVICEBUS_EMBEDDING_QUEUE_NAME
        ) as sender:
            await sender.send_messages(message)
