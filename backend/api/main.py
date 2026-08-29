import os
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, time
from typing import Literal
import json
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
from azure.identity.aio import DefaultAzureCredential
from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential
import psycopg
import redis.asyncio as redis
from sqlmodel import create_engine, Session, select
from models import TickerJob, ResearchReport
from llm.embeddings_client import embed
from auth import require_user
from pii_scrub import scrub_pii

# Phase 10, Stage B -- no-op locally (APPLICATIONINSIGHTS_CONNECTION_STRING is
# only set in Azure), same "real service in Azure, silent no-op locally"
# shape as every other Azure-only feature in this project. Called before the
# FastAPI app exists: this sets up the global tracer/logger providers that
# FastAPIInstrumentor and every `trace.get_tracer(...)` call below plug into.
if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    configure_azure_monitor()

# Phase 8, Stage B -- Managed Identity instead of a password secret, when
# running in Azure. DATABASE_HOST is only ever set there: the local Docker
# Postgres container has no AAD support at all, so (unlike Service Bus's
# DefaultAzureCredential, which works unchanged locally via `az login`) this
# genuinely needs two different code paths, not one that happens to work
# both places.
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

# Phase 8, Stage B -- Managed Identity instead of a SAS connection string.
# DefaultAzureCredential tries several methods in order; in Azure it uses this
# Container App's own system-assigned identity (granted "Azure Service Bus
# Data Sender" on research-jobs specifically, not the whole namespace), and
# locally it falls back to `az login`'s cached credentials -- same code path
# either way, no separate local-dev branch needed.
SERVICEBUS_FQDN = os.environ.get("SERVICEBUS_FQDN", "alpharesearchsb.servicebus.windows.net")
SERVICEBUS_QUEUE_NAME = os.environ.get("SERVICEBUS_QUEUE_NAME", "research-jobs")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:5173")

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6380"))
REDIS_SSL = os.environ.get("REDIS_SSL", "false").lower() == "true"

# Phase 8, Stage C -- Managed Identity instead of a password secret, when
# running in Azure. Same reasoning as Postgres: the local Docker Redis
# container has no AAD support at all, so this is a genuine second code
# path. Unlike Postgres, a Redis connection needs its token refreshed and
# re-AUTH'd periodically for the life of the connection, not just once at
# connect time -- redis-entraid's CredentialProvider handles that refresh
# loop automatically.
REDIS_USE_ENTRA_AUTH = os.environ.get("REDIS_USE_ENTRA_AUTH", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.servicebus_credential = DefaultAzureCredential()
    app.state.servicebus_client = ServiceBusClient(
        fully_qualified_namespace=SERVICEBUS_FQDN,
        credential=app.state.servicebus_credential,
    )
    # One sender, opened once and reused for the app's whole lifetime — opening/closing
    # a new AMQP link per message added real overhead and inconsistent delivery latency.
    app.state.servicebus_sender = app.state.servicebus_client.get_queue_sender(
        queue_name=SERVICEBUS_QUEUE_NAME
    )
    await app.state.servicebus_sender.__aenter__()
    if REDIS_USE_ENTRA_AUTH:
        from redis_entraid.cred_provider import create_from_default_azure_credential

        app.state.redis = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, ssl=REDIS_SSL,
            credential_provider=create_from_default_azure_credential(
                scopes=("https://redis.azure.com/.default",)
            ),
            decode_responses=True,
        )
    else:
        REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")  # unset locally
        app.state.redis = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD, ssl=REDIS_SSL,
            decode_responses=True,
        )
    yield
    await app.state.servicebus_sender.__aexit__(None, None, None)
    await app.state.servicebus_client.close()
    await app.state.servicebus_credential.close()
    await app.state.redis.aclose()


