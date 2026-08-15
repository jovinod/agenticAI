# Chapter 2 — The Backend Skeleton

## The Lying Stops

Chapter 1 ended with a real, live URL — serving a completely fake app. Typing a ticker and hitting submit did nothing but wait two seconds and print a made-up sentence. That was deliberate: it proved the frontend's shape (`idle → loading → done`) without needing anything real behind it.

Phase 2's job was to replace every part of that lie with something real, one piece at a time: a real API to receive the request, a real queue so the request doesn't get lost or block anything, a real worker to do the (still-fake) research work, and a real database to remember what happened — deployed and checked live in the browser before moving on, same discipline as Chapter 1.

## Choosing the Backend Stack

**Python, via FastAPI.** The realistic alternatives were Node/Express (same language as the frontend, one less context switch) and Django (batteries-included, but heavier than a single-purpose API needs). FastAPI won for a specific reason beyond popularity: it generates a live, interactive API doc (`/docs`) directly from Python type hints — genuinely useful for testing each endpoint by hand before the frontend or a queue even exists. Python was also the natural choice looking ahead — the agent/LLM ecosystem (LangGraph, MCP SDKs, most model SDKs) is Python-first, and this project's backend was always going to need that eventually.

**`uv`, not pip/venv.** A single tool for creating the environment, managing dependencies, and running the project (`uv run ...`) — faster than the traditional pip+venv combination, and one fewer thing to explain to a beginner than juggling `requirements.txt`, `venv activate`, and separate installs.

**Postgres for durable state.** The one piece of information that must never be lost is "what did this job actually decide/find" — that belongs in a real relational database, not disposable in-memory state.

**A queue in between the API and the worker.** This was the least obvious piece, and worth explaining properly.

## Why a Queue At All?

Without a queue, the API would have to call the (eventually slow, LLM-driven) research work directly and wait for it — meaning a visitor's browser sits there for however long real research takes, and if the API process restarts mid-request, the work is just gone.

A queue is, at its core, the same idea as a Python `list` used as a waiting line — `list.append()` to add work, something else `list.pop()`s it off later — except durable (survives a restart) and shared across separate processes/machines instead of living in one process's memory. The API's whole job on `POST /research` becomes: write "here's a job" onto the queue and immediately tell the browser "got it, check back later." A separate worker process — which can be scaled independently, added, or restarted without touching the API at all — picks jobs off the queue whenever it's free.

**First pass: `arq` + local Redis.** `arq` is a small Python library that turns a Redis instance into a job queue with almost no setup: define an async function, point `arq`'s CLI at it, and Redis handles the waiting-line mechanics underneath. Real, working, and fast to prove locally — exactly what a fake-to-real first pass needs.

```python
# backend/worker/worker.py — first version, arq
async def process_research(ctx, job_id: str, tickers: list[str]):
    print(f"Processing job {job_id} for {tickers}...")
    await asyncio.sleep(3)  # fake delay — stands in for real agent work, later phases
    ...
```

**Second pass: real Azure Service Bus.** `arq` riding on Redis is fine locally, but Redis-as-a-queue isn't what a production Azure deployment would reach for — Azure Service Bus is a managed queue service built for exactly this job, with real delivery guarantees (a message that isn't explicitly acknowledged gets automatically redelivered, rather than just vanishing if a worker crashes mid-task). Since this project deploys as it goes, the migration happened here in Phase 2 rather than being deferred:

```python
# backend/worker/worker.py — after migrating to Service Bus
async def main():
    client = ServiceBusClient.from_connection_string(SERVICEBUS_CONNECTION_STRING)
    async with client:
        async with client.get_queue_receiver(queue_name=SERVICEBUS_QUEUE_NAME) as receiver:
            print("Worker started, waiting for messages...")
            async for msg in receiver:
                data = json.loads(str(msg))
                await process_research(data["job_id"], data["tickers"])
                await receiver.complete_message(msg)  # acknowledge — without this, Service Bus redelivers it
```

Service Bus has no equivalent of `arq`'s "call this named Python function automatically" convenience — a message is just plain JSON we invented ourselves (`{"job_id", "tickers"}`), and the loop reading it is now fully visible in our own code rather than hidden inside a library. `receiver.complete_message(msg)` is the acknowledgment — Service Bus holds a message as "in flight" for a lock duration (1 minute here) after handing it out, and redelivers it automatically if nothing confirms it got done, which is exactly the durability a bare Redis list doesn't give you for free.

