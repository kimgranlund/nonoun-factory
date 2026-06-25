#!/usr/bin/env python3
"""app-regen.py — the outer loop's regeneration: an edited spec invalidates downstream, then re-opens it.

The harness-council's stale-but-trusted Critical: when a committed spec changes, its decomposed tickets and
their minted signals must NOT stay trusted. This closes that. Given a committed spec that has been edited:

  1. GATE the edited spec (regeneration from a broken spec is refused).
  2. CASCADE staleness — flip the spec cell and every dependent whose `validated_against` hash no longer
     matches the new spec content to `stale`, using the kernel's own `propagate_staleness` graph walk, and
     ledger the invalidation (provenance, not memory).
  3. RE-CRYSTALLIZE — drop the now-stale spec-derived cells + signals + ticket files and re-commit, so the
     frontier re-opens with fresh `defined` tickets stamped against the NEW spec hash.

Net: a spec revision can never leave validated work trusted against an outdated definition — the loop
re-builds the affected tickets. Stdlib, Python 3.8+.

  app-regen.py <project> <spec-relpath>   # e.g. app-regen.py projects/quicklog spec/cli.md
  app-regen.py selftest
"""
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL = os.path.join(os.path.dirname(HERE), "kernel")
sys.path.insert(0, KERNEL)
import lattice as _lat   # noqa: E402
import ledger as _led    # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GATE = _load("app_spec_gate", os.path.join(HERE, "app-spec-gate.py"))


def _hash(path):
    try:
        return "sha256:" + hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    except OSError:
        return ""


def _scope_slug(cid):
    parts = cid.split(".")
    return (parts[1], parts[2]) if len(parts) == 3 else ("task", parts[-1])


