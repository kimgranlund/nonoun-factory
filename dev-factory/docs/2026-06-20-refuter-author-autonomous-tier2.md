# Refuter-author — the autonomous producer for earned Tier 2

_Last reviewed: 2026-06-20._

The keystone work (re-audit rounds 1–5, `2026-06-20-harness-council-reaudit.md`) made the **false-pass
measurement unforgeable**: a refuter counts toward `false_pass` (→ Tier 2) only if its sidecar is
`measuring: true`, which the server stamps only after a behavioral refute set clears calibration. But the
behavioral refute set itself was **hand-authored** — so a cell stayed honestly `unmeasured` (Tier 1) until a
human wrote one. **Tier 2 was earnable, but not _autonomously_.** This change adds the missing producer.

## What landed

**The producer — `author_refuter` / `author_refuters` (`dispatch.py`).** A gate-BLIND rubric-architect role
that authors the cell's behavioral `refute` set into `coordination/verify-spec/<cell>.json` from the SPEC.
Wired into the heartbeat (headless only, one cell per tick, budget-bounded): for each validated CODE cell
whose refuter is still liveness-only (`refute_author_frontier`), it dispatches the author, then re-runs
`produce_refuter`, which UPGRADES the cell's liveness floor to MEASURING iff the authored set clears calibration.

**The boundary — `REFUTE_AUTHOR` (`_gates.py`) + `gate-verifier --allow-refute`.** The inverse of the
verifier-author: it may write `coordination/verify-spec/*` (the oracle source) and is denied `verify.mjs`
(the gate), the refuter sidecars, signals, the lattice/ledger, and the product barrel. The two flags are
mutually exclusive — a verifier-author writes the gate, a refute-author writes the oracle, never one dispatch both.

