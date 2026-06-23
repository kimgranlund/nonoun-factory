---
name: app-factory-document-model
stage: document-model
status: phase-C hardened (post red-team) — walking-skeleton thin slice
depends_on: 01-lifecycle
---

# Document model — artifacts, the prose↔typed boundary, prose-driven loop

**Intent.** Define the artifact types the human cultivates, the frontmatter contract
each carries, the moment prose **crystallizes** into the gated regime, and how the
loop is invoked by *writing* rather than by hand-building typed tickets. This is the
heart of what `dev-factory` lacked — and the seam the red-team attacked hardest, so
the crystallization rule below is specified on its failure branches, not just its
happy path.

## Project layout (the corpus = the backing store)

```
projects/<name>/
├── idea.md
├── research/            # optional, advisory
├── prototype/           # optional, throwaway + handed-forward assets
├── prd.md
├── spec/                # committed specs are PROTECTED (deny-on-write to executor)
│   ├── cli.md
│   └── storage.md
├── tickets/             # generated from committed specs; `acceptance` is PROTECTED
│   ├── t1-storage.md
│   └── …
├── knowledge/           # curated reference the loop reads (see 04)
├── qa.md                # PROTECTED
└── .factory/            # ledger + signals + protected-path registry (PROTECTED)
```

The corpus is **git-tracked files**; every state change is a ledgered,
server-mediated edit (the substrate the future UI renders).

**Protected perimeter** *(red-team fix, H3-M1/M2).* Committed `spec/*.md`, the
`tickets/*.md` `acceptance` field, `qa.md`, and the app-factory ledger are
registered **deny-on-write to the executor** — they live in `projects/<name>/`, so
they are explicitly added to the spine's protected glob (they are *not* covered by
`harness-forge`'s default `.agents/harness/` protection). A coding agent cannot edit
the bar it is graded against. Reads go through the MCP query surface (`04`), not
ad-hoc filesystem access.

## Artifact types & frontmatter

```yaml
---
kind: idea | research | prototype | prd | spec | ticket | qa | knowledge
name: <slug>
maturity: draft | cultivated | committed     # document maturity (01)
goal: false | true                            # is this an /app-goal destination?
---
```

- **idea** — free prose; only intent required.
- **prd** — user stories, outside-in, **narrative-acceptance** (a usage narrative).
  Gated by prd-quality on commit. *Narrative-acceptance is never a `/app-goal met`
  predicate* — a PRD destination is met *via its specs* (see below).
- **spec** — inside-out, **checkable-acceptance** (executable `check` or a validated
  `rubric_cell`) + non-goals + decomposition. Gated by spec-quality + spec-council.
  Reuses the `dev-kernel` spec-format discipline, authored as prose first.
- **ticket** — a unit of execution work; carries **checkable** `acceptance`,
  `blocks`/`blocked_by` edges, a budget. Generated from committed specs, editable as
  prose, but its `acceptance` field is protected once sealed.
- **qa** — a manual test plan for a human, emitted by the loop.
- **knowledge** — curated reference (see `04`).

**"acceptance" disambiguated** *(red-team fix).* The word names three distinct
things — *narrative-acceptance* (PRD), *checkable-acceptance* (SPEC/ticket), and the
*bound predicate* a ticket's `acceptance` resolves to. Only checkable-acceptance can
ever be a `/app-goal met` predicate. There is **no "or a committed spec criterion"
escape**: every ticket acceptance resolves to an executable check or a validated
rubric cell, or it cannot crystallize.

## The prose↔typed boundary (the crystallization rule)

A document lives as **freely-editable prose** until the human commits it. **Commit**
is a distinct mechanism — the `/app-spec commit` action (server-mediated), **not
`git commit`** — performed by **the human** as the sealing actor. Crystallization
turns prose into a typed, gated artifact, and **refuses to complete unless every
guarantee below holds**:

```
draft/cultivated prose          ──(commit: /app-spec commit, human seals)──▶  typed, gated artifact
   (edit freely, no gate)                                                     (cell minted to `validated`)
```

On commit, in order — any failure rejects the commit (no silent limbo):

