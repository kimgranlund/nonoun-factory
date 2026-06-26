# rubric-teeth — the rubric meta-verifier earns its seat

A rubric is the verifier a spec/PRD/pattern is graded against. A rubric cell becomes `validated` — trusted
to gate — only when it passes its own **meta-verifier**, `bin/rubric-check.py`, whose exit status mints the
signal. So the legitimacy of every downstream signal rests on rubric-check.py having **teeth**.

It used not to. The first cut string-matched for `[gate]` / `pristine` / `calibration` anywhere in the
rubric JSON, so a rubric carrying the *words* and no real gate passed — a presence-predicate posing as
calibration (harness-council **verifier-integrity CRITICAL**; promoted from latent to blocking once the
autonomous triager began binding rubrics unattended).

The fix: rubric-check.py now **runs the rubric's mechanized gate against a labeled exemplar set** and
requires it to DISCRIMINATE — reject the planted-defect exemplars (on their named dimension) and pass the
gate-clean ones, deterministically, spanning both outcomes. Labels are *checked against real gate behavior*,
never trusted: a hollow gate that passes everything fails on the `fail` exemplars; an all-`pass` set with no
planted defect fails the span requirement. The exemplar sets are **plugin-static** (`rubric/exemplars/`,
resolved relative to the kit), so a runtime worker cannot author a rubric *and* forge its own passing
calibration — a new validated verifier requires a CI-reviewed kit-level exemplar set.

`check.py` is the falsifiable proof + the regression guard:

- **shipped/** — `spec-quality`, `prd-quality`, `pattern-quality` each PASS their meta-verifier. spec/prd
  reuse the `spec-review-calibration` gate fixtures (the gate is `spec-quality-check.py`); pattern uses the
  authored set under `rubric/exemplars/pattern-quality/`. If a real rubric rots into a presence-predicate —
  a hollowed gate, a deleted or mislabeled exemplar set — this fails in CI before it can grade anything.
- **hollow** — a shape-only rubric (the right words, no gate or exemplars) is REJECTED. The teeth contrast.

The engine itself (a hollow gate, a teeth-less all-`pass` set, a worker-writable pristine reference, a
non-existent gate script all rejected) is covered by `bin/rubric-check.py selftest`, run in CI alongside the
other kit verifiers.

Run: `python3 dev-factory/dev-kit-corpus/evals/rubric-teeth/check.py` — exit 0 = the contract holds.
