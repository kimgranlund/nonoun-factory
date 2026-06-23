---
description: Start the zero-dependency productivity shell — a project drawer + per-project view (lifecycle stage · Specs & Inputs · tickets kanban · ledger · trust tier) over a projects root, with a LIVE layer (SSE auto-refresh) and a ▶ Run loop action. Read state is a pure projection; the one action invokes the gated controller server-side. Open the printed URL.
argument-hint: "[--root DIR] [--port N]   (DIR=./projects, N=8765 with fallback)"
---

Start the dev-server. **$ARGUMENTS**

```
python3 "${CLAUDE_PLUGIN_ROOT}/dev-server/serve.py" --root projects --port 8765
```

A buildless vanilla UI on stdlib `http.server` — **no FastAPI, no build step** (app-factory stays self-contained). It scans the projects root for corpora (`<name>/.factory/`) and serves:

- **a project drawer** — every project with its stage + ticket progress + earned trust tier;
- **Specs & Inputs first** — idea · PRD · QA maturities and the committed specs, because cultivating better specs is the work that makes the loop reliable;
- **a tickets kanban** — each crystallized ticket grouped by its cell's real maturity (draft → validated, or blocked);
- **the lattice histogram + ledger feed** and the trust-tier reason.

Every value is read from the corpus + the vendored kernel (`ledger.py trust`, the lattice) — the shell is a projection over git-tracked state, never a second source of truth. It is **live**: the UI subscribes to `GET /api/stream?project=<name>` (SSE) and re-renders the instant the lattice/ledger changes, so the kanban moves tickets to `validated` as the loop runs. The port auto-advances if taken; the bound URL is printed.

> **The one write path is gated, not a bypass.** The ▶ Run loop button POSTs `/api/project/<name>/loop`, which the server fulfils by invoking the controller (`app-loop.py run`) — armed fail-closed, signals minted by the independent validator, every step ledgered. Authoring mutations (`/app-new`, `/app-spec`) stay in the commands. The UI drives the factory **through** its gates; it never writes state directly.
