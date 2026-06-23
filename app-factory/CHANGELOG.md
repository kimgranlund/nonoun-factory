# Changelog

All notable changes to **app-factory** are documented here.

## [0.6.0] — 2026-06-23

The dev-server gets a live layer — watch the loop run in the browser.

### Added
- **Server-Sent Events** (`GET /api/stream?project=<name>`) — the shell subscribes and re-renders the instant the project's lattice/ledger mtime advances, so the kanban moves tickets to `validated` live with no reload.
- **A server-mediated loop action** (`POST /api/project/<name>/loop`) + a **▶ Run loop** button. The action does not mutate state itself — it invokes the **gated** controller (`app-loop.py run`), server-mediated and ledgered, exactly as dev-factory routes a drag through a transition endpoint. The UI triggers the factory through its gates; it never bypasses them.
- Verified live on quicklog: both tickets `defined` → hit Run loop → SSE pushes the change → both `validated` in the browser.

## [0.5.0] — 2026-06-22

The deferred web UI lands — a zero-dependency productivity shell.

### Added
- **`dev-server/`** — a buildless productivity shell on stdlib `http.server` (no FastAPI; app-factory stays self-contained). `serve.py` exposes a read-only JSON API (`/api/projects`, `/api/project/<name>`) over a projects root, reusing the vendored kernel for the lattice histogram and `ledger.py trust`; `ui/` is vanilla HTML/JS/CSS — a **project drawer** + a per-project view that foregrounds **Specs & Inputs** (the cultivation focus), then the tickets kanban, the ledger feed, and the trust tier. The port auto-advances if taken; the shell is a projection over git-tracked state and **never writes**.
- **`/app-serve`** command to start it.
- Verified live over the `quicklog` corpus: the drawer lists projects with stage + progress + tier, and the detail view renders the committed spec, both validated tickets, the crystallize/validate ledger, and the honest Tier-0 trust reason — all read live from the corpus.

## [0.4.0] — 2026-06-22

The loop closes itself — `/app-loop` runs the frontier autonomously under caps.

### Added
- **`app-loop.py` — the bounded loop controller.** The deterministic half of `/app-loop`: `arm` (fail-closed budget + a trust-tier refusal for unearned unattended runs), `next` (the top ready **dispatchable** ticket — a capability cell with a validated sealed-bar verifier, so seed/non-ticket cells are ignored), `advance` (headless: run the sealed bar via `validate.py`), `check` (no-progress block + budget status), `stop` (report), and a `run` driver. Like harness-builder, control flow is code; the model dispatches `app-worker`/`app-validator` between the decisions.
- Proven autonomous on `quicklog`: after `commit spec/cli.md`, `app-loop.py run --max-cells 5` armed the budget, drove **both** tickets to validated (independent signals), and stopped frontier-empty — 2 validated, 0 blocked, 0 pending, no human in the iteration. The full **idea → spec → kanban → execution** lifecycle now runs end-to-end, autonomously and bounded.
- `/app-loop` now routes its decisions through `app-loop.py` (arm → next → dispatch → validate → check → stop).

## [0.3.0] — 2026-06-22

`/app-spec commit` becomes runnable — the prose↔typed boundary, crystallized.

