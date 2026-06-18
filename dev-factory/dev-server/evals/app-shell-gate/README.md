# app-shell-gate — the kit can tell a runnable app from a re-export barrel

_Last reviewed: 2026-06-18._

**What it proves.** A new kit gate closes the "built modules but no assembled app" gap. The kit grades
capabilities as pure ES modules imported headlessly by their sibling `verify.mjs` — which proves the *logic*
but not that the modules *assemble* into a running app. A real shader-playground build exposed this: every
capability validated, but the `app` cell degenerated to `export * as core/ui/persistence` (a re-export
barrel), the product had no browser entry, and the pieces didn't even cohere (a `#version 300 es` compiler
vs a GLSL 1.00 default shader). "validated" meant "modules exist," not "the app runs."

**The gate.** A slug-targeted `app-shell` validation adapter binds `capability.*.shell` to
`dev-kit-app/bin/app-shell-check.mjs`, which statically verifies the entry (`index.html`) is a coherent
runnable assembly over the built modules: a `<canvas>`, a `<script type="module">`, it actually imports the
product, and **every import in the reachable module graph resolves** to a file the build produced (no
dangling `./ui/missing.mjs`). The kit's adapter matching gained slug-specificity (`_kit_verifier`): a
slug-targeted adapter wins over the layer-default, backward-compatibly.

**The honest limit.** This is a *static* gate — it does not prove the app **renders**. Runtime/semantic
coherence (a fragment shader written for the wrong GLSL version, a uniform-name mismatch) needs the page
executed: a **browser/headless-gl harness adapter** (puppeteer / headless-gl + screenshot-diff), the next
adapter on the kit's roadmap. This gate is its floor, not its ceiling.

## Answer key

| Check | Asserts |
| --- | --- |
| **A1** | `capability.system.shell` binds the `app-shell` gate (`app-shell-check.mjs`), not the generic harness. |
| **A2** | `capability.system.core` STILL binds the default `capability-harness` — slug-specificity didn't break layer-default resolution. |
| **A3** | The gate PASSES a coherent shell (canvas + module entry + every product import resolves). |
| **A4** | The gate FAILS a re-export barrel — it passes module checks but is not a runnable app (the exact gap). |

`python3 evals/app-shell-gate/replay.py` → exit 0. `node dev-kit-app/bin/app-shell-check.mjs --selftest` covers the verifier directly. Stdlib only.
