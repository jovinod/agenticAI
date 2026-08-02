# Concepts Learned — Running Notes

Personal glossary of concepts explained during tutoring sessions, in plain language. Updated as new ground is covered — read `progress.md` for phase/status, this file for "what does X actually mean and why."

---

## Phase 1 — Frontend

### Why React at all (vs. plain HTML/CSS/JS)
- We still write JSX (HTML-shaped) and CSS ourselves — React doesn't remove that.
- What it removes: **manually creating/removing/updating real DOM elements by hand** as data changes. In vanilla JS, keeping the page in sync with changing state means writing (and maintaining) a pile of "find element → show/hide/update it" code yourself — easy to forget a spot, easy to get out of sync.
- React's model instead: describe *what the UI should look like for the current state*; React figures out what changed and updates only that.
- Picked React specifically because our app's shape is a state machine (`idle → loading → done/error`), which is React's core specialty — not because "SPA = simple," SPA is just an app shape any framework (or vanilla JS) could build.

### The build step (JSX → real JS)
- Browsers never learned to read JSX (`<div>` mixed directly into JS) — it's not valid JavaScript.
- JSX is shorthand for `React.createElement(...)` calls, which *are* valid JS. The build step **transpiles** JSX → plain JS.
- It also **bundles** many source files into few files (browsers loading dozens of files one-by-one is slow/fragile), and **strips dev-only extras** (React's helpful console warnings) that a real visitor doesn't need.
- `npm run dev` = translates on the fly in memory, for local editing with instant reload.
- `npm run build` = writes the final transpiled+bundled+stripped result to a `dist/` folder as plain `.html`/`.js`/`.css` — these are **static files**: pre-made files a server just hands out as-is, no computation per request (like a PDF on a shelf, vs. a server computing a fresh response every time).
- This is not a tutorial simplification — production React apps ship through this exact same build step.

### Block diagram — React across client and server

```mermaid
sequenceDiagram
    participant B as Browser (Client)
    participant S as Static File Server<br/>(Azure Static Web Apps)
    participant A as Backend API<br/>(FastAPI, Phase 2+)

    Note over B,S: 1. Initial page load
    B->>S: GET / 
    S-->>B: near-empty HTML shell + JS bundle<br/>(same for every visitor — static files)

    Note over B: 2. Browser runs the JS bundle<br/>React builds the UI in memory → writes into the DOM<br/>(this is "client-side rendering")
    Note over B: Page now shows the idle ticker-input screen

    Note over B: 3. User types a ticker, hits submit<br/>setStatus("loading") called
    Note over B: React re-renders in memory (cheap),<br/>diffs, updates only the real DOM bits that changed<br/>— still 100% inside the browser, no network yet

    Note over B,A: 4. Only now does a real request happen
    B->>A: GET /research/{job_id}<br/>(separate API call, different server)
    A-->>B: JSON data (the real report)

    Note over B: 5. setStatus("done", data) called<br/>React re-renders again with real content<br/>Page now shows the finished report
```

- **Two different servers, not one**: the static file server only ever hands out the same fixed shell + JS bundle — it doesn't know or care about tickers. The backend API is the only one that ever sees a real ticker or returns real data. This split is why Phase 1 (frontend + fake mocked data) can be built and deployed entirely before Phase 2 (real backend) exists.
- **Steps 2–3 never touch the network** — rendering and re-rendering (idle → loading) happen purely in-browser, in memory. A network call only happens at step 4, and only because our code chose to make one.
- This is why the Phase 1 → Phase 2 swap works cleanly: build/deploy steps 1–3 fully with a fake job_id and fake polling, then later point step 4 at a real API — steps 1–3 don't change at all.

### Client-side rendering (CSR) — what plain React (via Vite) does
1. Server sends back a near-empty HTML shell (`<div id="root"></div>` + a `<script>` tag) — same shell to every visitor, regardless of what data they're after.
2. Browser downloads the JS bundle and **runs it** — that JS is your React code, and it builds the actual visible page into that empty div.
3. For *dynamic* data (e.g. a stock report): the server never bakes it into the shell. Instead, your running React code makes a **separate API call** (e.g. `GET /research/{job_id}`) after the page is already up, and updates the page once that data arrives. Page shell and real data arrive via two independent trips.

### State → UI mapping (no separate "store")
- State is just a plain variable: `const [status, setStatus] = useState("idle")`.
- The "mapping" from state to UI is just ordinary JS conditionals written directly inside the component function (`{status === "loading" && <p>Loading...</p>}`) — no registry or config file involved.
- Your component function **is** the mapping — React calls it again whenever state changes, and it returns what the UI should look like *right now*.

### Why re-running the function isn't slow
- Returning JSX doesn't touch the real page — it builds a small, cheap **in-memory JS object** describing desired UI (e.g. `{ type: "p", props: { children: "Loading..." } }`), same cost as building any plain object like `{ name: "Sam" }`.
- The expensive browser operation is touching the **real DOM** (layout/repaint) — React's diffing step exists to minimize exactly that, only updating what actually changed.
- So: cheap in-memory recompute happens often; expensive real-DOM writes happen only for the actual differences.

### Lists / dynamic data — where React actually saves real complexity
- For a small fixed number of branches (e.g. 4 status states), React's conditionals aren't meaningfully simpler than vanilla JS's — roughly a wash.
- The real win is **lists that grow/shrink** (e.g. a list of tickers). Vanilla JS requires manually clearing old DOM nodes and recreating new ones every time the array changes (forgetting to clear = duplicates piling up). React: `{tickers.map(t => <li key={t}>{t}</li>)}` — no manual node bookkeeping, React reconciles automatically.
- **The trigger is always explicit**: you never watch individual items for changes. You call `setTickers(newArray)` once whenever anything about the array changes, and React cascades the re-render through every component that depends on it (via props) — you don't wire that cascade yourself.
- **Important gotcha:** React only reacts to `setState` calls, not in-place mutation. `tickers.push(x)` → React never finds out, screen stays stale. Must build a *new* array/object (`setTickers([...tickers, x])`) — this is the actual signal React listens for, not smart change-detection.

### Vite vs. React — different layers, no overlap
- **React** runs *in the browser* — owns all runtime behavior (state, re-render, diff, DOM updates) covered elsewhere in this doc.
- **Vite** runs *on your machine* (dev) and *once at deploy* (build) — never runs in the browser, has zero involvement in state/re-render/diffing. Its job ends once code is delivered to the browser in runnable form; React takes over completely from there.
- Concretely: Vite serves/translates `main.jsx` (starts React) and `App.jsx` (your component) — JSX → real JS, file by file while developing, or bundled+minified into `dist/` for shipping.
- Hot Module Replacement (HMR): on save, Vite pushes just the changed piece into the already-open tab — instant update, no full reload, no lost input state. Dev-experience feature only, unrelated to React's own behavior.
- Vite isn't React-specific — also works with Vue, Svelte, plain JS. It doesn't know what "state" or "a component" is; it only transforms/serves files via a small per-framework plugin (e.g. JSX support).

### Does React "listen" for state changes?
- No — the setter from `useState` (e.g. `setStatus`) is not your function, it's **React's own function**, handed to you. Calling it is a direct call straight into React's code, not an outside notification React has to detect/listen for. There's no gap where React could "miss" a change.
- Mental model: not eavesdropping/polling — more like pressing a button that's wired directly into React's machinery.

### Bundle scope — does the browser run "all" the JS?
- The build step decides bundle contents ahead of time, not the browser — by the time it reaches the browser, it's already exactly what's needed, not "many files to pick from."
- Our app is a single page, so the bundle ≈ the whole app — browser runs essentially all of it.
- Larger multi-page apps use **code-splitting** (separate chunks per route, loaded on demand) — not needed for us.
- "Executing the bundle" = running top-level setup once (definitions + one `render(<App />)` call that triggers the first component run) — not invoking every function immediately. Later runs only happen when state changes, as covered above.

### Who resolves state after an async API call (polling)
- Nothing automatic — React has no built-in awareness of network requests. *We* write the code that calls the API and explicitly calls `setStatus(...)` once the response arrives:
  ```jsx
  async function checkStatus(jobId) {
    const response = await fetch(`/research/${jobId}`);
    const data = await response.json();
    setStatus("done");
    setReport(data);
  }
  ```
- `fetch` returns a Promise (JS's "this finishes later" mechanism); `await` pauses *this function* until the response lands, then our own next lines (including `setStatus`) run — same explicit-trigger rule as everywhere else in React.
- Our backend job is queued/async (worker processes it), so the first status check may come back "still running" — real implementation will **poll** (`GET /research/{job_id}` on a repeating timer) until it says done, then stop. Browser isn't notified proactively; it keeps asking.
- 🏭 Production lens: polling is simple and fine at our scale. Higher-scale systems might use WebSockets/Server-Sent Events so the server pushes "done" instead — a deliberate scope choice here, not a shortcut to fix later.

### Controlled components
- Making an `<input>`'s displayed value come *from React state* (`value={tickerInput}`) instead of letting the browser silently track it internally — React always knows the exact current value, which matters once you need to actually use/validate/submit it.
- Pairs with `onChange={(e) => setTickerInput(e.target.value)}` — fires every keystroke; `e.target.value` is the input's current text; passing it to the setter is the same direct-call mechanism covered earlier, just triggered by typing instead of a click.

### Regex for basic format validation
- A regex (e.g. `/^[A-Z]{1,5}$/`) is a pattern-matching rule — this one reads "1 to 5 uppercase letters, nothing else." Used here to catch obviously-malformed ticker input before submit.
- 🏭 Production lens: this only checks *shape*, not whether a ticker is real/tradeable — that requires checking against a real data source (Phase 3). Catching malformed input early client-side is still exactly what production apps do; it's just not the whole validation story.
- Error display reuses the same `{condition && <element>}` conditional-rendering pattern from the state→UI mapping section above — one more concrete use of it.

### Routing
- Multi-page apps: each navigation = new request = new full-page reload from the server.
- SPA routing: JS intercepts the "navigation," swaps which components are shown, no reload. React doesn't include this by default — a separate small library is added if needed.
- Our app is one screen — no routing needed.

### React vs. Angular vs. Next.js
- **React**: small library, UI-only. You add routing/forms/HTTP separately as needed.
- **Angular**: all-in-one opinionated framework (routing, forms, HTTP, DI, testing built in). Best for large teams/enterprise apps needing one enforced "right way." Uses its own template syntax, not JSX (e.g. `*ngIf`).
  - **Correction to remember: Angular is client-side rendered by default, same as plain React.** SSR is only available via an optional add-on (Angular Universal) — it is *not* automatic. Don't conflate Angular with SSR/SEO benefits.
- **Next.js**: not a peer of React — it's React *plus* extra machinery. The bigger feature is **server-side rendering / static generation** (not just routing, though it adds that too).

### Client-side vs. server-side rendering, and search engine crawlers
- CSR: server always sends the same near-blank shell; real content appears only after JS runs in the browser.
- Two separate reasons this matters for crawlers:
  1. **Capability limit (the bigger one):** most bots (Bing, DuckDuckGo, social link-preview bots like Slack/Twitter) **never execute JavaScript at all**, ever — a CSR page is permanently empty to them, not a timing issue.
  2. **Timing risk (Google specifically):** Googlebot *does* run JS, but as a delayed second pass (fetch HTML first, come back later — sometimes much later — to render JS and snapshot the result). If real content depends on a slow/flaky API call, Google's snapshot may capture a still-loading state.
- SSR sidesteps both: full real content is in the very first HTTP response, before any crawler-specific JS execution or timing behavior is relevant.
- **Not relevant to our project** — our tool isn't meant to be search-indexed, just documenting the mechanism since it came up.