### Added
- **`app-spec-gate.py`** — the mechanical half of spec-quality: a spec commits only if it is well-formed (an embedded `json` contract, ≥1 **checkable** acceptance criterion, declared non-goals, a decomposition whose tickets fully **cover** the criteria). The adversarial half remains the spec-council.
- **`app-commit.py` — the crystallizer.** Given a sealed spec, it runs the gate, mints the spec cell to `validated` **through the real signal path** (`validate.py` with the gate as verifier — the spec's own doneness is a signal, not an assertion), decomposes into draft ticket files + ready `capability` cells (each with a per-ticket `rubric` cell minted `validated` by a certification signal standing for the entailment-critic + human seal), and stamps each spec→ticket edge with the spec's content hash. Refuses any ticket whose sealed acceptance is absent; rejects a gate-failing spec (the doc stays `cultivated`).
- Proven end-to-end on `quicklog`: `commit spec/cli.md` → `spec.task.cli` validated + 2 sealed tickets → the frontier surfaces them → worker builds `build/storage.py` → the independent validator passes the sealed bar → `capability.task.storage` validated, **goal MET**, with `t2-search` still ready & unbuilt. commit → ticket → execute → validate, closed.
- `/app-spec` now cites the runnable backbone (`app-commit.py`).

## [0.2.0] — 2026-06-22

The trust ladder gets a first rung, and the kernel layout is corrected.

### Added
- **The refuter — the trust SENSOR** (`bin/app-refute.py` + `agents/app-refuter.md`). The harness-council found a trust gauge with no sensor: `false_pass_rate` is UNMEASURED until an independent `refute` event exists. The refuter is an independent oracle (a family disjoint from worker/validator/deriver) that audits a passed ticket and records `corroborate` (the pass held under a mutation probe) or `refute` (the bar was hollow) in the exact shape the kernel reads.
- **`tier-gate.py` — the autonomy ACTUATOR.** A dispatch-time consumer that refuses autonomy above the earned tier (exit 0 iff earned ≥ requested). `/app-loop` and `/app-goal` consult it before running unattended.
- Proven end-to-end on `quicklog`: Tier 0 (unmeasured → gate DENY) → 5 corroborated passes climb to Tier 2 (gate ALLOW) → one refuted false pass auto-demotes to Tier 1 (gate DENY). Sensor + gauge + actuator + dashboard.

### Fixed
- **INT-1** — the vendored kernel resolves a project root as the grandparent of its `--dir`. Kernel state is now nested at `.factory/state/` (two levels under the project root), so the root resolves correctly and `validated_against` staleness hashing is sound. `app-new.py`'s selftest asserts `grandparent(state) == project root`.

## [0.1.0] — 2026-06-22

The first walking skeleton: app-factory stands up as an installable plugin with a runnable, self-testing spine.

Cultivate a project as a corpus of prose documents — idea → PRD → SPEC → tickets → QA — and compile it into software with a bounded `/app-goal` + `/app-loop`. A prose-cultivation front door over a vendored, self-testing verification spine: a coding agent never grades its own work and never authors the bar it is graded against (acceptance is independently derived, entailment-checked, and human-sealed).

### Added
- **Vendored kernel spine** (`kernel/`) from harness-forge — bounded loop (`goal.py`), lattice, ledger, signal minting (`validate.py`), frontier ranking, the code-enforced budget stop-gate. All selftests green from the vendored location.
- **`/app-new` corpus scaffolder** (`bin/app-new.py`) — lays a project corpus + the hidden `.factory/` spine (lattice via the proven `lattice.py init`) + the deny-on-write protected perimeter. Selftested.
- **`/app-status` dashboard** (`bin/app-status.py`) — a no-agent operator view over a scaffolded corpus.
- **The `app-{verb}` command surface** — `app-new`, `app-goal`, `app-loop`, `app-spec`, `app-qa`, `app-status`.
- **Keystone agent roster** — `acceptance-deriver` (non-executor), `entailment-critic` (fidelity gate), `app-worker`, `app-validator` (independent signal).
- **Vendored gates** — `spec-quality` / `prd-quality` rubrics from dev-kit-corpus.
- **Read-only corpus-query MCP** + an advisory save hook.
- **The spec set** (`specs/`) — charter, lifecycle, document-model, loop-and-goal, knowledge-corpus, packaging — hardened against a two-council red-team (spec-council + harness-council).

### Known integration backlog
- INT-1: the vendored kernel resolves a project root as the grandparent of its state dir (`<root>/.agents/harness`); app-factory's `.factory/` is one level shallower, so `validated_against` staleness hashing needs a root-resolution shim. Pass/fail verdicts are unaffected.
- Full dev-kernel authoring vendoring (spec-author, spec-council, refuter, calibration) is referenced and partially vendored (rubrics); remaining pieces are the next increment.
- The web UI (productivity shell + project drawer) is deferred to a later session.
