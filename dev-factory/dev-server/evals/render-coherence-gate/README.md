# render-coherence-gate — the kit can tell an app that renders from one that merely assembles

_Last reviewed: 2026-06-18._

**What it proves.** A new kit gate closes the "assembles but doesn't render" gap above the static app-shell
floor. `app-shell-check` statically verifies the shell ASSEMBLES — a `<canvas>`, a `<script type="module">`,
it imports the product, and every import in the reachable module graph resolves. But an assembled page can
still throw on load, link a program and never draw, or wire a uniform that isn't there: it passes every
static check and renders nothing. "Assembles" is not "renders."

**The gate.** A slug-targeted `render-coherence` validation adapter binds `capability.*.shell` to
`dev-kit-app/bin/render-check.mjs`, which **composes** the static app-shell floor and then **executes** the
shell's on-load path headlessly — against a recording mock WebGL2 context + a focused DOM shim — and asserts
the render contract: the module entry runs without throwing, a linked program is `useProgram`'d, and a draw
call (`drawArrays`/`drawElements`) is issued. It drives both the inline-script shell and the `main.mjs`
exporting `mount(root)` integrator convention. The kit's adapter matching (`_kit_verifier`) is slug-specific:
the slug-targeted adapter wins over the layer-default, backward-compatibly.

**The honest limit.** The mock GL reports compile/link SUCCESS, so this gate verifies the render PATH
executes and draws against a conformant GL — it does **not** catch GLSL-compile errors or verify the actual
pixels. That needs a real GPU: a browser/SwiftShader (Playwright) or headless-gl harness — a **heavy
dependency** (a browser binary / native build) that would break the marketplace's zero-dependency,
copy-alone-install property. So real-pixel fidelity stays an **optional escalation**, not the always-on CI
gate. This harness is Node-builtins only and runs anywhere `node` does; it is the runtime floor, not the
pixel ceiling. The static-only `app-shell-check.mjs` remains a standalone tool and the composed floor.

## Answer key

| Check | Asserts |
| --- | --- |
| **R1** | `capability.system.shell` binds the `render-coherence` gate (`render-check.mjs`), not the generic harness. |
| **R2** | `capability.system.core` STILL binds the default `capability-harness` — slug-specificity didn't break layer-default resolution. |
| **R3** | The gate PASSES a coherent shell that compiles + USES a program + DRAWS a frame. |
| **R4** | The gate FAILS a shell that assembles but NEVER DRAWS — the runtime gap the static floor cannot see. |
| **R5** | The gate FAILS a re-export barrel at the composed static floor (the app-shell checks still bite). |

`python3 evals/render-coherence-gate/replay.py` → exit 0. `node dev-kit-app/bin/render-check.mjs --selftest`
and `node dev-kit-app/bin/app-shell-check.mjs --selftest` cover the verifiers directly. Stdlib + Node builtins only.
