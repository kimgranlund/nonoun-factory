#!/usr/bin/env python3
"""app-loop.py — the bounded loop CONTROLLER (the `/app-loop` orchestrator's deterministic half).

Like harness-forge's harness-builder, the control flow is CODE and the dispatch is the model: the
`/app-loop` command (the orchestrator) calls these subcommands to DECIDE, and between them dispatches
the `app-worker` (writes one ticket's code) and the independent `app-validator` (mints the signal). The
decisions never live in the model:

  app-loop.py arm    --dir D [--max-iterations N --max-cells M --wall-clock-s S] [--request-tier T]
  app-loop.py next   --dir D                 # the top ready DISPATCHABLE ticket, or "STOP: <reason>" (exit 3)
  app-loop.py advance --dir D --project P --cell C   # headless: run the sealed bar via validate.py (worker output assumed)
  app-loop.py check  --dir D [--no-progress-n N]      # block stuck cells; "CONTINUE" or "STOP: <reason>" (exit 3)
  app-loop.py stop   --dir D                 # end the run + report
  app-loop.py run    --dir D --project P [caps] [--no-progress-n N]   # headless: drive the whole loop to a stop
  app-loop.py selftest

A "dispatchable ticket" is a READY `capability` cell whose verifier rubric is `validated` and carries a
sealed acceptance (`asset_ref`) — exactly what crystallization produces, so the loop ignores non-ticket
cells. Doneness is the validated signal, never the worker's claim; autonomy above attended is gated by the
earned trust tier. Stdlib, Python 3.8+.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL = os.path.join(os.path.dirname(HERE), "kernel")
sys.path.insert(0, KERNEL)
import lattice as _lat   # noqa: E402
import ledger as _led    # noqa: E402


def _k(script, *args):
    return subprocess.run([sys.executable, os.path.join(KERNEL, script), *args], capture_output=True, text=True)


def _flag(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def dispatchable(lat, project=None):
    """Ranked READY tickets to VALIDATE: capability cells whose verifier rubric is validated and carries a
    sealed bar — and (when `project` is given) whose build artifact already EXISTS. A ticket with no build
    is not the validate loop's job; it needs AI building (`/app-loop` in a session), so it is excluded here
    rather than spun against a missing artifact."""
    out = []
    for p, c, _r in _lat.rank(lat):
        if c.get("layer") != "capability" or not c.get("verifier"):
            continue
        v = _lat.find(lat, c["verifier"])
        if not (v and v.get("maturity") == "validated" and v.get("asset_ref")):
            continue
        if project is not None and not (c.get("asset_ref") and os.path.isfile(os.path.join(project, c["asset_ref"]))):
            continue
        out.append((p, c))
    return out


def arm(state, caps, request_tier=None):
    if request_tier is not None:
        tier = _led.trust_tier(_led.read(state))[0]
        if tier < request_tier:
            return 1, (f"REFUSED — requested Tier {request_tier} but earned Tier {tier}. Run attended (Tier 0) "
                       f"or earn it first (independent refuter checks via app-refute.py).")
    r = _k("run-budget.py", "start", *caps, "--dir", state)
    return r.returncode, (r.stdout or r.stderr).strip()


def advance(state, project, cell_id):
    """Headless advancer: the worker's build artifact is assumed present; run the SEALED bar via the
    independent validate.py path (in a live loop this is the app-worker → app-validator dispatch)."""
    lat = _lat.load(state)
    c = _lat.find(lat, cell_id)
    if c is None:
        return 2, f"no such cell {cell_id}"
    v = _lat.find(lat, c.get("verifier", ""))
    acc = v.get("asset_ref") if v else None
    build = c.get("asset_ref")
    if not acc:
        return 2, f"{cell_id}: verifier carries no sealed bar"
    if not build or not os.path.isfile(os.path.join(project, build)):
        _led.append(state, {"operation": "validate", "actor": "app-validator", "cell_id": cell_id, "result": "fail",
                            "rationale": f"no build artifact at {build} — needs implementation", "cost": {"iterations": 1}})
        return 1, f"{cell_id}: worker has not produced {build} — cannot validate (needs implementation)"
    r = _k("validate.py", cell_id, "--dir", state, "--harness", "app-loop", "--",
           sys.executable, os.path.join(project, acc), project)
    _led.append(state, {"operation": "validate", "actor": "app-validator", "cell_id": cell_id,
                        "result": "pass" if r.returncode == 0 else "fail",
                        "rationale": ("sealed acceptance passed" if r.returncode == 0
                                      else f"sealed acceptance failed — {(r.stdout or r.stderr).strip()[-160:]}"),
                        "cost": {"iterations": 1}})
    return (0 if r.returncode == 0 else 1), (r.stdout or r.stderr).strip()


def check(state, n=3):
    evs = _led.read(state)
    blocked = []
    for s in _led.no_progress(evs, n):
        lat = _lat.load(state)
        _lat.set_blocked(lat, s["cell_id"], blocked=True, reason=f"no-progress ({s['fails']} fails)")
        _lat.save(state, lat)
        blocked.append(s["cell_id"])
    if _k("run-budget.py", "status", "--dir", state).returncode == 1:
        return 3, "STOP: budget exhausted"
    return 0, "CONTINUE" + (f" (blocked stuck: {', '.join(blocked)})" if blocked else "")


def stop(state):
    _k("run-budget.py", "stop", "--dir", state)
    lat = _lat.load(state)
    val = [_lat.cid(c) for c in lat["cells"] if c.get("layer") == "capability" and c.get("maturity") == "validated"]
    blk = [_lat.cid(c) for c in lat["cells"] if c.get("layer") == "capability" and _lat.is_blocked(c)]
    pend = [_lat.cid(c) for c in lat["cells"] if c.get("layer") == "capability"
            and c.get("maturity") != "validated" and not _lat.is_blocked(c)]
    n_iter = len([e for e in _led.read(state) if e.get("operation") == "validate"])
    lines = [f"run stopped — {n_iter} validate iteration(s)",
             f"  tickets validated: {len(val)}  ({', '.join(val) or 'none'})",
             f"  blocked:           {len(blk)}  ({', '.join(blk) or 'none'})",
             f"  still pending:     {len(pend)}  ({', '.join(pend) or 'none'})"]
    return 0, "\n".join(lines)


def run(state, project, caps, n=3):
    rc, msg = arm(state, caps)
    out = [f"armed: {msg}"]
    if rc != 0:
        return rc, "\n".join(out)
    max_cells = int(_flag(caps, "--max-cells", "0")) or None
    advanced = 0
    while True:
        d = dispatchable(_lat.load(state), project)
        if not d:
            out.append("· next → STOP: frontier empty (nothing to validate — built tickets only)")
            break
        cell = _lat.cid(d[0][1])
        arc, amsg = advance(state, project, cell)
        advanced += 1
        out.append(f"· advance {cell} → {'PASS' if arc == 0 else 'FAIL'}")
        crc, cmsg = check(state, n)
        if crc == 3:
            out.append(f"· check → {cmsg}")
            break
        if cmsg != "CONTINUE":
            out.append(f"· check → {cmsg}")
        if max_cells and advanced >= max_cells:
            out.append(f"· STOP: max-cells {max_cells} reached")
            break
    _, rep = stop(state)
    out.append(rep)
    return 0, "\n".join(out)


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    if not argv:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    op = argv[0]
    state = _flag(argv, "--dir", ".agents/harness")
    project = _flag(argv, "--project")
    cap_args = []
    for fl in ("--max-iterations", "--max-cells", "--max-cost", "--wall-clock-s"):
        if fl in argv:
            cap_args += [fl, _flag(argv, fl)]
    n = int(_flag(argv, "--no-progress-n", "3"))
    if op == "arm":
        rt = _flag(argv, "--request-tier")
        rc, msg = arm(state, cap_args, int(rt) if rt is not None else None)
    elif op == "next":
        d = dispatchable(_lat.load(state), project or os.path.dirname(os.path.dirname(state.rstrip("/"))))
        if not d:
            print("STOP: frontier empty (nothing to validate — built tickets only)")
            return 3
        print(_lat.cid(d[0][1]))
        return 0
    elif op == "advance":
        rc, msg = advance(state, project, _flag(argv, "--cell"))
    elif op == "check":
        rc, msg = check(state, n)
    elif op == "stop":
        rc, msg = stop(state)
    elif op == "run":
        rc, msg = run(state, project, cap_args, n)
    else:
        print(f"unknown op {op!r}", file=sys.stderr)
        return 2
    print(msg)
    return rc


def _mk(state, build_ok):
    """Build a minimal 1-ticket scenario in `state` (+ its project) for the selftest."""
    project = os.path.dirname(os.path.dirname(state.rstrip("/")))
    os.makedirs(os.path.join(project, "build"), exist_ok=True)
    lat = {"version": "1", "project": "t", "frontier_scope": "task", "produced_by": "app-factory", "cells": [
        {"layer": "ontology", "scope": "task", "slug": "d", "maturity": "validated", "depends_on": [], "signal_refs": ["x"]},
        {"layer": "spec", "scope": "task", "slug": "s", "maturity": "validated", "depends_on": [], "signal_refs": ["x"]},
        {"layer": "rubric", "scope": "task", "slug": "a", "maturity": "validated", "depends_on": ["spec.task.s"],
         "asset_ref": "acc.py", "signal_refs": ["x"]},
        {"layer": "capability", "scope": "task", "slug": "a", "maturity": "defined", "depends_on": ["spec.task.s"],
         "verifier": "rubric.task.a", "asset_ref": "build/a.py"},
    ]}
    _lat.save(state, lat)
    with open(os.path.join(project, "acc.py"), "w") as f:
        f.write("import os,sys\nsys.path.insert(0,os.path.join(sys.argv[1],'build'))\n"
                "import a\nsys.exit(0 if a.ok() else 1)\n")
    with open(os.path.join(project, "build", "a.py"), "w") as f:
        f.write(f"def ok():\n    return {build_ok}\n")
    return project


def selftest():
    import tempfile
    fails = []
    def expect(c, m):
        if not c:
            fails.append(m)
    # success: the loop drives the one ticket to validated, then stops frontier-empty
    with tempfile.TemporaryDirectory() as root:
        state = os.path.join(root, ".factory", "state")
        os.makedirs(os.path.join(state, "ledger"))
        proj = _mk(state, True)
        rc, msg = run(state, proj, ["--max-cells", "5"], 3)
        expect(rc == 0, f"run errored: {msg}")
        expect(_lat.find(_lat.load(state), "capability.task.a")["maturity"] == "validated",
               f"loop did not validate the ticket:\n{msg}")
        expect("tickets validated: 1" in msg, f"report wrong:\n{msg}")
    # no-progress: a failing bar is retried then BLOCKED, and the loop halts (not infinite)
    with tempfile.TemporaryDirectory() as root:
        state = os.path.join(root, ".factory", "state")
        os.makedirs(os.path.join(state, "ledger"))
        proj = _mk(state, False)
        rc, msg = run(state, proj, ["--max-cells", "20"], 3)
        expect(_lat.is_blocked(_lat.find(_lat.load(state), "capability.task.a")),
               f"a repeatedly-failing ticket must be blocked:\n{msg}")
        expect("blocked:           1" in msg, f"report should show 1 blocked:\n{msg}")
        expect(msg.count("· advance") == 3, f"no-progress should block after exactly 3 fails:\n{msg}")
    if fails:
        sys.stderr.write("app-loop selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("app-loop selftest: OK (drives a ready ticket to validated then stops frontier-empty; a repeatedly-"
          "failing ticket is blocked after the no-progress threshold and the loop halts — bounded, not infinite)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
