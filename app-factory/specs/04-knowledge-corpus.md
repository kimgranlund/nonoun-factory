---
name: app-factory-knowledge-corpus
stage: knowledge-corpus
status: phase-C hardened (post red-team) — walking-skeleton thin slice
depends_on: 02-document-model
---

# Knowledge corpus — "better specs → cheaper build", made mechanical

**Intent.** The factory's thesis is that improving the specs and inputs is the
human's highest-leverage activity. This doc makes that mechanical: what the loop
*reads* when it builds, how that context is assembled, and how the corpus grows so
each build is cheaper and more reliable than the last — with the freshness
discipline the red-team found missing.

## What the loop reads (deterministic context assembly)

When a coding agent picks up a ticket, its context is assembled **deterministically**
from named corpus sources — never from conversation memory and never via ad-hoc
filesystem scans (red-team fix, AC-04-1):

1. **The ticket** and its sealed acceptance.
2. **The committed spec** the ticket decomposed from (resolved by the spec→ticket
   edge, not a fuzzy match).
3. **Knowledge docs** selected by an **explicit, recorded selector** on the ticket
   (e.g. `reads: [knowledge/conventions, knowledge/storage]`) — not "relevant
   knowledge docs." The read set is logged in the ledger for that dispatch.
4. **Distilled patterns** whose index matches the ticket's context *and* that are
   not `stale`.
5. **Cached research** (`research/*.md`) the team already paid for.

The leverage claim becomes testable: a richer corpus shrinks the agent's explore
cost per ticket and raises first-result quality. The delta is observable —
**probe-cost per ticket** is read from `ledger.py cost.iterations` and trended; a
**named reader** surfaces the trend in `/app-status` (red-team fix: the metric had
collection but no reader).

## Retrieval surface

A **read-only MCP query** surface over the corpus (reuses the
`lattice-query`/`factory-query` pattern): list/search/fetch specs, knowledge docs,
patterns, and ledger windows. Agents read through it; they do not shell around the
corpus. This keeps the read perimeter curated, observable, and bounded.

## Freshness discipline (red-team fix, H7-M3/M4)

The corpus is an asset only if it cannot silently rot:

- **Knowledge docs** carry a freshness signal; a doc edited after a build that
  consumed it is flagged, and `/app-status` shows stale knowledge so a wrong doc is
  at least *visible* before it is injected again.
- **Distilled patterns** inherit staleness from the ledger window they were distilled
  from; a pattern from a superseded window is marked `stale` and excluded from
  assembly (step 4) until re-distilled. No frozen-knowledge injection.
- **Cross-project knowledge (OD-04-A)** — if a factory-wide knowledge layer exists,
  it is subject to the same freshness signal; its larger blast radius makes the
  visibility requirement non-negotiable.

## How the corpus grows (the compounding asset)

- **Curation (human, authoritative).** The human writes/refines `knowledge/*.md` and
  the specs — the workflow the UI (later) is built around.
- **Distillation (machine, proposes-with-provenance).** A distiller compresses
  recurring ledger precedent into pattern docs *with provenance*; it proposes, it
  does not silently author canon (reuses the distiller discipline).
- **Regeneration (outer loop).** Execution/QA evidence proposes revisions to specs
  and knowledge; merged via the regenerate path, never silently (`01`), and bounded
  by the regenerate-count cap.

> The artifacts compound, not the agents. Humans curate; the spine enforces
> provenance, freshness, and bounded reads — no write-only drift.

## Acceptance criteria

- AC-04-1: Context assembly is deterministic and sourced from **named** corpus files
  (explicit per-ticket reader selector logged in the ledger); no fuzzy "relevant
  docs" and no conversation-memory dependence.
- AC-04-2: The leverage claim ties to an observable ledger metric (probe-cost /
  first-result quality per ticket) **with a named reader surfaced in `/app-status`**.
- AC-04-3: Knowledge docs and patterns carry a freshness signal; stale items are
  excluded from assembly and shown in `/app-status`.
- AC-04-4: All corpus reads go through the read-only MCP surface, not ad-hoc file
  access by workers.

## Non-goals

- Not a vector DB / embedding pipeline — start with the file corpus + grep/search;
  richer retrieval is a later, evidence-driven addition.
- Not the human-facing curation UI (deferred to the UI session).

## Open decisions

- OD-04-A: Per-project `knowledge/` only, or a cross-project factory-wide layer too
  (same freshness discipline either way).
- OD-04-B: Does distillation run inside `/app-loop` on a cadence, or only on an
  explicit `/app-distill`.
