---
name: not-falsifiable
description: >
  Planted defect — a pattern with provenance and consequences but NO refutation condition. A pattern that
  nothing could disprove is folklore, not a falsifiable claim; the gate must REJECT it on falsifiable.
---
# not falsifiable

```json
{
  "cell": "pattern.system.not-falsifiable",
  "context": "selecting the next ticket from a frontier of ready work",
  "forces": "throughput versus respecting dependency order",
  "solution_shape": "rank ready tickets by unlock value and dispatch the top one per tick",
  "consequences": "buys: steady forward progress; costs: a greedy choice can starve a high-value but lower-ranked ticket",
  "provenance": {
    "ledger_refs": ["ledger:51", "ledger:73"],
    "confirmed": true
  }
}
```
