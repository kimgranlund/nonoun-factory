# app-factory — ROADMAP

## 0.1.0 (done) — the walking skeleton stands up
Installable plugin; vendored spine selftests green; `/app-new` scaffolds a corpus; the mechanical keystone loop (verify → signal → settle → `goal met`) proven on `quicklog`, including a hollow attempt rejected.

## 0.2.0 (done) — the trust ladder gets a first rung
- **INT-1 — fixed.** Kernel state nested at `.factory/state/` so the kernel root resolves to the project root; selftest asserts it.
- **Refuter wired (the trust sensor) — done.** `bin/app-refute.py` (corroborate/refute → ledger), `bin/tier-gate.py` (dispatch-time actuator), `agents/app-refuter.md` (independent oracle). Auto-demotion is the rate rising on the next read. Proven on quicklog (Tier 0 → 2 → demote).

## 0.3.0 (done) — `/app-spec commit` is runnable
- **Mechanical spec gate** (`bin/app-spec-gate.py`) + **the crystallizer** (`bin/app-commit.py`): gate → mint the spec cell via the real signal path → decompose into draft tickets + ready `capability`/`rubric` cells + stamped spec→ticket edges. Proven on quicklog: commit → ticket → execute → validate, `goal MET`. The derive/entail/seal *agents* produce the sealed acceptance the crystallizer consumes; the crystallizer refuses any ticket whose bar is absent.

## 0.4.0 (done) — the loop runs itself
- **`bin/app-loop.py`** — the bounded controller (arm fail-closed + trust-tier refusal · `next` dispatchable ticket · advance · no-progress block + budget check · stop+report), with a headless `run` driver; control flow in code, agent dispatch by the model. Proven on quicklog: `commit spec/cli.md` then `app-loop run --max-cells 5` drove **both** tickets to validated autonomously and halted frontier-empty. The full **idea → spec → kanban → execution** lifecycle now runs end-to-end and bounded.

## 0.5.0 (done) — the productivity shell
- **`dev-server/`** — a zero-dependency stdlib shell: `serve.py` (read-only JSON API over a projects root, reusing the kernel for the lattice histogram + `ledger.py trust`) + a buildless vanilla `ui/` (project drawer · Specs&Inputs-first per-project view · tickets kanban · ledger feed · trust tier). `/app-serve` starts it. Read-only projection over git-tracked state; never writes. Run live over the quicklog corpus.

## 0.6.0 (done) — the live layer
- SSE (`GET /api/stream`) auto-refresh + a server-mediated **▶ Run loop** action (`POST …/loop` → the gated `app-loop.py run`, ledgered, never a bypass). The kanban moves tickets to `validated` live as the loop runs. Proven on quicklog (defined → Run loop → validated, no reload).

## 0.7.0 (done) — the keystone ENFORCED (M2, part 1)
- **`bin/gate-protect.py`** — a blocking `PreToolUse(Write|Edit)` hook: every agent is deny-on-write to the `.factory/` verifier substrate (signals · ledger · lattice · budget · sealed bars · wiring). A worker can't forge a pass, launder the ledger, fake maturity, lift the budget, or edit its bar. Bars sealed by copy (writable `spec/bars/` → protected `.factory/acceptance/`). Wired in the plugin `hooks.json` (no per-project `wire.py`). Proven: the four reward-hacking moves are denied (exit 2), legitimate writes allowed.

## 0.8.0 (done) — the dev-server made foolproof
- Hardened `serve.py` (async locked validate runs streaming progress over SSE; `/run`, `/reset`, read-only `/file`; doc-aware refresh; friendly errors) + a foolproof UI (connection pill, honest "Validate frontier" vs. AI-build framing, live progress + terminal banner, guarded Reset, results viewer, blocked cards) + `bin/app-reset.py`. Verified by an internal eval flow: `dev-server/rubric/foolproof-ux.rubric.json` + `dev-server/evals/run-evals.py` — 21 sloppy-user scenarios, score 1.00.

