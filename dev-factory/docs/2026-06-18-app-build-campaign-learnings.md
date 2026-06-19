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
| 2 | **Presence-predicate verifiers (the deep one).** The per-cell `verify.mjs` are mock (`ready === true`). A module reaching `validated` proved only "it exports `ready`," **not** "it implements the spec." | The `design-tokens-lab` modules were good only because the *worker* followed the spec; the *critic* never checked. wireframe-studio's `core` *failed* a real verifier on attempt 1 (a mock check would have passed it) and was fixed on retry — the real gate has teeth. | **Mechanism landed.** Real spec-conformance `core` verifiers proven across the campaign; then made factory-native: a **verifier-authoring dispatch** (`kind == "verifier"` → `_verifier_prompt`, the rubric-architect authoring `verify.mjs` *from the spec*) + `author_verifier()`. **Open:** wire it into the autonomous build loop (run before each capability cell) + the headless verifier-author worktree gate-permit; extend beyond `core` to `ui`/`persistence`. |

## The open frontier — make verification first-class

Weakness #2 is the remaining architectural debt. The loop's legitimacy (the generator/critic split) is only
as real as the critic, and a presence-predicate critic is no critic. Two moves close it:

1. **Real per-cell verifiers as the default**, not mock stubs — the `core` of each app now has one; extend to
   `ui` (drive `mount()` against a DOM shim + assert structure) and `persistence` (pure
   serialize/deserialize round-trip). The render-coherence gate already covers the `shell`.
3. **Extending real verifiers to DOM cells — the learning loop, run on the factory itself.** Pushing
   factory-authored verifiers past the pure-logic cells (`core`, `persistence`) to `ui` taught two things, fast.
   (a) **The verifier-author punted on DOM modules** — pointed at `ui` (functions that take a root element), the
   rubric-architect left the mock `ready` check, because the prompt never said how to test a DOM module with no
   DOM. Fixed: `_verifier_prompt` now guides a `globalThis.document` shim + driving the render functions against
   a mock root (it then produced a real 168-line DOM verifier). (b) **That real DOM verifier immediately caught a
   defect**: the `ui` *barrel* (`index.mjs`) didn't re-export `renderGallery`/etc. — the shell had been importing
   them from the sub-files directly, so the spec-required "barrel surfaces the full API" was quietly violated and
   the mock gate missed it. Two real bugs surfaced by *making the gate real* — the whole point of #2, now true
   across logic AND DOM cells. The capstone re-build pattern (author verifier → re-build module to pass it) fixes
   each; doing it for `ui` (which would also tighten the barrel) is the same recipe applied once more.

2. **Factory-authored verifiers — landed and proven.** The verifier-authoring dispatch (`kind == "verifier"`
   → `HeadlessClaudeAdapter._verifier_prompt`, the rubric-architect authoring `verify.mjs` *from the spec*) +
   `author_verifier()` + the **`gate-verifier --allow-verify` worktree permit** (dev-kernel 0.2.13 — the
   verifier-author may write the harness it authors while signals/lattice stay denied) mean the **factory**
   authors the contract-as-test, not the operator. A live demo confirmed it end-to-end **and immediately found
   a real defect**: a headless rubric-architect authored a real spec-conformance `persistence/verify.mjs` for
   `icon-forge`; run against the mock-validated module it FAILED — *"persistence must export `saveForge`"* — the
   module had built `storageGet`/`storageSet` instead, **deviating from its spec'd contract** while the mock
   `ready` gate rubber-stamped it. The modules cohere with each other (the app runs), but only a real
   spec-derived verifier enforces the named contract. **The one remaining piece:** run `author_verifier` ahead
   of each capability cell *inside the autonomous loop* (it's a callable helper today), and extend past `core`
   to `ui`/`persistence`/`shell`. Then every cell builds against a real, factory-authored, spec-derived gate —
   "validated" earned everywhere, no human in the verifier loop.

## Net

After this campaign the factory builds a **whole app end-to-end** — every module *and* the integration shell
authored by workers, the `core` validated against a real contract (`icon-forge`, `wireframe-studio`). The
shell-authoring and DOM-render gaps are closed. The next investment is verifier integrity: real, factory-
authored per-cell harnesses, so the green grid is earned everywhere, not just at `core` and `shell`.