> 🏭 **Production Lens:** Building the `arq`/Redis version first, then migrating to Service Bus, was a *learning* sequence, not a production one — a real team would likely pick the production queue technology up front rather than build a throwaway version first. It was worth doing here anyway: seeing the same problem solved by a 3-line library call, and then by explicit code with no library doing the acknowledging for you, made *what a queue actually guarantees* concrete rather than assumed.

## The API and the Worker

The API side stayed close to the FastAPI/Pydantic basics from `/docs` testing — a request model that Pydantic validates automatically:

```python
class ResearchRequest(BaseModel):
    tickers: list[str]

@app.post("/research")
async def create_research(request: ResearchRequest):
    job_id = str(uuid.uuid4())
    with Session(engine) as session:
        job = Job(job_id=job_id, tickers=",".join(request.tickers), status="queued")
        session.add(job)
        session.commit()

    message_body = json.dumps({"job_id": job_id, "tickers": request.tickers})
    async with app.state.servicebus_client.get_queue_sender(queue_name=SERVICEBUS_QUEUE_NAME) as sender:
        await sender.send_messages(ServiceBusMessage(message_body))

    return {"job_id": job_id}
```

Two things happen on submit, in order: a row is written to Postgres as `"queued"` (so `GET /research/{job_id}` has something to report immediately), then the same job is handed to Service Bus for the worker to actually process. The worker, on its own separate loop, does the (still-fake) work and updates that same Postgres row to `"running"` then `"done"`:

```python
class Job(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str = Field(index=True, unique=True)
    tickers: str
    status: str = "queued"
    result: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
```

Postgres, not Service Bus, is the actual *source of truth* here for status — the queue's only job is getting the work to the worker reliably; once picked up, the durable record of what happened lives in the database, which is what the API reads back from on every `GET /research/{job_id}` poll.

## Docker, and a Detail That Mattered on Deploy

