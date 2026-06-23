#!/usr/bin/env python3
"""app-spec-gate.py — the MECHANICAL half of spec-quality (the checkable gate).

A spec commits only if it is well-formed: this gate is the deterministic predicate
`app-commit.py` runs as the spec cell's verifier (the adversarial half is the
spec-council). It reads a spec doc — frontmatter + an embedded ```json contract — and
checks the structure the crystallizer depends on:

  - frontmatter has kind: spec, a name, a maturity
  - an embedded ```json block parses, with title + cell ({layer}.{scope}.{slug}, layer=spec)
  - ≥1 acceptance_criteria, EACH checkable (a non-empty `check` or `rubric_cell` — never prose-only)
  - ≥1 non_goals (the scope boundary is declared, not implied)
  - a decomposition with ≥1 ticket, each carrying target_cell + acceptance.cmd + covers[]
  - COVERAGE: every criterion id is covered by ≥1 ticket, and every `covers` names a real criterion

Exit 0 = well-formed; 1 = findings (printed); 2 = bad invocation. Stdlib, Python 3.8+.

  app-spec-gate.py <spec-doc>
  app-spec-gate.py selftest
"""
import json
import os
import re
import sys

CELL_RE = re.compile(r"^spec\.[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*$")


def parse(text):
    """Return (frontmatter dict, contract dict) — best-effort; missing pieces surface as gate findings."""
    fm = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        for line in (text[3:end] if end > 0 else "").splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip()
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    contract = None
    if m:
        try:
            contract = json.loads(m.group(1))
        except ValueError:
            contract = None
    return fm, contract


def gate(text):
    findings = []
    fm, c = parse(text)
    if fm.get("kind") != "spec":
        findings.append("frontmatter `kind` must be `spec`")
    if not fm.get("name"):
        findings.append("frontmatter missing `name`")
    if not fm.get("maturity"):
        findings.append("frontmatter missing `maturity`")
    if c is None:
        findings.append("no parseable ```json contract block")
        return findings
    if not c.get("title"):
        findings.append("contract missing `title`")
    cell = c.get("cell", "")
    if not CELL_RE.match(cell):
        findings.append(f"contract `cell` must be spec.<scope>.<slug> (got {cell!r})")
    crits = c.get("acceptance_criteria") or []
    if not crits:
        findings.append("contract needs ≥1 acceptance_criteria")
    crit_ids = set()
    for i, cr in enumerate(crits):
        cid = cr.get("id")
        if not cid:
            findings.append(f"acceptance_criteria[{i}] missing `id`")
            continue
        crit_ids.add(cid)
        if not (cr.get("check") or cr.get("rubric_cell")):
            findings.append(f"acceptance_criterion {cid} is prose-only — needs a `check` or `rubric_cell` (predicate-honesty)")
    if not c.get("non_goals"):
        findings.append("contract needs ≥1 `non_goals` (declare the scope boundary)")
    tickets = ((c.get("decomposition") or {}).get("tickets")) or []
    if not tickets:
        findings.append("decomposition needs ≥1 ticket")
    covered = set()
    for i, t in enumerate(tickets):
        if not t.get("target_cell"):
            findings.append(f"ticket[{i}] missing `target_cell`")
        if not ((t.get("acceptance") or {}).get("cmd")):
            findings.append(f"ticket[{i}] missing `acceptance.cmd` (the sealed acceptance command)")
        covs = t.get("covers") or []
        if not covs:
            findings.append(f"ticket[{i}] covers no criterion")
        for cv in covs:
            if cv not in crit_ids:
                findings.append(f"ticket[{i}] covers unknown criterion {cv!r}")
            covered.add(cv)
    for cid in sorted(crit_ids - covered):
        findings.append(f"criterion {cid} is covered by no ticket (decomposition does not entail the spec)")
    return findings


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    if not argv:
        print("usage: app-spec-gate.py <spec-doc>", file=sys.stderr)
        return 2
    try:
        text = open(argv[0], encoding="utf-8").read()
    except OSError as e:
        print(f"cannot read {argv[0]}: {e}", file=sys.stderr)
        return 2
    findings = gate(text)
    if findings:
        print(f"SPEC-GATE FAIL — {len(findings)} finding(s):")
        for f in findings:
            print(f"  - {f}")
        return 1
    print("SPEC-GATE PASS — well-formed (checkable criteria, declared non-goals, full ticket coverage)")
    return 0


GOOD = """---
kind: spec
name: cli
maturity: cultivated
---
# cli
```json
{"title":"x","cell":"spec.task.cli",
 "acceptance_criteria":[{"id":"a1","check":"roundtrip"},{"id":"a2","check":"search ci"}],
 "non_goals":["no sync"],
 "decomposition":{"tickets":[
   {"id":"t1","target_cell":"capability.task.storage","acceptance":{"cmd":"acceptance/t1.sh"},"covers":["a1"]},
   {"id":"t2","target_cell":"capability.task.search","acceptance":{"cmd":"acceptance/t2.sh"},"covers":["a2"]}]}}
```
"""


def selftest():
    fails = []
    def expect(c, m):
        if not c:
            fails.append(m)
    expect(gate(GOOD) == [], f"a well-formed spec must pass: {gate(GOOD)}")
    # prose-only criterion is rejected
    prose = GOOD.replace('{"id":"a2","check":"search ci"}', '{"id":"a2"}')
    expect(any("prose-only" in f for f in gate(prose)), "a prose-only criterion must be rejected")
    # an uncovered criterion is rejected (decomposition does not entail the spec)
    uncov = GOOD.replace('{"id":"t2","target_cell":"capability.task.search","acceptance":{"cmd":"acceptance/t2.sh"},"covers":["a2"]}', '')
    uncov = uncov.replace(',\n   ]', ']').replace(',\n]', ']')
    expect(any("covered by no ticket" in f for f in gate(uncov)), f"an uncovered criterion must be rejected: {gate(uncov)}")
    # a malformed cell id is rejected
    badcell = GOOD.replace('"spec.task.cli"', '"task.cli"')
    expect(any("spec.<scope>.<slug>" in f for f in gate(badcell)), "a malformed cell id must be rejected")
    if fails:
        sys.stderr.write("app-spec-gate selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("app-spec-gate selftest: OK (passes a well-formed spec; rejects prose-only criteria, uncovered criteria, malformed cell ids)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
