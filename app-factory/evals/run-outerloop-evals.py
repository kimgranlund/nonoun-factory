#!/usr/bin/env python3
"""run-outerloop-evals.py — the internal eval flow for the outer loop.

Builds a project, validates a ticket, then drives it through distillation, regeneration, and context
assembly — asserting each property and scoring against rubric/outer-loop.rubric.json. Exit 0 iff the
pass_threshold is met. Stdlib only; Python 3.8+.
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))           # repo root
BIN = os.path.join(ROOT, "app-factory", "bin")
KERNEL = os.path.join(ROOT, "app-factory", "kernel")
RUBRIC = os.path.join(HERE, "outer-loop.rubric.json")
PY = sys.executable
sys.path.insert(0, KERNEL)
import lattice as _lat   # noqa: E402
import ledger as _led    # noqa: E402


def _load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


REGEN = _load("app_regen", os.path.join(BIN, "app-regen.py"))
DISTILL = _load("app_distill", os.path.join(BIN, "app-distill.py"))
CONTEXT = _load("app_context", os.path.join(BIN, "app-context.py"))

SPEC1 = ('---\nkind: spec\nname: cli\nmaturity: cultivated\n---\n# cli\n```json\n'
         '{"title":"x","cell":"spec.task.cli","acceptance_criteria":[{"id":"a1","check":"ok"}],'
         '"non_goals":["v1"],"decomposition":{"tickets":[{"id":"t1","target_cell":"capability.task.thing",'
         '"acceptance":{"cmd":"spec/bars/t1.py"},"covers":["a1"]}]}}\n```\n')
SPEC2 = SPEC1.replace('"non_goals":["v1"]', '"non_goals":["v1","added-in-revision"]')


def build(proj):
    state = os.path.join(proj, ".factory", "state")
    subprocess.run([PY, os.path.join(BIN, "app-new.py"), os.path.basename(proj), "--into", os.path.dirname(proj)], capture_output=True)
    os.makedirs(os.path.join(proj, "spec", "bars"), exist_ok=True)
    open(os.path.join(proj, "spec", "bars", "t1.py"), "w").write("import sys; sys.exit(0)\n")
    open(os.path.join(proj, "build", "thing.py"), "w").write("ok = True\n")
    open(os.path.join(proj, "spec", "cli.md"), "w").write(SPEC1)
    subprocess.run([PY, os.path.join(BIN, "app-commit.py"), proj, "spec/cli.md"], capture_output=True)
    subprocess.run([PY, os.path.join(KERNEL, "validate.py"), "ontology.task.domain", "--dir", state, "--harness", "x",
                    "--", PY, "-c", "import sys; sys.exit(0)"], capture_output=True)
    subprocess.run([PY, os.path.join(KERNEL, "validate.py"), "capability.task.thing", "--dir", state, "--harness", "x",
                    "--", PY, os.path.join(proj, "spec", "bars", "t1.py")], capture_output=True)
    return state


def cap(state):
    return next(c for c in _lat.load(state)["cells"] if c["layer"] == "capability" and c["slug"] == "thing")


def run_scenarios(tmp):
    R = []
    def ok(i, cond, d=""):
        R.append((i, bool(cond), d))

    proj = os.path.join(tmp, "demo")
    state = build(proj)
    old_hash = cap(state).get("validated_against", {}).get("spec.task.cli")
    assert cap(state)["maturity"] == "validated", "precondition"

    # ── regeneration ──
    open(os.path.join(proj, "spec", "cli.md"), "w").write(SPEC2)
    REGEN.regenerate(proj, "spec/cli.md")
    c = cap(state)
    ok("regen-reopens", c["maturity"] == "defined")
    ok("regen-new-hash", c.get("validated_against", {}).get("spec.task.cli") not in (None, old_hash))
    sig = os.path.join(state, "signals", "capability.task.thing")
    ok("regen-signal-invalidated", not os.path.isdir(sig) or not os.listdir(sig))
    ok("regen-ledgered", any(e.get("operation") == "regenerate" for e in _led.read(state)))

    # ── distillation ──
    for cid in ("capability.task.aa", "capability.task.bb"):
        _led.append(state, {"operation": "validate", "actor": "v", "cell_id": cid, "result": "fail",
                            "rationale": f"sealed acceptance failed — FAIL {cid} not advanced", "ts": "t"})
    _led.append(state, {"operation": "validate", "actor": "v", "cell_id": "capability.task.cc", "result": "pass",
                        "rationale": "one-off pass", "ts": "t"})
    written = DISTILL.distill(proj, min_occur=2)
    anti = [w for w in written if w.startswith("anti-pattern")]
    ok("distill-recurring", bool(anti))
    doc = open(os.path.join(proj, "knowledge", "patterns", anti[0] + ".md")).read() if anti else ""
    ok("distill-provenance", "capability.task.aa" in doc and "capability.task.bb" in doc)
    ok("distill-proposes-draft", "maturity: draft" in doc)
    ok("distill-one-off-skipped", not any(w.startswith("solution") for w in written))

    # ── context assembly ──
    open(os.path.join(proj, "knowledge", "conventions.md"), "w").write("# conventions\n")
    os.makedirs(os.path.join(proj, "knowledge", "patterns"), exist_ok=True)
    open(os.path.join(proj, "knowledge", "patterns", "fresh.md"), "w").write("---\nmaturity: draft\n---\n# fresh\n")
    open(os.path.join(proj, "knowledge", "patterns", "stale.md"), "w").write("---\nmaturity: stale\n---\n# stale\n")
    out = CONTEXT.assemble(proj, "t1")
    paths = [s["path"] for s in out["sources"]]
    ok("context-named-sources", all(os.path.isfile(os.path.join(proj, p)) for p in paths) and len(paths) >= 2)
    ok("context-deterministic", CONTEXT.assemble(proj, "t1")["sources"] == out["sources"])
    ok("context-excludes-stale", "knowledge/patterns/stale.md" not in paths)
    ok("context-no-bar", not any("bars/" in p or ".factory/acceptance" in p for p in paths))
    ok("context-includes-knowledge", "knowledge/conventions.md" in paths)
    ok("context-includes-pattern", "knowledge/patterns/fresh.md" in paths)
    return R


def main(argv):
    with tempfile.TemporaryDirectory() as tmp:
        results = run_scenarios(tmp)
    passed = {i for i, p, _ in results if p}
    rubric = json.load(open(RUBRIC))
    print(f"\n  app-factory outer-loop eval  ({len(passed)}/{len(results)} scenarios)\n")
    failed = 0
    for d in rubric["dimensions"]:
        dim_ok = all(g in passed for g in d["gated_by"])
        failed += 0 if dim_ok else 1
        print(f"  [{'PASS' if dim_ok else 'FAIL'}] {d['id']:<26} {sum(g in passed for g in d['gated_by'])}/{len(d['gated_by'])}")
        for g in d["gated_by"]:
            if g not in passed:
                print(f"          ✗ {g}")
    score = (len(rubric["dimensions"]) - failed) / len(rubric["dimensions"])
    print(f"\n  rubric score: {score:.2f}  (threshold {rubric['pass_threshold']})  → "
          f"{'PASS' if score >= rubric['pass_threshold'] else 'FAIL'}\n")
    return 0 if score >= rubric["pass_threshold"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
