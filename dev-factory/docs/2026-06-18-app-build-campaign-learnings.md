# Dark-factory app-build campaign — architectural learnings

_Last reviewed: 2026-06-18._

What we learned by pointing the dark factory at five real apps (`shader-live`, `design-tokens-lab`,
`icon-forge`, `wireframe-studio`, + the redundant `shader-playground`) and building them out. The campaign was
a stress test: each app surfaced or confirmed a weakness, and the high-leverage ones were fixed in place. This
is the forward view on what "the factory builds real apps" actually requires.

## What the factory does well (confirmed)

- **Module authoring.** Given a clear spec, headless workers author genuinely good, decomposed multi-file
  modules — `icon-forge/core` came back as `icons.mjs` (10 real icons) · `params.mjs` · `renderer.mjs` ·
  barrel, all passing a strict contract on the first dispatch. The generator side is strong.
- **Dependency-ordered cascade.** Tier-1 cells validate and dependents proceed on the validated cell (the
  ticket parks for human acceptance). `core → persistence → ui → shell` builds in one armed run, ~10 min, ~4
  dispatches, concurrency 2.

## Weaknesses surfaced, and their status

| # | Weakness | Evidence | Status |
|---|----------|----------|--------|
| 1 | **Shell-authoring gap.** Capability authoring routes every cell to `../{slug}/`, but a shell's `index.html` belongs at the product **root**. The cell's `asset_ref` (`../index.html`) and the authoring layout (`../shell/`) disagreed — dispatch authored to one, validation checked the other. | `design-tokens-lab` shell ticket blocked: *"asset `../shell` absent/empty."* | **Fixed (PR #13).** Slug-specific `single-file` authoring at the root (`_authoring_for` gains slug-specificity; `_asset_rel` resolves `single-file`→`../index.html`). Proven: the factory authored `icon-forge`'s + `design-tokens-lab`'s shells unaided. |
| 3 | **Integrator-prompt vs. lattice mismatch.** The `is_integrator` prompt told the shell worker to author the *whole assembly* (barrel + `main.mjs` + html), conflicting with those already being separate cells. | The shell worker had no coherent task. | **Fixed (PR #13).** A shell-specific bootstrap prompt: *"the modules are ALREADY BUILT as sibling cells — import + mount them at the root."* |
| 12 | **Render gate was WebGL-only.** `render-check` asserted a WebGL draw; 3 of 4 apps are DOM/SVG. | A DOM app would fail "no frame." | **Fixed (PR #12).** An app "renders" if it draws a WebGL frame **or** mounts DOM. Proven on `design-tokens-lab` + `icon-forge`. |
| 2 | **Presence-predicate verifiers (the deep one).** The per-cell `verify.mjs` are mock (`ready === true`). A module reaching `validated` proved only "it exports `ready`," **not** "it implements the spec." | The `design-tokens-lab` modules were good only because the *worker* followed the spec; the *critic* never checked. | **Partially addressed.** We now author a **real** spec-conformance `core/verify.mjs` per app (e.g. icon-forge: ≥6 icons, complete `<svg>`, parametric output, sprite). `core` then validates against a real contract. **Open:** `ui`/`persistence` still mock; and the real verifier is **operator-authored**, not factory-authored. |

## The open frontier — make verification first-class

Weakness #2 is the remaining architectural debt. The loop's legitimacy (the generator/critic split) is only
as real as the critic, and a presence-predicate critic is no critic. Two moves close it:

1. **Real per-cell verifiers as the default**, not mock stubs — the `core` of each app now has one; extend to
   `ui` (drive `mount()` against a DOM shim + assert structure) and `persistence` (pure
   serialize/deserialize round-trip). The render-coherence gate already covers the `shell`.
2. **Factory-authored verifiers.** Today the operator authors the real `verify.mjs` (the rubric-architect's
   job done by hand). The systemic fix is a build step that dispatches the **rubric-architect** to author +
   calibrate the per-cell harness *from the spec* before the capability cell builds — so "validated" means
   "passed a real, spec-derived test" with no human in the verifier loop. Until then, the honest reading: the
   factory **authors** whole apps autonomously, but **rigorous validation** still depends on a human-seeded
   contract for the non-shell, non-core cells.

## Net

After this campaign the factory builds a **whole app end-to-end** — every module *and* the integration shell
authored by workers, the `core` validated against a real contract (`icon-forge`, `wireframe-studio`). The
shell-authoring and DOM-render gaps are closed. The next investment is verifier integrity: real, factory-
authored per-cell harnesses, so the green grid is earned everywhere, not just at `core` and `shell`.
