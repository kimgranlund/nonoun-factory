#!/usr/bin/env python3
"""app-new.py — scaffold an app-factory project CORPUS (the `/app-new` primitive).

A project is a corpus of prose documents the human cultivates (idea → PRD → specs →
knowledge) that a bounded loop compiles into software. This lays that corpus and the
hidden `.factory/` spine beneath it:

    projects/<name>/
      idea.md prd.md qa.md          # prose the human cultivates (draft maturity)
      research/ prototype/ spec/ tickets/ knowledge/ build/
      .factory/
        state/                      # the vendored kernel's `--dir` (lattice + ledger)
          lattice.json              # minted by the vendored `lattice.py init`
          ledger/ signals/ run/
        acceptance/                 # sealed acceptance scripts (the bars)
        project.json                # app-factory: stage, doc maturities, autonomy tier
        protected.json              # the deny-on-write perimeter

INT-1: the vendored kernel resolves a project root as the GRANDPARENT of its `--dir`
(it was built for `<root>/.agents/harness`). So the kernel state is nested at
`.factory/state/` — two levels under the project root — and `grandparent(.factory/
state) == projects/<name>`, the real project root, so asset_ref / `validated_against`
staleness hashing resolves correctly. The lattice itself is laid by the *vendored,
proven* kernel (`lattice.py init`), not re-implemented here. Stdlib, Python 3.8+.

  app-new.py <name> [--into DIR]   # default DIR = ./projects
  app-new.py selftest
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL = os.path.join(os.path.dirname(HERE), "kernel")

# The deny-on-write perimeter (spec 02): a coding agent must never edit the bar it is
# graded against, nor any spine state. The whole `.factory/` tree (lattice, ledger,
# signals, sealed acceptance, the manifests) plus committed specs / ticket acceptance
# / the QA plan are deny-on-write to the executor.
PROTECTED_GLOBS = ["spec/**", "tickets/**", "qa.md", ".factory/**"]

DOC_TEMPLATES = {
    "idea.md": (
        "---\nkind: idea\nname: {name}\nmaturity: draft\ngoal: false\n---\n\n"
        "# {name} — idea\n\n_One paragraph: what is this, who is it for, what does "
        "'good' look like? Cultivate this, then move it toward a PRD._\n"
    ),
    "prd.md": (
        "---\nkind: prd\nname: {name}\nmaturity: draft\ngoal: false\n---\n\n"
        "# {name} — PRD\n\n**Narrative-acceptance** (a usage narrative — NOT a "
        "/app-goal predicate; a PRD is met via its specs).\n\n## User stories\n\n"
        "- As a user, I can …\n\n## Non-goals\n\n- …\n"
    ),
    "qa.md": (
        "---\nkind: qa\nname: {name}\nmaturity: draft\ngoal: false\n---\n\n"
        "# {name} — QA plan\n\n_Emitted by the loop for a human to run. Each step "
        "replays a sealed acceptance criterion._\n"
    ),
}
SUBDIRS = ["research", "prototype", "spec", "tickets", "knowledge", "build"]


def state_dir(root):
    """The vendored kernel's `--dir` for this project (two levels under the project root — INT-1)."""
    return os.path.join(root, ".factory", "state")


