# Troubleshooting Index

Use this index by symptom. It links to incidents and mechanisms in revised manuscript files that physically exist in this workspace. Revised Chapters 10, 15, and 16 are absent, so no troubleshooting links are invented for them.

## Deployment and Revision Problems

### The hosted frontend uses the wrong API URL

Check [Incident: Build-Time Frontend Configuration](chapter-02-backend-contract.md). Vite variables are compiled into the static bundle; changing a host setting without rebuilding does not rewrite existing assets.

### A deploy succeeds, but old behavior remains

Check [Incident: A Successful Stale Deployment](chapter-04-real-data-fanout.md) and [Incident: A Successful Deploy Ran Old Worker Code](chapter-18-scaling.md#incident-a-successful-deploy-ran-old-worker-code). Compare the active revision and image digest with the artifact containing the change.

### A feature works locally but is absent in the deployed system

Check [Incident: A Feature Was Only Half Deployed](chapter-09-memory-retrieval.md#incident-a-feature-was-only-half-deployed). List every independently deployable participant in the feature path.

### Cloud setup causes a non-fast-forward Git push

Check [Deploy the Thin Slice](chapter-01-frontend-shell.md). Inspect remote commits before rebasing or merging; an Azure wizard may have added a workflow.

## API and Browser Problems

### The browser request is blocked before reaching the route

Check [Build 4: Permit the Browser Origin](chapter-02-backend-contract.md). Validate the exact origin, including scheme and port, and inspect the preflight response.

### Polling never reaches a result

Check [Polling Tradeoffs](chapter-02-backend-contract.md), [Build 2: Surface Progress Through the API](chapter-09-memory-retrieval.md), and [How the Product States Fit Together](chapter-19-product-polish.md). Distinguish a running job, terminal failed ticker, lost connection, expired token, and client timeout.

### Authentication failures look like backend outages

Check [Build 5: Differentiate User-Recoverable Errors](chapter-19-product-polish.md). Token acquisition failure, 401/403, 5xx, fetch exceptions, and polling timeout should not share one message.

### One failed ticker hides successful tickers

Check [Build 1: Return Per-Ticker Status](chapter-19-product-polish.md). The top-level job state controls polling; `ticker_status` controls per-ticker rendering.

### An older report renders without structured cards

Check [Build 2: Render the Decision as Data](chapter-19-product-polish.md). Decision-less historical results should use the plain-summary fallback, not be inferred as failed.

## Queue and Worker Problems

### A job row exists, but no worker result appears

Check [Build 2: Write the Row Before Publishing](chapter-03-queue-worker-database.md) and [Build 3: Consume and Acknowledge in a Separate Process](chapter-03-queue-worker-database.md). Inspect queue depth, worker receipt, database identity, and message acknowledgement.

### Messages distribute unevenly across workers

Check [Incident: Uneven Service Bus Delivery](chapter-04-real-data-fanout.md). Observe message and replica timelines before assuming strict round-robin delivery.

### A completed job runs again

Check [How Correlation Actually Works](chapter-17-observability.md#how-correlation-actually-works). Service Bus can redeliver after work has completed; the durable done-state check should skip expensive repetition.

### The worker does not scale on queue depth

Check [Build 2: Capture the Starting Configuration](chapter-18-scaling.md) and [Incident: Cleanup Removed the Scaler Identity](chapter-19-product-polish.md#incident-cleanup-removed-the-scaler-identity). Verify queue metadata, target count, active revision, replica limits, and `identity: system` after every update.

### The queue scales, but downstream services throttle

Check [How It Works](chapter-18-scaling.md#how-it-works) and [Capacity and Dependency Risk](chapter-20-production-readiness.md#capacity-and-dependency-risk). Replica count is also downstream concurrency; inspect model quota, search budget, database connections, Redis, Content Safety, and API Management.

## Database, Cache, and Memory Problems

### The application reads from the wrong Redis instance

Check [Incident: The Wrong Redis Answered](chapter-03-queue-worker-database.md). Prove the endpoint and keyspace for every process rather than relying on a successful connection.

### The cloud database is empty while local tests pass

Check [Incident: The Empty Cloud Database](chapter-03-queue-worker-database.md). Verify connection targets, schema creation, and migrations in the deployed environment.

### Profile, progress, cache, and semantic search behavior are confused

Check [How It Works: Four Similar-Looking Features](chapter-09-memory-retrieval.md) and [How the Three Stores Differ](chapter-03-queue-worker-database.md). Identify whether the lookup is exact-key, expiring progress, daily cache, or vector similarity.

### Report history is missing expected records

Check [Build 4: Add History Without New Storage](chapter-19-product-polish.md). The list endpoint includes completed `TickerJob` rows, applies normalization and a limit, and retrieves full detail separately.

## MCP and Tool Problems

### MCP code from documentation fails against the installed package

Check [Incident: Documentation Did Not Match the Installed SDK](chapter-05-mcp-boundaries.md#incident-documentation-did-not-match-the-installed-sdk). Inspect the installed version and runtime signatures before adapting examples.

### A subprocess cannot find a file that exists

Check [Incident: The Working Directory Was Not the File Directory](chapter-05-mcp-boundaries.md#incident-the-working-directory-was-not-the-file-directory). Resolve paths from a stable project or module location rather than the caller's current directory.

### MCP initialization hangs through Container Apps ingress

Check [Incident: The POST Became a GET](chapter-18-scaling.md#incident-the-post-became-a-get). Capture raw HTTP. Call the final HTTPS URL directly so a 301 cannot convert the initialization POST to GET and discard its body.

### The MCP service starts before it can read Key Vault

Check [Incident: Identity Arrived Before Authorization](chapter-18-scaling.md#incident-identity-arrived-before-authorization). Verify the exact principal and scope, then allow for role-assignment propagation before changing correct configuration.

### A model calls a tool correctly but reasons incorrectly

Check [Incident: Correct Data, Incorrect Reasoning](chapter-06-first-tool-agent.md#incident-correct-data-incorrect-reasoning). Tool correctness does not guarantee interpretation correctness; inspect the transcript and strengthen the decision boundary or deterministic check.

### Tool arguments or messages become inconsistent across providers

Check [Incident: Compatible APIs Were Not Identical](chapter-07-model-boundaries-skills.md#incident-compatible-apis-were-not-identical) and [Build 2: Normalize Tool Arguments Without Mutating History](chapter-07-model-boundaries-skills.md).

## Agent Graph and Recovery Problems

### Parallel nodes appear serialized

Check [Build 4: Measure Concurrency, Do Not Read It From the Diagram](chapter-08-multi-agent-graph.md) and [Incident: The Parallel Graph Was Blocking](chapter-17-observability.md#incident-the-parallel-graph-was-blocking). Synchronous I/O inside async nodes can freeze the event loop even when graph edges are parallel.

### Two paths perform the same expensive work

Check [Incident: The Hybrid Became Duplicate Work](chapter-08-multi-agent-graph.md). Assign one owner to each capability and remove duplicate direct and model-selected execution.

### A resumed graph repeats more work than expected

Check [How It Works: Super-Steps Are the Commit Boundary](chapter-11-checkpointing.md) and [Incident: The Failure That Revealed the Boundary](chapter-11-checkpointing.md). Checkpoints commit at graph super-step boundaries, not after arbitrary lines inside a node.

### A transient error terminates the graph

Check [Build 2: Retry Transient Node Failures](chapter-12-resilience.md). Confirm the exception is retryable, the policy is attached to the node, and the failure injection reaches the intended call.

### A persistent node failure discards successful siblings

Check [Build 3: Degrade Persistent Failures Inside the Node](chapter-12-resilience.md) and [Build 4: Preserve Partial Work After the Graph](chapter-12-resilience.md).

### A failure test unexpectedly passes

Check [Incident: A Failure Test That Did Not Fail](chapter-12-resilience.md#incident-a-failure-test-that-did-not-fail). Prove that the injected failure is on the active code path and is not bypassed by cache, checkpoint, fallback, or a different deployment revision.

## Identity and Secret Problems

### A valid token is rejected for the wrong audience

Check [Incident: The Audience Changed Shape Twice](chapter-13-user-authentication.md#incident-the-audience-changed-shape-twice). Inspect the actual access-token claims and validate the API's identifier, not an assumed audience copied from another token type.

### PostgreSQL Managed Identity connections fail intermittently

Check [Build 2: Authenticate PostgreSQL Connections With Tokens](chapter-14-workload-identity-secrets.md). Acquire tokens when physical connections open and verify the database principal name and TLS requirements.

### Redis authentication expires on a long-running process

Check [Build 3: Handle Redis Token Renewal and Routing Honestly](chapter-14-workload-identity-secrets.md). Redis needs credential refresh and reauthentication during the connection lifetime.

### Secret retrieval causes message-lock loss or repeated latency

Check [Incident: Secret Retrieval Increased Message Time](chapter-14-workload-identity-secrets.md#incident-secret-retrieval-increased-message-time). Move secret ownership to the long-running service that uses it and avoid a Key Vault round trip for every tool call.

### A removed local secret still exists in an image

Check [Build 5: Exclude Secrets From Container Images](chapter-14-workload-identity-secrets.md). Inspect build context, ignore rules, and image layers; deleting a file later does not erase it from an earlier layer.

## Observability Problems

### Diagnostic settings report success but no records arrive

Check [Build 2: Export Model Request Metadata](chapter-17-observability.md). Inspect the raw destination configuration, send a real test request, and query the physical Log Analytics workspace.

### API and worker traces have different operation IDs

Check [How Correlation Actually Works](chapter-17-observability.md#how-correlation-actually-works). This deployment did not propagate trace context through Service Bus; join the operations with `job_id`.

### HTTP dependency spans are absent inside real graph traces

Check [Known Trace Gaps](chapter-17-observability.md#known-trace-gaps). HTTPX instrumentation worked in isolation but remained unresolved in the graph path. Do not claim hop-level coverage from per-agent spans alone.

### A trace exists, but it does not answer a user report

Check [Build 3: Make the Job ID a Product Feature](chapter-19-product-polish.md). Surface the same correlation value used by telemetry and database records.

## Readiness and Operations

### The system works, but release readiness is unclear

Use the [Readiness Scorecard](chapter-20-production-readiness.md#readiness-scorecard), [Principal Risks](chapter-20-production-readiness.md#principal-risks), and [Release Gates](chapter-20-production-readiness.md). Do not average critical gaps into a single percentage.

### The team needs a cost estimate

Start with [Cost Categories](chapter-20-production-readiness.md#cost-categories). Retrieve current regional prices, combine them with measured usage, and include retries and failed work.

### The deployed environment cannot be recreated from the repository

Check [Companion Material Still Needed](README.md#companion-material-still-needed) and [Reproducibility Risk](chapter-20-production-readiness.md#reproducibility-risk). The present repository lacks complete infrastructure as code, migrations, environment templates, and chapter tags.