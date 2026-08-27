import asyncio
import json
import os
from datetime import date, datetime, timedelta
from dotenv import load_dotenv
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.identity.aio import DefaultAzureCredential
import redis.asyncio as redis
from sqlmodel import create_engine, Session, select
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
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

# AsyncPostgresSaver wants a plain libpq conninfo string ("postgresql://...") --
# confirmed directly, it rejects SQLAlchemy's "+psycopg" dialect prefix outright
# (ProgrammingError: missing "=" after ...). Same database, just a different
# driver expecting a different string shape.
CHECKPOINT_DATABASE_URL = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

# Phase 8, Stage B -- Managed Identity instead of separate SAS connection
# strings per queue/direction. Both RBAC role assignments (Receiver on
# research-jobs, Sender on embedding-jobs) live on this SAME identity, so one
# credential covers both clients below -- the precision that used to come
# from separate SAS keys now comes from the separately-scoped role
# assignments instead.
SERVICEBUS_FQDN = os.environ.get("SERVICEBUS_FQDN", "alpharesearchsb.servicebus.windows.net")
SERVICEBUS_QUEUE_NAME = os.environ.get("SERVICEBUS_QUEUE_NAME", "research-jobs")
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


async def process_ticker(job_id: str, ticker: str, market: str, embed_sender, checkpointer):
    with Session(engine) as session:
        task = session.exec(
            select(TickerJob).where(TickerJob.job_id == job_id, TickerJob.ticker == ticker)
        ).first()
        if task is None:
            # Phase 7 -- a message referencing a (job_id, ticker) that doesn't
            # exist in THIS worker's own database must not crash the whole
            # process. Real, not hypothetical: hit this directly when a
            # locally-run API instance (pointed at a different database than
            # the real deployed worker) published a real message to the real
            # queue for a job_id the worker could never find -- crashed the
            # live worker with an uncaught AttributeError before this fix,
            # and Service Bus would have kept redelivering and re-crashing it.
            # Nothing to mark "failed" either, since there's no real row --
            # just log and move on.
            print(f"No TickerJob row found for job {job_id}, ticker {ticker} -- skipping.")
            return
        task.status = "running"
        session.add(task)
        session.commit()

    print(f"Processing {ticker} ({market}) for job {job_id}...")
    # The full multi-agent graph -- Fundamentals/Technical/News run in parallel,
    # Risk (deterministic flag_risk_factors + cross-signal judgment) waits for
    # all three, Synthesizer runs last. No separate direct calls here anymore --
    # the graph's own Fundamentals/Risk agents already do that internally.
    try:
        graph_result = await run_research(job_id, ticker, market, checkpointer)
    except Exception as exc:
        # Phase 7 (Resilience) -- a persistent, retry-exhausted failure must not
        # crash the whole worker process. Before this fix, an uncaught exception
        # here propagated straight out of main()'s message loop, killing every
        # OTHER job this worker replica happened to be handling too -- and since
        # complete_message() never ran, Service Bus would redeliver the same
        # message and crash the worker again, up to maxDeliveryCount (10) times,
        # before finally dead-lettering it. One bad ticker could take the whole
        # worker down repeatedly. This ticker now fails cleanly instead.
        print(f"{ticker} failed permanently: {exc}")
        error_summary = f"{ticker}: research failed - {exc}"
        with Session(engine) as session:
            task = session.exec(
                select(TickerJob).where(TickerJob.job_id == job_id, TickerJob.ticker == ticker)
            ).first()
            task.status = "failed"
            task.result = json.dumps({"tickers": [ticker], "summary": [error_summary]})
            session.add(task)
            session.commit()
        return

    data = graph_result.get("fundamentals_data", {})
    final_report = graph_result.get("final_report", "")

    # Phase 7 -- this used to gate final_report/TokenUsage/semantic-memory on
    # fundamentals specifically succeeding, written before graceful
    # degradation existed. Real, unplanned proof it was wrong: a live test
    # with fundamentals failing returned just "fundamentals data unavailable"
    # even when other agents' real work existed right there in graph_result,
    # silently discarded. The deterministic price line still needs real
    # fundamentals data -- nothing else here should depend on it.
    if not data or "error" in data:
        price_line = data.get("error", f"{ticker}: fundamentals data unavailable")
    else:
        price_line = (
            f"{ticker}: {data['currency']} {data['price']}, "
            f"P/E {data['pe_ratio']}, 52w range {data['fifty_two_week_low']}-{data['fifty_two_week_high']}"
        )
        flags = graph_result.get("risk_flags", [])
        if flags:
            price_line += " | Risk flags: " + "; ".join(flags)

    summary_line = price_line
    if final_report:
        summary_line += " | Report: " + final_report

    # Real cost can be incurred by Technical/News/Risk/Synthesizer even when
    # Fundamentals itself failed -- log whatever total_usage actually is,
    # not just when fundamentals specifically succeeded.
    usage = graph_result.get("total_usage") or {}
    if usage.get("total_tokens", 0) > 0:
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

    # Profile memory specifically needs real fundamentals-sourced sector/
    # industry -- this one genuinely stays conditional on fundamentals having
    # actually succeeded, unlike everything above.
    if data and "error" not in data:
        with Session(engine) as session:
            _upsert_ticker_profile(session, ticker, market, data.get("sector"), data.get("industry"))

    # Semantic memory: publish, don't embed inline -- embed-worker owns the
    # actual Foundry call and the ResearchReport write, so a slow or failing
    # embeddings call never adds latency to this job's own completion.
    # Whatever real report text exists is worth embedding, regardless of
    # whether fundamentals specifically succeeded.
    if final_report:
        embed_message = json.dumps({
            "job_id": job_id, "ticker": ticker, "market": market, "report_text": final_report,
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
    credential = DefaultAzureCredential()
    client = ServiceBusClient(fully_qualified_namespace=SERVICEBUS_FQDN, credential=credential)
    embed_client = ServiceBusClient(fully_qualified_namespace=SERVICEBUS_FQDN, credential=credential)
    async with client, embed_client, credential, AsyncPostgresSaver.from_conn_string(CHECKPOINT_DATABASE_URL) as checkpointer:
        # Idempotent -- confirmed safe to call on every startup, no separate
        # migration tracking needed. Creates its own 4 tables the first time
        # (checkpoints, checkpoint_blobs, checkpoint_writes, checkpoint_migrations);
        # no-ops after that.
        await checkpointer.setup()

        async with (
            client.get_queue_receiver(queue_name=SERVICEBUS_QUEUE_NAME) as receiver,
            embed_client.get_queue_sender(queue_name=SERVICEBUS_EMBED_QUEUE_NAME) as embed_sender,
        ):
            print("Worker started, waiting for messages...")
            async for msg in receiver:
                try:
                    data = json.loads(str(msg))
                    job_id, ticker, market = data["job_id"], data["ticker"], data["market"]
                except Exception as exc:
                    # A message that isn't valid JSON, or is missing an
                    # expected field, isn't a job we can ever process --
                    # redelivering it just crashes this loop again forever
                    # (hit this for real: a stray plain-text test message
                    # took the whole worker down in a crash-restart loop,
                    # since nothing here caught it before this fix). Drop it
                    # and move on instead of taking down every OTHER job
                    # this worker replica happens to be handling too.
                    print(f"Malformed message, dropping: {exc}")
                    await receiver.complete_message(msg)
                    continue

                await process_ticker(job_id, ticker, market, embed_sender, checkpointer)
                await receiver.complete_message(msg)  # acknowledge — without this, Service Bus redelivers it


if __name__ == "__main__":
    asyncio.run(main())
