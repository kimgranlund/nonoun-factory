#!/usr/bin/env python3
"""rubric-check.py — the corpus family's rubric-cell META-verifier (a kit validation harness).

The validation adapter `rubric-calibration-check` binds this to rubric-layer cells: validate.py mints a
rubric cell's signal from this script's EXIT STATUS, so a rubric becomes a trusted verifier ONLY once it
passes its own meta-verifier. The bar is **demonstrated teeth, not declared shape**: a rubric is calibrated
only if its mechanized [gate] provably DISCRIMINATES on a labeled exemplar set — it FAILS the planted-defect
exemplars and PASSES the good ones, deterministically. (The earlier cut of this file string-matched for the
words `[gate]`/`pristine`/`calibration` anywhere in the JSON, so a rubric with the right *words* and no real
gate passed — a presence-predicate masquerading as calibration. harness-council verifier-integrity CRITICAL.)

The check, in order (any failure → exit 1):

  1. STRUCTURE (parsed, never substring): >=1 dimension with `kind=="gate"` naming a `mechanized_by`
     `bin/<script>.py`; a `calibration.exemplars_ref`; a `pristine_reference` with `writable_by_worker:false`.
  2. The mechanizing gate script resolves to a REAL file under the PLUGIN's bin/ (not an arbitrary command —
     a worker cannot point this at `true`). The exemplar set resolves under the PLUGIN (rubric/exemplars/...),
     NOT instance state — so a runtime worker cannot author a rubric AND forge its own passing calibration;
     a new validated verifier requires a CI-reviewed kit-level exemplar set.
  3. TEETH: run the gate against every labeled exemplar (TWICE — determinism). Require each verdict to MATCH
     its label (expect:pass → exit 0; expect:fail → non-zero, and any declared `dimension` string present in
     the output), the two runs identical, and the set to SPAN both outcomes (>=1 pass AND >=1 fail). Labels
     are CHECKED against real gate behavior, never trusted: a hollow gate that passes everything fails on the
     `fail` exemplars; an all-`pass` set with no planted defects fails the span requirement.

Exemplar set layout — `<exemplars_ref>/manifest.json`:
    { "exemplars": [ {"file": "<path rel. to manifest dir>", "expect": "pass"|"fail", "dimension"?: "<substr>"} ] }

Usage:  rubric-check.py <asset-path>   |   rubric-check.py selftest
Exit 0 = pass; 1 = fail; 2 = bad invocation. Stdlib only; Python 3.8+.
"""
import json
import os
import re
import subprocess
import sys

# The plugin root: rubric-check.py lives in <plugin>/bin/, so calibration data (bin/ gates, rubric/exemplars/)
# is PLUGIN-STATIC — resolved here, never from the (worker-writable) instance the asset may live in.
_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_GATE_RE = re.compile(r"(bin/[A-Za-z0-9_-]+\.py)")


