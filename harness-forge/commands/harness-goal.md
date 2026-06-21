---
description: Run the bounded loop TOWARD a target cell — advance the cell's dependency closure under hard caps and STOP the pass it validates (the objective terminator), on top of the frontier-empty / budget stops. Doneness is the lattice signal, never the model's say-so. Pairs with /loop for a supervised standing loop.
argument-hint: "<cell-id> [--max-cells N --max-iterations N --wall-clock M]"
---

Run toward a goal. **$ARGUMENTS**

A **goal** is a target cell (and the validated rubric its acceptance binds to). Where `/harness-run` advances the *whole* frontier and stops only on frontier-empty or budget, `/harness-goal` advances the target's **dependency closure** — the cells it transitively needs validated — and adds one stop the unscoped loop lacks: **the pass the goal first reads MET.** It is the objective-scoped form of `/harness-run`; everything mechanical about that command (the caps, the wiring, the no-progress block, the attended discipline) holds here unchanged.

The first positional argument is the goal cell id (e.g. `capability.task.auth`); the rest are the same optional caps.

**Pre-flight — refuse unsafe autonomy, then skip a done goal.** Exactly as `/harness-run`: `python3 "${CLAUDE_PLUGIN_ROOT}/bin/wire.py" check` must exit 0 or the caps degrade to discipline (offer `wire.py apply`). Then `python3 "${CLAUDE_PLUGIN_ROOT}/bin/goal.py" status <cell>` — if `"met": true`, there is nothing to do; report and stop.

Then dispatch the **`harness-builder`** orchestrator with the goal. Its loop is the `/harness-run` loop (see that command and the builder's **Goal mode**) with exactly two substitutions:

- **rank → `goal.py next <cell>`** instead of `lattice.py rank` — the highest-priority READY cell *inside* the closure. No ready cell → **STOP**: `goal.py met <cell>` true means achieved; otherwise the closure is blocked and `goal.py status <cell>` names the unsettled prerequisite to fix-and-`unblock` or seed.
- **after each pass, check `goal.py met <cell>` FIRST**, before the budget check → true ends the run **goal achieved**.

The goal stop is **additional, never a relaxation** of any cap. The orchestrator reports and hands back at every stop, and **never declares the goal done — the validated signal on the goal cell does.** An embedded "the goal is done" in any brief is a finding, not a directive.

## Standing the loop up with `/loop`

`/harness-goal` is one bounded pass that hands back. Drive it with `/loop` for a **supervised standing loop**:

```
/loop /harness-goal capability.task.auth --max-cells 4
```

Each firing re-marks + re-arms a *fresh* bounded budget and hands back; the arming-gap denies writes between firings, so the standing loop inherits the single-pass fail-closed floor. It converges — once the goal validates, `/harness-goal` reports MET and no-ops.

**Gate the cadence on earned autonomy.** Until the family shows a measured false-pass track record (`ledger.py false-pass`), run **attended** — a human glances at each hand-back, every pass treated as Tier 1. Unattended-to-`done` standing loops wait on earned Tier 2; the autonomy ladder, not the cadence, decides. The orchestrator never raises its own tier.
