# tier1-acceptance-gate — the critic runs at every tier; the tier gates only acceptance

_Last reviewed: 2026-06-18._

**What it proves.** The core loop's autonomy tier governs **acceptance**, not **verification**. The
produce→validate→iterate loop — guided by the lattice model — runs at *every* tier; only the final
sign-off is tier-dependent (automatic at Tier 2+, the human gate at Tier 1).

**The gap it closes.** Previously `dispatch_unit(auto_validate=False)` (Tier 1) parked a signal-bearing
cell at `in-review` **without running the critic**. The cell could then never reach `validated` (the
critic that mints the unforgeable signal never ran), so `gate-signal` correctly refused the operator's
`done`, and the cell **livelocked** — blocking the whole partial order behind it (a single in-review PRD
stalled an entire build, and the heartbeat idled to deadline). Output iteration only worked unattended at
Tier 2+, defeating lattice-guided iteration *under human oversight*.

**The fix** (`dev-kernel/bin/lifecycle.py` `run_critic` + `dev-server/dispatch.py`): the critic is
extracted into one shared `run_critic` (the single place validation runs). The done-morphism calls it when
a verifier is supplied; the **Tier-1 dispatcher calls it eagerly** — so the cell is critic-validated at
Tier 1 and the operator's later *plain* `done` (no verifier to hand-supply) passes `gate-signal` because a
prior critic already validated the cell ("the board cannot disagree with the lattice"). A critic refusal
re-authors against the feedback, bounded, exactly as the unattended path does.

## Answer key

| Check | Asserts |
| --- | --- |
| **T1** | At Tier 1 the critic RUNS on a structured spec → the cell reaches `validated` with a critic-minted signal (not the old `instantiated` livelock). |
| **T2** | The ticket parks at `in-review` (not `done`) — acceptance is the human's, the cell's validity is the critic's. |
| **T3** | The operator's PLAIN `done` approval (no verifier supplied) then SUCCEEDS — `gate-signal` passes because a prior critic validated the cell. |
| **T4** | The iterate loop runs at Tier 1: a PROSE spec is REFUSED by the real rubric → the cell stays `instantiated` and the ticket returns to `active` to re-author (the reward-hack teeth bite at Tier 1). |
| **T5** | The reward-hack boundary holds: the Tier-1 signal is critic-minted (actor `cell-validator`), never worker-forged. |

`python3 evals/tier1-acceptance-gate/replay.py` → exit 0. Stdlib only; Python 3.8+.
