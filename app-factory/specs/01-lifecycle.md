---
name: app-factory-lifecycle
stage: lifecycle
status: phase-C hardened (post red-team) — walking-skeleton thin slice
depends_on: 00-charter
---

# Lifecycle — idea → QA

**Intent.** Define the stages a project moves through, the artifact each produces,
which are optional, and the gate that lets one stage hand off to the next — the
Matt Pocock lifecycle made concrete and bound to `/app-goal` + `/app-loop`.

## Stages

```
Idea ──▶ Research? ──▶ Prototype? ──▶ PRD* ──▶ SPEC ──▶ Kanban ──▶ Execution ──▶ QA
 │          (opt)        (opt)         (*skippable by explicit waiver)             │
 └────────────────────────  the corpus accumulates  ───────────────────────────┘
```

| Stage | Artifact | Optional | Hand-off gate | /app-goal·/app-loop |
|-------|----------|:--------:|---------------|---------------------|
| Idea | `idea.md` | no | human "ready" | capture |
| Research | `research/*.md` | yes | advisory (no gate) | `/app-loop` fan-out caches explorations |
| Prototype | spike code + reusable assets | yes | advisory | `/app-loop` spike, assets handed forward |
| PRD | `prd.md` | **waivable** | **prd-quality** | `/app-goal "PRD"` destination |
| SPEC | `spec/*.md` (depends_on PRD if present) | no | **spec-quality + spec-council** | `/app-goal "SPEC"` destination |
| Kanban | tickets w/ blocking edges | no | **ticket-ready** | committed SPEC decomposes here |
| Execution | code + signals | no | **per-ticket critic signal** | `/app-loop` core |
| QA | `qa.md` + acceptance replay | no | **honest-signal keystone** | `/app-goal met` |

**PRD ordering (resolved, OD-01-B).** PRD is **required by default** (matching the
Pocock flow) but may be **waived by an explicit declaration at project init** — for
a refactor or a small technical tool where outside-in user stories add little.
Waiver is recorded, not implicit. When a PRD exists, the SPEC `depends_on` it; the
partial order is never "spec atop air."

## Two maturities, with an explicit join

- **Document maturity** (what the human sees): `draft → cultivated → committed`.
  - `draft` — freely editable prose, nothing gated.
  - `cultivated` — human considers it ready; the quality gate may run advisorily.
  - `committed` — the crystallization gesture (`02`). **Commit mints a `validated`
    spine cell** (not merely a doc flag) and records the join in app-factory's own
    shipped ledger as an ontology event. A committed PRD/SPEC is now a `/app-goal`
    destination and decomposes into tickets.
- **Cell maturity** (hidden, the spine): the `harness-forge`
  `absent→defined→instantiated→validated→operating` machine still runs underneath;
  the human never names it. It is how the spine knows a ticket is honestly done.

**Acceptance binds to `validated`, never to `committed`** *(red-team fix, H1).* A
ticket's acceptance binds to a *validated* spec criterion. Crystallization mints the
spec cell to `validated` and stamps the spec→ticket edge with the spec's content
hash (the ticket's `validated_against`), so the dependency the spine trusts is real.

## Stage transitions

- A stage may **hand off** only when its gate is green — a verifier result
  (`validate.py`), not the loop's opinion.
- Optional stages (Research, Prototype) are **advisory**: they enrich the corpus,
  produce no hand-off gate; skipping them is first-class.
- **Regenerate (the outer loop), with staleness cascade** *(red-team fix, H7).* QA
  failure or execution evidence may flip a committed SPEC back to `cultivated` with
  a ledgered reason. Because the spec→ticket edges carry the content hash, the flip
  **cascades `stale` to every decomposed ticket and invalidates its signals** —
  no stale-but-trusted chain survives a regeneration. In-flight work on a staled
  ticket halts. (Resolves OD-01-A.) The regenerate loop is itself budget-capped
  (`05`) so spec↔cultivated oscillation can't churn unbounded.
- **Relaxing a committed bar requires independent authorization** *(red-team fix,
  H3-C3).* The loop's evidence may *raise* a committed acceptance, but the party
  that failed to meet it may not *lower* it; relaxation needs authorization
  independent of the loop plus a critic scoring "does this revision narrow scope to
  dodge a failing test?".

## Acceptance criteria

- AC-01-1: Every stage lists one primary artifact (or "—") and one hand-off gate
  (or "advisory").
- AC-01-2: The doc/cell maturity join is defined: commit mints a `validated` cell
  and is ledgered; the human never has to name a cell maturity to drive the flow.
- AC-01-3: Ticket acceptance binds to a `validated` (not `committed`) spec, and the
  spec→ticket edge carries the content hash.
- AC-01-4: A regenerate flip cascades `stale` to decomposed tickets and invalidates
  their signals; the regenerate loop is budget-capped; bar-relaxation requires
  loop-independent authorization.
- AC-01-5: PRD is required-by-default and waivable only by an explicit recorded
  declaration; SPEC `depends_on` PRD when one exists.

## Non-goals

- Not the *internal* schema of each artifact (that is `02`).
- Not the loop's stop conditions (that is `03`).

## Open decisions

- OD-01-C: Concrete regenerate-loop budget (max spec↔cultivated cycles before the
  factory halts and asks a human).
