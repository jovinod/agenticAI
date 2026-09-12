import json
import os

from azure.servicebus import ServiceBusMessage

from servicebus_client import build_servicebus_client

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
    client = build_servicebus_client()
    async with client:
        async with client.get_queue_sender(
            queue_name=SERVICEBUS_EMBEDDING_QUEUE_NAME
        ) as sender:
            await sender.send_messages(message)
