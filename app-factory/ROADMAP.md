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

## Next
- **Full dev-kernel authoring vendoring.** The actual derive/entail/calibration machinery (spec-author discipline, the spec-council + lens critics, `gate-ticket-ready`) behind the live loop's worker/deriver/validator/refuter agents — beyond the format/gate already built.

## Later
- Skills layer (cultivation · decompose · execute · distill).
- The shell's remaining **write actions** — drag a ticket, edit/commit a spec from the UI (each routed through a gated command server-side, like the Run loop action already shipped).
- An escalation path into the full typed lattice for very large projects (OD-00-C).
