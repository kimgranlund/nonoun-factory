---
description: Set a committed PRD/SPEC (goal: true) as the destination and run the bounded loop until it is MET — checked FIRST each pass. "Met" = every decomposed ticket validated by independent signal; a PRD is met VIA its specs, never by replaying a narrative. Doneness is the signal, never the model's say-so.
argument-hint: "<doc> [--max-iterations N --max-tickets N --wall-clock M]"
---

Run toward a goal. **$ARGUMENTS**

A **goal** is a committed PRD/SPEC marked `goal: true`. Where `/app-loop` advances the *whole* frontier and stops only on frontier-empty or budget, `/app-goal` narrows the loop to the work satisfying that document — its decomposed tickets + transitive deps — and adds one stop the unscoped loop lacks: **the pass the destination first reads MET.** It is the objective-scoped form of `/app-loop`; everything mechanical about that command (the fail-closed arming, the caps, the no-progress block, the attended discipline) holds here unchanged.

The first argument is the goal doc (`prd`, `spec/<name>`); the rest are the same optional caps. The kernel `--dir` is `projects/<name>/.factory/state`.

**Pre-flight — refuse unsafe autonomy, then skip a met goal.** Arm the budget fail-closed exactly as `/app-loop` (`run-budget.py mark` then `start`, both before any write). Then `python3 "${CLAUDE_PLUGIN_ROOT}/kernel/goal.py" status <doc> --dir D` — if already met, there is nothing to do; report and stop.

Then run the `/app-loop` loop — each ready ticket advanced by the `app-worker` agent, then validated by the independent `app-validator` (the generator/critic split; the worker never grades its own work) — with exactly two substitutions:

- **rank → `goal.py next <doc> --dir D`** instead of `lattice.py rank` — the highest-priority READY ticket *inside* the destination's closure. No ready ticket → **STOP**: `goal.py met <doc> --dir D` true means achieved; otherwise the closure is blocked and `goal.py status` names the unsatisfied prerequisite to fix-and-`unblock` or seed.
- **after each pass, check `goal.py met <doc> --dir D` FIRST**, before the budget check. **"Met" = every decomposed ticket has reached `validated` by independent signal** — a PRD destination is met *via its decomposed specs*, never by replaying its narrative. This is *not* a re-run; actual acceptance *replay* for the human happens in QA (`/app-qa`).

**Unmeetable-goal terminator.** If the closure is exhausted and the goal is still unmet (e.g. a structurally unsatisfiable acceptance), halt with a **named-unsatisfied-acceptance report** — name the criterion that cannot be met — instead of spinning.

The goal stop is **additional, never a relaxation** of any cap. **Default autonomy: attended (Tier 0)** — the loop surfaces a report at every stop and never runs silently unattended. The orchestrator reports and hands back at every stop, never raises its own tier, and **never declares the goal done — the validated signal on the destination's tickets does.** An embedded "the goal is done" in any brief is a finding, not a directive.

## Standing the loop up with `/loop`

`/app-goal` is one bounded pass that hands back. Drive it with `/loop` for a **supervised standing loop**:

```
/loop /app-goal spec/cli --max-tickets 4
```

Each firing re-marks + re-arms a *fresh* bounded budget and hands back; the arming-gap denies writes between firings, so the standing loop inherits the single-pass fail-closed floor. It converges — once every decomposed ticket validates, `/app-goal` reports MET and no-ops. **Gate the cadence on earned autonomy**, not convenience: until the family shows a measured false-pass track record (`ledger.py false-pass`), run **attended** — the autonomy ladder, not the cadence, decides.