Both the API and worker got Dockerfiles built on `uv`, multi-layer for build caching (dependencies installed in one layer, app code copied in a separate later layer, so a code-only change doesn't force a full dependency reinstall):

```dockerfile
FROM python:3.14-slim
ENV PYTHONUNBUFFERED=1
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY . .
RUN uv sync --frozen
CMD ["uv", "run", "python", "worker.py"]
```

`ENV PYTHONUNBUFFERED=1` turned out to matter in a very concrete way: Python buffers `print()` output when it isn't attached to an interactive terminal — exactly the situation inside a container — so without this line, the worker's logs would arrive late and in batches once deployed, rather than immediately as each job was processed. A small line, but the kind of thing you only actually notice once you're staring at a container's live log stream wondering where the output went.

A second real gotcha surfaced pushing images to Azure: this project is built on Apple Silicon (`arm64`), but Azure Container Apps expects `linux/amd64`. The first images built locally were silently the wrong architecture — fixed with `docker build --platform linux/amd64`, a flag that's easy to forget the first time you're deploying from an ARM machine to an x86 cloud.

## Deploying: Container Apps, Service Bus, Postgres

Provisioning used the `az` CLI rather than the Portal wizard this time — with several interconnected resources (registry, queue, database, two container apps sharing an environment), scripting it was more reliable than clicking through several separate wizards. In order: an Azure Container Registry (`alpharesearchacr`) to hold the images, a Service Bus namespace (`alpharesearchsb`) with a `research-jobs` queue, and an Azure Database for PostgreSQL Flexible Server (`alpha-research-pg`) — each provisioned once via a one-time resource-provider registration per subscription (`Microsoft.DBforPostgreSQL`, `Microsoft.App`), a step that only needs doing the first time a given resource type is used on a subscription.

Both container apps landed inside one Container Apps Environment (`alpha-env`) — `alpha-api` with external ingress on port 8000 (so the internet can reach it), `alpha-worker` with **no ingress at all**, since it isn't an HTTP server being called by anything — it just polls Service Bus on its own. The worker also got an explicit `--min-replicas 1`: Container Apps can scale a service down to zero replicas when idle, which is fine for an HTTP app (a request just wakes it back up), but would mean a queue-driven worker never runs again at all if left at its default.

**A real bug, caught by actually testing, not by the deploy succeeding:** the very first end-to-end test against live Azure infrastructure failed with `relation "job" does not exist`. `SQLModel`'s `create_all()` had only ever been run against the local Docker Postgres — the Azure database was a genuinely separate, empty database that needed the same table created in it once, by hand.

> 🏭 **Production Lens:** A real production app runs schema migrations (e.g. via Alembic) as an explicit, versioned step of every deploy — never a manual one-off script run once and forgotten. We used a one-off script here because this project only has one table so far and migrations-as-a-formal-practice is its own thing to learn properly; noted honestly as a gap to revisit if the schema starts changing often enough for a manual step to become risky.

## Wiring the Frontend to the Real Thing

The frontend's fake `setTimeout` block was replaced with real `fetch` calls to the live API, and the hardcoded `localhost:8000` became `import.meta.env.VITE_API_URL` — a Vite environment variable, with `localhost:8000` as the local-dev fallback.

This produced a genuinely confusing failure the first time: setting a value on the Static Web App resource in the Portal did nothing to the already-deployed frontend. The reason is a real Vite mechanic worth understanding, not a fluke — **Vite environment variables are baked into the JavaScript bundle at build time**, not read at runtime the way a server-side app's environment variables would be. By the time the built files exist, `VITE_API_URL` is just a plain string sitting inside them; nothing about the running Static Web App resource can change it after the fact. The actual fix was setting `VITE_API_URL` as a step-level `env:` on the "Build And Deploy" step inside the GitHub Actions workflow file Azure had generated — since that's where `npm run build` genuinely runs.

## Deploy & Verify

With everything live — frontend on Static Web Apps, API and worker on Container Apps, Service Bus and Postgres provisioned — the full path was tested for real: submit real tickers on the live public URL, watch a real job land in Service Bus, watch the real worker process it, watch the real Postgres row update, and see the real (still-stub) result come back through polling. Confirmed by the user directly in the browser, not just via `curl`.

## Azure Components Used This Chapter

- **Azure Container Registry (`alpharesearchacr`)** — private registry holding the built API and worker images, so Container Apps has somewhere to pull from that isn't a public registry. Images pushed via the developer's own Azure AD login (`az acr login`), not a stored username/password.
- **Azure Service Bus (`alpharesearchsb`)** — the real, managed queue. Chosen over continuing with Redis/`arq` because Service Bus gives explicit delivery guarantees (message redelivery on a missed acknowledgment) that a plain Redis list doesn't provide on its own.
- **Azure Database for PostgreSQL Flexible Server (`alpha-research-pg`)** — the durable source of truth for job status and results, reachable first for direct verification via a firewall rule scoped to this machine's IP (full VNet-private access is a later, Phase 7 concern).
- **Azure Container Apps (`alpha-env`, hosting `alpha-api` and `alpha-worker`)** — a managed environment for running containers without provisioning or patching VMs directly; `alpha-api` scales on HTTP traffic, `alpha-worker` runs continuously with a floor of 1 replica since nothing else would trigger it to wake up.

## The Architecture So Far

Grown by four real nodes this chapter — the frontend from Chapter 1 is unchanged, everything else is new.

```mermaid
flowchart TB
    User(["Visitor's browser"])
    SWA["Azure Static Web Apps<br/>React SPA"]
    API["Container App: alpha-api<br/>FastAPI (external ingress)"]
    SB["Service Bus: alpharesearchsb<br/>queue: research-jobs"]
    Worker["Container App: alpha-worker<br/>(no ingress, min 1 replica)"]
    PG[("Postgres Flexible Server:<br/>alpha-research-pg")]

    User --> SWA
    SWA -->|HTTPS| API
    API -->|send job| SB
    SB -->|deliver job| Worker
    API -->|read status| PG
    Worker -->|write status/result| PG

    classDef existing fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20
    classDef new fill:#69f0ae,stroke:#00c853,stroke-width:3px,color:#004d26
    class SWA existing
    class API,SB,Worker,PG new
```

## What Came Out of This Chapter

- A real distributed round trip: browser → API → queue → worker → database → back to the browser, with each hop independently real and independently deployed.
- A queue built twice on purpose — first the fast, convenient `arq`/Redis version, then real Azure Service Bus — specifically so the difference between "a library hides the durability mechanics" and "you write the acknowledgment loop yourself" became visible rather than assumed.
- Postgres established as the actual source of truth for status, distinct from the queue's narrower job of reliable delivery.
- Two real deploy-time gotchas resolved by testing live behavior, not by trusting a command's exit code: an `arm64`/`amd64` image mismatch, and a missing table only the real Azure database was missing.
- The report content itself is still a stub — real data sourcing, and the first taste of tools/MCP/Skills, is Chapter 3.
