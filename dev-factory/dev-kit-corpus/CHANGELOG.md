# Changelog

All notable changes to **dev-kit-corpus** are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/); versioning is [SemVer](https://semver.org/).

## [0.3.2] — 2026-06-26

### Added (rubric-teeth guards the verifier-OF-verifiers too)

- **`evals/rubric-teeth/check.py` now asserts `rubric-quality` (the kernel verifier-of-verifiers) meets the
  structural floor it sets** — a `[gate]` dimension naming a `mechanized_by` gate, and a `pristine_reference` with
  `writable_by_worker: false`. The council noted the standard the rubric-architect scores new rubrics against was
  itself a presence-predicate; dev-kernel 0.2.29 made it conformant, and this regression-guards it in CI so it can't
  rot back. The structural floor is what `rubric-check.py` mechanizes; the deeper (higher-order / calibration) dimensions
  remain the calibrated critic's job. plugin.json 0.3.1 → 0.3.2.

## [0.3.1] — 2026-06-25

### Changed (the rubric meta-verifier earns its teeth — harness-council verifier-integrity CRITICAL)

- **`bin/rubric-check.py` rewritten from a substring scan to a demonstrated-teeth check.** A rubric cell's
  `validated` signal is minted from this meta-verifier's exit status, so the loop's legitimacy rests on it.
  The old cut string-matched for `[gate]`/`pristine`/`calibration` ANYWHERE in the rubric JSON, so a rubric
  with the *words* and no real gate passed — a presence-predicate posing as calibration (promoted from latent
  to blocking once the autonomous triager began binding rubrics unattended). It now **runs the rubric's
  mechanized gate against a labeled exemplar set** and requires it to DISCRIMINATE: reject the planted-defect
  exemplars (on their named dimension), pass the gate-clean ones, deterministically (run-twice), spanning both
  outcomes. Labels are checked against real gate behavior, never trusted — a hollow gate that passes everything
  fails the `fail` exemplars; an all-`pass` set fails the span requirement.
- **Reward-hacking hardening (council H3):** the exemplar set is bound to the rubric's own cell-id slug (no
  borrowing another rubric's proven set), exemplar paths are plugin-root-contained (no `..`/absolute escape to
  worker-writable instance state), and the gate must resolve to a real plugin `bin/` script (no arbitrary
  command). The exemplar sets are plugin-static — combined with the kernel's kit write-protection (dev-kernel
  0.2.28), a runtime worker cannot author a rubric AND forge its own passing calibration.
- **New labeled exemplar sets** under `rubric/exemplars/{spec,prd,pattern}-quality/`: spec/prd reference the
  `spec-review-calibration` fixtures (the gate is `spec-quality-check.py`); pattern uses authored good/defect
  exemplars (each defect removes one load-bearing property: provenance, falsifiability, structured shape).
  prd-quality gains a `calibration` block + `pristine_reference`.
- **New eval `evals/rubric-teeth/`** (CI-wired): every shipped rubric PASSES its meta-verifier with demonstrated
  teeth, and a shape-only rubric is REJECTED — the falsifiable proof the presence-predicate hole stays closed.
- Native (no kernel edit; `check-kit-conform` clean). plugin.json 0.3.0 → 0.3.1.

## [0.3.0] — 2026-06-15

### Added

- **`rubric/prd-quality.rubric.json`** — the verifier for a **PRD** cell (the product from the **outside-in**), the upstream sibling of `spec-quality` (inside-out). Gate dimensions (a PRD is still a contract-bearing spec artifact: `schema-valid` · `user-acceptance-checkable` — every acceptance criterion is USER-FACING + checkable · `non-goals-present`) + review dimensions that are the outside-in judgment: `target-users-and-jobs` (who + jobs-to-be-done), `ux-requirements` (the experience the user needs), `outside-in-acceptance` (doneness as a usage narrative the SPEC must entail), `product-coherence` (one product, not a feature pile). `facing: outside-in`, `binds_to_layer: spec`. The `/debug/` cold-start seeds it as the MILESTONE-1 gate (PRD → SPEC → CAPABILITY → SHIP). plugin.json 0.2.0 → 0.3.0.

## [0.2.0] — 2026-06-15

### Changed

- **`spec-quality-check.py` validates SKILL-format specs.** The gate now reads a spec asset that is a **SKILL-format artifact** (front-matter intent surface + brief + the embedded ```json contract + optional `references/`), a **folder** (`spec/<slug>/SKILL.md`), or the legacy json-only contract — the embedded contract is the single source of truth either way, so every existing gate (schema-valid · criteria-checkable · rubric-binds · non-goals-present · decomposition-entailment) is unchanged. Added a `skill-shape` gate: when front-matter is present, the skill surface and the machine contract must AGREE (`name` present, `description` present, the contract `cell`'s slug == `name`); a legacy json-only spec passes it vacuously. Backs dev-kernel 0.2.0's `spec-author` skill; selftest extended (a SKILL-format file, the folder shape, and a name↔cell-slug disagreement).
- **`spec-quality.rubric.json`** notes the SKILL-format asset shape and carries the matching `skill-shape` gate dimension.
- **(0.2.0 council fixes)** `schema-valid` now asserts the cell's layer is `spec` (the spec gate rejects a non-spec cell asset) and **requires a cell id** (a cell-less asset can no longer pass the spec-layer invariant vacuously — the second council pass's hole); two negative selftest fixtures lock both. The `rubric-binds` dimension clarified — the gate checks the *binding*, the rubric-maturity precondition is a lattice invariant (`lattice.py` validity + `gate-ticket-ready`), not this standalone gate.

## [0.1.0] — 2026-06-14

Initial cut — the corpus family kit (the reference family binding the kernel's contracts).
