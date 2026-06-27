---
name: mismapped-coverage
description: >
  A criterion asserts EVERY color pair clears AA, but its scored_by dimension scores only the default pair —
  the spec-quality gate PASSES (a dimension is named); only critic-spec-coverage catches the narrowed observable.
---
# Contrast checker — every pair clears AA

**Intent.** EVERY generated color pair clears WCAG AA contrast — not just the default pair. A criterion bound to
a rubric must be scored by a dimension that measures *every* pair, or the property it names is unverified.

**Non-goals.** Color-blindness simulation; AAA contrast.

```json
{ "title": "Contrast checker", "cell": "spec.system.mismapped-coverage",
  "binds_rubric": "rubric.system.spec-quality",
  "acceptance_criteria": [
    { "id": "cc-01",
      "observable": "every generated color pair clears WCAG AA contrast",
      "rubric_cell": "rubric.system.palette-contrast",
      "scored_by": [ "contrast-default-pair" ] } ],
  "non_goals": [ "color-blindness simulation", "AAA contrast" ] }
```

**The defect (answer key — not read by the gate).** `cc-01` asserts EVERY pair clears AA; its `scored_by`
dimension `contrast-default-pair` scores only the DEFAULT pair — pairs[1..n] are unmeasured. The gate passes
(a non-empty `scored_by` is named); only `critic-spec-coverage` reads the criterion's observable against the
named dimension and catches that the dimension measures a NARROWER observable than the criterion demands.
Expected: `critic-spec-coverage` → Critical → BLOCKED.
