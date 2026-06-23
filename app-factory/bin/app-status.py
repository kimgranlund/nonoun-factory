#!/usr/bin/env python3
"""app-status.py — a no-agent operator dashboard over an app-factory project (`/app-status`).

Cheap, read-only, deterministic. Reads the corpus (doc maturities), the hidden `.factory/`
spine (the lattice histogram), and shells the vendored kernel for the budget state and the
earned trust tier — so the dashboard reflects the SAME mechanisms the loop is bound by, not a
re-implementation. The trust tier is *displayed* here; it is not *enforced* until the refuter
+ dispatch-time consumer are wired (see ROADMAP). Stdlib, Python 3.8+.

  app-status.py <name|path> [--into DIR]   # default DIR=./projects
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL = os.path.join(os.path.dirname(HERE), "kernel")


def _resolve(arg, base):
    for cand in (arg, os.path.join(base, arg)):
        if os.path.isdir(os.path.join(cand, ".factory")):
            return os.path.abspath(cand)
    return None


def _frontmatter(path):
    if not os.path.exists(path):
        return {}
    try:
        t = open(path, encoding="utf-8").read()
    except OSError:
        return {}
    if not t.startswith("---"):
        return {}
    end = t.find("\n---", 3)
    out = {}
    for line in (t[3:end] if end > 0 else "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _ls(root, sub, suffix=".md"):
    d = os.path.join(root, sub)
    return sorted(f for f in os.listdir(d) if f.endswith(suffix)) if os.path.isdir(d) else []


def _kernel(script, *args):
    try:
        r = subprocess.run([sys.executable, os.path.join(KERNEL, script), *args],
                           capture_output=True, text=True, timeout=60)
        return ((r.stdout or "") + (r.stderr or "")).strip()
    except Exception as e:  # noqa: BLE001
        return f"(unavailable: {e})"


def status(root):
    F = os.path.join(root, ".factory")
    S = os.path.join(F, "state")          # the kernel --dir (INT-1: two levels under the project root)
    proj = json.load(open(os.path.join(F, "project.json"))) if os.path.exists(os.path.join(F, "project.json")) else {}
    print(f"app-factory · {proj.get('name', os.path.basename(root))}")
    print(f"  stage:      {proj.get('stage', '?')}")
    print(f"  lifecycle:  {' → '.join(proj.get('lifecycle', [])) or '?'}")
    print(f"  autonomy:   Tier {proj.get('autonomy_tier', '?')} (attended until earned)")

    print("  documents:")
    for fn, kind in (("idea.md", "idea"), ("prd.md", "prd"), ("qa.md", "qa")):
        print(f"    {kind:<9} {_frontmatter(os.path.join(root, fn)).get('maturity', '—')}")
    print(f"    {'specs':<9} {len(_ls(root, 'spec'))}  ({', '.join(_ls(root, 'spec')) or 'none committed'})")
    print(f"    {'tickets':<9} {len(_ls(root, 'tickets'))}")
    print(f"    {'knowledge':<9} {len(_ls(root, 'knowledge'))}")

    lat = os.path.join(S, "lattice.json")
    if os.path.exists(lat):
        cells = json.load(open(lat)).get("cells", [])
        hist = {}
        for c in cells:
            m = c.get("maturity", "absent")
            hist[m] = hist.get(m, 0) + 1
        print("  lattice (hidden spine):")
        print("    " + ("   ".join(f"{k}:{v}" for k, v in sorted(hist.items())) or "empty"))
        print(f"  budget:     {(_kernel('run-budget.py', 'status', '--dir', S).splitlines() or ['?'])[-1]}")
        print(f"  trust:      {(_kernel('ledger.py', 'trust', '--dir', S).splitlines() or ['?'])[0]}")

    ev = os.path.join(S, "ledger", "events.jsonl")
    if os.path.exists(ev):
        lines = [l for l in open(ev, encoding="utf-8").read().splitlines() if l.strip()]
        print(f"  ledger:     {len(lines)} event(s)")
        for l in lines[-3:]:
            try:
                e = json.loads(l)
                print(f"    · {e.get('operation', '?')} {e.get('cell_id', '')} → {e.get('result', '')}")
            except json.JSONDecodeError:
                pass
    return 0


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    pos = [a for a in argv if not a.startswith("--")]
    base = argv[argv.index("--into") + 1] if "--into" in argv else "projects"
    if not pos:
        print("usage: app-status.py <name|path> [--into DIR]", file=sys.stderr)
        return 2
    root = _resolve(pos[0], base)
    if not root:
        print(f"no app-factory project (a dir with .factory/) at {pos[0]!r} or {base}/{pos[0]}", file=sys.stderr)
        return 2
    return status(root)


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run([sys.executable, os.path.join(HERE, "app-new.py"), "demo", "--into", tmp],
                       capture_output=True, text=True)
        rc = status(os.path.join(tmp, "demo"))
    if rc != 0:
        sys.stderr.write("app-status selftest: FAIL\n")
        return 1
    print("app-status selftest: OK (renders stage, doc maturities, lattice histogram, budget, trust over a scaffolded corpus)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
