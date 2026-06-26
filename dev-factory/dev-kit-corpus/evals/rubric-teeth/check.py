#!/usr/bin/env python3
"""check.py — rubric-teeth: the rubric META-verifier (rubric-check.py) earns its seat.

A rubric cell's `validated` signal is minted from rubric-check.py's EXIT STATUS, so the whole loop's
legitimacy rests on that meta-verifier having TEETH: it must PASS a genuinely calibrated rubric (its
mechanized gate demonstrably discriminates on a labeled exemplar set — rejects planted defects, passes the
gate-clean ones) and REJECT a hollow one (the right words, no real gate or exemplars). The earlier
rubric-check.py string-matched for `[gate]`/`calibration` ANYWHERE in the JSON, so a rubric with the words
and no teeth passed (harness-council verifier-integrity CRITICAL — a presence-predicate posing as
calibration). This eval is the falsifiable proof the fix closed it, and the regression guard that keeps it
closed:

  shipped/  — every rubric the corpus kit ships (spec-quality, prd-quality, pattern-quality) must PASS its
              own meta-verifier. A rubric that rots back into a presence-predicate (a hollowed gate, a
              deleted/mislabeled exemplar set) FAILS here, in CI, before it can grade anything.
  hollow    — a shape-only rubric (the words, no gate/exemplars) must be REJECTED — the teeth contrast that
              proves the meta-verifier discriminates rather than pattern-matches.

Exit 0 = the contract holds. Stdlib only; Python 3.8+.
"""
import json
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_KIT = os.path.dirname(os.path.dirname(_HERE))                 # dev-kit-corpus/
_CHECK = os.path.join(_KIT, "bin", "rubric-check.py")
_RUBRIC = os.path.join(_KIT, "rubric")

SHIPPED = ["spec-quality", "prd-quality", "pattern-quality"]


def _run(asset):
    r = subprocess.run([sys.executable, _CHECK, asset], capture_output=True, text=True)
    return r.returncode, (r.stdout + r.stderr)


def main():
    fails = []
    print("· shipped/ — every kit rubric must PASS its OWN meta-verifier (its gate discriminates on a labeled exemplar set)")
    for slug in SHIPPED:
        asset = os.path.join(_RUBRIC, f"{slug}.rubric.json")
        code, out = _run(asset)
        ok = code == 0 and "CALIBRATED" in out
        print(f"  {'PASS' if ok else 'FAIL'}  {slug:18} -> {(out.strip().splitlines() or [''])[-1][:96]}")
        if not ok:
            fails.append(f"shipped/{slug}: expected a CALIBRATED pass, got exit {code}: {out.strip()[:120]}")
    print("· hollow — a shape-only rubric (the right words, no real gate or exemplar set) must be REJECTED")
    with tempfile.TemporaryDirectory() as d:
        hollow = os.path.join(d, "hollow.rubric.json")
        json.dump({"cell": "rubric.system.hollow",
                   "description": "has the words [gate] pristine reference calibration exemplar but no real gate or exemplars"},
                  open(hollow, "w"))
        code, out = _run(hollow)
        ok = code == 1
        print(f"  {'PASS' if ok else 'FAIL'}  hollow             -> meta-verifier {'rejected' if ok else 'ACCEPTED'} it (exit {code})")
        if not ok:
            fails.append(f"hollow: the meta-verifier must REJECT a shape-only rubric (teeth), got exit {code}")

    if fails:
        sys.stderr.write("rubric-teeth: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print(f"rubric-teeth: OK — {len(SHIPPED)} shipped rubrics each PASS their meta-verifier with demonstrated teeth "
          "(gate discriminates on labeled exemplars); a shape-only rubric is REJECTED (the presence-predicate hole stays closed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
