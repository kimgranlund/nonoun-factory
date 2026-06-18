# tier1-strict-gate — opt-in: downstream waits for the human sign-off, cell-by-cell

_Last reviewed: 2026-06-18._

**What it proves.** An **opt-in** policy (`DEV_FACTORY_TIER1_STRICT=1`) that makes Tier 1 *strict*: a
dependent cell is held until its dependency cells are human-**ACCEPTED** (carried by a `done` ticket), not
merely critic-**validated**. So instead of the default — the build flows on validation and tickets park at
`in-review` for async acceptance — the build advances cell-by-cell *behind* the operator's sign-off.

**Where it lives.** This is a **server policy** (`heartbeat.strict_accept_filter`, applied in `on_tick`
when the flag is set and `tier < 2`), layered on top of the kernel's partial order. The kernel still only
requires dependencies `validated`; the policy adds the acceptance wait. It is **moot at Tier 2+**, where the
ticket auto-closes to `done` on validation (so accepted == validated).

**Default is unchanged.** With the flag unset, Tier 1 flows on validation (the general, lattice-guided
iteration under async human oversight). The flag only tightens the gate for operators who want per-cell
sign-off before the build advances.

## Answer key

| Check | Asserts |
| --- | --- |
| **S1** | Dependency `validated` but NOT accepted (no `done` ticket) → `strict_accept_filter` DROPS the dependent (held). |
| **S2** | Once the dependency is ACCEPTED (a `done` ticket carries it) → the dependent is KEPT. |
| **S3** | A no-dependency ticket is always kept (nothing to wait on). |
| **S4** | End-to-end: `on_tick(strict_accept=True, tier=1)` does NOT dispatch the held dependent (cell stays `instantiated`); `on_tick(strict_accept=False)` DOES (cell critic-`validated`) — same lattice, the flag is the only difference. |

`python3 evals/tier1-strict-gate/replay.py` → exit 0. Stdlib only; Python 3.8+.
