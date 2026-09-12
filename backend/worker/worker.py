import asyncio
import json
import os

from azure.servicebus.aio import ServiceBusClient
from sqlmodel import Session, SQLModel, create_engine, select

from checkpointing import get_checkpointer
from containment import run_ticker_safely
from graph import build_graph
from models import Job
from thread import build_thread_id, resolve_resume_input

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


research_graph = None


async def get_research_graph():
    """Built once, lazily, on first use -- constructing it needs a real
    async connection to Postgres for the checkpointer, which module
    import time cannot provide."""
    global research_graph
    if research_graph is None:
        checkpointer = await get_checkpointer()
        research_graph = build_graph(checkpointer)
    return research_graph


async def _run_graph_for_ticker(ticker: str, job_id: str) -> str:
    graph = await get_research_graph()
    checkpointer = await get_checkpointer()
    thread_id = build_thread_id(job_id, ticker)
    resume_input, config = await resolve_resume_input(
        checkpointer, thread_id, {"ticker": ticker, "job_id": job_id}
    )
    state = await graph.ainvoke(resume_input, config)
    return f"{ticker} [{state.get('recommendation', 'N/A')}]: {state['final_report']}"


async def summarize_ticker(ticker: str, job_id: str) -> str:
    """Each node already carries a RetryPolicy for transient failures;
    this is the containment boundary for what happens after retries are
    exhausted -- one ticker degrades to an explicit unavailable line
    rather than taking down the rest of the job."""
    return await run_ticker_safely(ticker, lambda: _run_graph_for_ticker(ticker, job_id))


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
        "summary": [await summarize_ticker(ticker, job_id) for ticker in tickers],
    }

    with Session(engine) as session:
        job = session.exec(select(Job).where(Job.job_id == job_id)).first()
        job.status = "done"
        job.result = json.dumps(result)
        session.add(job)
        session.commit()


async def _mark_job_failed(job_id: str, exc: Exception) -> None:
    with Session(engine) as session:
        job = session.exec(select(Job).where(Job.job_id == job_id)).first()
        if job is None:
            return
        job.status = "failed"
        job.result = json.dumps({"jobId": job_id, "error": str(exc)})
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
                # A per-ticker failure is already contained inside
                # process_message; this catches something unexpected
                # enough to reach here (e.g. a DB write failure) so one
                # bad job marks itself failed instead of killing the
                # receive loop for every job after it.
                try:
                    await process_message(data["job_id"], data["tickers"])
                except Exception as exc:
                    await _mark_job_failed(data["job_id"], exc)
                await receiver.complete_message(message)


if __name__ == "__main__":
    asyncio.run(main())
