#!/usr/bin/env python3
"""replay.py — Tier-1 STRICT acceptance gating (opt-in): downstream waits for the human sign-off, cell-by-cell.

By default (DEV_FACTORY_TIER1_STRICT unset) the loop flows on critic-VALIDATION: at Tier 1 a cell is
critic-validated and downstream proceeds while the ticket parks at in-review for async human acceptance.
This eval proves the OPT-IN stricter policy: a dependent is held until its dependency cells are human-
ACCEPTED (their tickets `done`), not merely validated — so the build advances behind your sign-off.

The policy is a SERVER concern layered on the kernel's partial order (the kernel still only requires deps
`validated`); it is moot at Tier 2+ where the ticket auto-closes on validation (accepted == validated).

Falsified if any breaks:
  S1  with a dependency cell `validated` but NOT accepted (no `done` ticket), strict_accept_filter DROPS the
      dependent — it is held.
  S2  once the dependency is ACCEPTED (a `done` ticket carries it), strict_accept_filter KEEPS the dependent.
  S3  a no-dependency ticket is always kept (nothing to wait on).
  S4  end-to-end: on_tick(strict_accept=True, tier=1) does NOT dispatch the held dependent (its cell stays
      `instantiated`); on_tick(strict_accept=False) DOES (the cell is critic-validated) — same lattice, the
      flag is the only difference.

Exit 0 = the opt-in strict gate holds downstream for human acceptance. Stdlib only; Python 3.8+. Answer key in README.md.
"""
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SERVER = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _SERVER)
import api as _api          # noqa: E402
import heartbeat as _hb     # noqa: E402
import dispatch as _disp    # noqa: E402
sys.path.insert(0, _api._store._KERNEL_BIN)
import lattice as _lat      # noqa: E402

SRV = {"kind": "server", "id": "dev-server"}


def _seed(d):
    _api.init_instance(d)
    _api.seed_cell(d, "rubric", "system", "r", maturity="validated", signal_refs=["signals/rubric.system.r/seed.json"])
    _api.seed_cell(d, "spec", "system", "up", maturity="validated", signal_refs=["signals/spec.system.up/seed.json"], asset_ref="spec/up.md")
    _api.seed_cell(d, "spec", "system", "down", maturity="instantiated", asset_ref="spec/down.md", depends_on=["spec.system.up"])
    os.makedirs(os.path.join(d, "spec"), exist_ok=True)
    open(os.path.join(d, "spec", "up.md"), "w").write("# up\n")
    open(os.path.join(d, "spec", "down.md"), "w").write("# down\n")


def _down_ticket(d):
    t = _api.create_ticket(d, "feature", "down", target_cell="spec.system.down",
                           target_transition={"from": "instantiated", "to": "validated"},
                           acceptance={"rubric_cell": "rubric.system.r"},
                           budget={"iterations": 2, "tokens": 9000},
                           dependencies={"cells_ready": ["spec.system.up"]})
    _api.transition_ticket(d, t["id"], "active", SRV)
    return _api.get_ticket(d, t["id"])


def _accept_up(d):
    """Create a ticket for the already-validated `up` cell and drive it to done — so `up` is ACCEPTED."""
    t = _api.create_ticket(d, "feature", "up", target_cell="spec.system.up",
                           target_transition={"from": "instantiated", "to": "validated"},
                           acceptance={"rubric_cell": "rubric.system.r"}, budget={"iterations": 2, "tokens": 9000})
    for to in ("active", "claimed", "in-progress", "in-review", "done"):
        ok, _t, msg = _api.transition_ticket(d, t["id"], to, SRV)
        assert ok, f"could not drive up ticket to {to}: {msg}"


def run():
    fails = []
    def check(cond, label):
        print(f"  {'PASS' if cond else 'FAIL'}  {label}")
        if not cond:
            fails.append(label)

    print("· strict_accept_filter — the policy predicate")
    with tempfile.TemporaryDirectory() as root:
        d = os.path.join(root, ".factory")
        _seed(d)
        down = _down_ticket(d)
        kept = _hb.strict_accept_filter(d, [down])
        check(kept == [], "S1: dependency validated but NOT accepted → dependent is HELD (dropped from the batch)")
        _accept_up(d)
        kept = _hb.strict_accept_filter(d, [_api.get_ticket(d, down["id"])])
        check([t["id"] for t in kept] == [down["id"]], "S2: once the dependency is ACCEPTED (done ticket) → dependent is KEPT")
        # a no-dependency ticket is always kept
        nodep = _api.create_ticket(d, "feature", "free", target_cell="spec.system.up",
                                   target_transition={"from": "instantiated", "to": "validated"},
                                   acceptance={"rubric_cell": "rubric.system.r"})
        _api.transition_ticket(d, nodep["id"], "active", SRV)
        check(len(_hb.strict_accept_filter(d, [_api.get_ticket(d, nodep["id"])])) == 1,
              "S3: a ticket with no dependencies is always kept")

    print("· on_tick end-to-end — the flag is the only difference (same lattice)")
    for strict, expect_mat, tag in ((True, "instantiated", "strict=True → HELD"), (False, "validated", "strict=False → built")):
        with tempfile.TemporaryDirectory() as root:
            d = os.path.join(root, ".factory")
            _seed(d)
            _down_ticket(d)
            _hb.arm(d, deadline_s=3600, max_dispatches=10, token_ceiling=10_000_000)
            _hb.on_tick(d, adapter=_disp.MockAdapter(), tier=1, max_concurrency=2, strict_accept=strict)
            mat = _lat.find(_lat.load(d), "spec.system.down")["maturity"]
            check(mat == expect_mat, f"S4: {tag} — spec.system.down is {mat!r} (expected {expect_mat!r})")

    print()
    if fails:
        print(f"tier1-strict-gate: GAP OPEN — {len(fails)} check(s) failed:")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("tier1-strict-gate: OK — the opt-in DEV_FACTORY_TIER1_STRICT policy holds a dependent until its "
          "dependency cells are human-ACCEPTED (ticket done), not merely critic-validated. A server policy on top "
          "of the kernel's partial order; the flag is the only difference between a build that flows on validation "
          "and one that advances cell-by-cell behind the operator's sign-off.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