def regenerate(project, spec_rel):
    project = os.path.abspath(project)
    state = os.path.join(project, ".factory", "state")
    spec_abs = os.path.join(project, spec_rel)
    if not os.path.isfile(spec_abs):
        return 2, f"no spec at {spec_abs}", []
    text = open(spec_abs, encoding="utf-8").read()
    findings = GATE.gate(text)
    if findings:
        return 1, "SPEC-GATE FAIL — regeneration refused (fix the spec first):\n  - " + "\n  - ".join(findings), []
    _fm, contract = GATE.parse(text)
    spec_cell = contract["cell"]
    new_hash = _hash(spec_abs)

    lat = _lat.load(state)
    sc = _lat.find(lat, spec_cell)
    if sc is None:
        return 1, f"{spec_cell} is not committed yet — use `/app-spec commit`, not regenerate", []

    # 2. CASCADE: flip the spec cell + hash-mismatched dependents stale (the kernel's graph walk)
    flipped = []
    if sc.get("maturity") in _lat.SETTLED:
        sc["maturity"] = "stale"
        flipped.append(spec_cell)
    flipped += _lat.propagate_staleness(lat, spec_cell, new_hash)
    _lat.save(state, lat)
    if flipped:
        _led.append(state, {"operation": "regenerate", "actor": "app-regen", "cell_id": spec_cell, "result": "stale",
                            "rationale": f"spec edited after validation; cascade flipped {len(flipped)} cell(s) stale",
                            "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds")})

    # 3. RE-CRYSTALLIZE: drop the spec-derived cells + their signals + ticket files, then re-commit fresh.
    derived = {spec_cell}
    for t in (contract.get("decomposition") or {}).get("tickets", []):
        target = t["target_cell"]
        ts_, sl = _scope_slug(target)
        derived |= {target, f"rubric.{ts_}.{sl}"}
        tf = os.path.join(project, "tickets", f"{t['id']}.md")
        if os.path.isfile(tf):
            os.remove(tf)
    lat = _lat.load(state)
    lat["cells"] = [c for c in lat["cells"] if _lat.cid(c) not in derived]
    _lat.save(state, lat)
    for cid in derived:
        shutil.rmtree(os.path.join(state, "signals", cid), ignore_errors=True)

    r = subprocess.run([sys.executable, os.path.join(HERE, "app-commit.py"), project, spec_rel],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return 1, f"re-crystallize failed: {(r.stdout or r.stderr).strip()}", flipped

    reopened = [t["target_cell"] for t in (contract.get("decomposition") or {}).get("tickets", [])]
    return 0, (f"regenerated {spec_rel}: cascaded {len(flipped)} cell(s) stale, re-crystallized → "
               f"{len(reopened)} ticket(s) re-opened as `defined` against the new spec hash"), reopened


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2:
        print("usage: app-regen.py <project> <spec-relpath>", file=sys.stderr)
        return 2
    rc, msg, _ = regenerate(pos[0], pos[1])
    print(msg)
    return rc


SPEC1 = ('---\nkind: spec\nname: cli\nmaturity: cultivated\n---\n# cli\n```json\n'
         '{"title":"x","cell":"spec.task.cli","acceptance_criteria":[{"id":"a1","check":"ok"}],'
         '"non_goals":["v1"],"decomposition":{"tickets":[{"id":"t1","target_cell":"capability.task.thing",'
         '"acceptance":{"cmd":"spec/bars/t1.py"},"covers":["a1"]}]}}\n```\n')
SPEC2 = SPEC1.replace('"non_goals":["v1"]', '"non_goals":["v1","no-sync-added-in-revision"]')


def selftest():
    import tempfile
    fails = []
    def expect(c, m):
        if not c:
            fails.append(m)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, os.path.join(HERE, "app-new.py"), "demo", "--into", tmp], capture_output=True)
        proj = os.path.join(tmp, "demo")
        state = os.path.join(proj, ".factory", "state")
        os.makedirs(os.path.join(proj, "spec", "bars"), exist_ok=True)
        open(os.path.join(proj, "spec", "bars", "t1.py"), "w").write("import sys; sys.exit(0)\n")
        open(os.path.join(proj, "build", "thing.py"), "w").write("ok = True\n")
        open(os.path.join(proj, "spec", "cli.md"), "w").write(SPEC1)
        subprocess.run([sys.executable, os.path.join(HERE, "app-commit.py"), proj, "spec/cli.md"], capture_output=True)
        subprocess.run([sys.executable, os.path.join(KERNEL, "validate.py"), "ontology.task.domain", "--dir", state,
                        "--harness", "x", "--", sys.executable, "-c", "import sys; sys.exit(0)"], capture_output=True)
        subprocess.run([sys.executable, os.path.join(KERNEL, "validate.py"), "capability.task.thing", "--dir", state,
                        "--harness", "x", "--", sys.executable, os.path.join(proj, "spec", "bars", "t1.py")], capture_output=True)
        cap = lambda: next(c for c in _lat.load(state)["cells"] if c["layer"] == "capability" and c["slug"] == "thing")
        old_hash = cap().get("validated_against", {}).get("spec.task.cli")
        expect(cap()["maturity"] == "validated", "precondition: ticket should be validated before regen")

        open(os.path.join(proj, "spec", "cli.md"), "w").write(SPEC2)    # edit the committed spec
        rc, msg, reopened = regenerate(proj, "spec/cli.md")
        expect(rc == 0, f"regenerate failed: {msg}")
        c = cap()
        expect(c["maturity"] == "defined", f"the ticket must be re-opened (`defined`), not stay validated (got {c['maturity']})")
        expect(c.get("validated_against", {}).get("spec.task.cli") != old_hash, "the spec→ticket edge must carry the NEW spec hash")
        sig = os.path.join(state, "signals", "capability.task.thing")
        expect(not os.path.isdir(sig) or not os.listdir(sig), "the old signal must be invalidated")
        evs = _led.read(state)
        expect(any(e.get("operation") == "regenerate" for e in evs), "the regeneration must be ledgered")
    if fails:
        sys.stderr.write("app-regen selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("app-regen selftest: OK (editing a committed spec cascades its validated ticket stale, re-opens it as "
          "`defined` against the new spec hash, invalidates the old signal, and ledgers the regeneration — no "
          "validated work survives an outdated definition)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
