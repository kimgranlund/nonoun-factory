# dev-factory — Build Plan & Live State

_Last reviewed: 2026-06-19._

**Status:** **delivered through Run + a full app-build campaign.** The system ships as `dev-kernel` (0.2.16), `dev-kit-corpus` (0.3.0), `dev-kit-app` (0.5.1), and the `dev-server` runtime. Since the original Run milestone, dev-factory was stress-tested by building **four real apps** (shader-live, design-tokens-lab, icon-forge, wireframe-studio) end-to-end, which matured it from *"builds modules"* to *"builds, assembles, and rigorously validates whole apps"*: the integration **shell** is factory-authored at the product root (single-file authoring); the **render-coherence gate** (`dev-kit-app/bin/render-check.mjs`) validates WebGL *and* DOM apps actually render; and the **presence-predicate-verifier weakness is closed** — the rubric-architect authors a cell's *real, spec-derived* `verify.mjs` (gate-permitted), now the **default** on every real build (`dispatch_unit`), so "validated" means "implements the spec." A live capstone proved the closed loop unattended (the factory authored a verifier *and* the module that passes it). **Source of truth for what's delivered:** the per-component CHANGELOGs + `dev-server/evals/` + `dev-server/RUNBOOK.md`. **How to use it:** `docs/USAGE.md`. **What the campaign taught:** `docs/2026-06-18-app-build-campaign-learnings.md`. **Companion design:** `docs/spec/dev-factory-spec/`. This document is the build sequence + load-bearing decisions + remaining frontier — kept as the forward view, not a restatement of the spec.

> **Naming note.** The components on disk are `dev-kernel · dev-kit-corpus · dev-kit-app · dev-server`; the marketplace/repo is `nonoun-factory`. (Earlier drafts called the kernel/kits/server `nonoun-*` — that rename is complete.)

---

## 1 · Built ON harness-forge (the decision that shaped everything) — DONE

The lattice machine was **not** built from scratch: `dev-kernel` **vendors** harness-forge's lattice kernel (`lattice.py` + `validate.py` + `cell.schema.json`), byte-identical, drift-gated by `tools/sync-dev-kernel.py --check`. Re-deriving the maturity machine / engine / compass / gates would have been the grid-filling anti-pattern applied to our own foundation. What dev-kernel *added* on top:

