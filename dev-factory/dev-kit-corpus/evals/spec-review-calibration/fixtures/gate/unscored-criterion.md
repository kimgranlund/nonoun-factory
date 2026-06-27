---
name: unscored-criterion
description: >
  A contrast checker whose acceptance criterion binds a rubric but names no scoring dimension — coverage is
  declared in name only, so the spec-quality gate must reject it on criteria-rubric-coverage.
---
# Contrast checker — accessible color pairs

**Intent.** Generated color pairs clear WCAG AA contrast; a rubric scores them.

**Non-goals.** Color-blindness simulation; AAA contrast.

```json
{ "title": "Contrast checker", "cell": "spec.system.unscored-criterion",
  "binds_rubric": "rubric.system.spec-quality",
  "acceptance_criteria": [
    { "id": "cc-01", "rubric_cell": "rubric.system.palette-contrast" } ],
  "non_goals": [ "color-blindness simulation", "AAA contrast" ] }
```
