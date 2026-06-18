#!/usr/bin/env python3
"""replay.py — the app-shell coherence gate: the kit can now tell a runnable APP from a re-export barrel.

The kit grades capabilities as pure ES modules imported headlessly by their sibling verify.mjs — which can
prove the LOGIC but not that the modules ASSEMBLE into a running app. A real build exposed the gap: every
capability validated, the `app` cell degenerated to `export * as core/ui/persistence`, and the product had
no browser entry (and the pieces didn't even cohere — a 300es compiler vs a 1.00 default shader). This eval
proves the new gate: a slug-targeted `app-shell` adapter binds `capability.*.shell` to app-shell-check, which
statically verifies the entry is a coherent runnable assembly over the built modules.

Falsified if any breaks:
  A1  a `capability.system.shell` cell binds the app-shell gate (app-shell-check), NOT the generic harness.
  A2  a `capability.system.core` cell STILL binds the default capability-harness (the slug-specific adapter
      did not break layer-default resolution — backward compatible).
  A3  the gate PASSES a coherent shell (canvas + a module entry + every product import resolves).
  A4  the gate FAILS a re-export barrel — it passes module checks but is NOT a runnable app (the exact gap).

Exit 0 = the kit distinguishes an assembled app from built-but-unassembled modules. Stdlib only; Python 3.8+.
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
        open(os.path.join(d, "core", "index.mjs"), "w").write("export const compileShader = () => ({ program: {}, errors: [] });\n")
        open(os.path.join(d, "index.html"), "w").write(
            '<!doctype html><canvas id=gl></canvas><script type="module">'
            'import { compileShader } from "./core/index.mjs"; compileShader();</script>')
        open(os.path.join(d, "barrel.html"), "w").write(
            '<!doctype html><script type="module">export * from "./core/index.mjs";</script>')

        unit = {"worktree": d}
        shell = {"layer": "capability", "scope": "system", "slug": "shell", "asset_ref": "index.html", "maturity": "instantiated"}
        core = {"layer": "capability", "scope": "system", "slug": "core", "asset_ref": "core", "maturity": "instantiated"}

        v_shell = _disp._kit_verifier(d, shell, unit) or []
        v_core = _disp._kit_verifier(d, core, unit) or []
        check("app-shell-check.mjs" in " ".join(v_shell),
              f"A1: capability.system.shell binds the app-shell gate (got {' '.join(v_shell[:3])}…)")
        check(bool(v_core) and v_core[-1].endswith("verify.mjs"),
              f"A2: capability.system.core still binds the default capability-harness (got {' '.join(v_core)})")

        check(subprocess.run(v_shell, capture_output=True).returncode == 0,
              "A3: the gate PASSES a coherent shell (canvas + module entry + every product import resolves)")
        v_bad = _disp._kit_verifier(d, {**shell, "asset_ref": "barrel.html"}, unit)
        r_bad = subprocess.run(v_bad, capture_output=True)
        check(r_bad.returncode != 0,
              "A4: the gate FAILS a re-export barrel — passes module checks but is not a runnable app")

    print()
    if fails:
        print(f"app-shell-gate: GAP OPEN — {len(fails)} check(s) failed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("app-shell-gate: OK — a slug-targeted app-shell adapter binds capability.*.shell to app-shell-check, "
          "the integration gate the headless verify.mjs model lacked: it passes a coherent runnable shell and "
          "rejects a re-export barrel, while the generic capability-harness still grades every other capability. "
          "The kit now distinguishes 'an assembled app' from 'built-but-unassembled modules' (runtime render "
          "coherence is the next adapter — a browser/headless-gl harness).")
    return 0


if __name__ == "__main__":
    sys.exit(run())
