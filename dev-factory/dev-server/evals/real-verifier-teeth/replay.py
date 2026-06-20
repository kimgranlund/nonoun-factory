#!/usr/bin/env python3
"""replay.py — REAL verifiers have TEETH, and a presence stub does not (harness-council H2-M1).

CI's MockAdapter authors a lenient smoke verify.mjs (it only reads `m.ready`/exists), so green CI has only ever
proven the MOCK loop closes on itself — it never exercises a REAL spec-conformance gate, which is exactly where
the #2 fix's correctness lives ("validated" = "implements the spec", not "exports ready"). This eval drives a
REAL, spec-derived verify.mjs through the kernel's ACTUAL validation path (validate.run_validation — the
signal-minter dispatch uses, verdict = the verifier's exit status) and proves the gate both BITES and is
SATISFIABLE — and that the stub it replaces is blind to the very deviation it catches:

  H1  a REAL verify.mjs (asserts BEHAVIOR: compute(2,3)===5 and compute(10,0)===10) FAILS a deviating module
      (compute = a*b) — the cell is NOT advanced and a `fail` signal is minted from the nonzero exit.
  H2  the SAME verify.mjs PASSES a conformant module (compute = a+b) — the cell advances to `validated` and a
      `pass` signal is minted. (Teeth that never pass anything are useless; a real gate must be satisfiable.)
  H3  the CONTRAST that MOTIVATES the #2 fix: the seeded MOCK smoke stub (only checks `typeof m.compute`) PASSES
      the SAME deviating module H1 refused — a presence predicate is structurally blind to a value/behavior
      deviation. This is the rubber stamp the factory-authored verifier replaces; green-under-the-stub proves
      nothing about conformance.

Exit 0 = a real gate has teeth AND is satisfiable, through the real validation path, with no model + no mock.
Needs `node` (the verifier is a real ES-module harness); skips with exit 0 if absent. Stdlib only; Python 3.8+.
Answer key in README.md (outside the fixture).
"""
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _SERVER)
import api          # noqa: E402  (the server operations layer)
import store as _store  # noqa: E402
sys.path.insert(0, _store._KERNEL_BIN)
import validate as _val   # noqa: E402  (the kernel signal-minter: run the verifier, mint the signal from its exit)
import lattice as _lat    # noqa: E402

CELL = "capability.system.calc"
ASSET = os.path.join("capability", "calc")

# A REAL spec-conformance harness: it CALLS the export and asserts the contract's VALUES, not just presence.
REAL_VERIFY = """import * as m from './index.mjs';
const cases = [[2, 3, 5], [10, 0, 10], [4, 4, 8]];
for (const [a, b, want] of cases) {
  const got = m.compute(a, b);
  if (got !== want) { console.error(`FAIL: compute(${a},${b}) must be ${want}, got ${got}`); process.exit(1); }
}
console.log('pass'); process.exit(0);
"""

# The seeded MOCK smoke stub: a PRESENCE predicate — it only checks the export EXISTS, never what it computes.
MOCK_VERIFY = """// dev-factory:mock-verifier
import * as m from './index.mjs';
if (typeof m.compute !== 'function') { console.error('FAIL: no compute export'); process.exit(1); }
console.log('pass'); process.exit(0);
"""

CONFORMANT = "export const ready = true;\nexport const compute = (a, b) => a + b;\n"   # 2+3=5 ✓
DEVIATING = "export const ready = true;\nexport const compute = (a, b) => a * b;\n"    # 2*3=6 ✗ (but still a function)


def run():
    if shutil.which("node") is None:
        print("real-verifier-teeth: SKIP (node not on PATH; the verifier is a real ES-module harness)")
        return 0

    fails = []
    def check(cond, label):
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            fails.append(label)

    with tempfile.TemporaryDirectory() as root:
        d = os.path.join(root, ".factory")
        api.init_instance(d)
        adir = os.path.join(d, ASSET)
        os.makedirs(adir, exist_ok=True)
        vpath = os.path.join(adir, "verify.mjs")
        ipath = os.path.join(adir, "index.mjs")

        def seed_instantiated():
            api.seed_cell(d, "capability", "system", "calc", maturity="instantiated", asset_ref=ASSET)

        def maturity():  # read the source of record (the lattice validate.py writes), not the lazily-rebuilt store
            return (_lat.find(_lat.load(d), CELL) or {}).get("maturity")

        print("· H1 — a REAL verify.mjs REFUSES a deviating module (compute = a*b)")
        open(vpath, "w").write(REAL_VERIFY)
        open(ipath, "w").write(DEVIATING)
        seed_instantiated()
        ok, sig, msg = _val.run_validation(d, CELL, "calc-contract", ["node", vpath])
        mat = maturity()
        check((not ok) and sig["result"] == "fail", f"H1a: the real gate REFUSES the deviating module (fail signal) — {msg}")
        check(mat == "instantiated", f"H1b: the deviating cell is NOT advanced (stays instantiated, got {mat})")

        print("· H2 — the SAME verify.mjs PASSES a conformant module (compute = a+b)")
        open(ipath, "w").write(CONFORMANT)
        seed_instantiated()
        ok, sig, msg = _val.run_validation(d, CELL, "calc-contract", ["node", vpath])
        mat = maturity()
        check(ok and sig["result"] == "pass", f"H2a: the real gate PASSES the conformant module (pass signal) — {msg}")
        check(mat == "validated", f"H2b: the conformant cell advances to validated (got {mat})")
        # the pass signal is a real file on disk minted by the validation path (not forgeable by the worker)
        sdir = os.path.join(d, "signals", CELL)
        check(os.path.isdir(sdir) and any(s.endswith(".json") for s in os.listdir(sdir)),
              "H2c: a real pass signal file is on disk (minted from the verifier's exit, worker-deny)")

        print("· H3 — the CONTRAST: the MOCK presence stub PASSES the SAME deviating module H1 caught")
        open(vpath, "w").write(MOCK_VERIFY)
        open(ipath, "w").write(DEVIATING)
        seed_instantiated()
        ok, sig, msg = _val.run_validation(d, CELL, "calc-smoke", ["node", vpath])
        check(ok and sig["result"] == "pass",
              "H3a: the presence stub PASSES the deviating module (it checks `typeof compute`, never the value) "
              f"— the rubber stamp the #2 fix replaces ({msg})")

    print()
    if fails:
        print(f"real-verifier-teeth: NOT MET — {len(fails)} check(s) failed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("real-verifier-teeth: OK — a real spec-conformance verify.mjs, run through the kernel's actual "
          "validation path, REFUSES a deviating module and PASSES a conformant one, while the seeded presence "
          "stub waves the same deviation through. Green CI now exercises a gate with teeth, not just the mock "
          "loop closing on itself (the #2 fix is regression-guarded).")
    return 0


if __name__ == "__main__":
    sys.exit(run())
