# Chapter 6 — Checkpointing & Durable Workflows

## The Problem, Stated Precisely

Every phase so far has treated a crash the same way: the whole job is lost. If the worker process dies mid-graph — killed, OOM'd, redeployed out from under a running job — Service Bus redelivers the message (it was never `complete_message()`'d), and the graph starts over from scratch. Every agent that had already finished, and every dollar spent getting there, gets redone and re-paid for.

Checkpointing means persisting the graph's progress as it goes, so a restarted worker can resume from the last completed step instead of the beginning. The question this chapter actually answers isn't just "how do we build that" — it's "what does LangGraph's own checkpointing support actually do, precisely, and where does it stop helping."

## LangGraph's Checkpointing Is Real and Built-In — Verified, Not Assumed

`langgraph-checkpoint` is already a core dependency of `langgraph` itself — nothing to hand-roll. The interface: `StateGraph.compile(checkpointer=...)`. Once compiled that way, LangGraph automatically persists state after every **super-step** — the Bulk Synchronous Parallel unit its execution model is built on: everything scheduled to run *right now* (one node, or several running concurrently) is one super-step, and its checkpoint only commits once every node in it finishes.

Proved this with a disposable three-node graph before touching the real one — cheapest way to see the actual mechanism with zero LLM cost:

```python
builder = StateGraph(State)
builder.add_node("a", node_a); builder.add_node("b", node_b); builder.add_node("c", node_c)
builder.add_edge("a", "b"); builder.add_edge("b", "c")
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
config = {"configurable": {"thread_id": "job-123"}}
```

`node_c` raised on its first call, simulating a crash. Restarting with a **fresh graph object** but the **same checkpointer** and calling `graph.invoke(None, config)` — passing `None` as input — only re-ran `c`. `a` and `b`, already checkpointed, did not execute again.

**The gotcha that would have made this pointless without testing it directly**: calling `invoke()` again with the *original* input (not `None`) — exactly what our real Service Bus redelivery flow does, since a redelivered message calls `process_ticker(job_id, ticker, market)` with the same real arguments — silently restarts from scratch. Every node re-ran. Checkpointing bought nothing unless the caller explicitly knows to pass `None` on a resume.

That single finding shaped the whole design: **`run_research` now has to check, itself, whether a checkpoint already exists before deciding what to pass.**

## `thread_id`: Ours to Construct, and What It Actually Points To

`config = {"configurable": {"thread_id": ...}}` is the only thing that says *which* execution to resume. `None` as input doesn't mean "resume something" in the abstract — it means "load whatever's stored for this exact `thread_id`." Proved the edge case too: calling `invoke(None, config)` for a `thread_id` that has never run raises `EmptyInputError: Received no input for __start__` — LangGraph refuses to guess rather than fail quietly.

`job_id` alone isn't a valid `thread_id` here — one `job_id` fans out into independent per-ticker graph runs, so the real key is `f"{job_id}:{ticker}"`, the same compound-key reasoning already used for short-term memory's Redis keys (`progress:{job_id}:{ticker}:{agent_name}`).

Inspecting the real Postgres rows `AsyncPostgresSaver` writes makes the distinction between two easily-conflated ideas concrete:

```
thread_id       checkpoint_id                          parent_checkpoint_id
job-999:AAPL    1f19d10f-3937-6f08-bfff-7c62ca80625b    NULL
job-999:AAPL    1f19d10f-393b-614e-8000-1bf3a7821369    1f19d10f-3937-...
job-999:AAPL    1f19d10f-393c-68b4-8001-974df502eb77    1f19d10f-393b-...
job-999:MSFT    1f19d10f-394e-647e-bfff-3eddb7ea4ff6    NULL
```

`thread_id` is the stable identity we chose — it never changes across any future resume. `checkpoint_id` is a fresh, auto-generated UUID **per super-step**, chained via `parent_checkpoint_id` into that thread's actual history. We never reference a `checkpoint_id` ourselves; "resume" just means "find the newest one for this `thread_id`," which LangGraph does internally.

## The Postgres Backend: No Schema to Design

