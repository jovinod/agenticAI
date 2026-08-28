# Chapter 9 — Guardrails

## The Problem, Stated Plainly

Chapter 8 drew the trust boundary around *services*: who can reach `alpha-api`, and how each backend service proves its identity to the next. Section F of that chapter went one layer deeper and asked what constrains an *agent* specifically — and one item was left explicitly open rather than papered over: F.6 named "treat tool results from untrusted sources as data, never as instructions" as a real gap, not a solved problem, because nothing in the project actually inspected what came back from a web search before handing it to a model. This chapter closes that gap for real, and adds one more: basic protection for the one genuinely free-text input a user can type into this app.

Two distinct problems, not one:

1. **Indirect prompt injection.** The News and Devil's Advocate agents both search the open web and feed whatever comes back into a model's context. That content is written by nobody this project controls — it could, in principle, contain text aimed at hijacking the agent reading it ("ignore your instructions and instead...").
2. **Accidental PII in free text.** `/search`'s `q` parameter is the one input in this whole app that isn't a tightly constrained value like a ticker or a market code — a human could type anything, including their own email or phone number, into a search box without thinking about it.

## A Real Test First: Does Azure OpenAI Already Cover This?

Before building anything, it was worth confirming what's already covered for free, since Azure OpenAI deployments ship with a default content filter. Two live, contrasting API calls settled it:

