---
name: app-factory-charter
stage: charter
status: phase-C hardened (post red-team) — walking-skeleton thin slice
session: 2026-06-22 review & planning
---

# app-factory — Charter

**Intent.** app-factory is the next, simpler software-factory-as-a-plugin. Where
`dev-factory` makes you operate a typed 9×5 lattice, app-factory makes you
**cultivate a corpus of prose documents** — an idea, a PRD, a set of SPEC docs —
and a bounded loop **compiles that corpus into software**. It is built around two
verbs: `/app-goal` (set a destination) and `/app-loop` (run until you reach it).

## The inversion

> **Simplicity lives in the human's authoring surface. Rigor stays in the
> verification spine.**

This is the load-bearing principle. The red-team (`phase-d-redteam.md`) sharpened
what "the spine" must contain:

- **What gets simpler** — the *operator surface*. The human edits prose (idea → PRD
  → specs → knowledge) and presses **commit**; they never operate a typed grid, and
  the command surface is ~6 verbs. Intent enters as prose; the loop is invoked by
  writing what you want.
- **What does NOT get lighter — the rigor.** app-factory carries the **same
  authoring + verification rigor as dev-factory**, vendored from `dev-kernel`
  (spec-author discipline, the spec-council, the gates, the refuter, calibration) —
  not only `harness-forge`'s loop primitives. "Simpler" means *simpler to operate*,
  not *weaker gates*. (Decided: OD-00-A → "same rigor, thinner operator surface".)

## The keystone (closed at the predicate, not just the signal)

The honest-doneness keystone is two guarantees, both required:

1. **Signal-honesty** *(reused as-is)* — the worker cannot forge its own pass; the
   signal is minted by a separate critic (`validate.py` + `gate-signal`).
2. **Predicate-honesty** *(new — the red-team's central fix)* — the worker cannot
   author or lower the bar it is graded against. A ticket's checkable acceptance is
   derived by a party **independent of the executor**, gated by an independent
   **entailment check** that it faithfully encodes the prose intent, and **sealed by
   the human** (not merely confirmed). (Decided: OD-02-B → "independent deriver +
   entailment gate".)

Only with both does the charter's promise hold: *the loop can neither lie about
whether it passed, nor arrange what passing means.* Signal-honesty alone is
strictly weaker — the gap the red-team found and this fix closes.

## The thesis: the spec is the program

A project is a **corpus**. Better specs + a richer knowledge corpus make it cheaper
and more reliable for the agent to build and iterate. The human's highest-leverage
activity is **improving the specs and inputs**, not steering execution. The loop is
cheap; the corpus is the asset.

## Walking skeleton (the thin end-to-end path)

Example project: **`quicklog`** — a tiny CLI journal (`add`, `today`, `search`).

| # | Stage | What happens | Artifact | Gate |
|---|-------|--------------|----------|------|
| 1 | Idea | Human writes a paragraph of intent | `idea.md` | — |
| 2 | Research *(skipped)* | none needed | — | — |
| 3 | PRD | `/app-goal "PRD"` → agent authors user stories | `prd.md` | prd-quality |
| 4 | SPEC | agent authors checkable specs; SPEC `depends_on` PRD | `spec/cli.md`, `spec/storage.md` | spec-quality + council |
| 5 | Kanban | commit decomposes specs into draft tickets → triaged to active, sequenced | `t1 storage` → `t2 add` → `t3 search` → `t4 today` | ticket-ready |
| 6 | Execution | `/app-loop` runs a coding agent per ready ticket; an **independent** critic verifies each against its **independently-derived** acceptance | code + signals | per-ticket critic signal |
| 7 | QA | loop emits a manual test plan; human runs it; acceptance replays | `qa.md` | honest-signal keystone |

`/app-goal` is met when every decomposed ticket of the destination has reached
`validated` by independent signal — doneness from the spine, never the loop's claim.

## Scope (this session)

- **In:** the document lifecycle, the document model, `/app-loop` + `/app-goal`, the
  knowledge corpus, and the plugin packaging — at thin-slice depth, hardened against
  the phase-D red-team.
- **Done:** phase D (spec-council + harness-council). Verdict was BLOCKED on the
  acceptance seam; this hardening pass clears the must-fixes (`phase-d-redteam.md`).
- **Deferred:** the web UI (productivity shell + project drawer). Deep per-component
  specs — a later pass.

## Non-goals

- **Not** weaker rigor than `dev-factory`. The lattice *operation* is hidden, not
  the verification rigor; the rigor is vendored and stays on.
- **Not** a chat UI. The UI (later) is a productivity shell over the corpus.
- **Not** a re-derivation of any spine primitive. We vendor from `harness-forge`
  *and* `dev-kernel` (see `05-packaging.md`), drift-checked.

## Relationship to the marketplace

A new catalog plugin in `nonoun-factory` (install id `…@nonoun-factory`), alongside
`plugins-factory`, `harness-forge`, `agent-ops`, `dev-factory`. Positioned as: **the
same rigor as dev-factory, behind a prose-cultivation front door.**

## Acceptance criteria

- AC-00-1: A reader can state the inversion (simple *operator surface* / rigorous
  spine) and that rigor is not lightened, in one sentence.
- AC-00-2: The walking skeleton names an artifact and a gate (or explicit "—") for
  every Pocock stage.
- AC-00-3: Every claimed-reused primitive is traceable to a real file in
  `harness-forge` **or** `dev-kernel`/`dev-kit-corpus`, per the split vendor table
  in `05-packaging.md`. (Fixed: the authoring/refuter/calibration half lives in
  dev-kernel, not harness-forge.)
- AC-00-4: The keystone is stated as *both* signal-honesty and predicate-honesty;
  neither alone satisfies it.

## Resolved decisions

- OD-00-A → **same rigor, thinner operator surface** (full vendored rigor, always on).
- OD-00-B → **`app-{verb}` namespacing** for the whole command surface (resolves the
  `/loop` collision). See `05-packaging.md`.

## Open decisions

- OD-00-C: Does the hidden spine expose an *escalation* path into the full typed
  lattice for unusually large projects, or is the vendored subset fixed? (Now a
  capacity question, not a rigor question — rigor is settled.)
