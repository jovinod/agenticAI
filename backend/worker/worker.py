import asyncio
import json
import os
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
import redis.asyncio as redis
from sqlmodel import create_engine, Session, select
from models import TickerJob, TokenUsage, TickerProfile
from agents.graph import run_research
from llm.model_client import AZURE_OPENAI_DEPLOYMENT

# No-op in Azure (no .env.local file there) — Container Apps sets real env vars directly.
# Doesn't override an already-set env var, so an explicit shell export still wins if used.
load_dotenv(".env.local")

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
)
engine = create_engine(DATABASE_URL)

SERVICEBUS_CONNECTION_STRING = os.environ.get("SERVICEBUS_CONNECTION_STRING")
SERVICEBUS_QUEUE_NAME = os.environ.get("SERVICEBUS_QUEUE_NAME", "research-jobs")

# Semantic memory's write side lives in a separate deployable (embed-worker),
# not here -- this worker only publishes a message and moves on, so a slow or
# failing embeddings call never blocks the actual research pipeline. Own
# queue, own SAS scope (send-only), same reasoning as research-jobs' own
# separate send-only/listen-only rules.
SERVICEBUS_EMBED_CONNECTION_STRING = os.environ.get("SERVICEBUS_EMBED_CONNECTION_STRING")
SERVICEBUS_EMBED_QUEUE_NAME = os.environ.get("SERVICEBUS_EMBED_QUEUE_NAME", "embedding-jobs")

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


def _upsert_ticker_profile(session, ticker: str, market: str, sector, industry):
    """Profile memory -- durable facts about this ticker, exact key lookup
    (ticker, market), unrelated to any single job. A new ticker gets a fresh
    row; a repeat gets its research_count bumped and last_researched_at
    refreshed, in place."""
    profile = session.exec(
        select(TickerProfile).where(TickerProfile.ticker == ticker, TickerProfile.market == market)
    ).first()

    if profile is None:
        profile = TickerProfile(ticker=ticker, market=market, sector=sector, industry=industry)
    else:
        profile.research_count += 1
        profile.last_researched_at = datetime.utcnow()
        if sector:
            profile.sector = sector
        if industry:
            profile.industry = industry

    session.add(profile)
    session.commit()


async def process_ticker(job_id: str, ticker: str, market: str, embed_sender):
    with Session(engine) as session:
        task = session.exec(
            select(TickerJob).where(TickerJob.job_id == job_id, TickerJob.ticker == ticker)
        ).first()
        task.status = "running"
        session.add(task)
        session.commit()

    print(f"Processing {ticker} ({market}) for job {job_id}...")
    # The full multi-agent graph -- Fundamentals/Technical/News run in parallel,
    # Risk (deterministic flag_risk_factors + cross-signal judgment) waits for
    # all three, Synthesizer runs last. No separate direct calls here anymore --
    # the graph's own Fundamentals/Risk agents already do that internally.
    graph_result = await run_research(job_id, ticker, market)
    data = graph_result.get("fundamentals_data", {})

    if not data or "error" in data:
        summary_line = data.get("error", f"{ticker}: fundamentals data unavailable")
    else:
        summary_line = (
            f"{ticker}: {data['currency']} {data['price']}, "
            f"P/E {data['pe_ratio']}, 52w range {data['fifty_two_week_low']}-{data['fifty_two_week_high']}"
        )
        flags = graph_result.get("risk_flags", [])
        if flags:
            summary_line += " | Risk flags: " + "; ".join(flags)
        summary_line += " | Report: " + graph_result.get("final_report", "")

        usage = graph_result["total_usage"]
        with Session(engine) as session:
            session.add(TokenUsage(
                job_id=job_id,
                ticker=ticker,
                model=AZURE_OPENAI_DEPLOYMENT,
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                total_tokens=usage["total_tokens"],
                estimated_cost_usd=usage["estimated_cost_usd"],
            ))
            session.commit()

        with Session(engine) as session:
            _upsert_ticker_profile(session, ticker, market, data.get("sector"), data.get("industry"))

        # Semantic memory: publish, don't embed inline -- embed-worker owns the
        # actual Foundry call and the ResearchReport write, so a slow or failing
        # embeddings call never adds latency to this job's own completion.
        report_text = graph_result.get("final_report", "")
        if report_text:
            embed_message = json.dumps({
                "job_id": job_id, "ticker": ticker, "market": market, "report_text": report_text,
            })
            await embed_sender.send_messages(ServiceBusMessage(embed_message))
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
    embed_client = ServiceBusClient.from_connection_string(SERVICEBUS_EMBED_CONNECTION_STRING)
    async with client, embed_client:
        async with (
            client.get_queue_receiver(queue_name=SERVICEBUS_QUEUE_NAME) as receiver,
            embed_client.get_queue_sender(queue_name=SERVICEBUS_EMBED_QUEUE_NAME) as embed_sender,
        ):
            print("Worker started, waiting for messages...")
            async for msg in receiver:
                data = json.loads(str(msg))
                await process_ticker(data["job_id"], data["ticker"], data["market"], embed_sender)
                await receiver.complete_message(msg)  # acknowledge — without this, Service Bus redelivers it


if __name__ == "__main__":
    asyncio.run(main())
