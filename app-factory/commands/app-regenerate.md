---
description: Regenerate after a committed spec changes — cascade staleness to every ticket validated against the old spec hash, invalidate their signals, and re-open them as `defined` against the new spec, so no validated work survives an outdated definition. The outer loop's correctness gate.
argument-hint: "<project> <spec-relpath>   (e.g. projects/quicklog spec/cli.md)"
---

Regenerate the spec. **$ARGUMENTS**

A committed spec is the contract its tickets were built against. When it changes, the tickets that passed against the *old* definition must not stay trusted — that is the harness-council's stale-but-trusted Critical. This closes it.

**If the spec needs revising from evidence first**, dispatch the **`app-factory:spec-regenerator`** agent: it turns ledger failures / QA findings / distilled anti-patterns into a PROPOSED spec revision (cited to evidence, never opinion) for you to review and commit. It never merges or regenerates itself.

**Then regenerate** — once the committed spec has been edited:

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/app-regen.py" projects/<name> spec/<doc>.md
```

This (1) **gates** the edited spec — regeneration from a broken spec is refused; (2) **cascades staleness** using the kernel's own `propagate_staleness` graph walk — the spec cell and every dependent whose `validated_against` hash no longer matches flip `stale`, ledgered as provenance; and (3) **re-crystallizes** — drops the now-stale derived cells + signals + ticket files and re-commits, so the frontier re-opens with fresh `defined` tickets stamped against the NEW spec hash. Then `/app-loop` re-builds the affected tickets.

> The cascade is a graph computation, not a thing anyone remembers — a spec revision can never silently leave a validated ticket trusted against a definition it no longer matches.
