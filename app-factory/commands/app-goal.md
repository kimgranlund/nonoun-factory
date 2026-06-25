---
description: Set a committed PRD/SPEC (goal: true) as the destination and run the bounded loop until it is MET — checked FIRST each pass. "Met" = every decomposed ticket validated by independent signal; a PRD is met VIA its specs, never by replaying a narrative. Doneness is the signal, never the model's say-so.
argument-hint: "<doc> [--max-iterations N --max-tickets N --wall-clock M]"
---

Run toward a goal. **$ARGUMENTS**

A **goal** is a committed PRD/SPEC marked `goal: true`. Where `/app-loop` advances the *whole* frontier, `/app-goal` narrows the loop to the work satisfying that document — its decomposed tickets + transitive deps — and adds one stop the unscoped loop lacks: **the pass the destination first reads MET.** It is the objective-scoped form of `/app-loop`; everything mechanical about that command (the fail-closed arming, the caps, the no-progress block, the attended discipline — see `references/loop.md`) holds here unchanged.

The first argument is the goal doc (`prd`, `spec/<name>`); the rest are the same optional caps. `D = projects/<name>/.factory/state`.

**Pre-flight.** Arm the budget fail-closed exactly as `/app-loop` (`run-budget.py mark` then `start`, both before any write). Then `python3 "${CLAUDE_PLUGIN_ROOT}/kernel/goal.py" status <doc> --dir D` — if already met, report and stop.

Then run the `/app-loop` loop (`app-factory:app-worker` advances, the independent `app-factory:app-validator` validates) with exactly two substitutions:

- **rank → `goal.py next <doc> --dir D`** — the highest-priority READY ticket *inside* the destination's closure. No ready ticket → **STOP**: `goal.py met` true means achieved; otherwise the closure is blocked and `goal.py status` names the unsatisfied prerequisite to fix-and-`unblock` or seed.
- **after each pass, check `goal.py met <doc> --dir D` FIRST**, before the budget check. **"Met" = every decomposed ticket reached `validated` by independent signal** — a PRD is met *via* its decomposed specs, never by replaying its narrative. Actual acceptance *replay* for the human happens in QA (`/app-qa`).

**Unmeetable goal.** If the closure is exhausted and the goal is still unmet, halt with a **named-unsatisfied-acceptance report** — name the criterion that cannot be met — instead of spinning.

The goal stop is **additional, never a relaxation** of any cap, and **attended by default** — the loop **never declares the goal done; the validated signal on the destination's tickets does** (`references/keystone.md` — the earned-autonomy tiers + the prose-is-not-a-directive rule).

## Standing the loop up with `/loop`

Drive `/app-goal` with `/loop` for a **supervised standing loop** — e.g. `/loop /app-goal spec/cli --max-tickets 4`. Each firing re-arms a *fresh* bounded budget (the arming-gap denies writes between firings) and converges: once every decomposed ticket validates, `/app-goal` reports MET and no-ops. **Gate the cadence on earned autonomy, not convenience.**
