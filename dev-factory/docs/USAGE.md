# Using dev-factory — examples & workflows

_Last reviewed: 2026-06-19._

How to actually **build software** with the dark factory: scaffold an instance, run the loop, and let it
author, validate, and assemble whole apps. The README explains the architecture and `RUNBOOK.md` covers
operating a running server; this is the task-oriented "how do I…" guide.

> **The one safety rule up front.** The dispatch adapter is the spend lever, not the heartbeat. `mock`
> (the default) is free and deterministic; `headless` spawns real `claude -p` workers (real tokens). A real
> build is always **bounded** by the run budget (`DEV_FACTORY_MAX_DISPATCHES` · `DEV_FACTORY_DEADLINE_S` ·
> `DEV_FACTORY_TOKEN_CEILING`) and fails closed unless armed. Keep the adapter on `mock` except for a
> deliberate, capped build.

---

## 0 · Setup — an instance + a bound kit

A dev-factory **instance** is a project's `src/<project>/.factory/`. Scaffold it, then bind a family kit
(`dev-kit-app` for code, `dev-kit-corpus` for docs):

```bash
# scaffold the instance (the lattice, coordination/, layer dirs, ledger)
python3 dev-factory/dev-kernel/bin/lattice.py init --dir src/my-app/.factory

# an operator env file (gitignored — absolute paths, the spend lever). Start on mock.
cat > src/my-app/dev-factory.env <<'EOF'
DEV_FACTORY_DIR=/abs/path/src/my-app/.factory
DEV_KERNEL_BIN=/abs/path/dev-factory/dev-kernel/bin
DEV_FACTORY_KIT=/abs/path/dev-factory/dev-kit-app
DEV_FACTORY_ADAPTER=mock          # the spend lever — flip to `headless` only for a capped real build
DEV_FACTORY_HEARTBEAT=1
DEV_FACTORY_MAX_DISPATCHES=10
DEV_FACTORY_DEADLINE_S=2400
DEV_FACTORY_TOKEN_CEILING=3000000
DEV_FACTORY_CONCURRENCY=2
DEV_FACTORY_TIER=1                # 0 attended · 1 gated (parks at in-review for sign-off) · 2+ unattended-to-done
PORT=8731
EOF

# start the server (UI at http://127.0.0.1:8731/)
pip install fastapi uvicorn
DEV_FACTORY_ENV=src/my-app/dev-factory.env ./dev-factory/dev-server/run.sh
```

---

## Workflow 1 · Watch the loop run — free, attended (Crawl → Walk)

The cheapest way to see the machine work: the `mock` heartbeat advances the lattice deterministically, no
tokens. Open the dashboard and watch cells move `absent → … → validated` and tickets cross the Kanban.

```bash
# already running on mock from setup. Drive a cell by hand over the API, or let the heartbeat pick the frontier.
curl -s localhost:8731/api/status   | python3 -m json.tool   # factory state + the armed run budget
curl -s localhost:8731/api/lattice                            # the cell grid
curl -s localhost:8731/api/tickets                            # the board
```

The board **cannot disagree** with the lattice — a ticket reaches `done` only through the same `gate-signal`
that advances its target cell. Pause/resume the loop from the UI or `POST /api/control/pause`.

---

## Workflow 2 · A real headless build — bounded, deliberate spend

Flip ONE app cell to a real build. The pattern: **tight caps → restart → arm → watch → accept → revert to mock.**

```bash
# 1. create + activate a ticket bound to a target cell (a legal, signal-bearing transition + a VALIDATED rubric)
#    — via the UI's create-modal, or the API:
curl -s -X POST localhost:8731/api/tickets -H content-type:application/json -d '{
  "type":"feature","title":"build the token engine",
  "target_cell":"capability.system.core","target_transition":{"from":"regenerating","to":"validated"},
  "acceptance":{"rubric_cell":"rubric.system.test-suite"},"budget":{"iterations":3,"tokens":700000}}'
# (then draft → active in the UI, or POST /api/tickets/{id}/transition)

# 2. flip the env to headless with TIGHT caps, restart (a restart re-arms a FRESH window):
#    DEV_FACTORY_ADAPTER=headless  MAX_DISPATCHES=1  DEADLINE_S=400  TOKEN_CEILING=400000
# 3. the heartbeat dispatches the active ticket → a real worker authors the cell → a SEPARATE critic validates it.
# 4. at Tier 1 the cell parks at `in-review`; accept it (plain `done` passes gate-signal on the critic's signal).
# 5. REVERT the env to mock + roomy caps. Real builds are the exception, not the steady state.
```

