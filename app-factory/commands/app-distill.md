---
description: Distill the ledger into reusable pattern drafts — recurring failure modes become anti-patterns, recurring solution shapes become patterns, each carrying its ledger provenance. The corpus compounds so later builds are cheaper. Distills, never authors canon.
argument-hint: "<project> [--window N] [--min-occur N]"
---

Distill the ledger. **$ARGUMENTS**

The factory only gets cheaper to build with if precedent is captured. Dispatch the **`app-factory:app-distiller`** agent, which:

1. Runs `python3 "${CLAUDE_PLUGIN_ROOT}/bin/app-distill.py" <project> [--window N] [--min-occur N]` — windows the ledger, groups recurring validate signatures, and writes a **DRAFT** pattern doc per recurring group to `knowledge/patterns/`, each carrying the exact ledger entries it was distilled from (a recurring failure → an anti-pattern; a recurring solution shape → a pattern).
2. **Curates** — keeps the drafts that name a genuinely reusable shape (or a real recurring failure mode + its fix), marks the noise; never invents a pattern the ledger doesn't support.
3. **Proposes, never authors canon** — promotes a canonical pattern only as a proposal, and proposes (does not silently make) any spec/rubric revision the patterns suggest.

The distilled patterns then feed every later build through `app-context.py`, which assembles a ticket's build context from the spec + knowledge + **non-stale** patterns — so a richer corpus deterministically enriches the next build, and a superseded (`stale`) pattern is excluded.

> Patterns are DISTILLED, not authored: the artifacts compound because humans curate what the distiller proposes, with provenance — not because an agent wrote canon.