1. **Quality gate fires** (prd-quality / spec-quality). Red → commit rejected, doc
   stays `cultivated` with the findings; it is never left in an undefined state.
2. **Acceptance is derived by a non-executor party** *(keystone fix)*. A deriver
   agent — drawn from a family **disjoint from any executor under the same goal**,
   enforced at dispatch, not requested in prose — produces the typed
   checkable-acceptance from the prose.
3. **Independent entailment check.** A separate critic verifies the derived
   predicate **faithfully entails the prose intent** (the fidelity check the
   deriver cannot reach) and that it is **deterministic** (calibration record, via
   the vendored `evals/calibration/` discipline). Fail → commit rejected.
4. **The human seals.** The human reviews and *seals* the derived, entailment-passed
   acceptance — an authorship act, not a rubber-stamp confirm (AC-02-4).
5. **Cell minted + decomposition proposed.** A `validated` spine cell is minted
   (`01`); the spec→ticket edge is stamped with the spec's content hash; commit
   proposes **draft** tickets, which become **active** only via triage
   (ticket-ready). (Resolves OD-02-A: decompose-on-commit produces *drafts*, not
   live work.)

After commit, edits flow through the regenerate path (`01`), never silent overwrite.

> Design rule: the human writes prose, then **seals** a typed acceptance they have
> read and an independent critic has certified faithful. Typing, cells, and signals
> remain machine concerns — but the *bar* is sealed by a human and an independent
> check, never by the agent that will be graded against it.

## Prose-driven loop invocation

The capability `dev-factory` lacked — invoke the loop by writing what you want,
*without* hand-building typed JSON:

- **A goal in prose.** Mark a committed PRD/SPEC `goal: true`. `/app-goal <doc>` sets
  its acceptance as the destination and runs the bounded loop until met (`03`). A
  PRD destination is met *via its decomposed specs*, never by replaying a narrative.
- **A ticket in prose.** A `tickets/*.md` written in plain prose is run through the
  same derive→entail→seal pipeline above: a non-executor deriver proposes the typed
  `acceptance`/`blocks`/`budget`, the entailment critic certifies fidelity, the
  human seals. The human writes the paragraph; the bar is machine-derived,
  independently certified, human-sealed — **not** worker-authored.
- **An ad-hoc instruction.** Free-prose guidance dropped into the loop is folded
  into its guidance buffer (reuses the `instruction` intake type). A **code gate**
  ensures the guidance buffer **can never alter a committed/sealed acceptance**
  *(red-team fix, H3-M1)*.

## Acceptance criteria

- AC-02-1: Each artifact type has a `kind` and a stated frontmatter contract.
- AC-02-2: Crystallization is specified on its failure branches — a red gate or a
  failed entailment check **rejects** the commit (doc stays `cultivated`); there is
  no committed-on-red limbo.
- AC-02-3: All three prose-driven paths derive the bar via a non-executor party and
  require no human-authored typed JSON.
- AC-02-4: **Acceptance fidelity, not a confirm click.** A ticket's bound predicate
  is valid only if (a) derived by a family disjoint from its executors, (b) certified
  by an independent entailment+determinism check, and (c) sealed by the human. A bare
  confirm does not satisfy this.
- AC-02-5: Committed specs, ticket `acceptance`, `qa.md`, and the ledger are
  deny-on-write to the executor; the guidance buffer cannot alter committed
  acceptance.
- AC-02-6: No ticket acceptance binds to a non-checkable criterion.

## Non-goals

- Not the exact JSON schema of the crystallized artifact — reuses `dev-kernel`'s
  `ticket.schema.json` / spec-format, bound in `05`.
- Not the retrieval mechanics of the knowledge corpus — that is `04`.

## Open decisions

- OD-02-C: Where the corpus lives relative to the target repo. Resolved-enough for
  the thin slice: committed/load-bearing assets are registered protected paths
  regardless of location; reads go through the MCP surface. The *physical* sibling-
  vs-inside choice remains open but no longer voids the read perimeter.
- OD-02-D: Is the deriver a dedicated `acceptance-deriver` agent, or the existing
  `spec-author`/`ticket-triager` constrained to a non-executor family? (Either
  satisfies AC-02-4; affects the agent roster in `05`.)
