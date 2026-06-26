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
LOOP = _load("app_loop", os.path.join(BIN, "app-loop.py"))
COMMIT = _load("app_commit", os.path.join(BIN, "app-commit.py"))
GATEPROTECT = os.path.join(BIN, "gate-protect.py")
HOOKS = os.path.join(ROOT, "app-factory", "hooks", "hooks.json")

# a real bar WITH TEETH (fails against an empty build) — required by app-commit's calibration floor
TEETH_BAR = ("import os, sys\nsys.path.insert(0, os.path.join(sys.argv[1], 'build'))\nimport thing\n"
             "sys.exit(0 if thing.ok else 1)\n")
SPEC1 = ('---\nkind: spec\nname: cli\nmaturity: cultivated\n---\n# cli\n```json\n'
         '{"title":"x","cell":"spec.task.cli","acceptance_criteria":[{"id":"a1","check":"ok"}],'
         '"non_goals":["v1"],"decomposition":{"tickets":[{"id":"t1","target_cell":"capability.task.thing",'
         '"acceptance":{"cmd":"spec/bars/t1.py"},"covers":["a1"]}]}}\n```\n')
SPEC2 = SPEC1.replace('"non_goals":["v1"]', '"non_goals":["v1","added-in-revision"]')


def build(proj):
    state = os.path.join(proj, ".factory", "state")
    subprocess.run([PY, os.path.join(BIN, "app-new.py"), os.path.basename(proj), "--into", os.path.dirname(proj)], capture_output=True)
    os.makedirs(os.path.join(proj, "spec", "bars"), exist_ok=True)
    open(os.path.join(proj, "spec", "bars", "t1.py"), "w").write(TEETH_BAR)
    open(os.path.join(proj, "build", "thing.py"), "w").write("ok = True\n")
    open(os.path.join(proj, "spec", "cli.md"), "w").write(SPEC1)
    # --seal: simulate the entailment-critic + human seal so the rubric is `validated` and the loop can run
    subprocess.run([PY, os.path.join(BIN, "app-commit.py"), proj, "spec/cli.md", "--seal"], capture_output=True)
    subprocess.run([PY, os.path.join(KERNEL, "validate.py"), "ontology.task.domain", "--dir", state, "--harness", "x",
                    "--", PY, "-c", "import sys; sys.exit(0)"], capture_output=True)
    subprocess.run([PY, os.path.join(KERNEL, "validate.py"), "capability.task.thing", "--dir", state, "--harness", "x",
                    "--", PY, os.path.join(proj, "spec", "bars", "t1.py"), proj], capture_output=True)
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
    ok("regen-removes-build", not os.path.isfile(os.path.join(proj, "build", "thing.py")))   # old code not re-trusted

    # ── distillation ──
    for cid in ("capability.task.aa", "capability.task.bb"):
        _led.append(state, {"operation": "validate", "actor": "v", "cell_id": cid, "result": "fail",
                            "rationale": f"sealed acceptance failed — FAIL {cid} not advanced", "ts": "t"})
    _led.append(state, {"operation": "validate", "actor": "v", "cell_id": "capability.task.cc", "result": "pass",
                        "rationale": "one-off pass", "ts": "t"})
    written, _aged = DISTILL.distill(proj, min_occur=2)
    anti = [w for w in written if w.startswith("anti-pattern")]
    ok("distill-recurring", bool(anti))
    doc = open(os.path.join(proj, "knowledge", "patterns", anti[0] + ".md")).read() if anti else ""
    ok("distill-provenance", "capability.task.aa" in doc and "capability.task.bb" in doc)
    ok("distill-proposes-draft", "maturity: draft" in doc)
    ok("distill-one-off-skipped", not any(w.startswith("solution") for w in written))
    # freshness: a pre-existing pattern from a superseded window is AGED to stale (the filter is live, not decorative)
    os.makedirs(os.path.join(proj, "knowledge", "patterns"), exist_ok=True)
    open(os.path.join(proj, "knowledge", "patterns", "superseded.md"), "w").write(
        "---\nkind: knowledge\nname: superseded\nmaturity: draft\ndistilled_window: ledger[-1]@1\n---\n# old\n")
    for i in range(8):
        _led.append(state, {"operation": "validate", "actor": "v", "cell_id": "capability.task.zz",
                            "result": "pass", "rationale": f"distinct run {i}", "ts": f"u{i}"})
    _w2, aged2 = DISTILL.distill(proj, window=2, min_occur=2)
    ok("distill-ages-superseded", "superseded" in aged2)

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

    # ── keystone integrity (the harness-council's three Criticals, verified on the BUILT code) ──
    # C1 — the deny gate is WIRED always-on in the plugin hooks.json (not merely that is_protected's logic works)
    hk = json.load(open(HOOKS))
    ok("keystone-gate-wired", "gate-protect.py" in json.dumps(hk.get("hooks", {}).get("PreToolUse", [])))
    # C1 — the wired gate actually DENIES a forged write to the .factory verifier substrate (exit 2 via the hook)
    deny_in = json.dumps({"tool_name": "Write", "tool_input": {
        "file_path": os.path.join(proj, ".factory", "state", "signals", "x", "forged.json")}})
    ok("keystone-gate-denies", subprocess.run([PY, GATEPROTECT, "--hook"], input=deny_in,
                                              capture_output=True, text=True).returncode == 2)
    # C1 — a legitimate worker write (build/) is ALLOWED (the gate doesn't break the real flow)
    allow_in = json.dumps({"tool_name": "Write", "tool_input": {"file_path": os.path.join(proj, "build", "thing.py")}})
    ok("keystone-build-allowed", subprocess.run([PY, GATEPROTECT, "--hook"], input=allow_in,
                                                capture_output=True, text=True).returncode == 0)
    # C2 — a tautology bar (passes against an empty build) is REJECTED at commit, not rubber-stamped `validated`
    kp = os.path.join(tmp, "kteeth")
    subprocess.run([PY, os.path.join(BIN, "app-new.py"), "kteeth", "--into", tmp], capture_output=True)
    os.makedirs(os.path.join(kp, "spec", "bars"), exist_ok=True)
    open(os.path.join(kp, "spec", "bars", "t1.py"), "w").write("import sys; sys.exit(0)\n")   # tautology
    open(os.path.join(kp, "spec", "cli.md"), "w").write(SPEC1)
    rct, msgt = COMMIT.crystallize(kp, "spec/cli.md")
    ok("keystone-bar-teeth", rct == 1 and "TEETH" in msgt.upper())
    # C2 (deeper) — an import-only bar (has teeth via ImportError, but asserts NO behaviour) must mint the
    # rubric `instantiated`, NOT `validated`: the loop can't auto-trust a bar that merely imports the build.
    kp2 = os.path.join(tmp, "kteeth2")
    subprocess.run([PY, os.path.join(BIN, "app-new.py"), "kteeth2", "--into", tmp], capture_output=True)
    os.makedirs(os.path.join(kp2, "spec", "bars"), exist_ok=True)
    open(os.path.join(kp2, "spec", "bars", "t1.py"), "w").write(   # import-only: teeth, tests nothing
        "import os, sys\nsys.path.insert(0, os.path.join(sys.argv[1], 'build'))\nimport thing\nsys.exit(0)\n")
    open(os.path.join(kp2, "spec", "cli.md"), "w").write(SPEC1)
    COMMIT.crystallize(kp2, "spec/cli.md")                          # NO --seal
    kp2_state = os.path.join(kp2, ".factory", "state")
    rub = next((c for c in _lat.load(kp2_state)["cells"] if c["layer"] == "rubric" and c["slug"] == "thing"), None)
    ok("keystone-teeth-not-validated", rub is not None and rub["maturity"] == "instantiated")
    ok("keystone-teeth-undispatchable", not LOOP.dispatchable(_lat.load(kp2_state), kp2))   # loop won't run it
    COMMIT.crystallize(kp2, "spec/cli.md", seal=True)              # the entailment seal
    rub2 = next((c for c in _lat.load(kp2_state)["cells"] if c["layer"] == "rubric" and c["slug"] == "thing"), None)
    ok("keystone-seal-validates", rub2 is not None and rub2["maturity"] == "validated")
    # C3a — editing a committed spec then running the LOOP (NOT /app-regenerate) cascades the ticket stale
    lp = os.path.join(tmp, "kstale")
    lstate = build(lp)
    assert cap(lstate)["maturity"] == "validated", "keystone precondition"
    open(os.path.join(lp, "spec", "cli.md"), "w").write(SPEC2)        # edit the committed spec out of band
    LOOP.recompute_staleness(lstate, lp)                             # exactly what /app-loop does FIRST
    ok("loop-recomputes-staleness", cap(lstate)["maturity"] == "stale")
    ok("loop-stale-not-dispatchable", not LOOP.dispatchable(_lat.load(lstate), lp))
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
