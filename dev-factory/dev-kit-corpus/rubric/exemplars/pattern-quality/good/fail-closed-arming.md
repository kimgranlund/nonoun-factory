---
name: fail-closed-arming
description: >
  A well-formed pattern: a retrieval context, a transferable solution shape, consequences both ways,
  and provenance with two ledger refs AND a refutation condition. The gate must PASS this.
---
# fail-closed arming

**Context.** A bounded autonomous loop that must never spend before its budget window is armed.

```json
{
  "cell": "pattern.system.fail-closed-arming",
  "context": "a bounded autonomous loop (heartbeat) that dispatches paid workers and must not spend before an attended, bounded budget window exists",
  "forces": "convenience — start dispatching the moment there is ready work — versus safety — no spend outside a bounded window the operator armed",
  "solution_shape": "arm the budget BEFORE the first dispatch; a wired gate denies every write/dispatch while run/heartbeat.json is absent, so SKIPPING the arm fails closed (the loop refuses to act) rather than open (the loop spends unbudgeted)",
  "consequences": "buys: no unbudgeted spend and an auditable window; costs: an 'arming gap' where the loop refuses writes until the operator arms it, which can read as the loop being stuck",
  "provenance": {
    "ledger_refs": ["ledger:142", "ledger:188"],
    "refuted_when": "a dispatch is observed against an instance with no armed window AND no corresponding deny event in the ledger",
    "confirmed": true
  }
}
```