| harness-forge shipped (reused) | dev-kernel added |
|---|---|
| Lattice + 8-state maturity machine + staleness-as-graph (`lattice.py`) | the `ticket`/`activity`/`dispatch-policy`/`kit`/`adapter` schemas (11 schemas total) |
| The engine + validation path (`validate.py`, signal from a verifier's exit status) | the ticket lifecycle machine + `gate-ticket-ready` + `gate-dispatch` |
| The immutable/rewritable boundary (`gate-signal`, `wire.py`) | `.factory`-anchored protected globs; the `DispatchAdapter` (OD-003) to a headless runtime |
| The budget bound (`run-budget.py` + `gate-budget`) | the autonomy trust-ladder (0→3) with **mechanical, ledger-measured demotion** |
| The structural-critic council pattern | the kernel/kit/instance/server tiering + the `kit-conform` gate (zero-kernel-edits boundary) |
| Typed naming (`naming.py`) | the 19-agent roster + 8 compound skills; `factory-query` read-only MCP |

---

## 2 · Layout (current)

- **`dev-kernel/`** — the plugin: the new schemas, the ticket lifecycle + `gate-ticket-ready`/`gate-dispatch`, the `DispatchAdapter` contract, the roster + 8 compound skills, the `factory-query` MCP. Vendors harness-forge's lattice kernel (sync-gated). Passes plugins-factory's gate suite. `stateNamespace = .factory` (optional/per-instance — the instance dir is set via `--dir`/`DEV_FACTORY_DIR`, not a fixed `.agents/` namespace).
- **`dev-kit-corpus/`, `dev-kit-app/`** — kit plugins: family ontology, rubric manifests, harness adapters, seed patterns. `dev-kit-app` (the app family) proves the kernel/kit boundary — adding it required **zero kernel edits** — and declares `authoring.output_root: ".."` so capability code lands in the clean product tree.
- **`dev-server/`** — **not a plugin** — a Python app (FastAPI · APScheduler heartbeat · single-writer SQLite store · SSE · web UI). `api.py · heartbeat.py · dispatch.py · store.py · ui/ · evals/ · RUNBOOK.md`.
- **Instance** — a project at **`src/<project>/`**: the clean, runnable **product** tree (capability code at `src/<project>/<capability>/`, beside its `verify.mjs`), with all factory **state** under **`src/<project>/.factory/`** (`lattice.json · coordination/ · spec/ rubric/ ontology/ policy/ … · signals/ · ledger/` + `index.db`, derived). (Relocated from `.agents/dev-factory/` in dev-kernel 0.2.11 / dev-kit-app 0.3.1.)
- **Marketplace** — the dedicated **`nonoun-factory`** marketplace carries the kernel + kits. The server ships separately.

---

## 3 · Build sequence — DELIVERED through Run (Fly partial)

The substrate-engineering arc (each phase earned the next) is built:

- **Crawl — Instrumentation. ✅ DONE.** The ticket lifecycle machine + `gate-ticket-ready`/`gate-dispatch` + the server skeleton + the `cell-advancer`/`cell-validator` split. The falsifiable milestone (one cell driven `absent → validated` by hand through the API, the typed `done ⟺ cell-advances` morphism via one `gate-signal`) is proven in `dev-server/evals/tracer-bullet/`, and the **reverse** direction in `evals/reverse-morphism/` — the biconditional holds both ways.
- **Walk — Delegation. ✅ DONE.** The heartbeat at Tier 1, the Kanban + lattice-grid UI + SSE, budgets + no-progress, and the `DispatchAdapter` headless binding (OD-003) — proven across `evals/{walk-milestone,crawl-milestone,server-smoke,integration-milestone}`. (Real token/cost attribution fixed once the loop ran live.)
- **Run — Regeneration. ✅ DONE.** `pattern-distiller` + `spec-regenerator`; the outer loop proposes upstream spec/rubric revisions through a deliberate transition; operating evidence distills into the pattern layer; the independent refuter measures false-pass and the autonomy ladder demotes mechanically — `evals/{run-milestone,demotion,self-heal}` + the `debug-coldstart` brief→build→ship arc.
- **Fly — Dark Factory. 🟡 PARTIAL.** Self-heal on a caught false pass is live; `dev-kit-app` ships as the second family (the boundary's falsification test passes); the `debug/` ralph harness builds a shippable app end-to-end. **Not yet:** Tier-3 lights-out at *fleet* scope, and the "improves its own definitional knowledge across a window" watched metric (see §5).

---

## 4 · Decisions (resolved)

- **D-A · harness-forge reuse — RESOLVED.** dev-kernel vendors harness-forge's `lattice.py`/`validate.py`/`cell.schema.json` via `tools/sync-dev-kernel.py` (drift-gated), not a cross-plugin import. Re-implementation rejected as grid-filling.
- **D-B · marketplace home — RESOLVED.** The dedicated `nonoun-factory` marketplace carries the kernel + kits.
- **OD-003 · DispatchAdapter binding — RESOLVED.** The headless Claude Code (`claude -p`) binding is live in `dev-server/dispatch.py` (streaming tool events into the ledger, gates wired inside the worktree).
- **OD-005 · fleet scope — instance-scope shipped.** One server per instance on SQLite (`.factory/index.db`). Postgres/fleet is the deferred horizon (§5).
- **OD-001 · files-of-record + single-writer — decided** (the store is a rebuildable projection of the ledger).
- **OD-002 · cold-start risk** — kit priors + triage at cold-start; the compass goes empirical once the ledger has signal metrics. Done.

---

## 5 · Remaining (the live Fly/fleet frontier)

The genuine not-yet-done work:

- **Tier-3 lights-out at fleet scope.** Instance-scope autonomy is earned; scaling to a *fleet* (many instances, one operator on-the-loop) with a hermetic sandbox + tamper-evident audit trail for fully-unattended operation is the open Fly horizon.
- **OD-005 horizon · Postgres / fleet store.** The SQLite single-writer store is right at instance scope; the multi-instance/fleet store (Postgres) is unbuilt — don't build it before the boundary needs it.
- **OD-004 · cross-cell re-validation ordering.** When a regenerated upstream cell stales a cone of dependents, the order in which they re-validate is a Run/Fly concern not yet pinned.
- **OD-006 · regenerator merge granularity.** How coarse/fine an upstream-revision PR should be (per-cell vs per-cone) when the outer loop proposes spec/rubric changes.
- **Self-improvement as a watched metric.** The Fly milestone — the factory *measurably* improves its own definitional knowledge across a window, with substrate-accretion (not just output) as the tracked metric and reward-hack incidents held at zero — is demonstrated in evals but not yet instrumented as a standing, watched signal.

---

## 6 · Design risks (how each was handled) — kept as rationale

1. **The server as a new class of artifact.** Built as its own component (`dev-server/`) with its own tests (`evals/`) + RUNBOOK, outside the plugin-primitive model — as planned.
2. **The DispatchAdapter to a headless runtime.** Pinned against current Claude Code headless docs at build time (not guessed); the live binding is in `dispatch.py`.
3. **Grid-filling the meta-system.** Avoided — Crawl shipped one cell by hand (no UI) before the Kanban/kits/dashboards; the rest was earned.
4. **Unattended safety mechanical, not aspirational.** The `.factory/`-anchored immutable boundary, the trust ladder, and ledger-measured demotion are gated code (`_gates.py`, `autonomy.py`), proven by `evals/{demotion,self-heal}` — not prose.
