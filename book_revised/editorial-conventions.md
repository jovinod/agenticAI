# Editorial Conventions

This document keeps the revised manuscript internally consistent. It is primarily for authors and reviewers, but readers can also use it to understand the book's structure and code labels.

## Book Model

Building Agentic AI Systems is a **concept-first technical book with one running example**.

The reader studies an agentic stock-research application one working layer at a time. Stock Research Assistant is the running example. Each chapter introduces a problem, explains one part of the solution, and uses the companion repository as the complete implementation reference.

## Voice and Language

Use present tense for the main teaching narrative:

- Write “we build,” “the API returns,” and “the worker reads.”
- Use “you” for actions the reader takes.
- Use “we” for design decisions made together during the build.
- Use past tense only in a clearly labeled incident or historical note.

Write for a developer who is new to distributed and agentic applications:

- Prefer short sentences and familiar words.
- Introduce one new idea at a time.
- Explain a technical term when it first appears.
- Show a concrete example before discussing the general rule.
- Expand an abbreviation the first time it appears.
- Avoid phrases that assume prior cloud, AI, or distributed-systems experience.
- Keep technical accuracy. Simplify the explanation, not the behavior.

## Standard Chapter Contract

Use these sections when they apply:

1. **Chapter title and opening problem** - establish the practical tension in a few paragraphs.
2. **Chapter Snapshot** - state what already exists, what the reader adds, and whether the finished repository differs from this step.
3. **What This Chapter Explains** - describe the reader-visible behavior and design change in plain language. Lead with the lifecycle or outcome; introduce route names, function names, and protocol details only when they clarify the explanation.
4. **Runtime Behavior** - describe falsifiable observations without turning the chapter into a setup guide.
5. **Design** - explain responsibilities, boundaries, state changes, and tradeoffs before implementation details. Put the chapter's orienting architecture or sequence diagram here, before code.
6. **Behavior evidence** - use a compact table or focused observation when it clarifies a boundary.
7. **How It Works** - explain the mechanism after the reader has a concrete anchor.
8. **Incident** - include a real failure only when it changes the lesson.
9. **Production Lens** - state what is already production-shaped and what remains simplified.
10. **Known Limitations** - state unresolved failures, missing guarantees, and deliberate simplifications.
11. **Azure Resources for This Stage** - name the resources used by this chapter and explain their runtime responsibilities without provisioning instructions.
12. **Azure Architecture** - when the chapter activates Azure resources, bridge explicitly from the local responsibilities to their Azure services, then show the deployed components in a clear top-down runtime flow. Keep secondary dependencies visually subordinate and avoid large filled containers that dominate the diagram.
13. **Architecture After This Chapter** - show only what exists at this point.
14. **Read the Chapter Code** - near the end, provide a compact map to the final chapter tag and the few files that best reveal the completed implementation.
15. **See What Changed** - when useful, follow the final-code map with the starting tag, final tag, and direct Git diff in one compact table.
16. **Next** - introduce the unresolved problem that motivates the next chapter.

Do not force every heading into short conceptual chapters. Preserve the contract, not mechanical uniformity.

Open each technical section with the component's responsibility, behavior, or design purpose in plain language. Do not lead with HTTP methods, route paths, function signatures, environment variables, or commands. Introduce those details after the reader understands why they matter.

## Snapshot Block

Every chapter begins with a block in this form:

```markdown
> **Chapter snapshot**
> - **Starting point:** What the reader has built so far.
> - **Focus in this chapter:** The behavior or component the reader studies now.
> - **Local reference:** An intermediate teaching tag, only when it makes the core mechanism easier to study.
> - **Finished repository:** Whether current files still match this chapter.
> - **Coming next:** The next change that affects this part of the system.
```

The finished repository field points to the chapter's final completion tag, including its cloud adaptation. If the chapter uses a smaller local implementation to teach the mechanism, identify it separately as the local reference rather than presenting it as the finished state.

Do not force history into the snapshot. Include an intermediate tag only when readers need it to understand why the excerpts differ from the final chapter code.

## Code in the Manuscript

Use code only when a small excerpt makes a concept easier to understand.

- Prefer diagrams, state transitions, request examples, and pseudocode over complete files.
- Show the minimum lines needed to expose the decision being discussed.
- Do not reproduce complete route handlers, models, workers, tests, Dockerfiles, or infrastructure commands in conceptual chapters.
- Introduce a full file with its decisive slice, then point to the chapter tag and path for imports, setup, and boilerplate.
- Point to the chapter completion tag and repository path for the complete implementation.
- Keep Azure provisioning and deployment commands in repository scripts, not in chapters. Assume the shared Azure foundation is provisioned during the book's initial setup. Each chapter names the resources that become active at that stage and explains their runtime responsibilities.
- A reader must be able to understand the chapter without typing the code.