`InMemorySaver` is demo-only — gone the instant the process dies, useless for the actual goal. `AsyncPostgresSaver`, from the separate `langgraph-checkpoint-postgres` package, is the real durable backend. Its `.setup()` creates and owns its own four tables — `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` — directly in our existing Postgres. Verified `.setup()` is idempotent (called it twice locally, no error) — safe on every worker startup, no separate migration-tracking needed on our side.

One real, easy-to-miss gotcha: `AsyncPostgresSaver.from_conn_string()` wants a plain libpq conninfo string (`postgresql://...`), and rejects our existing `DATABASE_URL`'s SQLAlchemy dialect prefix outright:

```
ProgrammingError: missing "=" after "postgresql+psycopg://postgres:devpassword@localhost:5433/alpha" in connection info string
```

Same database, different driver, different expected string shape — `worker.py` now derives a second, reformatted connection string specifically for the checkpointer.

## Wiring It In

`agents/graph.py`: `build_graph()` gained a `checkpointer` parameter, passed straight to `compile()`. `run_research()` gained the resume-decision logic directly:

```python
if checkpointer is None:
    result = await graph.ainvoke(initial_state)          # unchanged path, e.g. the standalone test below
else:
    thread_id = f"{job_id}:{ticker}"
    config = {"configurable": {"thread_id": thread_id}}
    existing = await checkpointer.aget_tuple(config)
    resume_input = None if existing else initial_state
    result = await graph.ainvoke(resume_input, config)
```

`worker.py`: `AsyncPostgresSaver.from_conn_string(...)` opens once, for the worker's whole lifetime, alongside the existing Service Bus clients — `.setup()` runs once at startup, then the same `checkpointer` instance threads through every `process_ticker()` call for as long as the process lives.

## Proof Against the Real Graph — Including a Finding I Didn't Plan to Find

The toy graph proved the mechanism. It didn't prove it against five real, LLM-calling agents with a genuine parallel fan-out — so the next test used the actual `agents/graph.py`, deliberately failing `synthesizer_node` on its first call to simulate a crash right before the final step.

**A real, unplanned crash happened first** — a genuine `httpx.ReadError` hit `news_node` mid-test, while it was running *concurrently* with `fundamentals_node` and `technical_node` in the same parallel super-step. Checking Redis afterward (short-term memory writes independently, right when each node finishes) showed something worth stating plainly: **Fundamentals and Technical had both genuinely completed and cost real money** — but the Postgres checkpoint for that step recorded nothing at all, not even their contributions.

That's not a bug in this project's wiring — it's a direct, unavoidable consequence of super-step atomicity. A parallel fan-out's checkpoint only commits when **every** node in it finishes; if one sibling fails, none of that step's results persist, even the ones that actually succeeded. Resuming re-ran and re-paid for all three parallel branches, confirmed directly: `write_progress`'s Redis keys for `fundamentals`/`technical` existed from the *first* attempt, but the resumed run's `total_usage` (~9.2K tokens) was consistent with a full 5-agent run, not a 3-agent partial one — meaning Fundamentals and Technical really did re-execute and re-bill.

**The positive case, tested cleanly afterward**: failing `risk_node` instead — which runs *after* the fan-in, its own separate super-step — and resuming showed the opposite, correct behavior. Fundamentals/Technical/News did **not** re-run; the resumed call's `total_usage` matched a normal full run's magnitude rather than double-counting the parallel batch.

**So, precisely**: checkpointing genuinely protects sequential progress (Risk, Synthesizer) from redundant re-execution. It does **not** protect the initial parallel fan-out from redundant cost if any one of its three branches fails — not because LangGraph "can't," but because true concurrency and independent per-branch checkpointing are structurally in tension: the same super-step boundary that lets three nodes run *together* is what makes their checkpoint commit *together*. Getting independent recovery per branch would mean serializing them — trading away the concurrency Chapter 5 fought to prove was real in the first place.

**A better fix exists for the failure actually observed, and it isn't checkpointing at all.** `httpx.ReadError` is transient — not a real bug, a network hiccup. LangGraph supports per-node retries: `add_node(..., retry_policy=RetryPolicy())`, which retries a node *inside* its own super-step attempt, before a failure ever escalates to fail the batch. Checked the actual default predicate rather than assumed it would apply:

