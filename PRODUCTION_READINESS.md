# Production readiness -- this branch, chapter 20

This branch was rebuilt from chapter 4 forward with a different goal than
the original pass: not "does this chapter's mechanism exist somewhere,"
but "checkout `chapter-N-start`, deploy `infra/params/chapter-N.json`,
run the real app, and see chapter N's own mechanism actually execute."
That closes what was previously this branch's largest honesty gap: the
real deployed worker used to be Chapter 3's placeholder all the way
through Chapter 20, with every advanced mechanism (the specialist graph,
Devil's Advocate, checkpointing, retries, trust-boundary dispatch, Prompt
Shields, standalone MCP search) proven only in isolated
`chapter-NN-illustrative/` modules the real worker never imported.

That gap is closed here. `backend/worker`'s real `process_message` now
runs the real six-node graph, with real memory, real debate, real
checkpointing, real retries, and real content-safety scanning, calling a
real standalone MCP search service and a real Azure OpenAI deployment.
This document is the honest accounting of what that rebuild actually
proved, what's still a real limitation, and what would need attention
before treating this as a genuine production system rather than a
faithful, chapter-by-chapter validation of the book's claims.

## What's real and deployed

Every Azure resource referenced by `infra/main.bicep` is real and was
verified by live deployment during this rebuild, not simulated:

- Azure Static Web App (frontend)
- Azure Container Apps: API, worker, embed worker, and (from Chapter 18)
  a standalone `mcp-search` service -- all with system-assigned managed
  identities
- Azure Database for PostgreSQL Flexible Server, with pgvector and
  Microsoft Entra authentication for the worker's own role
- Azure Service Bus (two queues: `research-jobs`, `embedding-jobs`),
  with queue-scoped RBAC per identity and KEDA queue-depth autoscaling
  on the worker
- Azure Managed Redis (`Microsoft.Cache/redisEnterprise` -- classic
  Azure Cache for Redis is being retired)
- Azure OpenAI (chat + embedding deployments) behind Azure API
  Management, authenticated with APIM's own managed identity
- Azure AI Content Safety (Prompt Shields for Documents)
- Azure Key Vault (RBAC-authorized), the one authoritative home for the
  Tavily search key
- Application Insights (workspace-backed) with OpenTelemetry tracing
  across the API and worker, correlated by `job_id`
- Microsoft Entra ID app registration backing real user sign-in (MSAL
  redirect flow with PKCE) and API token validation

## What's real in the deployed worker's own job path

Checking out any `chapter-N-complete` tag from 4 through 20, deploying
that chapter's `infra/params/chapter-N.json`, and submitting a real job
exercises that chapter's own claimed mechanism, not a placeholder:

- **Chapter 4**: real per-ticker market data (yfinance) and deterministic
  risk rules
- **Chapter 5**: a real MCP stdio search server and client (later
  promoted to a standalone HTTP service in Chapter 18)
- **Chapter 6**: a real tool-dispatch harness with a real allowlist
  registry
- **Chapter 7**: a real Azure OpenAI/APIM model client, skill discovery,
  and direct-call synthesis
- **Chapter 8**: a real five-node LangGraph (Fundamentals, Technical,
  News fan out; Risk fans in; Synthesizer combines)
- **Chapter 9**: real memory -- Redis progress, a durable Postgres ticker
  profile, and pgvector semantic recall across research runs, plus a
  real embed worker
- **Chapter 10**: real Devil's Advocate dissent and a real Decision node
  that overwrites the model's proposed recommendation fields with
  deterministic hard-stop and intrinsic-value calculations from real
  fundamentals data
- **Chapter 11**: real LangGraph checkpointing (`AsyncPostgresSaver`)
  against the real deployed Postgres -- a crashed job resumes from its
  last committed super-step
- **Chapter 12**: a real `RetryPolicy` on every node, and the
  chapter's own documented "broad try/except swallows the exception
  before the retry policy sees it" gap is fixed, not reproduced
- **Chapter 13**: real Microsoft Entra ID sign-in and token validation
- **Chapter 14**: real workload identity -- Entra-token Postgres access,
  queue-scoped Service Bus RBAC, and a real Key Vault-owned secret
- **Chapter 15**: real trust-boundary dispatch enforcement, inventoried
  and proven across the deployed worker's actual registries
- **Chapter 16**: real Prompt Shields scanning, wired into the actual
  search path every specialist uses
- **Chapter 17**: real Application Insights tracing with manual
  `job_id` correlation across the API/worker boundary
- **Chapter 18**: MCP search as its own standalone, identity-isolated
  Container App with a real Tavily backend (not a stub -- a real key was
  available for this rebuild), and real KEDA queue-depth autoscaling
- **Chapter 19**: a real report-history endpoint over existing storage,
  and a real sign-in bug found and fixed (redirect flow instead of
  popup, which Static Web Apps' Cross-Origin-Opener-Policy silently
  breaks)

## Real, currently-open gaps

These are not oversights hidden from this document -- they are known,
named limitations worth understanding before extending this branch.

- **Chapter 10's decision/hard-stop gap is deliberately not fixed.**
  `decision.py` does not force a recommendation to change when a hard
  stop is triggered -- a BUY can survive alongside a triggered stop. This
  was the original chapter's own documented gap, preserved here on
  purpose (Chapter 12's retry-swallow gap was fixed because that
  chapter's own point was resilience; Chapter 10's point was showing
  that Python-owned deterministic fields don't automatically become
  Python-owned *decisions*).
