# app-factory — spec set

The walking-skeleton spec set for **app-factory**, the document-cultivation software
factory built on `/app-goal` + `/app-loop`. Authored 2026-06-22.

**Status: phase-C hardened.** The thin slice traced one end-to-end path (idea→QA),
was red-teamed by two councils (phase D, verdict BLOCKED on the acceptance seam), and
this set has since cleared every must-fix. It is now a *sound thin skeleton* — still
thin (deep per-component specs and the UI remain to come), but no longer structurally
broken at the seam.

| Doc | Covers |
|-----|--------|
| [00-charter](00-charter.md) | The inversion (simple **operator surface** / undiminished rigor), the two-part keystone, thesis, walking skeleton |
| [01-lifecycle](01-lifecycle.md) | Stages idea→QA, gates, doc↔cell maturity join, validated-not-committed binding, regenerate cascade |
| [02-document-model](02-document-model.md) | Artifact types, the prose↔typed boundary + crystallization on its failure branches, the derive→entail→seal pipeline, protected perimeter |
| [03-loop-and-goal](03-loop-and-goal.md) | The two verbs, stop conditions, the two-half keystone, trust sensor+gauge+actuator |
| [04-knowledge-corpus](04-knowledge-corpus.md) | Deterministic context assembly, freshness discipline, the compounding corpus |
| [05-packaging](05-packaging.md) | `app-{verb}` commands, the **split** vendor table (harness-forge + dev-kernel), marketplace placement |
| [phase-d-redteam](phase-d-redteam.md) | The two-council red-team: verdict, convergent wound, the phase-C must-fix backlog |

Deferred to a later session: the web UI (productivity shell + project drawer).

## Phases

- **A** lock charter + branching decisions — ✅ (reuse spine / core-first / breadth-first)
- **B** walking-skeleton spec across the lifecycle — ✅
- **D** red-team with two councils (run early) — ✅ BLOCKED → must-fixes identified
- **C** harden the set against the red-team — ✅ this pass (all must-fixes cleared)
- **next** deepen each component spec (route through `plan-spec` / `spec-author`),
  then optionally re-run the councils to confirm the seam is closed

## Decisions resolved this session

- Kernel: **reuse spine, hide lattice** · session scope: **breadth-first thin slice**
- Rigor model (OD-00-A): **same rigor, thinner operator surface** — rigor vendored
  from `harness-forge` *and* `dev-kernel`, always on
- Acceptance origin (OD-02-B): **independent deriver + entailment gate + human seals**
- Naming (OD-00-B / OD-05-A): **`app-{verb}`** for the whole command surface
- Decompose-on-commit (OD-02-A): commit proposes **draft** tickets; triage makes them active
- PRD ordering (OD-01-B): **required by default, waivable by explicit declaration**
- Acceptance binds to **`validated`**, not `committed` (OD-01-A regenerate cascade)

## Open decisions carried forward

- **OD-00-C** — does the hidden spine expose an escalation path into the full typed
  lattice for very large projects (a capacity question; rigor is settled).
- **OD-02-D / OD-05-C** — dedicated `acceptance-deriver` agent vs. constrained reuse
  of `spec-author`/`ticket-triager`.
- **OD-03-A / OD-01-C** — concrete default caps (iterations, tickets, wall-clock,
  regenerate-count).
- **OD-03-C** — no-progress failure-support UX (actionable prompt vs. halt-and-report).
- **OD-04-A/B** — cross-project knowledge layer; distill on cadence vs. explicit.
- **OD-05-B** — vendor both kernels wholesale vs. slim a forked `kernel/`.

## Recommended next red-team

The harness-council flagged the *usability* of the derive→seal model (a human sealing
machine-derived acceptance) as outside the structural lens, and recommended the
`agent-ops:agentic-council` (accountable-but-not-in-control; trust calibration) before
the model is built. Worth running before phase-C deepening.
