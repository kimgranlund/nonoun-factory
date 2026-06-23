#!/usr/bin/env python3
"""gate-protect — the blocking deny-on-write gate that makes the keystone ENFORCED, not declared.

The whole verifier substrate of an app-factory project lives under `.factory/`: the minted signals,
the append-only ledger, the lattice, the run budget, the sealed acceptance bars, and the project
manifests. Every one of those is written ONLY by the kernel/validation path (Python subprocess), never
by an agent's Write/Edit tool. So a coding agent that uses Write/Edit can be made *mechanically*
deny-on-write to all of it — it cannot forge a pass signal, launder the ledger, fake a cell's maturity,
lift the budget ceiling, or edit the bar it is graded against. The plugin wires this as a
PreToolUse(Write|Edit) hook; a non-zero exit denies the write.

This is the gate species (it BLOCKS — `harness-hook` only advises). Unlike harness-forge's `wire.py`
(which installs into an arbitrary user project's settings), app-factory ships this in its own plugin
`hooks.json`, always-on for the session that operates its projects. `.claude/settings.json` is protected
too, so an agent cannot unwire the gate. Extra globs via `APP_FACTORY_PROTECTED` (a project that wants
its committed `spec/**` protected from the executor opts in).

Usage:
  gate-protect.py --hook          # reads PreToolUse JSON on stdin; exit 2 (+reason) = DENY a protected write
  gate-protect.py check <path>    # exit 1 if <path> is protected (for scripting/testing)
  gate-protect.py selftest
Stdlib only; Python 3.8+.
"""
import fnmatch
import json
import os
import sys


def _env_globs():
    env = os.environ.get("APP_FACTORY_PROTECTED")
    return [g.strip() for g in env.replace(",", "\n").splitlines() if g.strip()] if env else []


def is_protected(path, extra=None):
    """Protected iff the path lies inside any `.factory/` directory (the verifier substrate), is the
    wiring itself, or matches an opt-in glob. Segment-anchored — `.factory` must be a whole path segment,
    so `build/storage.py`, `spec/cli.md`, and `spec/bars/t1.py` (the writable bar SOURCE) stay writable."""
    if not path:
        return False
    p = path.replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    segs = p.split("/")
    if ".factory" in segs:                                  # anywhere under a project's .factory/ substrate
        return True
    if p == ".claude/settings.json" or p.endswith("/.claude/settings.json"):
        return True                                         # the wiring — an agent cannot unwire the gate
    for g in (extra if extra is not None else _env_globs()):
        if fnmatch.fnmatch(p, g) or fnmatch.fnmatch(p, "*/" + g):
            return True
    return False


def selftest():
    fails = []
    def expect(c, m):
        if not c:
            fails.append(m)
    for p in ("projects/quicklog/.factory/state/signals/capability.task.storage/x.json",  # can't forge a pass
              "projects/quicklog/.factory/state/ledger/events.jsonl",                       # can't launder the audit
              "projects/quicklog/.factory/state/lattice.json",                              # can't fake maturity
              "projects/quicklog/.factory/state/run/budget.json",                           # can't lift the ceiling
              "projects/quicklog/.factory/acceptance/t1-storage.py",                        # can't edit the sealed bar
              "projects/quicklog/.factory/protected.json", "projects/quicklog/.factory/project.json",
              ".factory/state/lattice.json",                                                # root-relative anchors too
              ".claude/settings.json", "sub/proj/.claude/settings.json"):                   # the wiring
        expect(is_protected(p), f"failed to protect a verifier asset: {p}")
    for p in ("projects/quicklog/build/storage.py", "projects/quicklog/build/search.py",   # the worker's output
              "projects/quicklog/spec/cli.md",                                              # the human cultivates specs
              "projects/quicklog/spec/bars/t1-storage.py",                                  # the WRITABLE bar source (pre-seal)
              "projects/quicklog/idea.md", "src/main.py", "README.md",
              "docs/my.factory.notes.md",                                                   # `.factory` only as a basename ≠ segment
              "a/.factoryx/y"):                                                             # not the `.factory` segment
        expect(not is_protected(p), f"wrongly protected a writable path: {p}")
    expect(is_protected("projects/x/spec/cli.md", ["spec/**"]), "opt-in glob (spec/**) did not protect")
    if fails:
        sys.stderr.write("gate-protect selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("gate-protect selftest: OK (denies Write/Edit to the whole .factory/ verifier substrate — signals, "
          "ledger, lattice, budget, sealed bars, manifests — plus the wiring; build/, specs, and the bar SOURCE stay writable)")
    return 0


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    if argv and argv[0] == "check" and len(argv) > 1:
        return 1 if is_protected(argv[1]) else 0
    if argv and argv[0] == "--hook":
        try:
            data = json.load(sys.stdin)
            ti = data.get("tool_input") or data.get("toolInput") or {}
            path = ti.get("file_path") or ti.get("path") or ti.get("file")
        except Exception:
            return 0                                          # malformed input → fail-open on parse
        if is_protected(path):
            sys.stderr.write(f"gate-protect: DENY — `{path}` is under the .factory/ verifier substrate; agents are "
                             f"deny-on-write to it. Signals/ledger/lattice/bars are written only by the kernel path "
                             f"(the worker never grades its own work nor edits its own bar).\n")
            return 2                                           # non-zero = block the write
        return 0
    print(__doc__.split("Usage:")[1].split("Stdlib")[0].strip(), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