- **The checkpointer's Entra token is fetched once at startup, not
  refreshed.** `AsyncPostgresSaver` holds one connection for the whole
  worker process's lifetime; a worker long-lived enough to outlast that
  token's validity window would need the connection recycled, which this
  integration does not do. `db.py`'s own engine (used for everything
  else) does not have this problem -- it fetches a fresh token per new
  physical connection.
- **Job granularity is whole-ticker-list, not per-ticker.** The real
  deployed `Job` model holds one row per submitted ticker list, with one
  job-level status -- not the finished book's per-ticker `TickerJob` row
  design. The research graph runs once per ticker inside the existing
  job loop rather than requiring a schema change, but the API surface
  (one job, one status, an array of per-ticker summary strings) is a
  real, intentional simplification versus a from-scratch per-ticker
  fan-out.
- **No real Tavily subscription tier guarantees.** Search results are
  real, but rate limits, quota, and result quality are whatever the
  configured Tavily plan provides -- this was not load-tested.
- **Identity, RBAC, and Postgres role/grant setup are imperative, not
  IaC.** `az role assignment create`, `pgaadauth_create_principal_with_oid`,
  and the resulting `GRANT` statements were run by hand against the live
  resources during this rebuild and are not reproducible by re-running
  `infra/deploy.sh` alone. A fresh resource group needs these steps
  repeated -- they are documented in this branch's own chapter commit
  messages (Chapters 14, 16, 18), not captured in Bicep.
- **Single-region, no DR.** Everything lives in one resource group
  across two Azure regions chosen for SKU availability (`centralindia`
  for most resources, `southindia` for Azure OpenAI and Content Safety),
  with no failover, backup restore testing, or multi-region design.
- **`chapter-04-illustrative` through `chapter-15-illustrative` no
  longer exist on this branch.** Their content was absorbed into the
  real `backend/worker` chapter by chapter, not left behind as parallel,
  unintegrated proof. `git log` on this branch's earlier commits (or the
  `pre-rebuild-backup` tag) still has the prior state if that history is
  ever needed.

## Readiness scorecard

| Area | Status |
|---|---|
| Infrastructure as code | Strong for resource shape; imperative gaps for identity/RBAC/DB grants (see above) |
| Agent orchestration | Real and deployed -- the six-node graph, memory, debate, checkpointing, and retries all run in the actual job path |
| Authentication and authorization | Real (Entra ID, allow-list, queue-scoped workload identity) |
| Observability | Real (Application Insights, correlated tracing) |
| Content safety | Real (Prompt Shields wired into the actual search path) |
| Secrets management | Real (Key Vault, RBAC-authorized, one consumer) |
| Autoscaling | Real (KEDA queue-depth, verified with a live burst) |
| Test coverage | Strong at the unit/integration level; no load testing |
| Disaster recovery | Not addressed |

## Evidence still required before any production claim

1. Load testing against real Tavily/Azure OpenAI rate limits and quotas.
2. Convert the imperative identity/RBAC/Postgres-grant steps into
   reproducible IaC (Bicep `roleAssignment` resources, a deployment
   script step for the Postgres role, or a Terraform/Bicep-adjacent
   provisioning tool that supports both).
3. A resolved position on Chapter 10's decision/hard-stop gap -- either
   document it as permanent product behavior or fix it deliberately,
   not leave it ambiguous.
4. Multi-region or backup/restore drill for Postgres and the vector
   store.
5. A real load/soak test of the checkpointer's non-refreshing token
   limitation, to know how long a worker process can actually run
   before that becomes a real failure instead of a theoretical one.

## Lessons learned during this rebuild

Real incidents hit while doing this work, kept here because each one
was a genuine surprise, not a hypothetical:

- Piping `docker push` through `tail` discards the real exit code --
  a transient registry network failure was silently masked this way at
  least twice during this rebuild; always check the push's own exit
  code directly.
- `az acr repository delete --image <tag>` deletes by underlying
  manifest digest, not just the tag -- it can silently delete a
  co-tagged image.
- Azure Container Apps does not pull a new image for an unchanged tag
  string on `az containerapp update`; a same-tag rebuild needs a forced
  revision (`--revision-suffix`) to actually roll out.
- A partial `az containerapp update --scale-rule-metadata` update
  silently drops the KEDA scale rule's `identity: system` field --
  always redeploy the complete resource definition through Bicep
  instead.
- Container Apps' internal-ingress HTTP-to-HTTPS redirect turns a
  client's POST into a GET, discarding the JSON-RPC body -- MCP clients
  must be pointed at the final `https://` URL directly, never `http://`.
- The MCP SDK spawns a stdio subprocess with a minimal environment, not
  a copy of the parent's -- Container Apps' managed-identity token
  endpoint env vars (`IDENTITY_ENDPOINT`, `IDENTITY_HEADER`) must be
  explicitly forwarded for a subprocess's own `DefaultAzureCredential`
  to reach anything.
- `pgaadauth_create_principal_with_oid` and friends live in the
  `postgres` maintenance database, not the application database --
  connecting to the wrong database produces a plain "function does not
  exist" error with no hint about which database to use instead.
- Cognitive Services / Key Vault / API Management resources are
  soft-deleted, not immediately removable -- recreating a same-named
  resource in a fresh resource group after a teardown requires an
  explicit purge first.
- Device-code OAuth flows have a real, easy-to-hit expiry window in
  practice -- MFA and consent steps can take longer than the code's
  validity, especially across several back-to-back verification passes.
