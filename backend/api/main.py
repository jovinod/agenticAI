import os
import uuid
from contextlib import asynccontextmanager
from datetime import date
from typing import Literal
import json
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage
import redis.asyncio as redis
from sqlmodel import create_engine, Session, select
from models import TickerJob, ResearchReport
from llm.embeddings_client import embed
from auth import require_user

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha"
)
engine = create_engine(DATABASE_URL)

SERVICEBUS_CONNECTION_STRING = os.environ.get("SERVICEBUS_CONNECTION_STRING")
SERVICEBUS_QUEUE_NAME = os.environ.get("SERVICEBUS_QUEUE_NAME", "research-jobs")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "http://localhost:5173")

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6380"))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")  # unset locally; required for Azure Managed Redis
REDIS_SSL = os.environ.get("REDIS_SSL", "false").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.servicebus_client = ServiceBusClient.from_connection_string(
        SERVICEBUS_CONNECTION_STRING
    )
    # One sender, opened once and reused for the app's whole lifetime — opening/closing
    # a new AMQP link per message added real overhead and inconsistent delivery latency.
    app.state.servicebus_sender = app.state.servicebus_client.get_queue_sender(
        queue_name=SERVICEBUS_QUEUE_NAME
    )
    await app.state.servicebus_sender.__aenter__()
    app.state.redis = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        ssl=REDIS_SSL,
        decode_responses=True,
    )
    yield
    await app.state.servicebus_sender.__aexit__(None, None, None)
    await app.state.servicebus_client.close()
    await app.state.redis.aclose()


app = FastAPI(lifespan=lifespan)

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
    for agent_name in ("fundamentals", "technical", "news", "risk", "synthesizer"):
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
    for t in tasks:
        tickers.append(t.ticker)
        summary.extend(json.loads(t.result)["summary"])

    return {"status": "done", "result": {"tickers": tickers, "summary": summary}}


@app.get("/search", dependencies=[Depends(require_user)])
async def search_reports(q: str, limit: int = 5):
    """Semantic memory's read side -- a human's free-form question, matched
    against past synthesized reports by meaning, not by ticker/date key.
    Genuinely decoupled from the agent graph: this doesn't feed back into
    any agent's context, it's a standalone way to ask "what have we said
    that's relevant to this," across every ticker researched so far."""
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