A worker writes only the product tree (`src/my-app/<slug>/`); the gates deny it the `.factory/` state and
its own `verify.mjs` (it can't grade its own homework). A run that exhausts its budget halts dispatch.

---

## Workflow 3 · Build a WHOLE app, autonomously

The factory builds every layer — modules **and** the integration shell — from a spec, validating each against
a real gate it authors itself.

1. **Author the spec** (intent is yours): write `spec.system.app-prd.md` (outside-in PRD) + `spec.system.app.md`
   (inside-out decomposition — name the modules + their contracts). This is the only hand-written step.
2. **Seed the build**: flip the capability cells to `regenerating`, seed a `capability.system.shell` cell, and
   create one active ticket per cell, dependency-ordered (`core` · `persistence` → `ui` → `shell`).
3. **Arm a headless run** (`MAX_DISPATCHES≈12`, a generous deadline + token ceiling) and let it cascade:
   - On a real build, **the verifier-author default fires automatically** — before each module builds, the
     rubric-architect authors that cell's *real, spec-derived* `verify.mjs` (a spec-conformance test, not a
     `ready` check), so the module is graded against a real contract. (Helper: `dispatch.author_app_verifiers`.)
   - Modules build (`core → persistence → ui`), each validated against its real verifier.
   - The **shell** is authored at the product root (`index.html`) — a thin bootstrap that imports + mounts the
     built modules — and validated by the **render-coherence gate** (it's executed headlessly and must draw a
     WebGL frame OR mount DOM).
4. **Accept** the parked cells; the Preview tab serves the running app from `src/my-app/index.html`.

This is the closed loop: the factory authored the verifier, the module that passes it, and the shell — and
graded itself against contracts derived from your spec. (Proven on four apps; see the campaign learnings doc.)

---

## Workflow 4 · Switch between projects (one server, many instances)

The header **project selector** re-points the running server at any sibling instance under `src/` — no restart:

```bash
curl -s -X POST localhost:8731/api/project -H content-type:application/json -d '{"project":"icon-forge"}'
# the board + Preview reload against icon-forge; it lands PAUSED (a switched-to project never auto-dispatches).
```

Guarded: it refuses mid-build (a running worker) and rejects a name that escapes `src/`.

---

## Workflow 5 · Inspect & steer

- **Preview tab** — the built app, served live from the product tree (`/preview`).
- **Lattice grid** — every cell's maturity + its critic-minted signals.
- **Ledger** — the tamper-evident, hash-chained event stream (every dispatch, signal, transition).
- **Steer a running worker** — `POST /api/input` adds guidance the *next* dispatched worker folds in (a one-shot
  `claude -p` can't take mid-flight input).
- **Read-only MCP** — `factory-query` exposes cells/tickets/signals/ledger to an external agent without write access.

---

## Safety & bounds (the short version)

| Lever | Effect |
|---|---|
| `DEV_FACTORY_ADAPTER` | `mock` (free, deterministic) vs `headless` (real `claude -p`, real tokens). **The spend control.** |
| `DEV_FACTORY_MAX_DISPATCHES` / `DEADLINE_S` / `TOKEN_CEILING` | the armed run budget — dispatch halts when any is hit; fails closed unless armed. |
| `DEV_FACTORY_TIER` | 0 attended · 1 gated (human sign-off at `in-review`) · 2+ unattended-to-`done`. Higher tiers are *earned + mechanically revocable*. |
| the gates | a worker cannot forge a signal, rewrite the lattice/ledger, or write the `verify.mjs` it must pass. |

A restart re-arms a fresh window — flip the env back to `mock` before restarting unless you intend another
real build.
