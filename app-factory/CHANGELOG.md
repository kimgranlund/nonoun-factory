# Changelog

All notable changes to **app-factory** are documented here.

## [0.11.0] — 2026-06-25

Keystone integrity, hardened. A **confirmation pass** re-ran the same three critics on the *fixed* v0.10.0 code (the discipline: a fix isn't trusted on its author's own green eval) and found the closures were partial — the claims were still ahead of what was enforced. This makes them honest.

### Fixed
- **A teeth-only bar is no longer minted `validated` (C2, deeper — lifts the H2 cap).** The teeth floor catches `exit 0` but not `import thing; sys.exit(0)` (an ImportError against an empty build counts as "teeth", yet the bar asserts no behaviour). Minting `validated` on teeth-alone overclaimed. Now `app-commit.py` mints the rubric **`instantiated`** (structurally present + non-trivial, via a `teeth-cert` signal that says exactly that), and only an explicit **`--seal`** — the `entailment-critic`'s fidelity certification + the human seal (`seal_rubric`) — promotes it to `validated`. The loop's `dispatchable` requires a `validated` verifier, so it **refuses to auto-run a teeth-only ticket** until sealed. This finally enforces the keystone's documented human-seal instead of rubber-stamping it deterministically.
- **The deny-gate claim is narrowed to what it enforces (C1).** The gate is a `PreToolUse(Write|Edit)` matcher, so it binds the **executor** (`app-worker`, no Bash) — but it does NOT intercept Bash, so the independent Bash-carrying critics (`app-validator`/`app-refuter`/`app-distiller`) are constrained by role-separation + the validate path, not by this hook. `hooks.json`, the eval's `keystone-enforcement` dimension, and the docs now say so plainly (mechanical for the executor, trusted-by-role for the critics) rather than claiming the whole substrate is gated against every agent.
- **A vanished committed spec now cascades stale (C3).** `recompute_staleness` had silently skipped a spec whose file was missing; a deleted spec is maximally stale, so it now cascades its dependents via a sentinel hash.

