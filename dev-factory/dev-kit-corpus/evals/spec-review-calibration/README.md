# spec-review calibration — the answer key

Calibration for spec-author's **REVIEW** (the `spec-quality` gate **+** the `spec-council`). It closes the
councils' named blind spot: the kernel held its *gates* to planted-defect evals, but the new *council's*
verdict was un-calibrated model judgment with no falsifiable replay — and Elon M.'s *"no fixture shows the
council out-performs a single validator"* went unanswered. This fixture set is the answer.

`check.py` asserts the **deterministic** contract (run in CI). The **model** half — does the council actually
catch each `council/` defect? — is the table below: a recorded baseline a judge runs **cold** against the
fixtures (the key lives here, never inside a fixture, so a judge run stays honest).

## `fixtures/gate/` — the gate must REJECT each (deterministic)

| Fixture | Planted defect | Caught by (gate dimension) |
|---|---|---|
| `prose-only-criterion` | an acceptance criterion that is prose, not a `check`/`rubric_cell` | `criteria-checkable` |
| `no-non-goals` | no `non_goals` declared | `non-goals-present` |
| `wrong-layer` | the cell is `rubric.*`, not `spec.*` | `schema-valid` (layer == spec) |
| `unsound-decomposition` | a parent criterion (`ex-css`) covered by no child | `decomposition-entailment` |
| `unscored-criterion` | a criterion binds a `rubric_cell` but names no scoring dimension (`scored_by`) | `criteria-rubric-coverage` (declaration floor) |
| `phantom-dimension` | a `scored_by` names a dimension the (resolvable) bound rubric does not have | `criteria-rubric-coverage` (resolved on disk) |

## `fixtures/council/` — the gate PASSES each; only the lens catches it (the proof the council earns its seat)

Each is mechanically sound — `schema-valid`, `criteria-checkable`, `non-goals`, `rubric-binds`, (where
present) `decomposition-entailment`, `skill-shape` all pass. A gate-only / single-`cell-validator` review
waves them through. The defect is a judgment one:

| Fixture | Gate verdict | Judgment defect | Lens that must BLOCK | Expected council verdict |
|---|---|---|---|---|
| `hackable-criterion` | PASS | `cc-01` checks contrast for the **default** pair only — an impl that hardcodes one good pair and fails every other pair satisfies it without the intent (ALL pairs) | **`critic-spec-hackability`** | BLOCKED |
| `incomplete-coverage` | PASS | `tp-01` is the happy path only — no criterion for localStorage-unavailable, a corrupt stored value, or the first-paint flash the intent implies | **`critic-spec-completeness`** | BLOCKED |
| `weak-entailment` | PASS | the decomposition *covers* every parent criterion, but `rt-03` ("round-trips identically") is "covered" by a child whose acceptance grades only "accepts valid JSON" — strictly weaker; coverage, not entailment | **`critic-spec-entailment`** | BLOCKED |
| `mismapped-coverage` | PASS | `cc-01` asserts EVERY pair clears AA, but its `scored_by` dimension `contrast-default-pair` scores only the **default** pair — a dimension IS named (gate passes), but it measures a narrower observable than the criterion demands | **`critic-spec-coverage`** | BLOCKED |

## Run

```bash
python3 dev-factory/dev-kit-corpus/evals/spec-review-calibration/check.py   # exit 0 = the deterministic contract holds
```

A judge baseline (the model half): dispatch `dev-kernel:spec-council` on each `council/` fixture and confirm
the named lens raises a Critical/Major and the verdict is BLOCKED — the recorded expectation above. If the
council ever passes a `council/` fixture, either the council regressed or the defect is weaker than the key
claims; re-calibrate. (Cold-run discipline: the key is in this README, not in any fixture.)

**Recorded baseline (2026-06-15).** A cold `critic-spec-hackability` run on `hackable-criterion` (the fixture
only, not this key) independently found the defect: *"cc-01 pins only the default pair; a generator that
hardcodes one good pair and emits every other role at 2:1 passes it while failing the 'every pair' intent"* —
**Critical**, and prescribed the universal/property fix. The lens caught what the gate passed: the council
out-performs the gate, demonstrated, not asserted.

**Recorded baseline (2026-06-26).** A cold `critic-spec-coverage` run on `mismapped-coverage` (the fixture
only, not this key) independently found the defect: *"`cc-01`'s observable is 'every generated color pair
clears WCAG AA', but `scored_by: [contrast-default-pair]` measures the default pair only — pairs[1..n] are
entirely unmeasured; the named dimension scores a strictly narrower thing than the criterion's quantified
set"* — **Critical**, verdict **BLOCKED**. The gate passes the fixture (a non-empty `scored_by` is named, and
the fictional rubric doesn't resolve so the phantom check can't fire); only the coverage lens catches the
narrowed observable. The seventh lens earns its seat, demonstrated, not asserted.
