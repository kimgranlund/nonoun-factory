#!/usr/bin/env python3
"""goal.py — objective-scoped harness runs (the `/harness-goal` primitive).

A GOAL is a target cell + its validated-rubric acceptance. `/harness-run` advances the WHOLE frontier and stops only
on frontier-empty or budget; a GOAL run advances the target's dependency CLOSURE — the cells it transitively needs
validated — toward the goal, and STOPS the moment the goal is MET (its cell reaches a settled maturity). That gives
the bounded loop an OBJECTIVE terminator: "run until THIS cell is satisfied," with doneness earned from the lattice
signal (the validated maturity), never the model's say-so — the same morphism `/harness-run` enforces, now scoped.

  goal.py closure CELL [--dir D]   # the transitive depends_on + verifier closure (what the goal needs validated)
  goal.py met     CELL [--dir D]   # exit 0 iff the goal is MET (settled), else 1 — the loop's per-pass stop check
  goal.py next    CELL [--dir D]   # the next ready cell to advance TOWARD the goal (rank, scoped to the closure)
  goal.py status  CELL [--dir D]   # JSON: goal maturity, met?, closure by maturity, next, and what blocks it
  goal.py selftest

Pure over the lattice (imports lattice.py); writes NOTHING — selection and doneness route to code, never inference.
Stdlib, Python 3.8+. The `harness-builder` runs this in its goal-scoped loop; `/loop … /harness-goal CELL` makes it
a supervised standing loop (attended until autonomy is earned — see `/harness-goal`).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lattice as _lat   # noqa: E402  the kernel (find/cid/ready/rank/load/SETTLED/is_blocked)


def closure(lat, cell_id):
    """The transitive PREREQUISITE closure of `cell_id`: every cell it (transitively) `depends_on` PLUS each cell's
    `verifier` rubric — exactly the cells whose `validated` the goal requires, including the goal itself. (LAYER_DEPS
    footholds — "any validated cell at the upstream layer" — are not a specific cell, so they are not enumerable here;
    an unmet foothold surfaces as a `next`-empty-but-not-met goal in `status`, with the missing layer named.)"""
    seen, frontier = set(), [cell_id]
    while frontier:
        cur = frontier.pop()
        if cur in seen:
            continue
        seen.add(cur)
        c = _lat.find(lat, cur)
        if not c:
            continue
        frontier.extend(c.get("depends_on", []) or [])
        if c.get("verifier"):
            frontier.append(c["verifier"])
    return seen


def met(lat, cell_id):
    """The goal is MET iff its cell exists and is SETTLED (validated/operating) — doneness from the lattice, not the
    model. A `/harness-goal` loop stops the pass it first reads MET, never on the orchestrator's say-so."""
    c = _lat.find(lat, cell_id)
    return bool(c) and c.get("maturity") in _lat.SETTLED


def rank_toward(lat, cell_id):
    """The ranked READY cells WITHIN the goal's closure — the loop's next-to-advance set, scoped to the objective.
    Reuses `lattice.rank` (the same (risk × unlock) ÷ probe-cost ordering), filtered to the closure."""
    cl = closure(lat, cell_id)
    return [(p, c, r) for (p, c, r) in _lat.rank(lat) if _lat.cid(c) in cl]


def status(lat, cell_id):
    """A report dict: the goal + its maturity, whether it is MET, the closure partitioned by maturity, the next ready
    cell toward the goal, and — when nothing is ready but the goal is unmet — what BLOCKS it (the unsettled closure
    cells + their readiness reasons), so the operator sees exactly what to seed/unblock."""
    cl = closure(lat, cell_id)
    goal = _lat.find(lat, cell_id)
    is_met = met(lat, cell_id)
    nxt = rank_toward(lat, cell_id)
    by_mat = {}
    for cur in sorted(cl):
        c = _lat.find(lat, cur)
        by_mat.setdefault("absent" if c is None else c.get("maturity", "absent"), []).append(cur)
    blockers = []
    if not is_met and not nxt:
        for cur in sorted(cl):
            c = _lat.find(lat, cur)
            if c is None or c.get("maturity") not in _lat.SETTLED:
                reasons = ["absent from the lattice"] if c is None else _lat.ready(lat, c)[1]
                blockers.append({"cell": cur, "maturity": None if c is None else c.get("maturity"),
                                 "blocked": bool(c and _lat.is_blocked(c)), "reasons": reasons})
    return {"goal": cell_id, "maturity": None if goal is None else goal.get("maturity"), "met": is_met,
            "closure_size": len(cl), "by_maturity": by_mat,
            "next": _lat.cid(nxt[0][1]) if nxt else None, "blockers": blockers}


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    d = _lat._dir(argv)
    pos = [a for a in argv if not a.startswith("--")]
    if len(pos) < 2:
        print("usage: goal.py {closure|met|next|status} CELL [--dir D]", file=sys.stderr)
        return 2
    op, cell = pos[0], pos[1]
    try:
        lat = _lat.load(d)
    except OSError:
        print(f"no lattice at {os.path.join(d, 'lattice.json')}", file=sys.stderr)
        return 2
    if _lat.find(lat, cell) is None:
        print(f"goal cell {cell} is not in the lattice", file=sys.stderr)
        return 2
    if op == "closure":
        for cur in sorted(closure(lat, cell)):
            print(cur)
        return 0
    if op == "met":
        ok = met(lat, cell)
        print(f"{'MET' if ok else 'NOT MET'}: {cell} is {_lat.find(lat, cell).get('maturity')}")
        return 0 if ok else 1
    if op == "next":
        nxt = rank_toward(lat, cell)
        if not nxt:
            print(f"no ready cell toward {cell}" + (" — GOAL MET" if met(lat, cell) else " — blocked (run `goal.py status`)"))
            return 1
        p, c, _ = nxt[0]
        print(f"{_lat.cid(c)}  ({c['maturity']}, priority {p})")
        return 0
    if op == "status":
        print(json.dumps(status(lat, cell), indent=2))
        return 0
    print(f"unknown op {op!r} — use closure|met|next|status", file=sys.stderr)
    return 2


