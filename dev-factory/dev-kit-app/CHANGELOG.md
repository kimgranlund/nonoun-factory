# Changelog

All notable changes to **dev-kit-app** are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/); versioning is [SemVer](https://semver.org/).

## [0.4.1] — 2026-06-18

### Fixed

- **render-check's headless DOM/host shim covers more standard browser surface** — found by dogfooding the gate on a real shader-playground shell. Added `replaceChildren`/`replaceWith`/`before`/`after`/`cloneNode`/`insertAdjacent*` to the element shim (a shell using the standard `replaceChildren` no longer trips the gate as "render path THREW"), and a **working in-memory `localStorage`/`sessionStorage`** (a faithful browser has it; an app that round-trips save→load now runs cleanly instead of emitting a caught-`ReferenceError` warning). New selftest case (3b) locks the coverage in. The focused shim still fails clearly on genuinely unsupported APIs — this only closes the gap on common, standard ones.

plugin.json 0.4.0 → 0.4.1.

## [0.4.0] — 2026-06-18

### Added

- **The render-coherence gate (`bin/render-check.mjs`) — the kit can now tell an app that RENDERS from one that merely ASSEMBLES.** `app-shell-check` proved the shell assembles (canvas + module entry + every import resolves) but not that it *runs*: an assembled page can still throw on load, link a program and never draw, or wire a uniform that isn't there — passing every static check and rendering nothing. `render-check` **composes** the static app-shell floor and then **executes** the shell's on-load path headlessly against a **recording mock WebGL2 context + a focused DOM shim**, asserting the render contract: the entry runs without throwing, a linked program is `useProgram`'d, and a draw call is issued. It drives both an inline-script shell and the `main.mjs`-exports-`mount(root)` integrator convention. The slug-targeted **`render-coherence`** validation adapter binds `capability.*.shell` to `render-check` (it **supersedes** the static `app-shell` adapter, which composes inside it and remains a standalone tool). Proven by `dev-server/evals/render-coherence-gate/` (R1–R5) + `render-check --selftest`; CI-wired.
- **Honest limit (deliberate):** the mock GL reports compile/link SUCCESS, so this gate verifies the render PATH executes + draws against a conformant GL — it does NOT catch GLSL-compile errors or verify pixels. Real-GPU fidelity needs a browser/SwiftShader (Playwright) or headless-gl harness — a **heavy dependency** that would break the marketplace's zero-dependency, copy-alone-install property — so it stays an **optional escalation**, not the always-on CI gate. `render-check` is Node-builtins only and runs anywhere `node` does.

### Changed

- `bin/app-shell-check.mjs` exports `checkShell` (composed by `render-check`) and runs its CLI only when invoked directly. The `app-shell` adapter's slug=shell binding is superseded by `render-coherence`; the `app-shell-gate` eval is renamed `render-coherence-gate` and extended (R4 proves the runtime gap — assembles-but-never-draws — the static floor cannot see).

plugin.json 0.3.2 → 0.4.0.

## [0.3.2] — 2026-06-18

### Added

- **The app-shell coherence gate (`bin/app-shell-check.mjs`) — the kit can now tell a runnable APP from a re-export barrel.** The kit grades capabilities as pure ES modules imported headlessly by their sibling `verify.mjs`, which proves the *logic* but not that the modules *assemble* into a running app. A real shader-playground build exposed the gap: every capability validated, the `app` cell degenerated to `export * as core/ui/persistence`, and the product shipped **no browser entry** (and the pieces didn't even cohere — a `#version 300 es` compiler vs a GLSL 1.00 default shader). A new slug-targeted `app-shell` validation adapter binds **`capability.*.shell`** to `app-shell-check`, which statically verifies the entry (`index.html`) is a coherent runnable assembly over the built modules: a `<canvas>`, a `<script type="module">`, it imports the product, and **every import in the reachable module graph resolves** to a file the build produced. Backward-compatible — the generic `capability-harness` still grades every other capability (the dev-server's `_kit_verifier` gained slug-specificity: a slug-targeted adapter wins over the layer-default). Proven by `dev-server/evals/app-shell-gate/` (A1–A4) + `app-shell-check --selftest`; CI-wired.
- **Honest limit:** this is a *static* gate — it does not prove the app **renders**. Runtime/semantic coherence (a fragment shader for the wrong GLSL version, a uniform-name mismatch) needs the page executed — a **browser/headless-gl harness adapter** (puppeteer / headless-gl + screenshot-diff), the next adapter on the roadmap. This gate is its floor, not its ceiling.

plugin.json 0.3.1 → 0.3.2.

## [0.3.1] — 2026-06-17

### Added

- **`authoring[].output_root`** — the kit now declares WHERE a layer's multi-file CODE lands relative to the instance dir (`.factory/`). The `capability` layer sets `output_root: ".."`, rooting product source OUT of `.factory/` into the clean project tree (`src/<project>/<capability>/`), beside its sibling `verify.mjs` — so a build emits a navigable, runnable source tree instead of burying code inside the harness state. Read by dispatch's `_asset_rel`; **zero kernel edits** (the field is kit-local, the kit-conform boundary holds). The default (absent `output_root`) keeps a layer's asset inside `.factory/`, so dev-kit-corpus is unaffected.

plugin.json 0.3.0 → 0.3.1.

## [0.3.0] — 2026-06-15

### Added

- **`skills/ui-layout-decomposer/`** — the kit now ships a UI-layout decomposition skill, because building shippable apps includes laying out their UIs. It carries the **two-axis method** developed while building the dev-server cockpit: **OUTSIDE-IN** (macro→micro layout: frame → regions → groups → atoms) × **INSIDE-OUT** (feature-actions → feature-surfaces: verbs → bindings → feedback → coherence), as a **gated rubric** (`A1·A2·B1·B2` gates, the rest reviews) plus an **ASCII-wireframe reference library** of four shell archetypes — `productivity-shell` · `saas-dashboard` · `marketing-site` · `mobile-app` — each with a named-pattern vocabulary. Modes: DECOMPOSE (read a UI → region map + grade) · DESIGN (intent → wireframe) · GRADE. A general technique (not app-specific); kept in the app kit since UI layout is app-building knowledge. `check-kit-conform` is unaffected (a skill is not a kernel fork).

## [0.2.0] — 2026-06-15

The app family builds **real, shippable, multi-file software** (the DF-9 fix), graded by per-cell harnesses.

### Added / Changed

- **Multi-file code authoring** — `kit.json` gains a top-level `authoring` declaration: a `capability` is a real source **directory** (`{layer}/{slug}/`), not one `.md`. The dispatcher (`dispatch.py _authoring_for`) routes such a cell to a multi-file authoring prompt (industrial module boundaries, named exports, pure-logic ES modules + a thin shell). The kit/kernel stay generic; `check-kit-conform` ignores the kit-local `authoring` field.
- **The capability verifier is the per-cell critic harness** — the `capability` validation adapter's verifier is now `["node", "{asset}/verify.mjs"]`: each capability is graded by its own `verify.mjs` (planner-authored, worker-deny via dev-kernel 0.2.4), exit-status-minted by `validate.py`. This is the proven dark-factory-test pattern (a pristine reference + checkable `[gate]` predicates the worker can't see). The integrator cell `capability.system.app` uses the same mechanism as the **SHIP** gate (composes every capability + the spec's acceptance + a real-browser smoke).
- **A spec gate for the family** — a `spec`-layer validation adapter asserts the spec declares a real acceptance contract (`acceptance_criteria` + `non_goals`), so MILESTONE 1 is a measurable gate, not a file-exists check.
- Proven by the `/debug/` harness + the `debug-coldstart` replay (brief → 3 dynamic milestone rubrics → per-capability code cells → the integrator → SHIPPED, with bi-directional spec revision). plugin.json 0.1.0 → 0.2.0.

## [0.1.0] — 2026-06-14

Initial cut — the app family kit: the second family binding the kernel's contracts (the "Fly" milestone — a new family with zero kernel edits). Ontology · rubric manifest · the test-suite validation verifier · dispatch policy · seed patterns; `check-kit-conform` proves the boundary holds.
