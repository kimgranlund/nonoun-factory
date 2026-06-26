#!/usr/bin/env python3
"""run-evals.py — the internal eval flow for the dev-server's foolproof UX.

Boots serve.py on a free port over a temp projects root with fixtures, exercises every sloppy-user
scenario against the live API (and inspects the served UI assets for required affordances), then scores
the results against rubric/foolproof-ux.rubric.json. Exit 0 iff the rubric's pass_threshold is met.

  run-evals.py [--keep]     # --keep leaves the temp root + server up for inspection
Stdlib only; Python 3.8+.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.join(os.path.dirname(HERE), "serve.py")
RUBRIC = os.path.join(os.path.dirname(HERE), "rubric", "foolproof-ux.rubric.json")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))   # repo root
BIN = os.path.join(ROOT, "app-factory", "bin")
KERNEL = os.path.join(os.path.dirname(BIN), "kernel")
PY = sys.executable

SPEC = ('---\nkind: spec\nname: cli\nmaturity: cultivated\ngoal: true\n---\n# cli\n```json\n'
        '{"title":"x","cell":"spec.task.cli","acceptance_criteria":[{"id":"a1","check":"thing.ok is true"}],'
        '"non_goals":["none"],"decomposition":{"tickets":[{"id":"t1","target_cell":"capability.task.thing",'
        '"acceptance":{"cmd":"spec/bars/t1.py"},"covers":["a1"]}]}}\n```\n')
BAR = ("import os, sys\nsys.path.insert(0, os.path.join(sys.argv[1], 'build'))\n"
       "try:\n    import thing\n    assert thing.ok\nexcept Exception:\n    sys.exit(1)\nsys.exit(0)\n")


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True)


def fixture(root, name, built=True, commit=True, ok=True):
    sh(PY, os.path.join(BIN, "app-new.py"), name, "--into", root)
    proj = os.path.join(root, name)
    if commit:
        os.makedirs(os.path.join(proj, "spec", "bars"), exist_ok=True)
        open(os.path.join(proj, "spec", "bars", "t1.py"), "w").write(BAR)
        open(os.path.join(proj, "spec", "cli.md"), "w").write(SPEC)
        if built:
            open(os.path.join(proj, "build", "thing.py"), "w").write(f"ok = {ok}\n")
        # --seal: these fixtures simulate a committed+sealed project (entailment-critic + human seal done),
        # so the rubrics are `validated` and the loop can dispatch them; an unsealed rubric is `instantiated`.
        sh(PY, os.path.join(BIN, "app-commit.py"), proj, "spec/cli.md", "--seal")
        state = os.path.join(proj, ".factory", "state")
        sh(PY, os.path.join(KERNEL, "validate.py"), "ontology.task.domain", "--dir", state,
           "--harness", "x", "--", PY, "-c", "import sys; sys.exit(0)")
    return proj


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def get(base, path, raw=False):
    try:
        with urllib.request.urlopen(base + path, timeout=15) as r:
            body = r.read().decode()
            return r.status, (body if raw else json.loads(body or "null"))
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return e.code, (body if raw else json.loads(body or "null"))


def post(base, path):
    req = urllib.request.Request(base + path, method="POST", data=b"")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "null")


def wait_idle(base, name, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        _, st = get(base, f"/api/project/{name}/run")
        if isinstance(st, dict) and not st.get("running"):
            return st
        time.sleep(0.3)
    return {"running": True, "result": None, "steps": []}


# ---- scenarios: each returns (id, passed, detail) ----
def run_scenarios(base, root):
    R = []
    def ok(i, cond, detail=""):
        R.append((i, bool(cond), detail))

    # connection / read
    s, projs = get(base, "/api/projects")
    names = {p["name"] for p in projs} if isinstance(projs, list) else set()
    ok("projects-list", s == 200 and {"demo", "empty", "needsbuild", "failing"} <= names and all(p["running"] is False for p in projs))

    s, emp = get(base, "/api/project/empty")
    ok("empty-state", s == 200 and emp["tickets"] == [] and emp["dispatchable"] == 0)

    s, dem = get(base, "/api/project/demo")
    ok("detail-contract", s == 200 and dem["tickets"] and "built" in dem["tickets"][0]
       and dem["dispatchable"] >= 1 and "run" in dem and "builds" in dem)
    ok("builds-listed", any(b["path"].startswith("build/") for b in dem.get("builds", [])))
    ok("needs-build-flag", get(base, "/api/project/needsbuild")[1]["tickets"][0]["built"] is False)

    bp = dem["builds"][0]["path"] if dem.get("builds") else "build/thing.py"
    s, fv = get(base, f"/api/project/demo/file?path={bp}")
    ok("file-view", s == 200 and isinstance(fv, dict) and fv.get("content"))
    ok("path-traversal-denied", get(base, "/api/project/demo/file?path=../../../etc/hosts")[0] == 403
       and get(base, "/api/project/demo/file?path=.factory/state/lattice.json")[0] == 403)

    ok("error-json", get(base, "/api/project/nope")[0] == 404 and isinstance(get(base, "/api/project/nope")[1], dict)
       and post(base, "/api/project/demo/bogus")[0] == 404)

    # concurrency — deterministic via the lock file
    lock = os.path.join(root, "demo", ".factory", "state", "run", "ui-run.lock")
    os.makedirs(os.path.dirname(lock), exist_ok=True)
    open(lock, "w").write("{}")
    ok("run-lock-409", post(base, "/api/project/demo/loop")[0] == 409)
    ok("reset-blocked-while-running", post(base, "/api/project/demo/reset")[0] == 409)
    os.remove(lock)

    # real-time run on demo
    s, started = post(base, "/api/project/demo/loop")
    ok("validate-run-async", s == 202 and started.get("status") == "started")
    st = wait_idle(base, "demo")
    ok("progress-steps", any(x.get("phase") == "advance" for x in st.get("steps", [])))
    ok("validate-run-result", bool(st.get("result")) and st["result"].get("validated", 0) >= 1)

    # a built-but-failing ticket → blocked with a friendly reason
    post(base, "/api/project/failing/loop")
    wait_idle(base, "failing")
    _, fb = get(base, "/api/project/failing")
    ok("blocked-reason", any(t["status"] == "blocked" and t.get("reason") for t in fb["tickets"]))

    # reset re-arms demo
    s, rs = post(base, "/api/project/demo/reset")
    _, dem2 = get(base, "/api/project/demo")
    ok("reset-rearms", s == 200 and dem2["dispatchable"] >= 1
       and all(t["status"] != "validated" for t in dem2["tickets"]))

    # freshness — editing a doc bumps the version
    v1 = get(base, "/api/project/demo")[1]["version"]
    time.sleep(1.05)
    open(os.path.join(root, "demo", "idea.md"), "a").write("\nedited\n")
    v2 = get(base, "/api/project/demo")[1]["version"]
    ok("doc-freshness", v2 != v1)

    # served UI assets carry the required affordances
    _, appjs = get(base, "/app.js", raw=True)
    _, html = get(base, "/", raw=True)
    js = appjs if isinstance(appjs, str) else ""
    ok("asset-status-pill", "disconnected" in js and ".onerror" in js)
    ok("asset-why-disabled", "Commit a spec" in js and "All tickets" in js)
    ok("asset-progress", '"step"' in js or "step" in js and "phase" in js and "done" in js)
    ok("asset-results", "/file?path=" in js)
    ok("asset-honest-framing", "Validate frontier" in js and "/app-loop" in js and "Claude Code" in js)
    return R


def main(argv):
    keep = "--keep" in argv
    root = tempfile.mkdtemp(prefix="af-evals-")
    fixture(root, "empty", commit=False)
    fixture(root, "demo", built=True)
    fixture(root, "needsbuild", built=False)
    fixture(root, "failing", built=True, ok=False)
    port = free_port()
    srv = subprocess.Popen([PY, SERVER, "--root", root, "--port", str(port)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        for _ in range(40):
            try:
                if get(base, "/api/projects")[0] == 200:
                    break
            except Exception:
                pass
            time.sleep(0.25)
        results = run_scenarios(base, root)
    finally:
        if not keep:
            srv.terminate()
            shutil.rmtree(root, ignore_errors=True)
        else:
            print(f"\n[--keep] server: {base}   root: {root}", file=sys.stderr)

    passed = {i for i, p, _ in results if p}
    rubric = json.load(open(RUBRIC))
    print(f"\n  app-factory dev-server — foolproof-ux eval  ({len(passed)}/{len(results)} scenarios)\n")
    failed_dims = 0
    for d in rubric["dimensions"]:
        gates = d["gated_by"]
        dim_ok = all(g in passed for g in gates)
        failed_dims += 0 if dim_ok else 1
        print(f"  [{'PASS' if dim_ok else 'FAIL'}] {d['id']:<24} {sum(g in passed for g in gates)}/{len(gates)} gates")
        for g in gates:
            res = next((r for r in results if r[0] == g), None)
            mark = "✓" if (res and res[1]) else "✗"
            if not (res and res[1]):
                print(f"          {mark} {g}" + (f" — {res[2]}" if res and res[2] else (" — (not run)" if not res else "")))
    score = (len(rubric["dimensions"]) - failed_dims) / len(rubric["dimensions"])
    print(f"\n  rubric score: {score:.2f}  (threshold {rubric['pass_threshold']})  → "
          f"{'PASS' if score >= rubric['pass_threshold'] else 'FAIL'}\n")
    return 0 if score >= rubric["pass_threshold"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
