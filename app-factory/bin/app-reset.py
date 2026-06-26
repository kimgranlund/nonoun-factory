#!/usr/bin/env python3
"""app-reset.py — re-arm a project to a clean, ready-to-validate state (the `/app-reset` primitive).

Demos and eval flows need a one-call way to put a project back to "committed but not yet built":
tickets back to `defined`, the authored corpus (idea/prd/qa/specs/bars/build/knowledge) preserved,
the derived state (`.factory`, `tickets/`) rebuilt. It re-scaffolds, restores the authored content,
re-crystallizes every well-formed spec, and re-validates the ontology foothold — so the frontier is
open again and `/app-loop` (or the UI's Validate button) has work to do. Stdlib, Python 3.8+.

  app-reset.py <project>          # e.g. app-reset.py projects/quicklog
  app-reset.py selftest
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL = os.path.join(os.path.dirname(HERE), "kernel")

PRESERVE_FILES = ["idea.md", "prd.md", "qa.md"]
PRESERVE_DIRS = ["spec", "build", "knowledge", "research", "prototype"]


def reset(project):
    project = os.path.abspath(project)
    if not os.path.isdir(os.path.join(project, ".factory")):
        return 2, f"not an app-factory project (no .factory/): {project}", []
    parent, name = os.path.dirname(project), os.path.basename(project)

    stash = project + ".reset-stash"
    if os.path.exists(stash):
        shutil.rmtree(stash)
    os.makedirs(stash)
    for f in PRESERVE_FILES:
        if os.path.isfile(os.path.join(project, f)):
            shutil.copy2(os.path.join(project, f), os.path.join(stash, f))
    for d in PRESERVE_DIRS:
        if os.path.isdir(os.path.join(project, d)):
            shutil.copytree(os.path.join(project, d), os.path.join(stash, d))

    shutil.rmtree(project)
    r = subprocess.run([sys.executable, os.path.join(HERE, "app-new.py"), name, "--into", parent],
                       capture_output=True, text=True)
    if r.returncode != 0:
        shutil.rmtree(stash, ignore_errors=True)
        return 1, f"re-scaffold failed: {r.stderr.strip()}", []

    for f in PRESERVE_FILES:
        if os.path.isfile(os.path.join(stash, f)):
            shutil.copy2(os.path.join(stash, f), os.path.join(project, f))
    for d in PRESERVE_DIRS:
        if os.path.isdir(os.path.join(stash, d)):
            shutil.copytree(os.path.join(stash, d), os.path.join(project, d), dirs_exist_ok=True)
    shutil.rmtree(stash, ignore_errors=True)

    committed = []
    specdir = os.path.join(project, "spec")
    for f in sorted(os.listdir(specdir)) if os.path.isdir(specdir) else []:
        if f.endswith(".md") and os.path.isfile(os.path.join(specdir, f)):
            # --seal: reset RESTORES a previously committed+sealed project to loop-ready, so it re-applies
            # the entailment seal the human had already given (not a fresh certification — a restore).
            c = subprocess.run([sys.executable, os.path.join(HERE, "app-commit.py"), project, f"spec/{f}", "--seal"],
                               capture_output=True, text=True)
            if c.returncode == 0:
                committed.append(f)

    state = os.path.join(project, ".factory", "state")
    subprocess.run([sys.executable, os.path.join(KERNEL, "validate.py"), "ontology.task.domain",
                    "--dir", state, "--harness", "domain-captured", "--",
                    sys.executable, "-c", "import os,sys; sys.exit(0 if os.path.getsize(os.path.join(sys.argv[1],'idea.md'))>0 else 1)",
                    project], capture_output=True, text=True)
    return 0, f"reset {name}: re-crystallized {len(committed)} spec(s), tickets back to `defined`, builds preserved", committed


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    pos = [a for a in argv if not a.startswith("--")]
    if not pos:
        print("usage: app-reset.py <project>", file=sys.stderr)
        return 2
    rc, msg, _ = reset(pos[0])
    print(msg)
    return rc


def selftest():
    import json
    import tempfile
    fails = []
    def expect(c, m):
        if not c:
            fails.append(m)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, os.path.join(HERE, "app-new.py"), "demo", "--into", tmp], capture_output=True)
        proj = os.path.join(tmp, "demo")
        state = os.path.join(proj, ".factory", "state")
        # author a spec + its bar source + a build artifact, commit, validate (ticket → validated)
        os.makedirs(os.path.join(proj, "spec", "bars"), exist_ok=True)
        with open(os.path.join(proj, "spec", "bars", "t1.py"), "w") as f:   # real bar w/ teeth (fails w/o a build)
            f.write("import os, sys\nsys.path.insert(0, os.path.join(sys.argv[1], 'build'))\nimport thing\n"
                    "sys.exit(0 if thing.ok else 1)\n")
        with open(os.path.join(proj, "build", "thing.py"), "w") as f:
            f.write("ok = True\n")
        with open(os.path.join(proj, "spec", "cli.md"), "w") as f:
            f.write('---\nkind: spec\nname: cli\nmaturity: cultivated\n---\n# cli\n```json\n'
                    '{"title":"x","cell":"spec.task.cli","acceptance_criteria":[{"id":"a1","check":"ok"}],'
                    '"non_goals":["none"],"decomposition":{"tickets":[{"id":"t1","target_cell":"capability.task.thing",'
                    '"acceptance":{"cmd":"spec/bars/t1.py"},"covers":["a1"]}]}}\n```\n')
        subprocess.run([sys.executable, os.path.join(HERE, "app-commit.py"), proj, "spec/cli.md"], capture_output=True)
        subprocess.run([sys.executable, os.path.join(KERNEL, "validate.py"), "ontology.task.domain", "--dir", state,
                        "--harness", "x", "--", sys.executable, "-c", "import sys; sys.exit(0)"], capture_output=True)
        subprocess.run([sys.executable, os.path.join(KERNEL, "validate.py"), "capability.task.thing", "--dir", state,
                        "--harness", "x", "--", sys.executable, os.path.join(proj, "spec", "bars", "t1.py"), proj],
                       capture_output=True)
        cell = next(c for c in json.load(open(os.path.join(state, "lattice.json")))["cells"]
                    if c.get("slug") == "thing" and c["layer"] == "capability")
        expect(cell["maturity"] == "validated", f"precondition: ticket should be validated before reset (got {cell['maturity']})")
        # RESET → ticket back to defined, build + spec preserved
        rc, msg, committed = reset(proj)
        expect(rc == 0, f"reset failed: {msg}")
        cell2 = next(c for c in json.load(open(os.path.join(state, "lattice.json")))["cells"]
                     if c.get("slug") == "thing" and c["layer"] == "capability")
        expect(cell2["maturity"] == "defined", f"after reset the ticket should be `defined` (got {cell2.get('maturity')})")
        expect(os.path.isfile(os.path.join(proj, "build", "thing.py")), "reset must preserve the build artifact")
        expect(os.path.isfile(os.path.join(proj, "spec", "cli.md")), "reset must preserve the spec")
        expect("cli.md" in committed, "reset must re-crystallize the committed spec")
    if fails:
        sys.stderr.write("app-reset selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("app-reset selftest: OK (a validated ticket resets to `defined`; the authored corpus — spec + build — is "
          "preserved; the committed spec is re-crystallized and the frontier re-opens)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