app = FastAPI(lifespan=lifespan)
FastAPIInstrumentor.instrument_app(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    tickers: list[str]
    market: Literal["US", "India"]


@app.get("/")
def read_root():
    return {"status": "ok"}


@app.post("/research", dependencies=[Depends(require_user)])
async def create_research(request: ResearchRequest):
    job_id = str(uuid.uuid4())
    today = date.today().isoformat()

    # Phase 10, Stage B -- App Insights' own operation ID isn't ours to query
    # by; stamping our own job_id onto the request span is what makes "find
    # every trace for this job" possible later, same correlation-ID gap
    # Stage A's Azure OpenAI diagnostic logs surfaced for a different hop.
    trace.get_current_span().set_attribute("job_id", job_id)

    for ticker in request.tickers:
        cache_key = f"research:{request.market}:{ticker}:{today}"
        cached = await app.state.redis.get(cache_key)

        with Session(engine) as session:
            if cached:
                task = TickerJob(
                    job_id=job_id, ticker=ticker, market=request.market, status="done", result=cached
                )
            else:
                task = TickerJob(job_id=job_id, ticker=ticker, market=request.market, status="queued")
            session.add(task)
            session.commit()

        if not cached:
            message_body = json.dumps({"job_id": job_id, "ticker": ticker, "market": request.market})
            await app.state.servicebus_sender.send_messages(ServiceBusMessage(message_body))

    return {"job_id": job_id}


async def _read_progress(job_id: str, ticker: str) -> dict:
    """Read-only duplicate of worker/memory/short_term.py's read_progress --
    backend/api and backend/worker are separate uv projects (same reason
    TickerJob is duplicated in both models.py files), and only the worker
    ever WRITES progress, so only the read side needs to exist here."""
    progress = {}
    for agent_name in ("fundamentals", "technical", "news", "risk", "devil_advocate", "decision"):
        value = await app.state.redis.get(f"progress:{job_id}:{ticker}:{agent_name}")
        if value is not None:
            progress[agent_name] = value
    return progress


@app.get("/research/{job_id}", dependencies=[Depends(require_user)])
async def get_research(job_id: str):
    with Session(engine) as session:
        tasks = session.exec(select(TickerJob).where(TickerJob.job_id == job_id)).all()

    if not tasks:
        return {"error": "not found"}

    # "failed" is a real terminal state now too (Phase 7) -- a ticker that
    # failed permanently shouldn't leave the whole job stuck reporting "running"
    # forever just because it never reached "done".
    if any(t.status not in ("done", "failed") for t in tasks):
        progress = {}
        for t in tasks:
            if t.status not in ("done", "failed"):
                progress[t.ticker] = await _read_progress(job_id, t.ticker)
        return {"status": "running", "progress": progress}

    tickers = []
    summary = []
    decisions = {}
    ticker_status = {}
    for t in tasks:
        tickers.append(t.ticker)
        ticker_status[t.ticker] = t.status
        parsed = json.loads(t.result)
        summary.extend(parsed["summary"])
        decisions.update(parsed.get("decisions", {}))  # absent on a failed ticker's result -- not every job reaches Decision

    # Phase 12 -- a multi-ticker job can partially fail (one ticker permanently
    # failed, others succeeded), and the frontend previously had no reliable
    # way to tell WHICH ticker failed beyond string-sniffing the raw error
    # text embedded in `summary`. ticker_status makes that an explicit,
    # per-ticker signal instead.
    return {"status": "done", "result": {"tickers": tickers, "summary": summary, "decisions": decisions, "ticker_status": ticker_status}}


@app.get("/reports", dependencies=[Depends(require_user)])
async def list_reports(
    ticker: str | None = None,
    market: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
):
    """Phase 12 -- the History tab's read side: browse past completed
    research filtered by ticker/date, distinct from /search's semantic
    lookup by meaning. Reads the same TickerJob rows /research/{job_id}
    does -- no new table, this app already persists everything needed,
    just never had a way to list/filter across jobs instead of one job
    at a time."""
    with Session(engine) as session:
        query = select(TickerJob).where(TickerJob.status == "done")
        if ticker:
            query = query.where(TickerJob.ticker == ticker.strip().upper())
        if market:
            query = query.where(TickerJob.market == market)
        if date_from:
            query = query.where(TickerJob.created_at >= datetime.combine(date_from, time.min))
        if date_to:
            query = query.where(TickerJob.created_at <= datetime.combine(date_to, time.max))
        query = query.order_by(TickerJob.created_at.desc()).limit(limit)
        tasks = session.exec(query).all()

    reports = []
    for t in tasks:
        recommendation = ""
        if t.result:
            decision = json.loads(t.result).get("decisions", {}).get(t.ticker, {})
            recommendation = decision.get("recommendation", "")
        reports.append({
            "job_id": t.job_id,
            "ticker": t.ticker,
            "market": t.market,
            "created_at": t.created_at.isoformat(),
            "recommendation": recommendation,
        })

    return {"reports": reports}


@app.get("/search", dependencies=[Depends(require_user)])
async def search_reports(q: str, limit: int = 5):
    """Semantic memory's read side -- a human's free-form question, matched
    against past synthesized reports by meaning, not by ticker/date key.
    Genuinely decoupled from the agent graph: this doesn't feed back into
    any agent's context, it's a standalone way to ask "what have we said
    that's relevant to this," across every ticker researched so far."""
    q = scrub_pii(q)  # Phase 9 (Guardrails) -- the one free-text input in this app
    query_vector = await embed(q)
    with Session(engine) as session:
        reports = session.exec(
            select(ResearchReport)
            .order_by(ResearchReport.embedding.cosine_distance(query_vector))
            .limit(limit)
        ).all()

    return {
        "query": q,
        "results": [
            {
                "ticker": r.ticker,
                "market": r.market,
                "job_id": r.job_id,
                "report_text": r.report_text,
                "created_at": r.created_at.isoformat(),
            }
            for r in reports
        ],
    }
