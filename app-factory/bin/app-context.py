#!/usr/bin/env python3
"""app-context.py — deterministic build-context assembly (the 'better specs → cheaper build' mechanic).

When the loop builds a ticket, the worker shouldn't start from a blank page — it should build with the
accumulated corpus. This assembles a ticket's build context DETERMINISTICALLY from NAMED corpus sources:
the spec it decomposed from (the intent), the project's knowledge docs, and the non-stale distilled
patterns. Two disciplines make it trustworthy:
  - DETERMINISTIC: sourced from named files in a stable order — never a fuzzy "relevant docs" guess, so the
    same corpus always assembles the same context (and the source list is logged for observability).
  - FRESH: a pattern marked `maturity: stale` (superseded by regeneration) is EXCLUDED — frozen knowledge
    can't leak into a build.
The worker never receives the sealed bar (predicate-honesty): context is intent + knowledge, not the test.
Stdlib, Python 3.8+.

  app-context.py <project> <ticket-id|target-cell>   # e.g. app-context.py projects/quicklog t1-storage
  app-context.py selftest
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "kernel"))
import lattice as _lat  # noqa: E402


def _frontmatter(path):
    if not os.path.isfile(path):
        return {}
    t = open(path, encoding="utf-8").read()
    if not t.startswith("---"):
        return {}
    end = t.find("\n---", 3)
    out = {}
    for line in (t[3:end] if end > 0 else "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _resolve_spec(project, target_cell):
    """The spec a ticket decomposed from: the capability cell's spec dependency → its asset_ref."""
    lat = _lat.load(os.path.join(project, ".factory", "state"))
    cell = _lat.find(lat, target_cell)
    if not cell:
        return None
    for dep in cell.get("depends_on", []):
        dc = _lat.find(lat, dep)
        if dc and dc.get("layer") == "spec" and dc.get("asset_ref"):
            return dc["asset_ref"]
    return None


def assemble(project, ticket):
    project = os.path.abspath(project)
    # ticket may be a ticket id (tickets/<id>.md) or a target cell id
    target = ticket
    tf = os.path.join(project, "tickets", f"{ticket}.md")
    if os.path.isfile(tf):
        target = _frontmatter(tf).get("target_cell", ticket)

    sources = []
    spec_rel = _resolve_spec(project, target)
    if spec_rel and os.path.isfile(os.path.join(project, spec_rel)):
        sources.append({"kind": "spec", "path": spec_rel})
    kdir = os.path.join(project, "knowledge")
    if os.path.isdir(kdir):
        for f in sorted(f for f in os.listdir(kdir) if f.endswith(".md")):
            sources.append({"kind": "knowledge", "path": f"knowledge/{f}"})
    pdir = os.path.join(project, "knowledge", "patterns")
    if os.path.isdir(pdir):
        for f in sorted(f for f in os.listdir(pdir) if f.endswith(".md")):
            p = os.path.join(pdir, f)
            if _frontmatter(p).get("maturity") == "stale":
                continue                                   # freshness: a superseded pattern can't leak in
            sources.append({"kind": "pattern", "path": f"knowledge/patterns/{f}"})

    blocks = []
    for s in sources:
        blocks.append(f"# [{s['kind']}] {s['path']}\n" + open(os.path.join(project, s["path"]), encoding="utf-8").read())
    return {"ticket": ticket, "target": target, "sources": sources, "context": "\n\n".join(blocks)}


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2:
        print("usage: app-context.py <project> <ticket-id|target-cell>", file=sys.stderr)
        return 2
    out = assemble(pos[0], pos[1])
    if "--json" in argv:
        print(json.dumps(out, indent=2))
    else:
        print(f"context for {out['ticket']} ({out['target']}) — {len(out['sources'])} source(s):")
        for s in out["sources"]:
            print(f"  · [{s['kind']}] {s['path']}")
    return 0


def selftest():
    import subprocess
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
        os.makedirs(os.path.join(proj, "knowledge", "patterns"), exist_ok=True)
        open(os.path.join(proj, "spec", "bars", "t1.py"), "w").write(   # real bar with teeth (fails w/o a build)
            "import os, sys\nsys.path.insert(0, os.path.join(sys.argv[1], 'build'))\nimport thing\n"
            "sys.exit(0 if thing.ok else 1)\n")
        open(os.path.join(proj, "spec", "cli.md"), "w").write(
            '---\nkind: spec\nname: cli\nmaturity: cultivated\n---\n# cli\n```json\n'
            '{"title":"x","cell":"spec.task.cli","acceptance_criteria":[{"id":"a1","check":"ok"}],'
            '"non_goals":["v1"],"decomposition":{"tickets":[{"id":"t1","target_cell":"capability.task.thing",'
            '"acceptance":{"cmd":"spec/bars/t1.py"},"covers":["a1"]}]}}\n```\n')
        subprocess.run([sys.executable, os.path.join(HERE, "app-commit.py"), proj, "spec/cli.md"], capture_output=True)
        open(os.path.join(proj, "knowledge", "conventions.md"), "w").write("# conventions\nuse stdlib\n")
        open(os.path.join(proj, "knowledge", "patterns", "fresh.md"), "w").write("---\nmaturity: draft\n---\n# fresh\n")
        open(os.path.join(proj, "knowledge", "patterns", "old.md"), "w").write("---\nmaturity: stale\n---\n# old\n")

        out = assemble(proj, "t1")
        paths = [s["path"] for s in out["sources"]]
        expect("spec/cli.md" in paths, f"context must include the ticket's spec: {paths}")
        expect("knowledge/conventions.md" in paths, "context must include knowledge docs")
        expect("knowledge/patterns/fresh.md" in paths, "context must include a fresh pattern")
        expect("knowledge/patterns/old.md" not in paths, "context must EXCLUDE a stale pattern (freshness)")
        expect("t1.py" not in str(paths) and "acceptance" not in str(paths), "context must NOT include the sealed bar (predicate-honesty)")
        out2 = assemble(proj, "t1")
        expect(out["sources"] == out2["sources"], "assembly must be deterministic (stable order, same sources)")
    if fails:
        sys.stderr.write("app-context selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("app-context selftest: OK (assembles a ticket's spec + knowledge + non-stale patterns deterministically; "
          "excludes a stale pattern (freshness) and the sealed bar (predicate-honesty); same corpus → same context)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
