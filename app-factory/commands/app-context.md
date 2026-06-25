---
description: Show the deterministic build context a worker would receive for a ticket — the spec it decomposed from + the project's knowledge docs + the non-stale distilled patterns, in a stable order. The "better specs/knowledge → cheaper build" mechanic, made inspectable.
argument-hint: "<project> <ticket-id|target-cell> [--json]"
---

Assemble a ticket's build context. **$ARGUMENTS**

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/app-context.py" projects/<name> <ticket-id> [--json]
```

When the loop builds a ticket, the worker shouldn't start from a blank page — it builds with the accumulated corpus. This assembles that context from **named** sources in a **stable** order, with two disciplines:

- **Deterministic** — the spec the ticket decomposed from + every `knowledge/*.md` + every non-stale `knowledge/patterns/*.md`, sourced from named files (never a fuzzy "relevant docs" guess), so the same corpus always assembles the same context, and the source list is observable.
- **Fresh** — a pattern marked `maturity: stale` (superseded by `/app-regenerate`) is EXCLUDED; frozen knowledge can't leak into a build.

The assembled context is **intent + knowledge, never the sealed bar** — the worker builds to what the spec means, not to the test it will be graded against (predicate-honesty). Use this to see exactly what a build is grounded in — and to confirm that cultivating better specs and knowledge is what makes the next build cheaper.