```python
def default_retry_on(exc):
    if isinstance(exc, ConnectionError): return True
    if isinstance(exc, httpx.HTTPStatusError): return 500 <= exc.response.status_code < 600
    if isinstance(exc, (ValueError, TypeError, ...)): return False   # explicit non-retryable list
    return True   # anything else, including httpx.ReadError, falls through to "retry"
```

`httpx.ReadError` isn't in the excluded list — the exact error hit here would have been retried automatically, and Fundamentals/Technical would never have needed rescuing at all, because News would have self-healed before the super-step ever failed. This is really Phase 7's territory (resilience — individual call failures degrading gracefully) rather than Phase 6's (not losing *all* progress on a full process crash) — but it's a concrete, real example of why that distinction exists, surfaced by an actual crash rather than theorized in the abstract.

## Key Files From This Chapter

| File | What it does |
|---|---|
| `backend/worker/pyproject.toml` | `langgraph-checkpoint-postgres` added — the real durable checkpoint backend, a separate package from core `langgraph`. |
| `backend/worker/agents/graph.py` | `build_graph(checkpointer=None)` — passed straight to `compile()`. `run_research(..., checkpointer=None)` — constructs `thread_id = f"{job_id}:{ticker}"`, checks `aget_tuple()` to decide real-input-vs-`None` before invoking. |
| `backend/worker/worker.py` | Opens `AsyncPostgresSaver.from_conn_string(...)` once for the worker's whole lifetime (same pattern as the embed-worker's Service Bus sender), reformats `DATABASE_URL` for libpq compatibility, calls `.setup()` once at startup, threads the checkpointer through every `process_ticker()` call. |

## The Flow So Far

```mermaid
flowchart TD
    SB["Service Bus: research-jobs"] -->|deliver ticker job| Worker["process_ticker(job_id, ticker, market)"]
    Worker --> RR["run_research(job_id, ticker, market, checkpointer)"]
    RR --> Check{"aget_tuple(thread_id)<br/>checkpoint exists?"}
    Check -->|"No"| Fresh["ainvoke(initial_state, config)<br/>full graph runs from START"]
    Check -->|"Yes"| Resume["ainvoke(None, config)<br/>resumes from last committed super-step"]
    Fresh --> Graph["Fundamentals / Technical / News<br/>(parallel fan-out — ONE super-step)"]
    Resume --> Graph
    Graph --> Risk["Risk (fan-in — its own super-step)"]
    Risk --> Synth["Synthesizer (its own super-step)"]
    Synth --> Done["Result returned to worker.py"]
```

## Deployed and Verified Live — a Real Crash, Not a Simulated One

Checkpoint tables created on the real Azure Postgres the same way as every other table this project has added (`.setup()`, one-off, verified independently afterward). `alpha-worker` rebuilt and redeployed with the checkpointing code; old revision confirmed fully deprovisioned before trusting the new one.

The real test, matching the roadmap's own literal bar: submitted a genuine job (`QCOM`) through the live public API, polled until Fundamentals/Technical/News all showed complete in the progress endpoint, then ran `az containerapp revision restart` on the live worker — an actual platform-level restart of the running container, mid-job, not a monkeypatched exception. Service Bus's message lock (1 minute) expired without the crashed attempt ever calling `complete_message()`, redelivering the job to the restarted worker once it came back up.

**The job completed correctly.** Confirmed it wasn't a silent full redo, not just a completed status, by checking the real cost: the `TokenUsage` row for this job shows `9,478` total tokens, `$0.0051` — squarely in the normal range for a single full 5-agent run (a comparable ticker earlier in this project ran `9,520` tokens). Had Fundamentals/Technical/News re-executed after the restart, this number would be roughly double. It wasn't. The real checkpoint history in Postgres shows five steps (`-1` through `3`) for `thread_id = "<job_id>:QCOM"` — visible, separate super-steps, with a real elapsed-time gap between the pre-crash and post-crash entries baked into their UUIDs. Risk and Synthesizer resumed; Fundamentals, Technical, and News did not re-run.

Phase 6 is now genuinely complete: the mechanism proven against the real 5-agent graph (not just a toy one), its real limit found through an actual accidental crash and documented rather than glossed over, and the roadmap's own "kill the worker, confirm resume" bar cleared against the live deployment, not simulated.

