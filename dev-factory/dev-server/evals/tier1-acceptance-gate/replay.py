#!/usr/bin/env python3
"""replay.py — the Tier-1 acceptance gate: the critic runs at EVERY tier; the tier gates only ACCEPTANCE.

The gap this closes: previously `dispatch_unit(auto_validate=False)` (Tier 1) parked a cell at in-review
WITHOUT ever running the critic. A signal-bearing cell could then never reach `validated` (the critic that
mints the unforgeable signal never ran), so `gate-signal` correctly refused the operator's `done` — and the
cell livelocked, blocking the whole partial order behind it. The produce→validate→iterate loop only ran at
Tier 2+, so the lattice model could not guide output iteration under human oversight.

The fix: the critic ALWAYS runs (the lattice always gets its signal and the iterate loop runs at every tier);
the autonomy tier gates only ACCEPTANCE — auto-close at Tier 2+, the human sign-off gate at Tier 1.

Falsified if any breaks:
  T1  at Tier 1 the critic RUNS on a structured spec → the cell reaches `validated` with a critic-minted signal
      (it is NOT left at `instantiated`, the old livelock).
  T2  the ticket parks at `in-review` (not `done`) — acceptance is the human's, the cell's validity is the critic's.
  T3  the operator's PLAIN `done` approval (no verifier to hand-supply) then SUCCEEDS — gate-signal passes because
      a prior critic already validated the cell ("the board cannot disagree with the lattice").
  T4  the iterate loop runs at Tier 1: a PROSE spec is REFUSED by the real rubric → the cell stays `instantiated`
      and the ticket returns to `active` to re-author against the feedback (the reward-hack teeth bite at Tier 1).
  T5  the reward-hack boundary holds: the Tier-1 signal is critic-minted (actor cell-validator), never worker-forged.

Exit 0 = the critic runs at Tier 1 and only acceptance is gated. Stdlib only; Python 3.8+. Answer key in README.md.
"""
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER = os.path.dirname(os.path.dirname(_HERE))
_DF = os.path.dirname(_SERVER)
os.environ["DEV_FACTORY_KIT"] = os.path.join(_DF, "dev-kit-corpus")   # bind the corpus family
sys.path.insert(0, _SERVER)
import api as _api          # noqa: E402
import dispatch as _disp    # noqa: E402
sys.path.insert(0, _api._store._KERNEL_BIN)
import lattice as _lat      # noqa: E402

CELL = "spec.system.feature"
STRUCTURED = {
    "title": "First feature", "cell": CELL,
    "acceptance_criteria": [{"id": "c1", "check": "POST /x returns 200"},
                            {"id": "c2", "rubric_cell": "rubric.system.test", "scored_by": ["tests-pass"]}],
    "non_goals": ["password reset", "SSO"],
    "binds_rubric": "rubric.system.spec-quality",
}


def _seed(d, structured):
    _api.init_instance(d)
    _api.seed_cell(d, "rubric", "system", "spec-quality", maturity="validated", signal_refs=["signals/rubric.system.spec-quality/seed.json"])
    _api.seed_cell(d, "spec", "system", "feature", maturity="instantiated", asset_ref="spec/feature.md")
    os.makedirs(os.path.join(d, "spec"), exist_ok=True)
    body = ("# First feature\n\n```json\n" + json.dumps(STRUCTURED, indent=2) + "\n```\n") if structured \
           else "# First feature\n\nA prose spec — words, but nothing a rubric can mechanically gate.\n"
    open(os.path.join(d, "spec", "feature.md"), "w").write(body)


def _ticket(d, srv):
    t = _api.create_ticket(d, "feature", "validate the feature spec", target_cell=CELL,
                           target_transition={"from": "instantiated", "to": "validated"},
                           acceptance={"rubric_cell": "rubric.system.spec-quality"},
                           budget={"iterations": 4, "tokens": 80000}, priority={"risk": 0.9})
    _api.transition_ticket(d, t["id"], "active", srv)
    return t


def run():
    fails = []
    def check(cond, label):
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            fails.append(label)
    srv = {"kind": "server", "id": "dev-server"}
    human = {"kind": "human", "id": "operator"}

    print("· a STRUCTURED spec at Tier 1 — the critic runs, the cell validates, the ticket waits for the human")
    with tempfile.TemporaryDirectory() as root:
        d = os.path.join(root, ".factory")
        _seed(d, structured=True)
        t = _ticket(d, srv)
        ok, ticket, msg = _disp.dispatch_unit(d, _api.get_ticket(d, t["id"]), _disp.MockAdapter(), srv,
                                              tier=1, auto_validate=False)
        cell = _lat.find(_lat.load(d), CELL)
        check(ok and cell["maturity"] == "validated",
              f"T1: at Tier 1 the critic RAN → cell `validated` (not the old `instantiated` livelock). got {cell['maturity']!r} ({msg})")
        check(_api.get_ticket(d, t["id"])["state"] == "in-review",
              f"T2: the ticket parks at in-review (acceptance is the human's). got {_api.get_ticket(d, t['id'])['state']!r}")
        # T5: the signal that advanced the cell was critic-minted, never worker-forged
        sigs = [e for e in _api.ledger_query(d) if e.get("event") == "signal" and e.get("to") == "pass"]
        check(bool(sigs) and (sigs[-1].get("actor") or {}).get("id") == "cell-validator",
              "T5: the Tier-1 signal is critic-minted (actor cell-validator), not worker-forged")
        # T3: the operator's PLAIN done approval (no verifier) now succeeds
        aok, _t, amsg = _api.transition_ticket(d, t["id"], "done", human)
        check(aok and _api.get_ticket(d, t["id"])["state"] == "done",
              f"T3: the operator's plain `done` approval succeeds — gate-signal passes (a prior critic validated the cell). ({amsg[:80]})")
        check(_lat.find(_lat.load(d), CELL)["maturity"] == "validated", "T3b: the cell remains validated after acceptance")

    print("· the SAME pipeline with a PROSE spec at Tier 1 — the iterate loop runs, the rubric REJECTS it")
    with tempfile.TemporaryDirectory() as root:
        d = os.path.join(root, ".factory")
        _seed(d, structured=False)
        t = _ticket(d, srv)
        ok, ticket, msg = _disp.dispatch_unit(d, _api.get_ticket(d, t["id"]), _disp.MockAdapter(), srv,
                                              tier=1, auto_validate=False)
        cell = _lat.find(_lat.load(d), CELL)
        check(not ok and cell["maturity"] == "instantiated",
              f"T4: a PROSE spec is REFUSED at Tier 1 — cell stays `instantiated`, the teeth bite. got {cell['maturity']!r}")
        check(_api.get_ticket(d, t["id"])["state"] == "active",
              f"T4b: the ticket returns to `active` to re-author against the feedback (iterate). got {_api.get_ticket(d, t['id'])['state']!r}")

    print()
    if fails:
        print(f"tier1-acceptance-gate: GAP OPEN — {len(fails)} check(s) failed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("tier1-acceptance-gate: OK — the critic runs at EVERY tier (the lattice always gets its unforgeable "
          "signal and the produce→validate→iterate loop runs under human oversight); the autonomy tier gates only "
          "ACCEPTANCE. At Tier 1 a structured spec is critic-validated and parks for the operator's plain sign-off; "
          "a prose spec is refused and re-authored. A single in-review cell can no longer livelock the partial order.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