### Added
- **`app-commit.py --seal`** / the two-gesture `/app-spec … commit` then `--seal` flow (documented), making the human seal a real gesture, not a flag the crystallizer grants itself.
- **The eval tests the deeper property:** `keystone-teeth-not-validated` (an import-only bar mints `instantiated`, not `validated`), `keystone-teeth-undispatchable` (the loop won't run it), `keystone-seal-validates` (the seal promotes it). **25/25 scenarios, score 1.00**, clean-checkout-replayed. The dev-server fixtures now `--seal` so they stay loop-ready.

### Known limitations (named, not hidden)
- The **QA plan (`qa.md`) is not a lattice cell**, so a spec edit doesn't auto-stale it — `/app-qa emit` re-derives it manually. Making QA a tracked cell is scheduled.
- **Transitive staleness** (a cell validated against a *capability* rather than the spec) is caught by the kernel's `check()` sweep when the intermediate rebuilds, not at spec-edit time; the cascade is single-hop by design. Latent until a project grows past the flat spec→ticket shape.
- Mechanical **Bash-write** protection of `.factory/` would require kernel changes (the vendored kernel is drift-checked against harness-forge), so the Bash-carrying critics remain trusted-by-role for now.

## [0.10.0] — 2026-06-25

Keystone integrity, verified on the BUILT code. A harness-council red-team of v0.9.0 found the keystone was **claimed but not wired** — passing selftests and 1.00 evals had masked it because they tested the gate's *logic* and used *stub bars*. This closes all three Criticals, and the eval now tests wiring, not logic.

### Fixed
- **The deny gate is now actually WIRED (C1 — reward-hacking Critical).** The red-team found `gate-protect` was bundled by nothing — `hooks.json` excluded it and `kernel/wire.py` never installed it (and would have guarded `.agents/harness`, not the live `.factory/state`) — so a worker had an unobstructed Write/Edit path to forge a pass signal, launder the ledger to manufacture an autonomy tier, and edit the bar it is graded against. It is now an **always-on `PreToolUse(Write|Edit)` deny** in the plugin `hooks.json`, in force in every session: a worker is mechanically deny-on-write to the whole `.factory/` verifier substrate, while `build/`, specs, and the writable bar source stay untouched.
- **A hollow bar is rejected, not rubber-stamped (C2 — verifier-integrity Critical).** Crystallization minted every rubric `validated` from an `entailment-cert` signal written *unconditionally* — a tautology `exit 0` bar sailed through, and the evals' own fixtures used stub bars. `app-commit.py` now applies a **calibration floor**: the sealed bar must FAIL against an empty build (it must test the implementation, not mere presence), or the commit is rejected. The cert signal is now HONEST that the full entailment-to-prose fidelity is the live `entailment-critic` + human seal, not a deterministic stamp.
- **The plain loop closes stale-but-trusted too (C3 — staleness Critical).** Regeneration fired only on a manual `/app-regenerate`; editing a committed spec and running `/app-loop` left the old validated tickets trusted. `app-loop.py` now **recomputes staleness first** (the kernel's `propagate_staleness` graph walk): an edited committed spec cascades its tickets `stale`, so they are neither trusted nor dispatchable — you no longer have to remember to regenerate to AVOID trusting stale work. `app-regen.py` now **removes the stale build artifact** (old code can't be re-validated and re-trusted against the new bar), and `app-distill.py` now **ages superseded patterns to `stale`** so app-context's freshness filter is live, not decorative.

### Added
- **The internal eval flow now tests WIRING, not logic, and rejects stub bars.** `evals/outer-loop.rubric.json` gains `keystone-enforcement` (the gate is wired in `hooks.json` + denies a forged `.factory` write via the hook protocol + allows a `build/` write), `verifier-calibration` (a tautology bar is rejected at commit), and `loop-staleness-recompute` (an edited spec cascades stale under the plain loop). Plus `regen-removes-build` and `distill-ages-superseded`. **22/22 scenarios, score 1.00**, green from a clean checkout. The selftests' tautology fixtures were replaced with real teeth-bearing bars.

## [0.9.0] — 2026-06-25

The outer loop — the factory stays correct over time and compounds.

### Added
- **`bin/app-regen.py` — regeneration.** Editing a committed spec cascades staleness (via the kernel's `propagate_staleness` graph walk) to every ticket validated against the old spec hash, invalidates their signals, ledgers the flip, and re-crystallizes so the frontier re-opens as `defined` against the new hash. Closes the harness-council's stale-but-trusted Critical: no validated work survives an outdated definition.
- **`bin/app-distill.py` — distillation.** Windows the ledger and compresses recurring precedent into `knowledge/patterns/` DRAFT docs (recurring failure → anti-pattern; recurring shape → pattern), each carrying its ledger provenance. Distills, never authors canon.
- **`bin/app-context.py` — context assembly.** Assembles a ticket's build context deterministically from named corpus sources (spec + knowledge + non-stale patterns); excludes stale patterns (freshness) and the sealed bar (predicate-honesty). The "better specs → cheaper build" mechanic, made mechanical.
- **Agents** `app-distiller` + `spec-regenerator` (propose, never author/merge); **commands** `/app-regenerate`, `/app-distill`, `/app-context`.
- **An internal eval flow** — `evals/outer-loop.rubric.json` (6 dimensions) + `evals/run-outerloop-evals.py` drives an integrated build → validate → distill → regenerate → assemble scenario. **14/14 scenarios, score 1.00.**

## [0.8.0] — 2026-06-25

The dev-server made foolproof — hardened against sloppy use, verified by an internal eval flow.

### Added
- **`bin/app-reset.py`** — re-arm a project to ready-to-validate (preserve the authored corpus; rebuild `.factory` + tickets). Powers the UI's ↻ Reset and an eval. Selftested.
- **Hardened `dev-server/serve.py`** — async, per-project-locked `POST /loop` that streams step progress over SSE (reload-safe; `409` on concurrent); `GET /run` state; `POST /reset`; `GET /file` (read-only, allowlisted, traversal-guarded); doc-aware change detection; friendly JSON errors (never a stack); `dispatchable`/`built`/blocked-reason in the detail contract.
- **Foolproof UI** (`dev-server/ui/`) — a connection pill (live/reconnecting/disconnected) + offline banner; loading/empty states; **honest framing** ("Validate frontier" vs. "build with AI → `/app-loop` in a Claude Code session"); a live progress strip + clean terminal banner; an inline why-disabled hint; a guarded ↻ Reset; a results viewer (read-only build/spec files); friendly blocked cards with the reason + the fix.
- **An internal eval flow** — `rubric/foolproof-ux.rubric.json` (8 dimensions) + `evals/run-evals.py` boots the server on fixtures and asserts 21 sloppy-user scenarios, scoring against the rubric. **21/21 scenarios, score 1.00.**

### Fixed
- The validate loop now dispatches only **built** tickets (unbuilt ones need AI building) and records a fail for a missing build, so it can no longer silently spin to its cap. `serve.py` reads the kernel's `block` object via `is_blocked`/`block_reason` (it had checked a non-existent `blocked` flag, so blocks were invisible).

## [0.7.0] — 2026-06-23

M2: the keystone is **enforced**, not declared — a deny-on-write gate.

### Added
- **`bin/gate-protect.py`** — a blocking `PreToolUse(Write|Edit)` hook (modeled on harness-forge's `gate-signal`). An agent is mechanically **deny-on-write to the entire `.factory/` verifier substrate** — signals, ledger, lattice, run budget, sealed bars, and manifests — plus the wiring (`.claude/settings.json`). A worker cannot forge a pass signal, launder the ledger, fake a cell's maturity, lift the budget ceiling, or edit the bar it is graded against. `build/`, specs, and the bar source stay writable. Wired in the plugin `hooks.json` (always-on), so app-factory needs no per-project `wire.py`.
- **Bars are sealed by copy.** The acceptance-deriver authors a bar SOURCE in the writable `spec/bars/`; `/app-spec commit` copies it into the protected `.factory/acceptance/` (a kernel-path write), so the committed bar of record is the sealed copy — and `.factory/**` can be fully protected without breaking the authoring flow.
- Proven: the gate denies forging a signal / laundering the ledger / editing the bar / lifting the budget (exit 2) and allows the worker's build + the bar source (exit 0); the full lifecycle (commit → seal → loop → validated) still composes end-to-end.

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