Chapters are guided code readings, not step-by-step implementation tutorials. Avoid branch creation, dependency installation, file-editing sequences, terminal-by-terminal startup instructions, and completion checklists. Use Git tags as the source of complete code and retain only commands that help readers inspect a tagged change.

Do not include prompts that ask a coding agent to implement an entire chapter. Keep chapter-scale agent workflows in an appendix so the main narrative teaches readers to understand and verify each boundary themselves.

A repository tour should name each relevant file and tell the reader what design decision to inspect there. When useful, include a tag-to-tag `git diff` command instead of copying the diff into the book.

## Introducing Code Excerpts

Introduce each code block with a natural sentence that explains the behavior it demonstrates, such as “Here is a sample implementation of how a worker claims the next queued job.” Do not prefix excerpts with editorial labels such as “Chapter version,” “Current excerpt,” or a file path. Put complete file paths and milestone tags in the chapter's **Read the Chapter Code** section.

When an excerpt omits context or combines code for clarity, state that briefly in the surrounding prose. Use a formal label only when readers could otherwise mistake pseudocode or historical code for the current implementation.

Do not repeat “inspect the full file” after every excerpt. Consolidate references in the chapter's **Read the Chapter Code** section near the end. By default, point to the final chapter tag that contains the deployable implementation. Use one short introduction and one compact table with intuitive descriptions. If readers need to navigate the repository history, put the starting tag, final tag, and one direct start-to-finish diff in a separate compact section; omit intermediate milestones unless they are essential to the chapter's argument.

### Chapter Version

Use for code that represents the system at this step of the build but differs from the finished repository.

```markdown
**Chapter version - `frontend/src/App.jsx`:**
```

### Current

Use only when checked against the present repository.

```markdown
**Current excerpt - `backend/worker/agents/graph.py`:**
```

### Illustrative

Use for shortened pseudocode, omitted imports, ellipses, or merged examples.

```markdown
**Illustrative excerpt - error handling omitted:**
```

Never put an ellipsis inside executable-looking code without labeling it illustrative.

### Command

Name the shell when syntax differs:

```markdown
**PowerShell:**
```

```markdown
**Bash:**
```

Prefer cross-platform commands where practical. Do not present Bash environment assignment syntax as a Windows command.

## Behavior Evidence

Runtime evidence must be falsifiable. “The deployment succeeded” is weak. Better evidence includes:

- A new revision with a recent creation time exists.
- The old worker revision has zero replicas.
- An API response contains the expected field and status code.
- A failed node resumes without rerunning completed nodes.
- A trace contains the expected `job_id` and child spans.

Prefer a compact table that connects a situation, its observable result, and the guarantee it demonstrates. Include commands only when they help inspect repository history or clarify evidence that cannot be explained directly.

## Incidents

Keep incidents that reveal a general mechanism. Compress incidents that only record command history.

Each incident should answer:

- What did we expect?
- What happened instead?
- What evidence distinguished the two?
- What design or operating rule changed afterward?

Use “real,” “genuine,” and “verified live” sparingly. Evidence should establish credibility.

Incidents are the main exception to the present-tense rule. Use past tense to describe what happened, then return to present tense for the lesson and the reader's next action.

## Production Lens

A Production Lens is two to five sentences. It must say one of:

- This is already the production-shaped choice and why.
- This is deliberately simplified, what production adds, and when the book addresses it.
- This is an accepted limitation and the risk it creates.

Do not invent a difference merely to fill the callout.

## Architecture Diagrams

Chapter diagrams show the architecture at that point in the repository history.

- Show only components built by that point.
- Visually distinguish new and existing components when doing so remains legible and portable across Mermaid renderers.
- Keep one canonical final topology in the concluding chapter and root project documentation.
- Label a diagram as a chapter version when the finished repository has moved beyond it.

## Terminology

Use these terms consistently:

- **Chapter:** a unit of the book.
- **Phase:** avoid this term in the teaching narrative. Use it only in an optional historical note.
- **Stage:** a step within a chapter when several migrations form one change.
- **Tool:** a callable function whose use may be selected by a model.
- **Direct call:** deterministic application code invokes a function without model choice.
- **Skill:** a reusable capability package with instructions and optionally executable code.
- **Harness:** the loop that mediates model messages, tool calls, limits, and outputs.
- **Orchestrator:** the graph that schedules agents and moves shared state.
- **Checkpoint:** persisted graph execution state at a super-step boundary.
- **Thread:** the stable identifier LangGraph uses to locate a checkpoint history.

When an older code label differs, explain it once and then use the book's canonical term.

## Endings

Do not use both “Where This Stands” and “What Came Out of This Chapter” to repeat the same facts. Do not add review questions merely to recap the chapter. End with known limitations and the unresolved problem that motivates the next chapter.

The final chapter must conclude the book, not merely report another phase.
