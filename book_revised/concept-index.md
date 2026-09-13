# Concept Index

This index points to the most authoritative explanation of each concept in the revised manuscript. Use the [chapter map](README.md#chapter-map) for the linear reading order.

## Application Shape

- **Architecture snapshots:** [Chapter 1 architecture](chapter-01-frontend-shell.md), [Chapter 8 graph architecture](chapter-08-multi-agent-graph.md#architecture-after-this-chapter), and the [final architecture](chapter-20-production-readiness.md#the-final-architecture).
- **Browser/API separation:** [Client-Side Rendering and Two Servers](chapter-01-frontend-shell.md).
- **Finished repository versus chapter versions:** [Finished Repository Versus Chapter Versions](README.md#finished-repository-versus-chapter-versions).
- **Distributed request walkthrough:** [Full Walkthrough: One Multi-Ticker Request](chapter-20-production-readiness.md).
- **Production-shaped versus production-ready:** [Readiness Scorecard](chapter-20-production-readiness.md#readiness-scorecard) and [Release Gates](chapter-20-production-readiness.md).

## Frontend and Product States

- **Controlled React input:** [Build 2: Make the Input Controlled](chapter-01-frontend-shell.md).
- **Ticker parsing and validation:** [Build 3: Parse and Validate Tickers](chapter-01-frontend-shell.md).
- **Mocked waiting state:** [Build 4: Model the Waiting State](chapter-01-frontend-shell.md).
- **Polling:** [Polling Tradeoffs](chapter-02-backend-contract.md) and [How the Product States Fit Together](chapter-19-product-polish.md).
- **Structured reports:** [Build 2: Render the Decision as Data](chapter-19-product-polish.md).
- **Per-ticker failure:** [Build 1: Return Per-Ticker Status](chapter-19-product-polish.md).
- **History:** [Build 4: Add History Without New Storage](chapter-19-product-polish.md).
- **Support correlation:** [Build 3: Make the Job ID a Product Feature](chapter-19-product-polish.md).
- **User-recoverable errors:** [Build 5: Differentiate User-Recoverable Errors](chapter-19-product-polish.md).
- **Visual design:** [Build 6: Simplify the Visual Language](chapter-19-product-polish.md).

## HTTP, Jobs, and Queues

- **Asynchronous job contract:** [Build 1: Define the Request and Acceptance Response](chapter-02-backend-contract.md).
- **Status resource:** [Build 2: Add a Temporary Status Resource](chapter-02-backend-contract.md).
- **CORS:** [Build 4: Permit the Browser Origin](chapter-02-backend-contract.md).
- **Database as status authority:** [Build 1: Make PostgreSQL the Status Authority](chapter-03-queue-worker-database.md).
- **Persist before publish:** [Build 2: Write the Row Before Publishing](chapter-03-queue-worker-database.md).
- **Message acknowledgement:** [Build 3: Consume and Acknowledge in a Separate Process](chapter-03-queue-worker-database.md).
- **Per-ticker unit of work:** [Build 1: Change the Unit of Work](chapter-04-real-data-fanout.md).
- **Cache-aside fan-out:** [Build 2: Add Cache-Aside Fan-Out](chapter-04-real-data-fanout.md).

## Data and Memory

- **Direct market-data calls:** [Build 4: Fetch Data as a Direct Call](chapter-04-real-data-fanout.md).
- **Market qualification:** [Build 3: Require an Explicit Market](chapter-04-real-data-fanout.md).
- **Redis progress memory:** [Build 1: Write In-Flight Progress to Redis](chapter-09-memory-retrieval.md).
- **Profile memory:** [Build 3: Store Exact-Key Ticker Profiles](chapter-09-memory-retrieval.md).
- **Semantic memory purpose:** [Build 4: Decide What Semantic Memory Is For](chapter-09-memory-retrieval.md).
- **Asynchronous embedding:** [Build 5: Move Embedding Off the Research Path](chapter-09-memory-retrieval.md).
- **pgvector retrieval:** [Build 6: Query pgvector by Meaning](chapter-09-memory-retrieval.md).
- **Store responsibilities:** [How the Three Stores Differ](chapter-03-queue-worker-database.md) and [How It Works: Four Similar-Looking Features](chapter-09-memory-retrieval.md).

## Tools, MCP, and Skills

- **Narrow tool registration:** [Build 1: Register One Narrow Tool](chapter-05-mcp-boundaries.md).
- **MCP server wiring:** [Build 2: Wire a Specific Server Explicitly](chapter-05-mcp-boundaries.md).
- **Capability discovery:** [Build 3: Discover Before You Execute](chapter-05-mcp-boundaries.md).
- **Controlled external search:** [Build 4: Spend One Controlled Search](chapter-05-mcp-boundaries.md).
- **MCP wrapper boundary:** [Build 5: Wrap MCP Without Auto-Calling It](chapter-05-mcp-boundaries.md).
- **Registration, discovery, execution:** [Registration, Discovery, and Execution](chapter-05-mcp-boundaries.md).
- **Standalone MCP service:** [Build 4: Move MCP Out of the Worker](chapter-18-scaling.md).
- **Model/tool harness:** [Build 4: Turn Two Calls Into a Bounded Loop](chapter-06-first-tool-agent.md).
- **Harness versus orchestrator:** [How It Works: Harness Versus Orchestrator](chapter-06-first-tool-agent.md).
- **Skills on disk:** [Build 6: Package Instructions as a Skill](chapter-07-model-boundaries-skills.md) and [Build 7: Discover Skills From Disk](chapter-07-model-boundaries-skills.md).
- **Direct call versus model choice:** [How It Works: Direct Call or Model Choice](chapter-07-model-boundaries-skills.md).

## Models and Agent Orchestration

- **Model abstraction:** [Build 1: Define One Model Contract](chapter-07-model-boundaries-skills.md).
- **Transcript integrity:** [Build 2: Normalize Tool Arguments Without Mutating History](chapter-07-model-boundaries-skills.md) and [Build 3: Preserve the Transcript](chapter-06-first-tool-agent.md).
- **Asynchronous model transport:** [Build 3: Make Network Waiting Actually Asynchronous](chapter-07-model-boundaries-skills.md).
- **API Management boundary:** [Build 4: Keep APIM at the Transport Boundary](chapter-07-model-boundaries-skills.md).
- **Token and cost usage:** [Build 5: Track Usage at the Boundary](chapter-07-model-boundaries-skills.md).
- **Agent responsibilities:** [Build 1: Give Each Agent One Job](chapter-08-multi-agent-graph.md).
- **Shared graph state:** [Build 2: Define Shared State by Ownership](chapter-08-multi-agent-graph.md).
- **Fan-out and fan-in:** [Build 3: Wire Fan-Out and Fan-In](chapter-08-multi-agent-graph.md).
- **Measured concurrency:** [Build 4: Measure Concurrency, Do Not Read It From the Diagram](chapter-08-multi-agent-graph.md).
- **Bounded concurrency:** [Build 5: Keep Concurrency Bounded by Real Capacity](chapter-08-multi-agent-graph.md).
- **Super-step barrier:** [How It Works: A Super-Step Barrier](chapter-08-multi-agent-graph.md).

## Reliability and Recovery

- **Durable execution identity:** [Build 1: Name One Durable Execution](chapter-11-checkpointing.md).
- **PostgreSQL checkpointer:** [Build 2: Compile the Graph With a Saver](chapter-11-checkpointing.md).
- **Resume experiment:** [Build 3: Prove Resume Semantics Cheaply](chapter-11-checkpointing.md).
- **Checkpoint boundary:** [How It Works: Super-Steps Are the Commit Boundary](chapter-11-checkpointing.md).
- **Retry versus turn limit:** [Build 1: Separate Retries From Turn Limits](chapter-12-resilience.md).
- **Transient retry:** [Build 2: Retry Transient Node Failures](chapter-12-resilience.md).
- **Graceful degradation:** [Build 3: Degrade Persistent Failures Inside the Node](chapter-12-resilience.md).
- **Partial work:** [Build 4: Preserve Partial Work After the Graph](chapter-12-resilience.md).
- **Workflow containment:** [Build 5: Contain Failures Around the Workflow](chapter-12-resilience.md).

## Identity and Secrets

- **SPA identity boundary:** [Build 1: Choose the Identity Boundary](chapter-13-user-authentication.md).
- **Authorization Code Flow with PKCE:** [Build 2: Register SPA Redirects and Use PKCE](chapter-13-user-authentication.md).
- **Bearer tokens:** [Build 3: Attach a Token to Every Protected Call](chapter-13-user-authentication.md).
- **JWT validation:** [Build 4: Validate the Access Token in FastAPI](chapter-13-user-authentication.md).
- **Authorization allow-list:** [Build 5: Authorize the Authenticated User](chapter-13-user-authentication.md).
- **Workload identities:** [Build 1: Assign One Identity Per Workload](chapter-14-workload-identity-secrets.md).
- **PostgreSQL token auth:** [Build 2: Authenticate PostgreSQL Connections With Tokens](chapter-14-workload-identity-secrets.md).
- **Redis token renewal:** [Build 3: Handle Redis Token Renewal and Routing Honestly](chapter-14-workload-identity-secrets.md).
- **Key Vault:** [Build 4: Put the Third-Party Secret Behind Key Vault](chapter-14-workload-identity-secrets.md).
- **Container secret hygiene:** [Build 5: Exclude Secrets From Container Images](chapter-14-workload-identity-secrets.md).

## Observability and Scaling

- **Signal selection:** [Build 1: Separate the Questions](chapter-17-observability.md).
- **Azure OpenAI diagnostics:** [Build 2: Export Model Request Metadata](chapter-17-observability.md).
- **API tracing:** [Build 3: Instrument the API Boundary](chapter-17-observability.md).
- **Worker and agent spans:** [Build 4: Trace the Worker and Graph](chapter-17-observability.md).
- **Cross-trace correlation:** [How Correlation Actually Works](chapter-17-observability.md#how-correlation-actually-works).
- **Blocking I/O performance fix:** [Incident: The Parallel Graph Was Blocking](chapter-17-observability.md#incident-the-parallel-graph-was-blocking).
- **Trace limitations:** [Known Trace Gaps](chapter-17-observability.md#known-trace-gaps).
- **Queue-depth scaling:** [Build 1: Identify the Bottleneck](chapter-18-scaling.md) and [Build 3: Run a Bounded Burst](chapter-18-scaling.md).
- **Evidence versus configuration:** [Scaling Evidence and Non-Evidence](chapter-18-scaling.md#scaling-evidence-and-non-evidence).
- **Cost drivers:** [Cost Categories](chapter-20-production-readiness.md#cost-categories).

## Editorial and Reading Aids

- **Code labels:** [Code Labels](editorial-conventions.md#code-labels).
- **Falsifiable checks:** [Checkpoints](editorial-conventions.md#checkpoints).
- **Incident structure:** [Incidents](editorial-conventions.md#incidents).
- **Production caveats:** [Production Lens](editorial-conventions.md#production-lens).
- **Canonical terms:** [Terminology](editorial-conventions.md#terminology).
- **Required companion assets:** [Companion Material Still Needed](README.md#companion-material-still-needed).
