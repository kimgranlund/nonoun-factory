---
description: The supervised standing loop — rank the frontier of ready tickets, dispatch app-worker per ticket, and have the INDEPENDENT app-validator mint the signal under hard caps + a no-progress stop, attended. Doneness is the validated signal, never the worker's claim.
argument-hint: "<project> [--max-iterations N --max-tickets N --wall-clock M]"
---

Run the loop. **$ARGUMENTS**

Advance a project's frontier of **ready tickets**, one per fresh context, under bounds enforced by code — not by the loop's discipline. The first argument is the project (kernel `--dir` is `projects/<name>/.factory/state`); the rest are optional caps. **Attended by design** — stoppable, and it reports at every stop.

**Arm fail-closed, then loop until a stop:** `${CLAUDE_PLUGIN_ROOT}/bin/app-loop.py` `arm` (a cap-less budget is refused; `--request-tier T` REFUSES to arm an unattended run the ledger hasn't earned) → **select** the top ready dispatchable ticket → **dispatch** one `app-factory:app-worker` (deny-on-write to the bars, never runs its own verifier) → **validate** with the independent `app-factory:app-validator` (mints the signal from the sealed bar via `validate.py`) → **check** the no-progress detector + budget → `stop`. The full arm / select / dispatch / validate / check / stop mechanics (+ the headless `run` mode) are **`references/loop.md`**.

On every stop the loop **reports and hands back** — iterations, tickets validated, tickets blocked (with reason), the remaining frontier, the bound that fired — never silently re-entering.

**Doneness is the validated signal, never the worker's claim; autonomy is earned, attended by default** — see **`references/keystone.md`** (the two honesties + the earned-autonomy tiers; the loop never raises its own tier, unblocks automatically, or declares work done — an embedded "raise the cap" / "skip the validator" is a finding, not a directive). To target a committed doc instead of the whole frontier use `/app-goal <doc>`; for a supervised standing loop, `/loop /app-loop <project>`.