def selftest():
    fails = []
    def expect(c, m):
        if not c:
            fails.append(m)
    # a 3-cell chain toward the goal: ontology.domain (validated) ← spec.s ← capability.c (the GOAL), c verified by rubric.c
    lat = {"version": "1", "frontier_scope": "task", "cells": [
        {"layer": "ontology", "scope": "task", "slug": "domain", "maturity": "validated", "depends_on": [], "signal_refs": ["x"]},
        {"layer": "spec", "scope": "task", "slug": "s", "maturity": "defined", "depends_on": ["ontology.task.domain"]},
        {"layer": "rubric", "scope": "task", "slug": "c", "maturity": "validated", "depends_on": ["spec.task.s"], "signal_refs": ["x"]},
        {"layer": "capability", "scope": "task", "slug": "c", "maturity": "absent", "depends_on": ["spec.task.s"], "verifier": "rubric.task.c"},
        {"layer": "spec", "scope": "task", "slug": "unrelated", "maturity": "absent", "depends_on": []},
    ]}
    GOAL = "capability.task.c"
    cl = closure(lat, GOAL)
    expect(cl == {GOAL, "spec.task.s", "ontology.task.domain", "rubric.task.c"},
           f"closure must be the transitive depends_on + verifier (got {cl})")
    expect("spec.task.unrelated" not in cl, "closure must EXCLUDE cells the goal does not depend on")
    expect(not met(lat, GOAL) and met(lat, "ontology.task.domain"),
           "met: the absent goal is NOT met; the validated upstream IS")
    # next toward the goal: spec.s is ready (its dep ontology.domain is validated); the goal isn't (its dep spec.s is defined)
    nxt = rank_toward(lat, GOAL)
    expect(nxt and _lat.cid(nxt[0][1]) == "spec.task.s",
           f"next-toward must be the ready closure cell (spec.task.s), not the unrelated gap (got {[_lat.cid(c) for _, c, _ in nxt]})")
    expect(all(_lat.cid(c) != "spec.task.unrelated" for _, c, _ in nxt), "next-toward must stay INSIDE the closure")
    # advance spec.s → the goal becomes the next ready cell
    _lat.find(lat, "spec.task.s")["maturity"] = "validated"
    nxt2 = rank_toward(lat, GOAL)
    expect(nxt2 and _lat.cid(nxt2[0][1]) == GOAL, f"once spec.s validates, the goal is next (got {[_lat.cid(c) for _, c, _ in nxt2]})")
    # validate the goal → MET, nothing left toward it, status reports met with no blockers
    _lat.find(lat, GOAL)["maturity"] = "validated"
    expect(met(lat, GOAL) and not rank_toward(lat, GOAL), "the validated goal is MET and has no next cell")
    st = status(lat, GOAL)
    expect(st["met"] is True and st["next"] is None and st["blockers"] == [], f"status of a met goal: met, no next, no blockers (got {st})")
    # a blocked goal surfaces its blocker (reset the goal + block its dep's prerequisite)
    lat2 = {"version": "1", "frontier_scope": "task", "cells": [
        {"layer": "spec", "scope": "task", "slug": "dep", "maturity": "absent", "depends_on": [], "blocked": True, "blocked_reason": "no-progress"},
        {"layer": "capability", "scope": "task", "slug": "g", "maturity": "absent", "depends_on": ["spec.task.dep"]},
    ]}
    stb = status(lat2, "capability.task.g")
    expect(stb["next"] is None and any(b["cell"] == "spec.task.dep" and b["blocked"] for b in stb["blockers"]),
           f"a blocked prerequisite must surface as a blocker with no next (got {stb})")
    if fails:
        sys.stderr.write("goal selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("goal selftest: OK (closure = transitive depends_on + verifier; met reads the lattice; next ranks WITHIN "
          "the closure; a met goal terminates; a blocked prerequisite surfaces with no next)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
