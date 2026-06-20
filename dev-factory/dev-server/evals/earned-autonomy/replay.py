#!/usr/bin/env python3
"""replay.py — Tier 2 is EARNED by a LIVE refuter the server produced, not faked (harness-council H6).

The audit's H6 cap: nothing in the dev-server validation path PRODUCED the refuter sidecars the false-pass oracle
consumes (only `self_heal_cell` re-armed one post-incident, and eval fixtures hand-seeded them). So `false_pass`
stayed `unmeasured` forever, the app family could never legitimately reach Tier 2 (`autonomy.tier_for`), and the
only in-tree paths that reached Tier 2 asserted `record_refuter_check(agreed=True)`. This proves the HONEST
trajectory end to end — no `record_refuter_check` shortcut appears anywhere in this file:

  H1  a validated CODE cell with a budget armed is still capped at Tier 1 — `false_pass == 'unmeasured'` (you
      cannot claim a false-pass rate you never measured; the honest-scope invariant).
  H2  the LIVE PRODUCER arms an independent refuter at validation (`dispatch.produce_refuters` — the heartbeat's
      per-tick sweep): a `fresh_refute` oracle over the cell's exports, recovered from its verify.mjs, distinct
      from the `verify.mjs` gate the worker coded to.
  H3  the heartbeat's `run_refuter` runs that oracle (real `node`) and RECORDS the check — `false_pass` becomes
      MEASURED (0.0: one agreeing check, zero incidents) → with the validated verifier + the armed budget the
      family EARNS Tier 2.
  H4  the earned tier is REVOCABLE by the same path: an independent refuter that DISAGREES (a real domain oracle
      the cell fails) records an incident → `tier_for` mechanically caps back at Tier 1, no human. (The full
      self-heal repair of that false pass is proven by `evals/self-heal`; here we assert only the revocation.)

Exit 0 = Tier 2 is reachable AND revocable by a REAL oracle the server produced — the H6 cap's precondition is now
met on a real build. Needs `node` (the refuter runs a real harness); skips with exit 0 if absent. Stdlib only;
Python 3.8+. Answer key in README.md.
"""
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _SERVER)
import api          # noqa: E402
import store as _store  # noqa: E402
import dispatch as _disp  # noqa: E402
sys.path.insert(0, _store._KERNEL_BIN)
import validate as _val   # noqa: E402
import autonomy as _auto  # noqa: E402
import lattice as _lat    # noqa: E402

CELL = "capability.system.calc"
ASSET = os.path.join("capability", "calc")

# A real spec-conformance gate (the worker codes to THIS) — exports `compute`, asserts its values.
GATE = "import * as m from './index.mjs';\nconst r = [[2,3,5],[10,0,10]];\nfor (const [a,b,w] of r){ if (m.compute(a,b)!==w){console.error('FAIL');process.exit(1);} }\nconsole.log('pass');process.exit(0);\n"
CONFORMANT = "export const ready = true;\nexport const compute = (a, b) => a + b;\n"


def run():
    if shutil.which("node") is None:
        print("earned-autonomy: SKIP (node not on PATH; the refuter runs a real harness)")
        return 0
    fails = []
    def check(cond, label):
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            fails.append(label)

    # bind the app kit so capability cells are recognized as multi-file CODE (the producer only arms code cells)
    os.environ["DEV_FACTORY_KIT"] = os.path.join(os.path.dirname(_SERVER), "dev-kit-app")
    try:
        return _body(check, fails)
    finally:
        os.environ.pop("DEV_FACTORY_KIT", None)