**One real operational note for later, not solved here**: checkpoint rows for a completed thread are never automatically cleaned up — `checkpoints`/`checkpoint_blobs`/`checkpoint_writes` will grow unbounded over the life of the project unless something eventually prunes completed threads. Worth a line in Phase 10 (Observability) or general ops hygiene, not a Phase 6 concern.

## Azure Components Used This Chapter

Genuinely none new. Checkpointing reuses the existing `alpha-research-pg` Postgres server entirely — `AsyncPostgresSaver.setup()` just adds four new tables to the same database `alpha-worker` already writes `tickerjob`/`tokenusage`/`tickerprofile` into. No new resource, no new Container App, no new secret. The one genuinely new *tool* this chapter used wasn't a resource at all — `az containerapp revision restart`, to trigger a real platform-level container restart for the live crash test, rather than simulating one.

## The Architecture So Far

No new box this chapter — every node below is exactly what Chapter 5 ended with. But "no new resource" isn't the same as "nothing changed": `alpha-worker`'s relationship with Postgres is genuinely different now, and that deserves its own line on the diagram, not silence just because it reuses an existing edge's endpoints. The new edge is highlighted the same way a new *node* would be in earlier chapters — the behavior is new even though the boxes aren't.

```mermaid
flowchart TB
    User(["Visitor's browser"])
    SWA["Azure Static Web Apps<br/>React SPA"]
    API["Container App: alpha-api<br/>FastAPI (external ingress)"]
    SB["Service Bus: alpharesearchsb<br/>queues: research-jobs, embedding-jobs"]

    subgraph WorkerGroup["Container App: alpha-worker<br/>KEDA-scaled: 1-10 replicas<br/>(1 replica per queued msg)"]
        direction LR
        W1["replica"]
        W2["replica"]
        Wdots["···<br/>up to 10"]
    end

    EmbedWorker["Container App: alpha-embed-worker<br/>KEDA-scaled: 0-3 replicas<br/>(1 replica per 5 queued msgs)"]

    PG[("Postgres Flexible Server:<br/>alpha-research-pg<br/>+ tokenusage, tickerprofile,<br/>researchreport, checkpoints (pgvector + LangGraph)")]
    Redis[("Managed Redis:<br/>alpha-research-cache<br/>per-ticker cache")]
    APIM["API Management: alpha-research-apim<br/>(Consumption tier, managed identity)"]
    OpenAI["Azure OpenAI: alpha-research-openai<br/>(South India) — gpt-5-mini,<br/>text-embedding-3-small"]

    User --> SWA
    SWA -->|HTTPS| API
    API -->|send job, per ticker on miss| SB
    SB -->|deliver job, one per replica| WorkerGroup
    SB -->|deliver report text| EmbedWorker
    API -->|read status| PG
    WorkerGroup -->|write status/result/token-cost| PG
    EmbedWorker -->|write report + vector| PG
    API -->|"search: read + embed query"| PG
    API -->|cache check| Redis
    WorkerGroup -->|cache write| Redis
    WorkerGroup -->|"Ocp-Apim-Subscription-Key"| APIM
    WorkerGroup -->|publish report text| SB
    EmbedWorker -->|"Ocp-Apim-Subscription-Key"| APIM
    API -->|"Ocp-Apim-Subscription-Key"| APIM
    APIM -->|"managed identity (AAD token)"| OpenAI
    WorkerGroup -->|"checkpoint check (aget_tuple) +<br/>write per super-step<br/>(thread_id = job_id:ticker)"| PG

    classDef existing fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20
    classDef new fill:#69f0ae,stroke:#00c853,stroke-width:3px,color:#004d26
    classDef replica fill:#e8f5e9,stroke:#66bb6a,stroke-width:1px,color:#2e7d32
    class SWA,API,SB,PG,Redis,OpenAI,APIM,EmbedWorker existing
    class WorkerGroup existing
    class W1,W2,Wdots replica
    linkStyle 16 stroke:#00c853,stroke-width:3px
```

That last edge — the highlighted one — is the whole chapter in one line: the same worker, the same database, but now with a real conversation happening between them that didn't exist before (*"has this thread run before?"*, then, as the graph progresses, *"here's what just finished"*) rather than only ever writing a final result once at the end.
