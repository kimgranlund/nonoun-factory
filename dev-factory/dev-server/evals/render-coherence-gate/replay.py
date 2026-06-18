#!/usr/bin/env python3
"""replay.py — the RENDER-COHERENCE gate: the kit can now tell an app that RENDERS from one that merely assembles.

app-shell-check proved the shell ASSEMBLES (canvas + a module entry + every product import resolves) — its
static floor. But an assembled page can still throw on load, link a program and never draw, or wire a uniform
that isn't there: it passes every static check and renders nothing. This eval proves the runtime gate: the
slug-targeted `render-coherence` adapter binds `capability.*.shell` to render-check, which COMPOSES the static
floor and then EXECUTES the shell's on-load path against a recording mock WebGL2 context, asserting a frame is
actually DRAWN (useProgram + a draw call). Node-builtins only — real-GPU pixel fidelity is the optional
escalation, not the always-on gate.

Falsified if any breaks:
  R1  a `capability.system.shell` cell binds the render-coherence gate (render-check), NOT the generic harness.
  R2  a `capability.system.core` cell STILL binds the default capability-harness (slug-specific resolution did
      not break the layer default — backward compatible).
  R3  the gate PASSES a coherent shell that compiles + USES a program + DRAWS a frame.
  R4  the gate FAILS a shell that assembles but NEVER DRAWS — the runtime gap the static floor cannot see.
  R5  the gate FAILS a re-export barrel at the composed static floor (the app-shell checks still bite).

Exit 0 = the kit distinguishes 'an app that renders' from 'modules that merely assemble'. Stdlib only; 3.8+.
Answer key in README.md.
"""
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER = os.path.dirname(os.path.dirname(_HERE))
_DF = os.path.dirname(_SERVER)
os.environ["DEV_FACTORY_KIT"] = os.path.join(_DF, "dev-kit-app")   # bind the app family
sys.path.insert(0, _SERVER)
import api as _api          # noqa: E402
import dispatch as _disp    # noqa: E402

# a real compiler-shaped module the test shells import + drive against the mock GL
_CORE = """\
export function compileShader(gl, src) {
  const s = gl.createShader(gl.FRAGMENT_SHADER); gl.shaderSource(s, src); gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) return { program: null, errors: [] };
  const p = gl.createProgram(); gl.attachShader(p, s); gl.linkProgram(p);
  return gl.getProgramParameter(p, gl.LINK_STATUS) ? { program: p, errors: [] } : { program: null, errors: [] };
}
"""
# a shell that compiles AND draws a frame
_DRAWS = """<!doctype html><canvas id=gl></canvas><script type="module">
import { compileShader } from './core/index.mjs';
const gl = document.getElementById('gl').getContext('webgl2');
const { program } = compileShader(gl, 'void main(){}');
function frame(){ gl.useProgram(program); gl.uniform1f(gl.getUniformLocation(program,'iTime'), 0); gl.drawArrays(gl.TRIANGLES,0,3); requestAnimationFrame(frame); }
frame();
</script>"""
# a shell that assembles + links a program but NEVER draws (the runtime gap)
_NODRAW = """<!doctype html><canvas id=gl></canvas><script type="module">
import { compileShader } from './core/index.mjs';
const gl = document.getElementById('gl').getContext('webgl2');
compileShader(gl, 'void main(){}');
</script>"""


def run():
    fails = []
    def check(cond, label):
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            fails.append(label)

    with tempfile.TemporaryDirectory() as root:
        d = os.path.join(root, ".factory")
        _api.init_instance(d)
        os.makedirs(os.path.join(d, "core"), exist_ok=True)
        open(os.path.join(d, "core", "index.mjs"), "w").write(_CORE)
        open(os.path.join(d, "index.html"), "w").write(_DRAWS)
        open(os.path.join(d, "nodraw.html"), "w").write(_NODRAW)
        open(os.path.join(d, "barrel.html"), "w").write(
            '<!doctype html><script type="module">export * from "./core/index.mjs";</script>')

        unit = {"worktree": d}
        shell = {"layer": "capability", "scope": "system", "slug": "shell", "asset_ref": "index.html", "maturity": "instantiated"}
        core = {"layer": "capability", "scope": "system", "slug": "core", "asset_ref": "core", "maturity": "instantiated"}

        v_shell = _disp._kit_verifier(d, shell, unit) or []
        v_core = _disp._kit_verifier(d, core, unit) or []
        check("render-check.mjs" in " ".join(v_shell),
              f"R1: capability.system.shell binds the render-coherence gate (got {' '.join(v_shell[-2:])})")
        check(bool(v_core) and v_core[-1].endswith("verify.mjs"),
              f"R2: capability.system.core still binds the default capability-harness (got {' '.join(v_core)})")

        check(subprocess.run(v_shell, capture_output=True).returncode == 0,
              "R3: the gate PASSES a coherent shell that compiles + USES a program + DRAWS a frame")
        v_nodraw = _disp._kit_verifier(d, {**shell, "asset_ref": "nodraw.html"}, unit)
        r_nodraw = subprocess.run(v_nodraw, capture_output=True)
        check(r_nodraw.returncode != 0 and b"draw" in (r_nodraw.stderr + r_nodraw.stdout).lower(),
              "R4: the gate FAILS a shell that assembles but NEVER DRAWS (the runtime gap the static floor can't see)")
        v_barrel = _disp._kit_verifier(d, {**shell, "asset_ref": "barrel.html"}, unit)
        r_barrel = subprocess.run(v_barrel, capture_output=True)
        check(r_barrel.returncode != 0,
              "R5: the gate FAILS a re-export barrel at the composed static floor (the app-shell checks still bite)")

    print()
    if fails:
        print(f"render-coherence-gate: GAP OPEN — {len(fails)} check(s) failed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("render-coherence-gate: OK — a slug-targeted render-coherence adapter binds capability.*.shell to "
          "render-check, the RUNTIME gate above app-shell-check's static floor: it executes the shell's on-load "
          "path against a recording mock WebGL2 context and PASSES a shell that draws a frame while rejecting one "
          "that assembles but never draws (and still rejecting a barrel at the composed static floor), with the "
          "generic capability-harness still grading every other capability. Node-builtins only — real-GPU pixel "
          "fidelity is the optional escalation, not the always-on CI gate.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
