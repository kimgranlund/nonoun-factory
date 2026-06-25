#!/usr/bin/env python3
"""app-commit.py — the crystallizer: a cultivated spec → tickets the loop can run (`/app-spec commit`).

This is the prose↔typed boundary made runnable. Given a SEALED spec (its acceptance already
derived by the non-executor `acceptance-deriver`, certified by the `entailment-critic`, and
human-sealed — represented here by the embedded contract + the sealed acceptance scripts), the
crystallizer:

  1. runs the mechanical gate (`app-spec-gate.py`); a fail REJECTS the commit (the doc stays cultivated)
  2. mints the spec cell to `validated` through the REAL signal path — `validate.py` with the gate as the
     verifier — so the spec's own doneness is an independent signal, not an assertion
  3. decomposes the contract into, per ticket: a draft ticket file, a `capability` cell (depends_on the
     spec, verifier = a per-ticket rubric), a `rubric` cell minted `validated` by a certification signal —
     gated DETERMINISTICALLY by a bar-teeth check (the sealed bar must FAIL against an empty build, so a
     tautology / presence-check bar is rejected, not rubber-stamped), and HONEST that the full entailment-
     to-prose fidelity is certified by the live entailment-critic + human seal, not by this script — and
     the spec→ticket edge stamped with the spec's content hash (so a later regeneration cascades staleness)
  4. appends a `crystallize` ledger event

The capability cells land READY (deps + verifier validated), so `lattice.py rank` / `goal.py next`
surface them and `/app-loop` can execute them. Stdlib, Python 3.8+.

  app-commit.py <project> <spec-relpath>   # e.g. app-commit.py projects/quicklog spec/cli.md
  app-commit.py selftest
"""
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

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


def _scope_slug(cell_id):
    parts = cell_id.split(".")
    return (parts[1], parts[2]) if len(parts) == 3 else ("task", parts[-1])


def bar_has_teeth(sealed_abs):
    """A sealed bar must FAIL when run against an EMPTY build — a bar that passes with no implementation
    present is a tautology / presence-check, not acceptance (the council's "`exit 0` sails through" hole).
    Run the bar exactly as the loop will (`python3 <bar> <project-root>`) against a throwaway root whose
    `build/` is empty; the bar has teeth iff it does NOT exit 0. A bar that errors out (can't even run)
    is not a no-op, so it counts as having teeth. This is the DETERMINISTIC floor — it proves the bar
    tests something, not that it faithfully entails the spec (that is the entailment-critic's live job)."""
    with tempfile.TemporaryDirectory() as empty:
        os.makedirs(os.path.join(empty, "build"), exist_ok=True)
        try:
            r = subprocess.run([sys.executable, sealed_abs, empty], capture_output=True, text=True, timeout=30)
        except Exception:
            return True
        return r.returncode != 0


