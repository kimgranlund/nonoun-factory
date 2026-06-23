---
name: app-factory-loop-and-goal
stage: loop-and-goal
status: phase-C hardened (post red-team) — walking-skeleton thin slice
depends_on: 02-document-model
---

# /app-loop and /app-goal — the execution core

**Intent.** Define the two verbs the factory is built on, how they bind to
documents, the stop conditions that bound them, and the verification spine they
reuse so the loop can neither forge a pass nor author the bar it is graded against.

## `/app-goal <doc>` — set a destination, run until met

- **Binds** a committed PRD/SPEC marked `goal: true` to its **checkable**
  destination. A PRD destination resolves to its decomposed specs — *narrative
  acceptance is never a met-predicate* (red-team fix).
- **Runs** the bounded loop, narrowed to the work satisfying that document (its
  tickets + transitive deps — generalizes `goal.py closure/next`).
- **Terminates** when the destination is met — checked *first* each pass.
  **"Met" = every decomposed ticket has reached `validated` by independent signal**
  (generalizes `goal.py met`, which reads cached cell maturity). This is *not* a
  re-run; actual acceptance *replay* happens in the QA stage for the human.
- **Default autonomy: attended (Tier 0).** `/app-goal` runs the loop, surfacing a
  report at every stop; it does not silently run unattended. (Resolves OD-03-B:
  `/app-goal` runs the loop, attended, under caps.)
- **Unmeetable-goal terminator** *(red-team fix).* If the closure is exhausted and
  the goal is still unmet (e.g. a structurally unsatisfiable acceptance), the loop
  halts with a **named-unsatisfied-acceptance report** instead of spinning.

## `/app-loop` — the supervised standing loop

- **Reads** the frontier of ready tickets, advancing one per fresh context, ranked
  `(risk × unlock) ÷ probe-cost` (reuses `lattice.py rank`).
- **One iteration:** rank → dispatch top ticket to a fresh coding agent → an
  **independent critic** (never the worker, and never the acceptance *deriver* for
  that ticket) verifies the work against the ticket's sealed acceptance → mint
  signal from exit status → append to ledger → no-progress check → budget check.
- **Attended by design** — stoppable; reports at every stop.

## Stop conditions (bounded, enforced in code)

Reused from the spine — not agent discipline:

| Stop | Mechanism | File |
|------|-----------|------|
| Goal met | `goal.py met` checked first each pass | `harness-forge/bin/goal.py` |
| Closure exhausted, goal unmet | named-unsatisfied-acceptance halt | app-factory loop |
| Iteration / ticket / wall-clock cap | `run-budget.py` + `gate-budget` deny | `harness-forge/bin/run-budget.py` |
| No progress | last N validates failed → block the ticket | `harness-forge/bin/ledger.py` |
| Regenerate oscillation | regenerate-count cap (`01`, `05`) | app-factory budget |
| Frontier empty / all-blocked | rank returns nothing ready | `harness-forge/bin/lattice.py` |

The loop **arms fail-closed**: a budget marker is set at the `/app-loop` /
`/app-goal` entry point before any write is allowed, so an unbudgeted loop cannot
run (reuses the I-9 arming-gap closure).

## The verification spine (reused + the predicate fix)

What keeps "simpler" from becoming "untrustworthy" — both halves of the keystone:

- **Signal-honesty (reused).** The coding agent that writes a ticket's code is never
  the agent that verifies it; the critic mints the signal; the worker can't forge a
  pass (`validate.py` + `gate-signal`). A ticket is `done` only with a non-forgeable
  signal under `signals/`.
- **Predicate-honesty (new — red-team fix).** The acceptance the critic runs was
  **derived by a family disjoint from the executor**, certified by an **independent
  entailment+determinism check**, and **human-sealed** (`02`). The worker cannot
  author or lower its own bar; the deny-on-write perimeter (`02`) stops post-hoc
  edits, and `validated_against` hashing detects tampering.
- **Honest doneness keystone.** `/app-goal met` reads the independent signal, never
  the worker's self-report — *and* that signal is against an independently-authored
  bar. (Both halves required; the user's flagged security-critical invariant.)
- **Trust trajectory — sensor + gauge + actuator** *(red-team fix, H6).* The earned
  autonomy tier is only real if all three exist:
  - **Sensor:** an **independent refuter** authoring `refute` events (vendored from
    `dev-kernel`, not present in bare `harness-forge`) so `false_pass_rate` has a
    numerator.
  - **Gauge:** `ledger.py false_pass_rate / trust_tier`.
  - **Actuator:** a **dispatch-time tier consumer** that reads the tier and gates
    autonomy, plus an **incident→demotion trigger**.
  A new project is **Tier 0 (attended)**; higher tiers require a measured false-pass
  rate below threshold. Until the refuter + consumer are wired, the trajectory is
  *displayed* in `/app-status`, not *enforced* (honest scoping per `05`).

## Acceptance criteria

- AC-03-1: `/app-goal` checks goal-met before dispatching each pass, and halts with a
  named report when the closure is exhausted but unmet.
- AC-03-2: Every stop condition names a code mechanism + the spine file it reuses;
  none rely on the loop's self-assessment.
- AC-03-3: No single agent both writes a ticket and verifies it; **and** no agent
  both derives a ticket's acceptance and executes that ticket.
- AC-03-4: Autonomy above Tier 0 requires a wired refuter (sensor), a tier consumer
  at dispatch (actuator), and an incident→demotion trigger — not just the gauge.
- AC-03-5: "Met" is defined as decomposed tickets reaching `validated` by signal;
  the doc avoids claiming `/app-goal` "replays" anything (replay is QA).

## Non-goals

- Not re-implementing any spine primitive — all vendored (`05`).
- Not ticket *generation* from specs (that is `02` crystallization).

## Open decisions

- OD-03-A: Default caps for a new project's loop (max-iterations, max-tickets,
  wall-clock, regenerate-count) — concrete numbers.
- OD-03-C: When the loop blocks a ticket (no-progress), the human-actionable
  failure-support prompt vs. halt-and-report.