def _load_rubric(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"```json\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        raise


def _gate_script(doc):
    """The single mechanizing gate the rubric's [gate] dimensions name — resolved to a real plugin bin/ file.
    Returns (abs_path, None) or (None, reason)."""
    gate_dims = [d for d in (doc.get("dimensions") or []) if isinstance(d, dict) and d.get("kind") == "gate"]
    if not gate_dims:
        return None, "rubric declares no `kind:\"gate\"` dimension (a [review]-only rubric is scoring vibes)"
    scripts = set()
    for d in gate_dims:
        m = _GATE_RE.search(str(d.get("mechanized_by") or ""))
        if m:
            scripts.add(m.group(1))
    if not scripts:
        return None, "no gate dimension names a `mechanized_by: bin/<script>.py` (the gate is not mechanized)"
    if len(scripts) > 1:
        return None, f"gate dimensions name >1 mechanizing script {sorted(scripts)} (expected one gate)"
    rel = scripts.pop()
    abs_path = os.path.join(_PLUGIN_ROOT, rel)
    if not os.path.isfile(abs_path):
        return None, f"the mechanizing gate {rel} does not resolve to a real plugin bin/ script"
    return abs_path, None


def _contained(abs_path):
    """True iff abs_path is inside the PLUGIN root — the calibration data must be plugin-static, never reachable
    by `..`/absolute escape to (worker-writable) instance state. Both sides are realpath'd so a symlinked root
    (e.g. macOS /var -> /private/var) compares consistently."""
    try:
        root = os.path.realpath(_PLUGIN_ROOT)
        return os.path.commonpath([root, os.path.realpath(abs_path)]) == root
    except ValueError:        # different drives / mixed abs+rel — treat as escaped
        return False


def _exemplar_set(doc):
    """The labeled exemplar manifest the rubric's calibration declares — resolved under the PLUGIN and BOUND to
    this rubric's own identity. Returns (manifest_dir, exemplars_list, None) or (None, None, reason)."""
    cal = doc.get("calibration")
    if not isinstance(cal, dict) or not cal.get("exemplars_ref"):
        return None, None, "rubric carries no `calibration.exemplars_ref` (a calibrated verifier names its exemplar set)"
    pr = doc.get("pristine_reference")
    if not isinstance(pr, dict) or pr.get("writable_by_worker") is not False:
        return None, None, "rubric carries no `pristine_reference` with `writable_by_worker:false` (the worker could reach the answer key)"
    ref = cal["exemplars_ref"]
    if os.path.isabs(ref):
        return None, None, f"exemplars_ref {ref!r} is absolute — it must be a plugin-relative path (no escape from the kit)"
    # IDENTITY BINDING (anti-borrow): the exemplar set must be the one named for THIS rubric's cell, not any
    # already-validated set a hollow rubric could point its `mechanized_by`+`exemplars_ref` at to borrow teeth.
    cell = str(doc.get("cell") or doc.get("id") or "")
    slug = cell.rsplit(".", 1)[-1] if cell else ""
    if not slug or os.path.basename(os.path.normpath(ref)) != slug:
        return None, None, (f"exemplars_ref {ref!r} is not bound to this rubric's identity (must end in "
                            f"exemplars/{slug or '<cell-slug>'}/) — a rubric cannot borrow another's exemplar set")
    man_dir = os.path.normpath(os.path.join(_PLUGIN_ROOT, ref))
    if not _contained(man_dir):
        return None, None, f"exemplars_ref {ref!r} resolves outside the plugin (escape blocked)"
    man_path = os.path.join(man_dir, "manifest.json")
    if not os.path.isfile(man_path):
        return None, None, f"no exemplar manifest at {os.path.join(ref, 'manifest.json')} (the calibration set is referenced but absent)"
    try:
        man = json.load(open(man_path, encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, None, f"exemplar manifest does not parse: {e}"
    exemplars = man.get("exemplars")
    if not isinstance(exemplars, list) or not exemplars:
        return None, None, "exemplar manifest carries no `exemplars` list"
    return man_dir, exemplars, None


def _run_gate(gate, asset):
    r = subprocess.run([sys.executable, gate, asset], capture_output=True, text=True)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def check(path):
    if not path or not os.path.isfile(path):
        return False, f"no asset at {path!r}"
    try:
        doc = _load_rubric(path)
    except (ValueError, OSError) as e:
        return False, f"rubric is not valid JSON ({e})"
    if not isinstance(doc, dict):
        return False, "rubric is not a JSON object"

    gate, why = _gate_script(doc)
    if why:
        return False, why
    man_dir, exemplars, why = _exemplar_set(doc)
    if why:
        return False, why

    seen_pass = seen_fail = 0
    for ex in exemplars:
        if not isinstance(ex, dict) or not ex.get("file") or ex.get("expect") not in ("pass", "fail"):
            return False, f"malformed exemplar entry {ex!r} (need {{file, expect: pass|fail}})"
        if os.path.isabs(ex["file"]):
            return False, f"exemplar path {ex['file']!r} is absolute — exemplars must stay inside the plugin"
        asset = os.path.normpath(os.path.join(man_dir, ex["file"]))
        if not _contained(asset):
            return False, f"exemplar {ex['file']!r} resolves outside the plugin (`..` escape blocked)"
        if not os.path.isfile(asset):
            return False, f"exemplar {ex['file']!r} does not resolve on disk"
        code1, out1 = _run_gate(gate, asset)
        code2, _out2 = _run_gate(gate, asset)
        if code1 != code2:
            return False, f"gate is NON-deterministic on exemplar {ex['file']!r} (exit {code1} then {code2})"
        if ex["expect"] == "pass":
            if code1 != 0:
                return False, f"gate FAILED a `pass` exemplar {ex['file']!r} (exit {code1}): {out1.strip()[:120]}"
            seen_pass += 1
        else:  # expect fail — the gate must reject it, on the declared dimension if any
            if code1 == 0:
                return False, f"gate PASSED a `fail` exemplar {ex['file']!r} — no teeth (a planted defect waved through)"
            dim = ex.get("dimension")
            if dim and dim not in out1:
                return False, f"gate rejected `fail` exemplar {ex['file']!r} but NOT on dimension {dim!r}: {out1.strip()[:120]}"
            seen_fail += 1

    if seen_pass == 0 or seen_fail == 0:
        return False, (f"exemplar set does not SPAN both outcomes (pass={seen_pass}, fail={seen_fail}) — "
                       "teeth require >=1 good exemplar the gate passes AND >=1 planted defect it rejects")
    return True, (f"rubric is a CALIBRATED verifier: its gate discriminated on {seen_pass + seen_fail} labeled "
                  f"exemplars ({seen_pass} pass / {seen_fail} fail), deterministically — demonstrated teeth")


def selftest():
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as d:
        # A real, minimal mechanizing gate: exit 1 iff the asset contains the word "DEFECT" (a stand-in for a
        # gate dimension with teeth). Lives under a fake plugin's bin/ so resolution mirrors production.
        broot = os.path.join(d, "bin"); ex_dir = os.path.join(d, "rubric", "exemplars", "demo")
        os.makedirs(broot); os.makedirs(ex_dir)
        gate = os.path.join(broot, "demo-check.py")
        open(gate, "w").write("import sys\nsys.exit(1 if 'DEFECT' in open(sys.argv[1]).read() else 0)\n")
        open(os.path.join(ex_dir, "good.md"), "w").write("a clean exemplar\n")
        open(os.path.join(ex_dir, "bad.md"), "w").write("this one has a DEFECT\n")
        json.dump({"exemplars": [{"file": "good.md", "expect": "pass"},
                                 {"file": "bad.md", "expect": "fail"}]},
                  open(os.path.join(ex_dir, "manifest.json"), "w"))

        def rubric(**over):
            base = {"cell": "rubric.system.demo",
                    "dimensions": [{"id": "g", "kind": "gate", "mechanized_by": "bin/demo-check.py"}],
                    "calibration": {"exemplars_ref": "rubric/exemplars/demo/"},
                    "pristine_reference": {"writable_by_worker": False}}
            base.update(over)
            p = os.path.join(d, "r.rubric.json"); json.dump(base, open(p, "w")); return p

        # patch the plugin root to our fake plugin for the duration of the test
        global _PLUGIN_ROOT
        saved, _PLUGIN_ROOT = _PLUGIN_ROOT, d
        try:
            ok, msg = check(rubric())
            if not ok:
                fails.append(f"rejected a calibrated rubric whose gate discriminated: {msg}")
            # the OLD hollow shape — right words, NO real gate/exemplars — must now FAIL
            hollow = os.path.join(d, "h.rubric.json")
            json.dump({"x": "[gate] calibration pristine reference exemplar"}, open(hollow, "w"))
            if check(hollow)[0]:
                fails.append("accepted a shape-only rubric (the words, no real gate or exemplar set) — the hollow hole reopened")
            # a real gate but NO planted-defect exemplar (all `pass`) → no teeth proven → FAIL
            json.dump({"exemplars": [{"file": "good.md", "expect": "pass"}]}, open(os.path.join(ex_dir, "manifest.json"), "w"))
            if check(rubric())[0]:
                fails.append("accepted a rubric whose exemplar set never exercises a rejection (no teeth)")
            # restore the spanning set, then point the gate at a HOLLOW script (always exit 0) → must FAIL on the `fail` exemplar
            json.dump({"exemplars": [{"file": "good.md", "expect": "pass"}, {"file": "bad.md", "expect": "fail"}]},
                      open(os.path.join(ex_dir, "manifest.json"), "w"))
            open(os.path.join(broot, "hollow-check.py"), "w").write("import sys\nsys.exit(0)\n")
            if check(rubric(dimensions=[{"id": "g", "kind": "gate", "mechanized_by": "bin/hollow-check.py"}]))[0]:
                fails.append("accepted a rubric whose gate passes EVERYTHING (a hollow gate has no teeth)")
            # a missing pristine_reference → FAIL (the worker could reach the answer key)
            if check(rubric(pristine_reference={"writable_by_worker": True}))[0]:
                fails.append("accepted a rubric whose pristine reference is worker-writable")
            # a gate that doesn't resolve to a real plugin script → FAIL (no arbitrary commands)
            if check(rubric(dimensions=[{"id": "g", "kind": "gate", "mechanized_by": "bin/nonexistent.py"}]))[0]:
                fails.append("accepted a rubric naming a non-existent mechanizing gate")
            # MAJOR-1: a rubric cannot BORROW another rubric's exemplar set — exemplars_ref must bind to its own cell slug
            if check(rubric(cell="rubric.system.evil"))[0]:
                fails.append("accepted a rubric pointing exemplars_ref at a DIFFERENT cell's set (borrowed teeth)")
            # MAJOR-2: an exemplar `file` that escapes the plugin via `..` is rejected (no reach into instance state)
            json.dump({"exemplars": [{"file": "../../../../../../etc/hosts", "expect": "pass"}, {"file": "bad.md", "expect": "fail"}]},
                      open(os.path.join(ex_dir, "manifest.json"), "w"))
            if check(rubric())[0]:
                fails.append("accepted an exemplar whose `..` path escapes the plugin root (traversal)")
        finally:
            _PLUGIN_ROOT = saved

    if fails:
        sys.stderr.write("rubric-check selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("rubric-check selftest: OK (a rubric whose gate DISCRIMINATES on a spanning labeled exemplar set passes; "
          "a shape-only rubric, a teeth-less all-pass set, a hollow always-exit-0 gate, a worker-writable pristine "
          "reference, a non-existent gate script, a BORROWED exemplar set (bound to another cell's slug), and a `..`-"
          "escaping exemplar path all FAIL — a rubric earns 'verifier' by demonstrated teeth on its OWN plugin-static set)")
    return 0


def main(argv):
    if not argv:
        sys.stderr.write("usage: rubric-check.py <asset-path> | selftest\n")
        return 2
    if argv[0] == "selftest":
        return selftest()
    ok, msg = check(argv[0])
    print(msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
