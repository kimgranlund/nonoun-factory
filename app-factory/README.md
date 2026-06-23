# app-factory

Cultivate a project as a corpus of prose documents — idea → PRD → SPEC → tickets → QA — and compile it into software with a bounded `/app-goal` + `/app-loop`. app-factory is a prose-cultivation front door over a vendored, self-testing verification spine: a coding agent never grades its own work (the signal is minted from a real verifier command's exit status, not the worker's opinion) and never authors the bar it is graded against (a ticket's checkable acceptance is independently derived from the spec prose, entailment-checked for fidelity, and human-sealed). The simplicity is in the operator surface (prose + ~6 `app-{verb}` commands); the rigor is undiminished — vendored from harness-forge (the bounded loop, ledger, signal minting, frontier ranking, the code-enforced budget stop-gate) and dev-kernel (the spec-authoring discipline, the spec council, the gates, the refuter, calibration). Ships the `app-{verb}` command surface, a keystone agent roster (acceptance-deriver · entailment-critic · app-worker · app-validator · app-refuter), an independent trust sensor — the refuter records corroborate/refute events feeding a dispatch-time tier gate, so autonomy above attended must be earned — a working `/app-new` corpus scaffolder, a `/app-status` operator dashboard, and a read-only corpus-query MCP over a project's `.factory/` state. Self-contained.

## The thesis

The spec is the program. The human's highest-leverage activity is **improving the specs and inputs** — better specs + a richer knowledge corpus make it cheaper and more reliable for the agent to build. The loop is cheap; the corpus is the asset.

> **Simplicity lives in the human's authoring surface. Rigor stays in the verification spine.**

## The lifecycle (Idea → QA)

| Stage | Artifact | Gate |
|-------|----------|------|
| Idea | `idea.md` | — |
| Research *(opt)* | `research/*.md` | advisory |
| Prototype *(opt)* | spike + assets | advisory |
| PRD | `prd.md` | prd-quality |
| SPEC | `spec/*.md` | spec-quality + council |
| Kanban | `tickets/*.md` | ticket-ready |
| Execution | code + signals | per-ticket critic signal |
| QA | `qa.md` | the honest-signal keystone |

## The two-part keystone

1. **Signal-honesty** — the worker can't forge its own pass; the signal is minted by an independent verifier from its exit status (`validate.py`).
2. **Predicate-honesty** — the worker can't author the bar it's graded against; acceptance is derived by a non-executor, entailment-checked, and human-sealed.

Only with both can the loop neither lie about whether it passed nor arrange what passing means.

## Commands

`/app-new` · `/app-goal` · `/app-loop` · `/app-spec` · `/app-qa` · `/app-status`

## Layout

- `kernel/` — the vendored harness-forge spine (drift-checked).
- `bin/` — app-factory's own scripts (`app-new`, `app-status`, `app-spec-gate`, `app-commit`, `app-loop`, `app-refute`, `tier-gate`).
- `commands/` · `agents/` — the lifecycle surface.
- `dev-server/` — a zero-dependency productivity shell (project drawer) over a project corpus.
- `rubric/` — vendored spec-quality / prd-quality gates.
- `specs/` — the spec set that defines app-factory itself.

Designed in, and validated by, the `nonoun-factory` marketplace. The full design and its two-council red-team live under `specs/`.
