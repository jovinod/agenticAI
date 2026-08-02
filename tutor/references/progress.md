# Progress Log

Update this after each session: what got done, current phase/step, open questions, decisions made. Note explicitly when a "Deploy & verify" step has actually been completed live on Azure, not just built locally.

## Status
- Current phase: Phase 1 — Frontend shell, local build in progress (no Azure deploy yet). Phase 0 audit complete.
- Decisions locked in: React + Vite for frontend; deploy-as-you-go (build → deploy → verify live → next layer), not build-everything-then-deploy; ESLint (not Oxlint) for linting — matches Vite's default scaffold, ecosystem maturity (react-hooks rules) matters more than raw speed at this project's size; multi-ticker input = single comma-separated field (not add-one-at-a-time chips, at least for now)
- Frontend built so far (`frontend/src/App.jsx` + `App.css`): centered "Google-style" search box UI (reusing scaffold's existing `#center` flex utility), heading "Alpha - Stock Research", controlled input bound to `tickerInput` state, `handleSubmit` parses comma-separated input → uppercased/trimmed `tickers` array, basic regex format validation with inline error message. Full `idle → loading → done` flow now wired: submit generates a fake `crypto.randomUUID()` job id, shows a loading message, and after a 2s `setTimeout` shows a fake report (one line per ticker) with a "New search" reset button. Everything still mocked/hardcoded — no network calls yet.
- **Phase 1 build is functionally complete** — this was the last piece before the first Azure Static Web Apps deploy. Next up: deploy this build live and verify the mocked flow works from a public URL (Phase 1's "Deploy & verify" step), which kicks off Phase 2 (real backend) after that.
- Last session: Phase 0 audit done — repo was empty (only the tutor skill itself existed, no prior app code, not yet a git repo). Node v24.16 / npm 11.13 confirmed installed, no pnpm/yarn — using npm.

## Log

- 2026-08-02: Skill set up with full phase roadmap, decision cheat sheet, and target folder structure. Confirmed with user: incremental deploy-per-layer is required, not optional. Next: audit existing project (Phase 0), then build Phase 1 frontend shell locally, then deploy it live before touching the backend.
- 2026-08-02: Phase 0 audit — confirmed clean slate (no existing app code), git not yet initialized, npm available as package manager. Started Phase 1: guided user to scaffold `frontend/` with Vite + React.
- 2026-08-02: User scaffolded `frontend/` themselves (Vite + React + ESLint, default template). Extensive concept teaching this session — see `concepts.md` (JSX/build step, CSR, state→UI mapping, lists/re-render triggers, routing, React vs Angular vs Next.js, SEO/crawler mechanics, bundle scope, async state resolution/polling intent, Vite vs React separation, controlled components, regex validation). Built: static input → styled centered layout (Google-style) → controlled state → comma-separated parsing into `tickers` array → format validation with error display. User is alternating between typing code themselves and asking Claude to apply it directly — follow whichever the user asks for per-step, default to guiding when not specified.
- 2026-08-02: Added `references/concepts.md` as a new living reference (distinct from `progress.md`/`decisions.md`) to preserve concept explanations across sessions; wired into `SKILL.md` so future sessions keep updating it.

## Open questions
- None currently. Git init will be needed before the Phase 1 Azure Static Web Apps deploy step (typically deploys via GitHub Actions) — flagged for when we reach that point, not blocking local work now.