def _body(check, fails):
    import tempfile
    with tempfile.TemporaryDirectory() as root:
        d = os.path.join(root, ".factory")
        api.init_instance(d)
        # a validated verifier (rubric) → the family is at least Tier 1
        api.seed_cell(d, "rubric", "system", "spec-quality", maturity="validated",
                      signal_refs=["signals/rubric.system.spec-quality/seed.json"])
        # a CODE cell, validated against a real gate
        adir = os.path.join(d, ASSET)
        os.makedirs(adir, exist_ok=True)
        open(os.path.join(adir, "verify.mjs"), "w").write(GATE)
        open(os.path.join(adir, "index.mjs"), "w").write(CONFORMANT)
        api.seed_cell(d, "capability", "system", "calc", maturity="instantiated", asset_ref=ASSET)
        ok, _sig, msg = _val.run_validation(d, CELL, "calc-contract", ["node", os.path.join(adir, "verify.mjs")])
        check(ok and (_lat.find(_lat.load(d), CELL) or {}).get("maturity") == "validated",
              f"setup: the code cell validates against its real gate ({msg})")
        api._store.rebuild(d)

        print("· H1 — a budget is armed, but the family is UNMEASURED → capped at Tier 1")
        import heartbeat as _hb
        _hb.arm(d, max_dispatches=5, deadline_s=3600)
        check(_auto.false_pass(d) == "unmeasured", "H1a: false_pass is 'unmeasured' before any refuter check")
        check(_auto.tier_for(d) == 1, f"H1b: an unmeasured family is capped at Tier 1 even with a budget (got {_auto.tier_for(d)})")

        print("· H2 — the LIVE PRODUCER arms an independent refuter at validation (no hand-seeding)")
        armed = _disp.produce_refuters(d)
        side = os.path.join(d, "coordination", "refuters", f"{CELL}.json")
        check(CELL in armed and os.path.isfile(side), f"H2a: produce_refuters armed an independent oracle for the cell (armed={armed})")
        # the refuter is NOT the gate the worker saw — it is a fresh_refute invariant set over the exports
        spec = os.path.join(d, "coordination", "verify-spec", f"{CELL}.json")
        check(os.path.isfile(spec), "H2b: the verify-spec was persisted (the regeneration substrate now exists in dev-server)")

        print("· H3 — run_refuter MEASURES it (real node) → false_pass 0.0 → Tier 2 EARNED")
        agreed = _disp.run_refuter(d, CELL)
        check(agreed is True, f"H3a: the independent refuter AGREES with the conformant cell (got {agreed})")
        check(_auto.false_pass(d) == 0.0, f"H3b: false_pass is now MEASURED at 0.0 (got {_auto.false_pass(d)})")
        check(_auto.tier_for(d) == 2, f"H3c: validated verifier + measured-clean false_pass + armed budget → Tier 2 EARNED (got {_auto.tier_for(d)})")

        print("· H4 — the earned tier is REVOCABLE: a disagreeing independent oracle demotes, no human")
        # a real domain refuter the (otherwise valid) cell fails — overrides the generic floor (the planner/self-heal
        # path), proving run_refuter's catch demotes the family. The cell is re-validated to re-enter the frontier.
        import json
        json.dump({"harness": "import * as m from './index.mjs';\nif (m.compute(1,1) !== 999) process.exit(1);\nprocess.exit(0);\n"},
                  open(side, "w"))
        api.seed_cell(d, "capability", "system", "calc", maturity="validated", asset_ref=ASSET,
                      signal_refs=["signals/x"])  # re-validate → re-enters the refute frontier with the new oracle
        disagreed = _disp.run_refuter(d, CELL)
        check(disagreed is False, f"H4a: the disagreeing oracle catches a false pass (got {disagreed})")
        # the incident mechanically REVOKES the earned Tier 2 — it opens an incident AND stales the verifier cells
        # (so the family can drop below Tier 1 until they re-validate). Either way it is no longer Tier 2, no human.
        check(_auto.tier_for(d) <= 1, f"H4b: the caught false pass mechanically REVOKES the earned Tier 2 (got {_auto.tier_for(d)})")

    print()
    if fails:
        print(f"earned-autonomy: NOT MET — {len(fails)} check(s) failed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("earned-autonomy: OK — the live producer arms an independent refuter at validation, run_refuter MEASURES "
          "it, and a measured-clean false-pass earns Tier 2 — no record_refuter_check fake. The same oracle, when it "
          "disagrees, mechanically revokes the tier. Tier 2 is now EARNABLE (and revocable) on a real build (H6).")
    return 0


if __name__ == "__main__":
    sys.exit(run())
