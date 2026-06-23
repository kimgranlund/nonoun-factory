---
name: app-factory-phase-d-redteam
stage: red-team
status: complete — 2026-06-22
verdict: BLOCKED (spec-council) · TIER 0 only (harness-council)
---

# Phase D — red-team findings

Two councils over the thin set: the **spec-council** (is the set well-formed?) and
the **harness-council** (is the factory it describes structurally sound?).

**Verdict: BLOCKED — and this is the expected, healthy phase-B outcome.** Both
councils agree the skeleton's *inner loop is genuinely sound* (budget/caps/
done-judge/no-progress all reused verbatim and verified in code), the reuse claims
are *honest at the primitive level*, and every hole sits at the **novel seam where
the simple surface meets the rigorous spine** — exactly where the red-team was
aimed. Thin is not broken; the seam is.

## The convergent wound (5 spec lenses + 4 harness critics → one locus)

**The prose→typed acceptance derivation** (`02-document-model.md:90-94`). When
acceptance originates as prose and the spine derives the typed predicate:

- **No deriver/executor independence.** If the agent that derives a ticket's
  acceptance is in the executor family, the worker shapes its own scoreboard
  *before* the untouchable verify step. The spine makes the **signal** unforgeable
  but takes the **predicate** as a trusted upstream input.
- **No entailment/fidelity check.** Nothing verifies the derived predicate actually
  *entails the prose intent*; a shallow presence-predicate mints an honest-looking
  green.
- **"Confirm" ≠ "author."** AC-02-4's human-confirm is rubber-stamp theater, and
  the "simple surface" thesis structurally steers the human away from the one
  review that would close the gap. **The thesis fights the keystone.**

Net: *the loop cannot lie about whether it passed, but it can arrange what passing
means.* The charter's "the loop cannot lie about being done" is **false as
specified** — it guarantees signal-honesty, strictly weaker than predicate-honesty,
and weaker in exactly the way that matters.

## Four structural findings

1. **The vendor boundary is wrong (Critical).** Half the named reuse —
   `spec-author`, `spec-council`, `critic-spec-*`, `ticket.schema.json`,
   `gate-ticket-ready`, `spec-quality`/`prd-quality`, the `refute-author` +
   `autonomy.py` demotion path, `evals/calibration/` — lives in
   **dev-factory/dev-kernel, NOT harness-forge**. AC-00-3 is false. The machinery
   that would *close* the keystone breach is in a repo `05` doesn't vendor.
2. **"committed" ≠ "validated" (Critical).** Ticket acceptance binds to a
   *committed* (doc-gate-fired) spec, not a *validated* (cell) spec →
   rubric-before-validated-spec. And the regenerate flip doesn't cascade staleness
   to decomposed tickets/signals → stale-but-trusted on the central honesty
   mechanism.
3. **The autonomy ladder has no first rung (Critical).** `false_pass_rate` has no
   refuter to author `refute` events (the refuter lives in dev-kernel) → returns
   `None` forever → `trust_tier` returns `0` forever. "Trust trajectory reused
   as-is" is a gauge with no sensor. The Tier-0 *default* is honest; the
   *escalation* is unbacked.
4. **New assets sit outside the protected perimeter (Major, cap-arming).** Committed
   `spec/*.md`, the `tickets/*.md` acceptance field, `qa.md`, and the app-factory
   ledger live in `projects/<name>/`, NOT under `.agents/harness/`. A worker with
   Write could edit its own committed acceptance. Deny-on-write is assumed-inherited
   but doesn't cover the new paths.

## Cheaper fixes

- PRD/SPEC ordering contradiction (`01:28` non-optional vs OD-01-B skippable).
- `/loop` collides with the built-in `/loop`; OD-00-B is falsely marked
  "Resolved." Namespace **all** commands to `app-{verb}` (every sibling plugin does).
- The outer regenerate loop has no budget cap; knowledge/patterns have no freshness
  discipline; `/status` doesn't render the trust tier; "acceptance" is one word
  doing three jobs (PRD narrative vs SPEC predicate vs ticket bound-predicate).

## Phase-C must-fix backlog (merged, by severity)

1. **Split acceptance origin from execution; require entailment-calibration before
   binding.** Deriver ∉ executor family (enforced by dispatch, not requested in
   prose); the derived predicate carries a calibration record (determinism +
   entailment-to-prose, via vendored `evals/calibration/`) before any verifier
   binds to it; rewrite AC-02-4 to assert *fidelity*, not a confirm click. *(the
   convergent core — H3/H2 + Hackability/Testability/Entailment)*
2. **Fix the vendor boundary.** Add the dev-kernel/dev-kit-corpus authoring +
   refuter + calibration primitives to `05` with real citations (or scope out
   honestly); fix AC-00-3; reword "lighter than dev-factory" → **"same authoring
   rigor, thinner operator surface."** *(Scope C1)*
3. **Bind acceptance to a *validated* spec; cascade staleness on regenerate.**
   Crystallization mints the spec cell to `validated` and records the spec→ticket
   edge with the spec's content hash, so a regenerate flip cascades `stale` to
   every decomposed ticket and invalidates its signals. Add `propagate-staleness`
   to the vendor-and-wire set. *(H1 C1 + H7 C1)*
4. **Ship an independent refuter + a dispatch-time tier consumer + an
   incident→demotion trigger, or scope the autonomy claim honestly** (trajectory
   *displayed* via `/status`, not yet *enforced*; Tier 0 only). *(H6 Critical)*
5. **Map the new committed-corpus assets into the protected perimeter**
   (deny-on-write to the executor); make "guidance buffer never alters committed
   acceptance" a code gate. *(H3 M1/M2)*
6. **Cheap fixes:** PRD/SPEC ordering; `app-{verb}` naming + resolve OD-00-B for
   real; outer-loop regenerate budget cap; knowledge/pattern freshness in `/status`;
   render trust tier; disambiguate "acceptance" (narrative vs checkable) and forbid
   a non-checkable `/goal met` (a PRD destination is met *via its specs*, never
   directly).

## Forks the red-team sharpened (RESOLVED 2026-06-22)

- **The rigor model (OD-00-A).** → **Same rigor, thinner operator surface.** "Even
  simpler" means a prose front door + ~6 commands, not weaker gates; the dev-kernel
  authoring/refuter/calibration machinery is vendored and always on. Applied across
  `00`/`05`.
- **The confirm-to-author UX (OD-02-B).** → **Independent deriver + entailment gate +
  human seals.** A non-executor party derives the typed acceptance; an independent
  entailment+determinism check certifies fidelity; the human *seals* (authorship, not
  a confirm click). Applied in `02`/`03`. The harness-council's recommended
  `agent-ops:agentic-council` pass on the *usability* of the seal model remains a
  recommended next red-team (see README).

## Phase-C hardening — applied

All six must-fixes were applied in the 2026-06-22 hardening pass: acceptance
origin split from execution + entailment gate (`02`/`03`); the split vendor table
naming dev-kernel for the authoring/refuter/calibration half (`05`); validated-not-
committed binding + regenerate staleness cascade (`01`); refuter sensor + tier
actuator, honestly scoped (`03`/`05`); protected perimeter for the new corpus assets
(`02`/`05`); and the cheap fixes — `app-{verb}` naming, PRD ordering, regenerate
budget, freshness discipline, "acceptance" disambiguation (`01`/`04`/`05`).
