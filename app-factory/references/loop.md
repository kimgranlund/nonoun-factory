# The bounded loop — arm · select · dispatch · validate · check · stop

The mechanics behind `/app-loop` (and, scoped to a destination, `/app-goal`), lifted out so those commands stay thin routers. The two honesties + the earned-autonomy model are in [`keystone.md`](./keystone.md).

**The controller is `${CLAUDE_PLUGIN_ROOT}/bin/app-loop.py`; the model dispatches the agents between its decisions** (like harness-builder, the control flow is code, not the model's discipline). `D = projects/<name>/.factory/state`. **Attended by design** — stoppable, and it reports at every stop.

## Arm (fail-closed)

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/app-loop.py" arm --dir D --max-iterations N --max-cells M --wall-clock-s S [--request-tier T]
```

This marks **and** starts the budget — a cap-less budget is refused, and the wired `gate-budget` then denies every write past the ceiling (skipping it fails *closed*). `--request-tier T` consults the earned trust tier and **REFUSES to arm** an unattended run the ledger has not earned (run attended instead).

## The loop, until a stop

1. **select** — `app-loop.py next --dir D` prints the top ready **dispatchable** ticket: a `capability` cell whose verifier rubric is `validated` and carries a sealed bar (crystallized tickets only — seed/non-ticket cells are ignored). `STOP: frontier empty` (exit 3) ends the run.
2. **dispatch** — dispatch **one** `app-factory:app-worker` to implement that ticket into `build/` in a fresh context. The worker is **deny-on-write** to the committed bars and **never runs its own verifier**.
3. **validate** — dispatch the **independent** `app-factory:app-validator` (never the worker, never the ticket's acceptance *deriver*) to mint the signal from the sealed bar via `validate.py`, then `ledger.py append` the result. The signal — not the worker's claim — is doneness.
4. **check** — `app-loop.py check --dir D` runs the no-progress detector (a ticket stuck on repeated failures is **blocked**, leaving the frontier) and the budget status; `STOP: budget exhausted` (exit 3) ends the run.

## Stop

`app-loop.py stop --dir D` clears the budget + marker and reports iterations · tickets validated · blocked (with reason) · still pending. On every stop the loop **reports and hands back** and never silently re-enters.

*(Headless / CI: `app-loop.py run --dir D --project P [caps]` drives the whole loop with a built-in validate-only advancer — the live loop substitutes the agent dispatch of steps 2–3 for that advancer.)*