## 0.9.0 (done) — the outer loop (correctness + compounding)
- **Regeneration** (`bin/app-regen.py`): a spec edit cascades staleness to its validated tickets, invalidates their signals, and re-opens them against the new hash — the stale-but-trusted Critical, closed. **Distillation** (`bin/app-distill.py`): ledger windows → pattern drafts with provenance. **Context assembly** (`bin/app-context.py`): deterministic build context from spec + knowledge + non-stale patterns (excludes stale + the sealed bar). Agents `app-distiller` + `spec-regenerator`; commands `/app-regenerate` · `/app-distill` · `/app-context`. Eval flow `evals/outer-loop.rubric.json` + `evals/run-outerloop-evals.py` — 14/14, score 1.00.

## 0.10.0 (done) — keystone integrity, verified on the BUILT code
- **Re-ran the harness-council on the built v0.9.0** (the reward-hacking · verifier-integrity · staleness critics, on the code, not the specs). It found the keystone was **claimed but not wired** — three Criticals — which v0.9.0's passing selftests/evals had masked. All three are now closed:
- **C1 — the deny gate is wired.** `gate-protect` is an always-on `PreToolUse(Write|Edit)` deny in `hooks.json`; a worker is mechanically deny-on-write to the whole `.factory/` substrate (it had been bundled by nothing).
- **C2 — a hollow bar is rejected.** `app-commit.py` has a calibration floor: a sealed bar must FAIL against an empty build or the commit is rejected (no more `exit 0` rubber-stamp); the cert is honest that full entailment is the live critic's job.
- **C3 — the plain loop closes stale-but-trusted.** `app-loop.py` recomputes staleness first (edited spec → tickets cascade `stale`, un-dispatchable); `app-regen.py` removes the stale build artifact; `app-distill.py` ages superseded patterns to `stale`.
- The eval now tests WIRING (gate wired + denies), CALIBRATION (tautology bar rejected), and the loop's staleness recompute — `evals/run-outerloop-evals.py` **22/22, 1.00**.

## 0.11.0 (done) — keystone integrity, hardened (the confirmation pass)
- **Re-ran the same three critics on the FIXED v0.10.0** (the discipline: don't trust a fix on its author's own green eval). They found the closures were partial. Hardened:
- **C2 deeper** — teeth catches `exit 0` but not `import thing; exit 0`. The rubric now mints **`instantiated`** (teeth-checked, non-trivial), and only an explicit **`--seal`** (entailment-critic + human) promotes it to `validated`; the loop refuses a teeth-only verifier. This enforces the documented human-seal instead of rubber-stamping it.
- **C1 honesty** — the `Write|Edit` gate binds the executor (`app-worker`, no Bash); the Bash-carrying critics are trusted-by-role, not gated. The claim is narrowed to match (hooks.json, eval, docs).
- **C3** — a vanished committed spec now cascades stale.
- Eval hardened: `keystone-teeth-not-validated` · `keystone-teeth-undispatchable` · `keystone-seal-validates` → **25/25, 1.00**.
- **Named, not hidden:** the QA plan isn't yet a lattice cell (manual re-emit); transitive staleness is caught at rebuild by `check()`, not at edit time; mechanical Bash-write protection awaits a kernel change (the kernel is drift-checked against harness-forge).

## Next (M2 remainder)
- **Calibrate the verifiers further** — vendor/adapt dev-kernel's `evals/calibration` so the entailment-critic's fidelity check and the rubrics are calibrated (the bar-teeth floor + the human seal are the deterministic/judgement halves; agreement-calibration is the rest).
- **Make the QA plan a tracked cell** so a spec edit cascades staleness to it (closes the named limitation).
- **Vendor the full dev-kernel authoring rigor** (spec-author discipline, the spec-council lens critics, `gate-ticket-ready`) behind the live deriver/critic/refuter agents.

## Later
- Skills layer (cultivation · decompose · execute · distill).
- The shell's remaining **write actions** — drag a ticket, edit/commit a spec from the UI (each routed through a gated command server-side, like the Run loop action already shipped).
- An escalation path into the full typed lattice for very large projects (OD-00-C).
