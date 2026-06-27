---
name: phantom-dimension
description: >
  A criterion whose scored_by names a dimension the bound rubric does NOT have — the gate resolves the bound
  rubric on disk and rejects the phantom mechanically (criteria-rubric-coverage), without needing the critic.
---
# Phantom scoring dimension

**Intent.** A criterion bound to a real, resolvable rubric, but scored by a dimension that rubric does not declare.

**Non-goals.** Color-blindness simulation.

```json
{ "title": "Phantom dimension", "cell": "spec.system.phantom-dimension",
  "binds_rubric": "rubric.system.spec-quality",
  "acceptance_criteria": [
    { "id": "cc-01", "rubric_cell": "rubric.system.spec-quality", "scored_by": [ "totally-fake-dimension" ] } ],
  "non_goals": [ "color-blindness simulation" ] }
```