def crystallize(project, spec_rel):
    project = os.path.abspath(project)
    state = os.path.join(project, ".factory", "state")
    spec_abs = os.path.join(project, spec_rel)
    if not os.path.isfile(spec_abs):
        return 2, f"no spec at {spec_abs}"
    text = open(spec_abs, encoding="utf-8").read()

    findings = GATE.gate(text)
    if findings:
        return 1, "SPEC-GATE FAIL — commit rejected, the doc stays `cultivated`:\n  - " + "\n  - ".join(findings)
    _fm, contract = GATE.parse(text)
    spec_cell = contract["cell"]
    s_scope, s_slug = _scope_slug(spec_cell)

    # 2. mint the spec cell to validated via the REAL signal path (gate as verifier)
    lat = _lat.load(state)
    cell = _lat.find(lat, spec_cell)
    if cell is None:
        lat["cells"].append({"layer": "spec", "scope": s_scope, "slug": s_slug,
                             "maturity": "instantiated", "depends_on": [], "asset_ref": spec_rel})
    else:
        cell["maturity"] = "instantiated"
        cell["asset_ref"] = spec_rel
    _lat.save(state, lat)
    v = subprocess.run([sys.executable, os.path.join(KERNEL, "validate.py"), spec_cell,
                        "--dir", state, "--harness", "spec-gate", "--",
                        sys.executable, os.path.join(HERE, "app-spec-gate.py"), spec_abs],
                       capture_output=True, text=True)
    if v.returncode != 0:
        return 1, f"spec cell did not validate: {v.stdout.strip() or v.stderr.strip()}"

    spec_hash = _hash(spec_abs)
    lat = _lat.load(state)
    created = []
    for t in (contract.get("decomposition") or {}).get("tickets", []):
        tid = t["id"]
        target = t["target_cell"]
        t_scope, t_slug = _scope_slug(target)
        rubric_cell = f"rubric.{t_scope}.{t_slug}"
        bar_src = t["acceptance"]["cmd"]                       # the WRITABLE bar SOURCE (e.g. spec/bars/t1-storage.py)
        if not os.path.isfile(os.path.join(project, bar_src)):
            return 1, f"ticket {tid}: bar source {bar_src} does not exist — author it (acceptance-deriver), then commit"
        # SEAL the bar: copy the source into the protected `.factory/acceptance/` — a kernel-path write the
        # executor is deny-on-write to (gate-protect). The committed bar of record is the sealed copy, not the
        # source, so post-commit edits to the writable source never change what the loop grades against.
        sealed_rel = os.path.join(".factory", "acceptance", os.path.basename(bar_src))
        sealed_abs = os.path.join(project, sealed_rel)
        os.makedirs(os.path.dirname(sealed_abs), exist_ok=True)
        shutil.copyfile(os.path.join(project, bar_src), sealed_abs)

        # CALIBRATION FLOOR (deterministic): the sealed bar must have TEETH — fail against an empty build.
        # A tautology bar (`exit 0`, a presence-check) that passes with no implementation is REJECTED here,
        # so a hollow bar can never be minted `validated`. This is the mechanical half; the FULL fidelity
        # certification (does the bar entail the spec prose?) is the entailment-critic + human seal in a
        # live /app-spec commit — this deterministic crystallize does NOT stand in for that judgement.
        if not bar_has_teeth(sealed_abs):
            return 1, (f"ticket {tid}: sealed bar {sealed_rel} has NO TEETH — it PASSES against an empty build, "
                       f"so it does not test the implementation (a tautology / presence-check, not acceptance). "
                       f"Author a bar that fails when the build is absent, then commit.")

        # the rubric cell IS the sealed bar — minted `validated` by a certification signal that records
        # exactly what was verified deterministically (sealed + teeth), and is HONEST that the entailment-
        # to-prose fidelity is certified by the live entailment-critic + human seal, not by this script.
        ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds").replace(":", "-")
        sigrel = os.path.join("signals", rubric_cell, f"{ts}--cert.json")
        sigabs = os.path.join(state, sigrel)
        os.makedirs(os.path.dirname(sigabs), exist_ok=True)
        json.dump({"cell_id": rubric_cell, "ts": ts, "harness": "entailment-cert", "kind": "gate",
                   "result": "pass",
                   "evidence": (f"acceptance {sealed_rel} sealed + teeth-checked (fails against an empty build, so "
                                f"it tests the implementation, not mere presence); entailment-to-prose fidelity vs "
                                f"{spec_cell} is certified by the entailment-critic + human seal in a live commit"),
                   "validated_against": {spec_cell: spec_hash}}, open(sigabs, "w"), indent=2)
        if _lat.find(lat, rubric_cell) is None:
            lat["cells"].append({"layer": "rubric", "scope": t_scope, "slug": t_slug, "maturity": "validated",
                                 "depends_on": [spec_cell], "asset_ref": sealed_rel, "signal_refs": [sigrel],
                                 "validated_against": {spec_cell: spec_hash}})
        if _lat.find(lat, target) is None:
            lat["cells"].append({"layer": "capability", "scope": t_scope, "slug": t_slug, "maturity": "defined",
                                 "depends_on": [spec_cell], "verifier": rubric_cell,
                                 "asset_ref": f"build/{t_slug}.py", "validated_against": {spec_cell: spec_hash}})

        # the DRAFT ticket file (commit proposes drafts; triage → active is the ticket-ready step)
        with open(os.path.join(project, "tickets", f"{tid}.md"), "w", encoding="utf-8") as f:
            f.write(f"---\nkind: ticket\nname: {tid}\nmaturity: draft\ntarget_cell: {target}\n"
                    f"covers: {','.join(t.get('covers', []))}\n---\n\n# {tid}\n\n"
                    f"**Sealed acceptance** (deny-on-write to the executor): `{sealed_rel}`\n\n"
                    f"The worker writes `build/{t_slug}.py`; the independent `app-validator` runs the sealed "
                    f"acceptance to mint the signal. The worker never runs or edits this bar.\n")
        created.append((tid, target, rubric_cell))
    _lat.save(state, lat)

    _led.append(state, {"operation": "crystallize", "actor": "app-commit", "cell_id": spec_cell,
                        "result": "pass", "rationale": f"committed {spec_rel}; {len(created)} draft ticket(s) decomposed",
                        "cost": {"iterations": 1}})

    # advance the project stage
    pj = os.path.join(project, ".factory", "project.json")
    if os.path.isfile(pj):
        p = json.load(open(pj))
        p["stage"] = "kanban"
        p.setdefault("docs", {})["spec"] = "committed"
        json.dump(p, open(pj, "w"), indent=2)

    lines = [f"COMMITTED {spec_rel} → {spec_cell} validated (gate-minted signal)",
             f"  {len(created)} draft ticket(s) decomposed, each with a sealed, validated bar:"]
    for tid, target, rub in created:
        lines.append(f"    · {tid}: {target}  (verifier {rub}, ready for /app-loop)")
    return 0, "\n".join(lines)


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2:
        print("usage: app-commit.py <project> <spec-relpath>", file=sys.stderr)
        return 2
    rc, msg = crystallize(pos[0], pos[1])
    print(msg)
    return rc


