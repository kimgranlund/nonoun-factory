# Harness-council verdict — the refuter-author / autonomous-Tier-2 change (2026-06-20)

Four critics (reward-hacking, autonomy-trajectory, verifier-integrity, Jake V. scoreboard-independence)
reviewed the task-#20 refute-author. **Unanimous: NOT safe for lights-out as shipped — cap ≤ Tier 2.** The
producer + calibration + fail-safe defaults are real; the autonomous-Tier-2-for-lights-out *claim* is not earned.

## CRITICAL — the independence baseline is worker-controlled AND empty on the live path

`independent_of_gate`'s structured-`acceptance` arm derives "what the gate already enforces" from the
refute-author's OWN writable verify-spec `acceptance` field (`dispatch.py:produce_refuter`), not the real gate —
and `produce_refuter` seeds every verify-spec with `acceptance: []`, so on the live headless path the structured
arm never bites. Independence then rests entirely on the textual gate-SOURCE arm, which misses the data-driven
(`for ([a,b,w] of [[2,3,5]])`) and negative-form (`if (compute(2,3)!==5) exit`) gates the headless rubric-architect
emits (and that the eval's own `GATE` uses). A refute set re-testing the gate's *own canonical inputs*
(`compute(2,3)===5` — derivable from the spec, no gate-reading needed) passes all three proofs → fake 0.0 → Tier 2.

## MAJOR findings (convergent)

1. **The "human-glance" mitigation is documented but NOT enforced.** `heartbeat.py`: `tier = tier_for(d)` then
   `auto = tier >= 2` drives units to `done` unattended the moment the (fakeable) measurement lands. The loop
   self-promotes; the doc's safety sentence is prose, not a predicate.
2. **The operational catch cannot fire on the worst case.** `run_refuter` records an incident only on DISAGREEMENT;
   a systematically gate-copying oracle agrees with every gate-passing module → never disagrees → never demotes →
   permanent, unfalsifiable fake 0.0. The doc calls this "the un-caught case"; it is the *whole* failure mode for
   opaque-gate cells.
3. **H7 proves the plumbing, not the producer.** "Tier 2 EARNED autonomously" is demonstrated by `_FakeRefuteAuthor`,
   hard-wired to write an independent set + populate acceptance so calibration passes by construction. It never
   exercises the real producer against a readable gate.
4. **Blindness is prompt-level only.** The dispatch runs from `project_root` with `verify.mjs` readable; `REFUTE_AUTHOR`
   denies *writing* the gate, not reading it. (Jake V.: "told not to look at the answer key while sitting on it.")
5. **No per-cell `measuring` view / operator override.** Rollups aggregate `measuring` away; a human can't see which
   cells earned measurement nor demote a suspect oracle without editing a gate-protected sidecar.

## The fix (consensus)

- **Break self-promotion (load-bearing):** an autonomously-authored measuring oracle must NOT earn unattended Tier 2
  by itself — enforce the human-glance gate in `tier_for`, not in prose. Provenance-tag autonomous oracles
  (server-side, untamperable) and require a non-autonomous measuring check for Tier 2.
- **Stop trusting the worker's `acceptance`** for the independence decision (server-trusted gate material only).
- **Structural blindness** (highest-leverage, deferred): dispatch the refute-author in a dir scrubbed of
  `verify.mjs`/`index.mjs` so it physically cannot read the gate.
- **Mutation-grade calibration** (deferred, the path to FULL autonomous Tier 2): prove the refute set catches a
  gate-passing defect the gate misses — gate-agnostic. Genuinely hard for opaque gates (needs the gate's accepted
  inputs), hence the provenance gate is the safe interim.

## Round 6 — the provenance gate, and the laundering forge it first missed

The fix landed: an autonomously-authored oracle is server-stamped `autonomous: true` (a worker-protected registry
`run/autonomous-oracles.json` + the `coordination/refuters/*` sidecar), `ledger.trusted_refuter_checks` excludes
autonomous checks, and `autonomy.tier_for` grants unattended Tier 2 only with a TRUSTED (non-autonomous) check. The
**autonomy-trajectory** re-audit confirmed MAJOR-1 CLOSED — an all-autonomous family caps at Tier 1, the
self-promotion chain is broken at `tier_for`.

But the **reward-hacking** re-audit found a NEW CRITICAL the first cut of the provenance gate missed —
**cross-cell laundering**: provenance was registered for the dispatch's nominal *target* cell, while the
`--allow-refute` gate permits writing ANY cell's verify-spec (the per-cell scope was prompt-only). So a dispatch
targeting X could write a sibling Y's verify-spec; Y was never registered → the next sweep stamped it
`autonomous:false` (trusted) → Tier 2. **Closed** by registering provenance for what the dispatch actually WROTE
(diff the verify-spec dir before/after — `_verify_spec_hashes` in `author_refuters`), not the nominal target; the
module worker is gate-denied verify-spec entirely, so the only worker writes there are the refute-author's, every
one now stamped autonomous. Proven by eval **H8** (a laundering adapter writes a victim cell; it is registered, not
the target, and cannot earn Tier 2).

## Round 7 — the gate-agnostic independence proof lands, and the decoy forge it first missed

`_mutation_independent` (the deferred "full autonomous Tier 2" close) landed: an autonomous oracle is `mutation_verified`
→ TRUSTED iff it catches a gate-PASSING defect on a server-generated mutant (a witness G-pass/R-fail), run stdin-piped
(forge-resistant). The **reward-hacking** critic found a CRITICAL — the **decoy-export tripwire**: a worker plants a
non-spec export `_k=()=>7` the gate ignores + a refute `_k()===7`; a `7`→`8` mutant fakes a witness off the worker's
own dead export. **Closed** by `_gate_scoped_refute` (the witness must be on the gate's CONTRACT surface — refute
assertions calling only gate-declared exports); proven by eval H10. The **verifier-integrity** critic rated the proof
SOUND-BUT-WEAK-BAR (one witness over single-edit mutants ≠ adversarial-overfit competence) and flagged the
"full autonomy proven" overclaim — addressed by the gate-scope fix (witness now contract-anchored), honest reframing
("proven INDEPENDENT, not exhaustively competent — the same bar the human path uses, stronger"), and the
**double-bound** trust (a `mutation_verified` witness AND live `run_refuter` agreement on the real module; a weak/false
oracle that fails reality self-incidents → demotion). The reward-hacking re-audit confirmed the decoy CLOSED (rubric > 2).

## Disposition

The system is SAFE in layers: (1) the provenance gate (an autonomous oracle can't self-promote on a fake
measurement); (2) the mutation proof (an autonomous oracle that PROVES gate-independence earns Tier 2 hands-off —
full autonomy for the provable case); (3) the live re-check (a weak/false oracle that fails the real module
self-incidents). The residual — one-witness independence ≠ exhaustive adversarial competence — is fundamental for
opaque gates, shared by the human-vetted path, and bounded by (3). See
`2026-06-20-refuter-author-autonomous-tier2.md` for the as-built design.