**The calibration — the three-proof AND-gate in `produce_refuter`** (none is the author's say-so):

1. `is_behavioral` — the set invokes an export and asserts a value (no tautology / `typeof` probe).
2. `_refuter_discriminates` — it actually DISAGREES with two typed poison stubs (a random number AND a random string).
3. `independent_of_gate` — it carries a behavioral check the gate does not already enforce. The independence
   baseline is the **server-read gate SOURCE**, NOT the verify-spec's `acceptance` field — that field is
   worker-writable under `--allow-refute`, so trusting it would let an author declare `acceptance: []` and disarm
   the structured arm (round-6 CRITICAL). On the producer path `produce_refuter` passes `acceptance=[]` and relies
   on the gate-source arm; the structured arm applies only on the self-heal path, where `fold` computes it server-side.

This calibration catches a vacuous set, a poison-agreeing set, and a **positive-form literal** gate-copy. It does
NOT catch a semantic copy of an opaque **data-driven / negative-form** gate — the documented residual below.

**The human-glance gate — PROVENANCE (round 6, the load-bearing safety mechanism).** Because the calibration is
partial for opaque gates, an autonomously-authored oracle is not trusted to *self-promote* the loop to lights-out.
`author_refuters` records provenance in a server-owned, worker-protected registry (`run/autonomous-oracles.json`),
and `produce_refuter` STAMPS each upgraded oracle `autonomous: _is_autonomous_cell(...)` into the worker-protected
refuter sidecar — so the stamp lands wherever the measuring upgrade happens (the author pass OR a later sweep).
Provenance follows the **write, not the nominal target**: `author_refuters` diffs the verify-spec dir before/after
each dispatch (`_verify_spec_hashes`) and registers every cell the worker actually authored — closing a cross-cell
**laundering** forge (the `--allow-refute` gate permits writing any verify-spec, so a dispatch targeting X could
write sibling Y's; registering only X would mislabel Y trusted). `run_refuter` propagates the flag; the new
`ledger.trusted_refuter_checks` counts only NON-autonomous (human-vetted / server-folded) measuring checks; and
`autonomy.tier_for` requires at least one TRUSTED check to grant unattended Tier 2. So an autonomous oracle MEASURES
(it builds the visible false-pass rate + a track record) but **cannot, by itself, earn unattended Tier 2** — the
ladder, not the producer, decides, enforced in code rather than prose.

The self-heal RE-ARM uses the same AND-gate against the just-strengthened gate, so a fold cannot re-certify a fresh
refuter that only restates a folded check; a fold-armed oracle is server-trusted (not stamped autonomous).

## Why automation does not weaken the gate

The calibration is identical for a human- and an auto-authored set, and the provenance gate makes a self-authored
clean rate insufficient for lights-out on its own. A lazy or adversarial *human* refute-author had the same
gate-copy option, filtered the same way — but a human-vetted oracle is the trusted check that earns Tier 2, where
an autonomous one is not. Over-rejection is fail-safe throughout — a wrongly-rejected refuter just doesn't earn
Tier 2; it never falsely grants it. The mock author is an honest no-op (it cannot synthesize a domain contract),
so a mock build never fabricates measurement.

## Proof

`dev-server/evals/earned-autonomy/replay.py` (needs `node`):

- **H6a** — a **positive-form** gate-copy is rejected by the server-trusted gate-SOURCE arm → liveness-only.
- **H6b** — a **data-driven** gate-copy DOES measure (the calibration is partial — the documented residual); it is
  the **provenance gate**, not the calibration, that keeps it from earning Tier 2.
- **H7** — a validated cell sits liveness-only / `unmeasured` (Tier 1); a gate-blind refute-author (modeled by a
  fake adapter) writes a behavioral set; `produce_refuter` UPGRADES it to MEASURING and `author_refuters` STAMPS it
  `autonomous: true`. It **measures** — false_pass is a real, visible 0.0 — **but the family stays Tier 1**: an
  autonomous oracle cannot self-promote. A **human-vetted** oracle on a sibling cell is the TRUSTED check that lifts
  the family to Tier 2. The ladder, not the producer, decides.

Plus `verify_gen.selftest` (the `independent_of_gate` arms), `dispatch.selftest` (the frontier, the mock no-op, the
upgrade path, the positive-form gate-copy rejection, `_mark_autonomous`), `ledger.selftest`
(`trusted_refuter_checks`), and `autonomy.selftest` (the tier gate).

## The honest residual (the limit on fully-unattended Tier 2)

The static `independent_of_gate` is **complete only for positive-form-literal gates** (the gate-SOURCE arm). It does
NOT catch a SEMANTIC copy of an opaque **negative-form** (`if (compute(2,3)!==5) exit`) or **data-driven**
(`for ([a,b,w] of [[2,3,5]])`) gate — the shape a headless rubric-architect's free-form `verify.mjs` often takes.
There, a refute set re-testing the gate's own inputs **measures** a fake 0.0. Two further weaknesses the council
(`2026-06-20-refuter-author-council.md`) surfaced and this build does NOT fully close: the author's blindness is
only **prompt-level** (the dispatch runs in the project root with the gate readable), and the operational catch
(`run_refuter` → incident → demote) **cannot fire on a systematically gate-copying oracle** — it never disagrees.

**What makes it safe anyway: the provenance gate.** Regardless of the calibration's partiality, an autonomously-
authored oracle is `autonomous: true` and `tier_for` refuses it unattended Tier 2 on its own. So the worst case — a
self-authored gate-copy minting a fake 0.0 — buys the loop a *measurement it can show a human*, **not** a
self-granted lights-out tier. Promotion to unattended Tier 2 requires a TRUSTED (human-vetted or server-folded)
oracle. This is the doc's earlier "stay gated on a human glance," now enforced in code (`autonomy.tier_for` +
`ledger.trusted_refuter_checks`), not prose.

**FULL autonomous Tier 2 — the gate-agnostic independence proof (LANDED, harness-council round 7).**
`dispatch._mutation_independent` is the trust upgrade that drops the provenance cap for an oracle that PROVES it is
independent of the gate: it catches a gate-PASSING defect the gate misses — i.e. there exists a server-generated
text-mutant `M'` of the real module where the gate `G(M')` PASSES but the refuter `R(M')` FAILS. A gate-copy `R`
agrees with `G` on every mutant → no witness → not proven (fail-safe). It RUNS the real gate (never parses it), so
it works on the opaque data-driven/negative-form gates the static `independent_of_gate` arm cannot inspect. When it
finds a witness, `produce_refuter` stamps `mutation_verified: true` and `ledger.trusted_refuter_checks` counts the
check (`autonomous is not True OR mutation_verified`), so an autonomously-authored oracle can earn unattended Tier 2
with **no human** — `/loop`-driven lights-out becomes reachable hands-off.

Forge-resistance + the honest bar (round-7 council):
- **Forge-resistant:** `G` and `R` both run via STDIN-piped node — the worker's module can't read the harness source
  to tell them apart, so it can only suppress a witness (fail-safe), never selectively fake `G`-pass + `R`-fail.
- **Decoy close:** `_gate_scoped_refute` confines the proof to the gate's CONTRACT surface (refute assertions calling
  only gate-declared exports or JS globals), so a witness cannot ride a worker-invented non-spec export (the `_k`
  tripwire). Proven by eval **H10**.
- **Double-bound trust:** `mutation_verified` (a scoped witness) is necessary but not alone sufficient — the live
  `run_refuter` ALSO re-checks the oracle against the REAL module each epoch, and a weak/false oracle that fails the
  real module self-incidents → mechanical demotion. A forged witness requires an oracle that fails reality, which
  the re-check catches.
- **The bar is honest + bounded:** a witness proves `R` is INDEPENDENT of the gate (not a gate-copy) — a strictly
  stronger property than the bare human-authored `trusted` path, which proves nothing. It does NOT prove `R` is an
  EXHAUSTIVE oracle against every adversarial special-case overfit (no static check can, for an opaque gate; the
  mutants are single-edit perturbations, not wholesale gaming rewrites). So `mutation_verified` trusts an autonomous
  oracle at the SAME bar the human path uses — a documented residual the human path shares, bounded by the operational
  re-check. Proven by eval **H9** (independent → Tier 2) + **H7** (a tight-arithmetic oracle finds no witness → stays
  provenance-gated, the safe fail-negative).
