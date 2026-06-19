# dev-kit-app — the application family kit (the boundary proof)

A second `dev-factory` family, whose real purpose is the kernel/kit boundary's **falsification test** (TDD §5): adding it required **zero edits to `dev-kernel`**. A different family — `app` instead of `corpus` — with its own ontology, rubric manifest (`test-suite`, `contract-tests`), validation harness (a passing test suite, not a doc check), and dispatch policy (bisect for bugs, a tracer-bullet team for capabilities) — all bound through the *same* kernel contracts (`kit.schema.json`, `adapter.schema.json`, `dispatch-policy.schema.json`).

If adding this kit had required changing a kernel bin or schema, the boundary would have leaked. It didn't:

```bash
python3 ../dev-kernel/bin/check-kit-conform.py kit .   # exit 0 = binds the kernel, forks nothing
```

That a `corpus` kit and an `app` kit coexist over one unchanged kernel is the architecture's central claim, made checkable.

## Bind it — step by step

To run dev-factory with the **app** family (capability/protocol cells validated by a passing test suite):

```bash
# 1. install dev-kernel + dev-kit-app (project-local); 2. init the instance:
python3 ../dev-kernel/bin/lattice.py init --dir src/<project>/.factory
# 3. bind THIS kit when you start the server:
DEV_FACTORY_KIT=$PWD DEV_FACTORY_DIR=<repo>/src/<project>/.factory \
  DEV_FACTORY_HEARTBEAT=1 uvicorn dev-server.app:app --port 8731
```

Now capability/protocol cells validate against `test-suite-check` (the runner's real exit status), and bug tickets dispatch as a `bisect` loop per `dispatch-policy.json`. Sample prompt: *"create a ticket to advance the auth-service capability cell"*.

## Building whole apps — shells, the render gate, and factory-authored verifiers (0.4–0.5)

Stress-testing the app kit on four real apps grew it from "validate a module" to "build, assemble, and validate a whole runnable app":

- **The integration shell is factory-authored at the product root.** A `capability.*.shell` cell uses **single-file authoring** (`{ slug: "shell", mode: "single-file", entry: "index.html" }`) — its `index.html` lands at `src/<project>/index.html`, not a `../shell/` module dir. The worker gets a *bootstrap* prompt ("the modules are already built — import + mount them"), not a re-author of the whole assembly.
- **The render-coherence gate** (`bin/render-check.mjs`, adapter `render-coherence` on `capability.*.shell`) executes the shell's on-load path headlessly against a recording mock WebGL2 context + a DOM shim, asserting the app actually **renders a frame** — a WebGL draw **or** mounted DOM. It composes the static `bin/app-shell-check.mjs` floor (canvas/mount-root + every import resolves). Honest limit: it verifies the render *path*, not real-GPU pixels (a browser/SwiftShader harness is the optional escalation).
- **Factory-authored verifiers (the #2 fix).** Per-cell `verify.mjs` used to be a mock `ready === true` stub — so "validated" meant "exports `ready`," not "implements the spec." On a real build, the **rubric-architect now authors each cell's real, spec-derived `verify.mjs` first** (gate-permitted via `gate-verifier --allow-verify`; the module worker stays denied), then the module is graded against it. It catches real deviations (it caught a module that shipped `storageGet` instead of the spec'd `saveForge`) and self-corrects on re-build.

See **`../docs/USAGE.md` › Workflow 3** for the end-to-end whole-app build, and `../docs/2026-06-18-app-build-campaign-learnings.md` for what the campaign taught.

## Also ships: the `ui-layout-decomposer` skill

Building shippable apps includes laying out their UIs, so the app kit ships a UI-layout decomposition skill (`skills/ui-layout-decomposer/`). It carries the **two-axis method** developed while building the dev-server cockpit — **OUTSIDE-IN** (macro→micro layout: frame → regions → groups → atoms) × **INSIDE-OUT** (feature-actions → feature-surfaces: verbs → bindings → feedback → coherence) — as a **gated rubric** (`A1·A2·B1·B2` are gates; the rest reviews) plus an **ASCII-wireframe library** of four shell archetypes: `productivity-shell` · `saas-dashboard` · `marketing-site` · `mobile-app`. Three modes: **DECOMPOSE** (read a UI → named region map + a two-axis grade) · **DESIGN** (intent → wireframe) · **GRADE**. It's a general technique — kept here because UI layout is app-building knowledge, not a kernel concern (`check-kit-conform` is unaffected: a skill is not a kernel fork).