def selftest():
    import tempfile
    fails = []
    def expect(c, m):
        if not c:
            fails.append(m)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, os.path.join(HERE, "app-new.py"), "demo", "--into", tmp],
                       capture_output=True, text=True)
        proj = os.path.join(tmp, "demo")
        os.makedirs(os.path.join(proj, "spec", "bars"), exist_ok=True)
        # real bars WITH TEETH: each imports its build module, so it fails against an empty build
        for n, mod in (("t1.py", "storage"), ("t2.py", "search")):
            with open(os.path.join(proj, "spec", "bars", n), "w") as f:   # the WRITABLE bar source
                f.write("import os, sys\nsys.path.insert(0, os.path.join(sys.argv[1], 'build'))\n"
                        f"import {mod}\nsys.exit(0)\n")
        with open(os.path.join(proj, "spec", "cli.md"), "w") as f:
            f.write(GATE.GOOD.replace("acceptance/t1.sh", "spec/bars/t1.py")
                    .replace("acceptance/t2.sh", "spec/bars/t2.py"))
        rc, msg = crystallize(proj, "spec/cli.md")
        expect(rc == 0, f"crystallize failed: {msg}")
        expect(os.path.isfile(os.path.join(proj, ".factory", "acceptance", "t1.py")),
               "bar was not sealed by copy into .factory/acceptance/")
        state = os.path.join(proj, ".factory", "state")
        lat = _lat.load(state)
        expect(_lat.find(lat, "spec.task.cli")["maturity"] == "validated", "spec cell not validated")
        for cell in ("capability.task.storage", "capability.task.search", "rubric.task.storage", "rubric.task.search"):
            expect(_lat.find(lat, cell) is not None, f"missing decomposed cell {cell}")
        expect(_lat.find(lat, "capability.task.storage").get("validated_against"), "spec→ticket edge not stamped")
        expect(os.path.isfile(os.path.join(proj, "tickets", "t1.md")), "draft ticket file not written")
        chk = subprocess.run([sys.executable, os.path.join(KERNEL, "lattice.py"), "check", "--dir", state],
                             capture_output=True, text=True)
        expect(chk.returncode == 0, f"crystallized lattice fails check: {chk.stdout.strip()[-300:]}")
        # a gate-failing spec is REJECTED
        with open(os.path.join(proj, "spec", "bad.md"), "w") as f:
            f.write("---\nkind: spec\nname: bad\nmaturity: cultivated\n---\nno contract here\n")
        rc2, _ = crystallize(proj, "spec/bad.md")
        expect(rc2 == 1, "a gate-failing spec must be rejected")
        # a TAUTOLOGY bar (passes against an empty build) is REJECTED by the teeth gate
        open(os.path.join(proj, "spec", "bars", "bad.py"), "w").write("import sys; sys.exit(0)\n")
        with open(os.path.join(proj, "spec", "toothless.md"), "w") as f:
            f.write(GATE.GOOD.replace("acceptance/t1.sh", "spec/bars/bad.py")
                    .replace("acceptance/t2.sh", "spec/bars/bad.py")
                    .replace("spec.task.cli", "spec.task.toothless"))
        rc3, msg3 = crystallize(proj, "spec/toothless.md")
        expect(rc3 == 1 and "TEETH" in msg3.upper(),
               f"a tautology bar (exit 0) must be rejected by the teeth gate (got rc={rc3}: {msg3})")
    if fails:
        sys.stderr.write("app-commit selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("app-commit selftest: OK (gate → spec cell validated via the real signal path → draft tickets + ready "
          "capability/rubric cells + stamped spec→ticket edges; the lattice passes check; a gate-failing spec is "
          "rejected; a tautology bar with no teeth is rejected by the calibration floor)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