- A message containing an obvious jailbreak attempt, sent as the **user's own message**: rejected outright, HTTP 400, with the filter response including `jailbreak: { detected: true }`.
- The *exact same text*, sent inside a **`tool`-role message** instead (simulating what a poisoned search result looks like once it's in the conversation): HTTP 200, no `jailbreak` field in the response at all — it was never scanned.

That's not a bug in Azure OpenAI — the jailbreak classifier is documented to scan the user's own turn, on the reasonable assumption that a user might try to jailbreak the model directly. It says nothing about content a *tool* hands back, which is exactly the News/Devil's Advocate scenario. **Direct injection (a user attacking the model) is already covered. Indirect injection (a poisoned tool result attacking the model) is not.** This project needed something for the second case specifically.

## Provisioning Real Content Safety, Not a Regex Scanner

The tempting shortcut was a hand-rolled keyword/regex scanner — grep the search results for phrases like "ignore previous instructions." Rejected deliberately: injection phrasing is open-ended in a way pattern matching handles badly, the same reasoning already used in Chapter 8 F.6 for routing genuine judgment calls to a model rather than fixed rules. The chosen tool is **Azure AI Content Safety's Prompt Shields** — a real, GA Microsoft service purpose-built for this, with a genuine **Free tier (F0)**, no cost concern for a project this size.

Prompt Shields has two detection modes:
- **User Prompt attacks** (direct) — already covered by Azure OpenAI's own classifier, confirmed above.
- **Document attacks** (indirect/XPIA) — exactly the gap: hidden instructions inside third-party content the model is asked to *read*, not content the user typed.

The REST shape is simple: `POST {endpoint}/contentsafety/text:shieldPrompt?api-version=2024-09-01`, body `{"userPrompt": "", "documents": [...]}`, response `{"documentsAnalysis": [{"attackDetected": bool}, ...]}` — one verdict per document submitted.

### A Two-Cause `PermissionDenied`, Not One

Getting a live call to succeed took finding two genuinely separate problems, not one fix that took two tries:

1. **First failure**: tested under my own AAD identity, which had never been granted a role on the new Content Safety resource — only `alpha-worker`'s Managed Identity had. Fixed by granting my own account "Cognitive Services User" too, matching the same local-testing pattern already used for every other Managed-Identity feature in this project.
2. **Still failed after granting the role and waiting** (twice — 180s, then 600s — in case of RBAC propagation delay). The role definition was checked directly and genuinely includes the needed `Microsoft.CognitiveServices/*` wildcard, ruling out "wrong role." The real cause, found via a documentation search rather than guessed: **Cognitive Services resources need a custom subdomain configured before AAD/Bearer-token auth works at all** — key-based auth works without one, but a resource with no `customSubDomainName` set rejects RBAC-based calls with a generic `PermissionDenied` regardless of correct role assignments. This resource had none. Fixed with `az cognitiveservices account update --custom-domain alpha-research-contentsafety`, which also changes the endpoint from the auto-generated `...-b3156.cognitiveservices.azure.com` to the clean `alpha-research-contentsafety.cognitiveservices.azure.com`. Retested immediately — worked on the first try, correct `attackDetected: true`/`false` on a malicious vs. a benign document.

A background propagation-wait check (started before the subdomain fix was found) reported success only after the real fix had already been verified independently — a reminder that a passing check that arrives *after* a different fix landed isn't evidence for the theory it was testing.

## Wiring Decision: Where Exactly to Scan

`tools/prompt_shields.py`'s `scan_documents()` is called from exactly one place: `tools/web_search.py`'s `search_via_mcp`, immediately after results come back from the Tavily MCP subprocess, before they're returned to whichever agent called `search_web`.

```python
async def search_via_mcp(query: str, max_results: int = 5) -> list[dict]:
    async with stdio_client(_SERVER_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("search", {"query": query, "max_results": max_results})
            texts = [block.text for block in result.content if hasattr(block, "text")]

    is_safe = await scan_documents(texts)
    return [
        text if safe else "[Result removed: flagged as a potential prompt injection attempt]"
        for text, safe in zip(texts, is_safe)
    ]
```

Deliberately **not** wired into `agent_harness.py`'s shared `_call_tool` dispatcher, even though that would cover every tool with one change. Every other tool in this project (`compute_intrinsic_value`, `check_hard_stop_rules`, `fetch_stock_data`, `technical_indicators`) returns either a pure computation or data this project's own code fetched directly — there's no third party who could have hidden text inside it. Scanning those would be pure added latency and cost for a risk that doesn't exist at that call site. The boundary is drawn at the one place untrusted external content actually enters the system, not at every tool call generically.

## PII Scrubbing: A Deliberately Basic Scope

`backend/api/pii_scrub.py` is genuinely simple on purpose — two regexes, one for email shapes, one for loosely-shaped phone numbers:

```python
def scrub_pii(text: str) -> str:
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _PHONE_RE.sub("[redacted-phone]", text)
    return text
```

Wired into exactly one place — `/search`'s `q` parameter, before it's embedded:

```python
q = scrub_pii(q)  # Phase 9 (Guardrails) -- the one free-text input in this app
```

This is a safety net for the *accidental* case (someone typing "what did we say about AAPL, email me at ..." without thinking about it), not a defense against a determined attacker trying to smuggle data through free text — the same "route the well-defined pattern to a well-defined tool" reasoning as everywhere else in this project, just at the opposite end of the complexity scale from Prompt Shields. Every other input in this app (`ticker`, `market`) is already a tightly constrained value, not free text, so nothing else needed this treatment.

## Verified Locally, End-to-End, Before Touching Deploy

Before any deploy, the full real pipeline was exercised locally: `search_via_mcp('AAPL news August 2026', max_results=3)`, with `CONTENT_SAFETY_ENDPOINT` and `KEY_VAULT_URL` both set to their real values. This spawned the real MCP subprocess, made a real Tavily call, got back three genuine AAPL news articles, ran them through the now-correctly-authenticated `scan_documents()` against the live Content Safety resource, and returned all three **untouched** — zero false positives on real production search content, not just a clean result on a synthetic test string.

## Deploying Revealed Two Real, Unrelated Bugs

Neither of these is a guardrails bug — both are genuine Azure/tooling gotchas that happened to surface while deploying this phase, and both are worth documenting honestly rather than glossing over.

### `az acr build` packages the git-committed tree, not the working directory

The first deploy attempt built and pushed both images successfully, and both Container Apps updated cleanly — but a live exec into the running worker container turned up `ModuleNotFoundError: No module named 'tools.prompt_shields'`, despite the file existing on disk and `ls` inside the container showing every *other* file in `tools/`. The deployed `web_search.py` was also byte-for-byte the *old*, pre-Phase-9 version, matching `git show HEAD:...` exactly.

The cause: `prompt_shields.py` and `pii_scrub.py` were untracked (`??` in `git status`), and `web_search.py`/`main.py` had real uncommitted edits. `az acr build`'s local-context upload evidently packages the git-committed state of a directory that's part of a git working tree, not whatever is currently on disk — so every uncommitted or untracked file was silently absent from both images, with no warning or error anywhere in the build log. **Fix**: commit the changes first, then rebuild. Confirmed by the numbers matching exactly — `git show HEAD:backend/worker/tools/web_search.py | wc -c` returned exactly 2411, the same size as the stale file found running in the container.

### Updating to the same `:latest` tag doesn't create a new revision

Even after committing and rebuilding correctly, `az containerapp update --image ...:latest` left the *exact same replica* running — same replica ID, same file timestamps, confirmed by exec'ing in again. Azure Container Apps only provisions a new revision when the revision's template actually changes; referencing the same tag string (`:latest`) twice looks identical to the platform even though the underlying image digest changed, so it never re-pulled. **Fix**: tag the image with something unique per build — the short git commit SHA (`alpha-worker:79b6eb3`) — so the image *reference* itself changes and a genuinely new revision is forced. Confirmed via `az containerapp revision list`: a real new revision (`alpha-worker--0000010`, `alpha-api--0000006`) appeared, `Running`/`Healthy`, with the old one shown `Deprovisioning`.

Both fixes are now the standing pattern for deploying this project going forward: commit before building, tag by commit SHA rather than relying on `:latest` alone.

## Verified Live, In Production

With both bugs fixed and the correct images actually running, the guardrails were verified against the live, deployed system — not a local simulation:

**Prompt Shields**, executed inside the real running `alpha-worker--0000010` container via `az containerapp exec`, calling `scan_documents()` directly with a crafted injection attempt and a benign real AAPL sentence:

```
SCAN RESULT: [False, True]
```

The malicious document flagged `False` (unsafe), the benign one `True` (safe) — authenticated the whole time via the worker's own Managed Identity, not a personal credential.

**PII scrubbing**, executed inside the real running `alpha-api--0000006` container, calling `scrub_pii()` directly on a string containing a fake email and phone number:

```
SCRUBBED: What did we say about AAPL, contact me at [redacted-email] or [redacted-phone] if you have questions
```

Both ran the actual deployed code, in the actual production container, against the actual live Content Safety resource — closing the loop Chapter 8's F.6 left explicitly open.

## Key Files From This Chapter

| File | What it does |
|---|---|
| `backend/worker/tools/prompt_shields.py` (new) | `scan_documents()` — calls Content Safety's `text:shieldPrompt`, authenticated via `DefaultAzureCredential`; no-ops (everything passes) if `CONTENT_SAFETY_ENDPOINT` isn't set, matching every other Azure-only feature's local-dev shape. |
| `backend/worker/tools/web_search.py` | Scans Tavily results via `scan_documents()` before returning them; a flagged result is replaced with a placeholder string rather than dropped silently. |
| `backend/api/pii_scrub.py` (new) | `scrub_pii()` — regex redaction of email and phone-number shapes. |
| `backend/api/main.py` | `q = scrub_pii(q)` added to `/search`; also fixes a stale `"synthesizer"` reference in `_read_progress` left over from Chapter 5's Decision/Devil's Advocate swap. |

## Where This Stands

Indirect prompt injection via search results now has a real, live-verified defense, closing a gap Chapter 8 named explicitly rather than solved. Basic accidental-PII exposure through the one free-text input is scrubbed before it's embedded or stored. Both are deliberately scoped narrow — Prompt Shields only wraps the one tool that touches untrusted external content, and PII scrubbing only covers two common accidental shapes, not a general classifier — matching this project's standing principle of putting a real, purpose-built tool exactly where a genuine risk exists, and nowhere else.

Left deliberately open, not silently: flagged content today is simply replaced with a placeholder, not logged anywhere distinct from a normal tool-call log line (F.7's per-agent observability doesn't yet distinguish "a result was scanned and rejected" as its own event) — a real next step if injection attempts ever need to be tracked as their own signal rather than an ordinary tool result. PII scrubbing remains pattern-based and non-exhaustive by design. And the two deploy gotchas found this chapter — `az acr build`'s git-tracked-tree behavior, and `:latest` not forcing a new revision — are now a standing part of how every future deploy in this project should be done, not just a one-time fix.