def scaffold(name, into):
    root = os.path.abspath(os.path.join(into, name))
    if os.path.exists(root) and os.listdir(root):
        print(f"refusing to scaffold into non-empty {root}", file=sys.stderr)
        return 2
    factory = os.path.join(root, ".factory")
    state = state_dir(root)
    os.makedirs(state, exist_ok=True)
    os.makedirs(os.path.join(factory, "acceptance"), exist_ok=True)
    for d in SUBDIRS:
        os.makedirs(os.path.join(root, d), exist_ok=True)
        open(os.path.join(root, d, ".gitkeep"), "w").close()
    os.makedirs(os.path.join(root, "spec", "bars"), exist_ok=True)   # writable bar SOURCES; sealed into .factory on commit
    open(os.path.join(root, "spec", "bars", ".gitkeep"), "w").close()
    for fn, tmpl in DOC_TEMPLATES.items():
        with open(os.path.join(root, fn), "w") as f:
            f.write(tmpl.format(name=name))

    # The lattice + its tree come from the vendored, proven kernel — not re-implemented.
    r = subprocess.run([sys.executable, os.path.join(KERNEL, "lattice.py"),
                        "init", name, "--dir", state],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(f"lattice init failed: {r.stderr.strip()}", file=sys.stderr)
        return 1
    for d in ("ledger", "signals", "run"):
        os.makedirs(os.path.join(state, d), exist_ok=True)
    open(os.path.join(state, "ledger", "events.jsonl"), "a").close()

    project = {
        "name": name, "producer": "app-factory", "stage": "idea",
        "state_dir": ".factory/state",
        "docs": {"idea": "draft", "prd": "draft", "qa": "draft"},
        "prd_waived": False,           # OD-01-B: required by default, waivable explicitly
        "autonomy_tier": 0,            # Tier 0 (attended) until earned (ledger.py trust)
        "lifecycle": ["idea", "research?", "prototype?", "prd", "spec",
                      "kanban", "execution", "qa"],
    }
    with open(os.path.join(factory, "project.json"), "w") as f:
        json.dump(project, f, indent=2)
    with open(os.path.join(factory, "protected.json"), "w") as f:
        json.dump({"deny_on_write_to_executor": PROTECTED_GLOBS}, f, indent=2)

    print(f"scaffolded app-factory project: {root}")
    print(f"  corpus: idea.md prd.md qa.md + {', '.join(SUBDIRS)}/")
    print(f"  spine:  .factory/state/ (kernel --dir: lattice.json, ledger/, signals/, run/) + project.json + protected.json")
    print(f"  next:   cultivate idea.md, then `/app-spec` it toward a committed spec; `/app-status {name}` to watch.")
    return 0


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    pos = [a for a in argv if not a.startswith("--")]
    into = argv[argv.index("--into") + 1] if "--into" in argv else "projects"
    if not pos:
        print("usage: app-new.py <name> [--into DIR]   (default DIR=./projects)", file=sys.stderr)
        return 2
    return scaffold(pos[0], into)


def selftest():
    import tempfile
    fails = []
    with tempfile.TemporaryDirectory() as tmp:
        rc = scaffold("demo", tmp)
        root = os.path.join(tmp, "demo")
        if rc != 0:
            fails.append(f"scaffold returned {rc}")
        for p in ["idea.md", "prd.md", "qa.md", ".factory/state/lattice.json",
                  ".factory/project.json", ".factory/protected.json",
                  ".factory/state/ledger/events.jsonl"]:
            if not os.path.exists(os.path.join(root, p)):
                fails.append(f"missing {p}")
        # INT-1: the kernel resolves project root as grandparent of --dir; it must be the project root.
        st = state_dir(root)
        kernel_root = os.path.dirname(os.path.dirname(st.rstrip("/")))
        if os.path.abspath(kernel_root) != os.path.abspath(root):
            fails.append(f"INT-1: kernel root {kernel_root} != project root {root}")
        # the minted lattice must pass the vendored kernel's own check
        chk = subprocess.run([sys.executable, os.path.join(KERNEL, "lattice.py"),
                              "check", "--dir", st], capture_output=True, text=True)
        if chk.returncode != 0:
            fails.append(f"vendored lattice check rejected the scaffolded lattice: {chk.stderr.strip()[:200]}")
        prot = json.load(open(os.path.join(root, ".factory", "protected.json")))
        if ".factory/**" not in prot["deny_on_write_to_executor"]:
            fails.append("protected perimeter missing the .factory spine glob")
    if fails:
        sys.stderr.write("app-new selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("app-new selftest: OK (corpus + .factory/state scaffolded; INT-1: kernel root resolves to the project "
          "root; the minted lattice passes the vendored kernel check; the deny-on-write perimeter registers the spine)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
