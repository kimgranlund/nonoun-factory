#!/usr/bin/env python3
"""heartbeat.py — the dark factory's pulse: the bounded 30s outer loop (TDD §8).

By the routing law the loop is DETERMINISTIC and lives in the server — scanning, dependency-filtering,
ranking, and dispatching are graph/arithmetic over the lattice + the coordination index, never inference.
Agents enter only INSIDE a dispatched unit. One tick:

    on_tick():
      if paused: return
      reconcile_leases()                       # expire dead workers (dispatch.py)
      if budget_exhausted(): return            # SURFACE the ceiling — never burn through it (Failure 4)
      slots = max_concurrency - running()
      for t in compass.next_batch(tier, slots):   # ready + ranked (compass.py)
          dispatch_unit(t)                          # provision, claim, run, validate (dispatch.py)
      emit_metrics()

The loop is BOUNDED by construction — the same discipline harness-forge's I-9 run budget enforces, here
dev-native over dev's ledger: a window with a wall-clock deadline, a max-dispatch cap, and a token
ceiling, armed before the loop runs. An exhausted window halts dispatch; the budget file lives under the
worker-protected run/ perimeter, so a worker cannot lift its own ceiling.

Usage:
  heartbeat.py arm   --dir DIR [--deadline-s N] [--max-dispatches N] [--token-ceiling N]
  heartbeat.py tick  --dir DIR [--tier T] [--max-concurrency N]    # one tick (mock adapter)
  heartbeat.py selftest
Stdlib only; Python 3.8+.
"""
import datetime
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import api as _api          # noqa: E402
import dispatch as _disp    # noqa: E402
sys.path.insert(0, _api._store._KERNEL_BIN)
import compass as _compass  # noqa: E402
import ledger as _led       # noqa: E402
import autonomy as _auto    # noqa: E402


def _now():
    return datetime.datetime.now().astimezone()


def _budget_path(d):
    return os.path.join(d, "run", "heartbeat.json")


# the SAFETY deadline a window with no operator-set ceiling falls back to — so an armed run is NEVER unbounded
# (harness-council re-audit H5: app.py defaulted all four ceilings to None, leaving only the per-dispatch $ cap ×
# an unbounded number of cells/retries). 2h is generous for a real build; an operator sets explicit bounds to override.
DEFAULT_WINDOW_DEADLINE_S = 7200


def arm(d, now=None, deadline_s=None, max_dispatches=None, token_ceiling=None, dollar_ceiling=None):
    """Arm the loop's window. MUST be called before the loop runs (the arming discipline): an unarmed loop
    does not dispatch (fail-closed). The window is bounded by ANY of: a wall-clock deadline, a max-dispatch
    count, a token ceiling, or a DOLLAR ceiling — whichever is hit first halts dispatch. If the operator sets
    NONE of them, a safety wall-clock deadline (DEFAULT_WINDOW_DEADLINE_S) is stamped so the window can never be
    fully unbounded — an armed-but-uncapped run is a misconfiguration, not a license to spend without limit."""
    now = now or _now()
    # guard on FALSY, not `is None`: an explicit `arm(deadline_s=0)`/`max_dispatches=0` is a zero ceiling that the
    # `... if deadline_s else None` below would turn into an UNbounded window (harness-council re-audit 2). If no
    # ceiling is truthy, stamp the safety deadline so an armed window is never fully unbounded.
    if not deadline_s and not max_dispatches and not token_ceiling and not dollar_ceiling:
        deadline_s = DEFAULT_WINDOW_DEADLINE_S
    b = {"start_ts": now.isoformat(timespec="seconds"), "ticks": 0,
         "deadline_ts": (now + datetime.timedelta(seconds=deadline_s)).isoformat(timespec="seconds") if deadline_s else None,
         "max_dispatches": max_dispatches, "token_ceiling": token_ceiling, "dollar_ceiling": dollar_ceiling}
    os.makedirs(os.path.dirname(_budget_path(d)), exist_ok=True)
    json.dump(b, open(_budget_path(d), "w"), indent=2)
    return b


def load_budget(d):
    p = _budget_path(d)
    return json.load(open(p, encoding="utf-8")) if os.path.isfile(p) else None


def clear(d):
    p = _budget_path(d)
    if os.path.isfile(p):
        os.remove(p)


def _dispatches_since(d, start_ts):
    return sum(1 for e in _led.read(d, since=start_ts) if e.get("event") == "dispatch")


def _tokens_since(d, start_ts):
    tot = 0
    for e in _led.read(d, since=start_ts):
        m = e.get("metrics") or {}
        if isinstance(m.get("tokens"), (int, float)):
            tot += m["tokens"]
    return tot


def _cost_since(d, start_ts):
    tot = 0.0
    for e in _led.read(d, since=start_ts):
        m = e.get("metrics") or {}
        if isinstance(m.get("cost_usd"), (int, float)):
            tot += m["cost_usd"]
    return tot


def budget_exhausted(d, now=None):
    """(exhausted, reason). Unarmed → fail-closed (the loop must arm first). Computed from code + the
    ledger, never an agent's counting."""
    now = now or _now()
    b = load_budget(d)
    if b is None:
        return True, "loop not armed — arm the heartbeat window before dispatching (fail-closed)"
    if b.get("deadline_ts") and now.isoformat(timespec="seconds") >= b["deadline_ts"]:
        return True, f"wall-clock deadline reached ({b['deadline_ts']})"
    if b.get("max_dispatches") is not None:
        n = _dispatches_since(d, b["start_ts"])
        if n >= b["max_dispatches"]:
            return True, f"max-dispatches reached ({n}/{b['max_dispatches']})"
    if b.get("token_ceiling") is not None:
        t = _tokens_since(d, b["start_ts"])
        if t >= b["token_ceiling"]:
            return True, f"token ceiling reached ({t}/{b['token_ceiling']})"
    if b.get("dollar_ceiling") is not None:
        c = _cost_since(d, b["start_ts"])
        if c >= b["dollar_ceiling"]:
            return True, f"dollar ceiling reached (${c:.2f}/${b['dollar_ceiling']:.2f})"
    return False, None


def count_running(d):
    return sum(1 for t in _api.list_tickets(d) if t.get("state") in ("claimed", "in-progress"))


def strict_accept_filter(d, batch):
    """Tier-1 strict-acceptance policy: keep only dependents whose every dependency cell is human-ACCEPTED
    (carried by a `done` ticket), not merely critic-`validated`. The kernel's partial order already cleared
    the deps as validated; this SERVER policy additionally waits for the operator's sign-off, so at Tier 1 the
    build advances cell-by-cell behind your acceptance instead of flowing on validation. Pure over the tickets."""
    accepted = {t.get("target_cell") for t in _api.list_tickets(d)
                if t.get("state") == "done" and t.get("target_cell")}
    return [t for t in batch
            if all(c in accepted for c in (t.get("dependencies") or {}).get("cells_ready", []))]


PAUSED = {"v": False}


def on_tick(d, adapter=None, tier=None, max_concurrency=2, now=None, strict_accept=False):
    """One heartbeat tick. Deterministic end to end; agents run only inside dispatch_unit. The autonomy
    tier is READ from the ledger (autonomy.tier_for) unless overridden: Tier 0 dispatches nothing; Tier 1
    dispatches but stops at in-review for human review; Tier 2+ drives the unit to done unattended. Returns
    a summary {tier, dispatched, reconciled, halted, reason}.

    `strict_accept` (opt-in policy, DEV_FACTORY_TIER1_STRICT): at Tier 1, hold a dependent until every
    dependency cell is human-ACCEPTED (its ticket `done`), not merely critic-validated — so the build waits
    for your sign-off cell-by-cell instead of flowing on validation. A SERVER policy layered on the kernel's
    partial order (the kernel still only requires deps validated); moot at Tier 2+ (auto-accept)."""
    now = now or _now()
    if PAUSED["v"]:
        return {"halted": True, "reason": "paused (human kill-switch)", "dispatched": []}
    if tier is None:
        tier = _auto.tier_for(d, now=now)          # the EARNED tier — mechanically demoted on incident
    adapter = adapter or _disp.resolve_adapter()   # DEV_FACTORY_ADAPTER=headless → live workers; default mock (free)
    reconciled = _disp.reconcile_leases(d, now=now)
    exhausted, reason = budget_exhausted(d, now=now)
    if exhausted:
        return {"halted": True, "reason": reason, "tier": tier, "dispatched": [], "reconciled": reconciled}
    slots = max_concurrency - count_running(d)
    if slots <= 0:
        return {"halted": False, "reason": "no free slot (backpressure)", "tier": tier, "dispatched": [], "reconciled": reconciled}
    batch = _compass.next_batch(d, tier=tier, slots_free=slots)
    # the frontier must never SILENTLY starve: a depends_on CYCLE leaves its cells un-advanceable forever (each
    # waits on another around the loop, so every dispatch is refused by the partial-order gate with no event saying
    # why). When there is non-terminal work, check for a cycle and NAME it ONCE so the operator/dependency-arbiter
    # sees the loop to break — instead of the loop spinning on refused dispatches (harness-council H1).
    cycle = None
    if any(t.get("state") in ("active", "claimed", "draft", "in-progress") for t in _api.list_tickets(d)):
        cycle = _compass.surface_cycle(d)   # the readiness filter reports any cycle; the arbiter resolves it
    if strict_accept and tier < 2 and batch:
        batch = strict_accept_filter(d, batch)      # Tier-1 strict: hold dependents until their deps are human-accepted
    auto = tier >= 2                                # Tier 1 dispatches but pauses at in-review (human reviews)
    dispatched = []
    for t in batch:
        ok, _t, _msg = _disp.dispatch_unit(d, _api.get_ticket(d, t["id"]), adapter,
                                           {"kind": "server", "id": "heartbeat"}, tier=tier, auto_validate=auto)
        dispatched.append({"ticket": t["id"], "ok": ok, "to": "done" if auto else "in-review"})
    # PRODUCE → MEASURE the false-pass oracle (earned autonomy):
    #  1. ARM — a freshly-validated CODE cell (Tier 1 human-accepted OR Tier 2 auto) gets an independent refuter, so
    #     it becomes MEASURABLE. Without this live producer false_pass stays 'unmeasured' and Tier 2 is unreachable.
    #  2. RE-CHECK — re-validate one armed-but-unrefuted cell against its HIDDEN refuter. The check is the false-pass
    #     denominator; a DISAGREEMENT records an incident (autonomy demotes — the NEXT tick reads the lower tier_for).
    # One re-check per tick keeps ticks cheap.
    produced = _disp.produce_refuters(d)
    #  1b. AUTHOR — the autonomous producer (headless only): a gate-BLIND refute-author writes a behavioral oracle
    #      into ONE still-unmeasured cell's verify-spec, which the next produce_refuter calibrates + UPGRADES to
    #      measuring — so the factory earns Tier 2 WITHOUT a human hand-authoring the refute set. Mock cannot
    #      synthesize a domain contract, so this is a real-build step; one per tick keeps the loop cheap + budget-bounded.
    authored = {}
    if getattr(adapter, "name", "mock") != "mock":
        authored = _disp.author_refuters(d, adapter, limit=1)
    refuted = None
    frontier = _disp.refute_frontier(d)
    if frontier:
        refuted = {"cell": frontier[0], "agreed": _disp.run_refuter(d, frontier[0])}
    # REGENERATION: distill the ledger's recurring success signatures into `pattern.system.*` cells — the pattern
    # layer (the one a build never seeds) populates from real operating evidence (operate → ledger → distill → patterns).
    distilled = _disp.distill_to_patterns(d)
    b = load_budget(d)
    if b is not None:
        b["ticks"] = b.get("ticks", 0) + 1
        json.dump(b, open(_budget_path(d), "w"), indent=2)
    return {"halted": False, "reason": None, "tier": tier, "dispatched": dispatched,
            "reconciled": reconciled, "produced": produced, "authored": authored, "refuted": refuted,
            "distilled": distilled, "cycle": cycle}


def run(d, adapter=None, tier=1, max_concurrency=2, period_s=30):
    """The live loop (the server's scheduler calls this). Blocks; the server runs it as a task."""
    import time
    while True:
        summ = on_tick(d, adapter=adapter, tier=tier, max_concurrency=max_concurrency)
        if summ.get("halted") and "deadline" in (summ.get("reason") or ""):
            return summ
        time.sleep(period_s)


def selftest():
    import tempfile
    fails = []
    def expect(c, m):
        if not c:
            fails.append(m)
    with tempfile.TemporaryDirectory() as root:
        d = os.path.join(root, ".factory")
        _api.init_instance(d)
        srv = {"kind": "server", "id": "dev-server"}
        _api.seed_cell(d, "rubric", "task", "r", maturity="validated", signal_refs=["signals/rubric.task.r/seed.json"])
        _api.seed_cell(d, "spec", "task", "s", maturity="instantiated", asset_ref="spec/s.md")
        os.makedirs(os.path.join(d, "spec"), exist_ok=True)
        open(os.path.join(d, "spec", "s.md"), "w").write("# s\n")
        t = _api.create_ticket(d, "feature", "the slice", target_cell="spec.task.s",
                               target_transition={"from": "instantiated", "to": "validated"},
                               acceptance={"rubric_cell": "rubric.task.r"}, budget={"iterations": 2, "tokens": 50000})
        _api.transition_ticket(d, t["id"], "active", srv)

        # UNARMED → fail-closed (no dispatch)
        s0 = on_tick(d)
        expect(s0["halted"] and "not armed" in s0["reason"], f"unarmed loop did not fail closed: {s0}")
        expect(_api.get_ticket(d, t["id"])["state"] == "active", "unarmed loop dispatched anyway")

        # at Tier 2 the tick drives the ready ticket to done, UNATTENDED (Tier 1 would stop at in-review). This UNIT
        # test exercises the DISPATCH path with an EXPLICIT tier=2 override — it does NOT mint a fake measurement to
        # "earn" the tier (the honest earning is proven end-to-end, node-gated, in evals/earned-autonomy; minting a
        # non-oracle measuring check to reach Tier 2 was the counting-default hole).
        arm(d, max_dispatches=5, deadline_s=3600)
        s1 = on_tick(d, tier=2, max_concurrency=2)
        expect(s1.get("tier") == 2, f"tier-2 dispatch path not exercised; got tier {s1.get('tier')}")
        expect(not s1["halted"] and any(x["ok"] for x in s1["dispatched"]), f"armed tick did not dispatch: {s1}")
        expect(_api.get_ticket(d, t["id"])["state"] == "done", "heartbeat did not drive the slice to done unattended")
        cell = next(c for c in _api.lattice_grid(d) if c["id"] == "spec.task.s")
        expect(cell["maturity"] == "validated", "heartbeat-dispatched cell not validated")

        # the bound HALTS: a past deadline stops dispatch (surface, not burn)
        arm(d, deadline_s=-1, max_dispatches=5)
        _api.seed_cell(d, "spec", "task", "s2", maturity="instantiated", asset_ref="spec/s2.md")
        open(os.path.join(d, "spec", "s2.md"), "w").write("# s2\n")
        t2 = _api.create_ticket(d, "feature", "slice2", target_cell="spec.task.s2",
                                target_transition={"from": "instantiated", "to": "validated"},
                                acceptance={"rubric_cell": "rubric.task.r"}, budget={"iterations": 2, "tokens": 50000})
        _api.transition_ticket(d, t2["id"], "active", srv)
        s2 = on_tick(d)
        expect(s2["halted"] and "deadline" in s2["reason"], f"exhausted budget did not halt: {s2}")
        expect(_api.get_ticket(d, t2["id"])["state"] == "active", "dispatched past the deadline (burned through the bound)")

        # the DOLLAR ceiling halts too — and FAILURE-path spend counts toward it (H5-C1/C3): a worker run that
        # produced no artifact still spent, so its activity-fail carries cost_usd/tokens, which _cost_since sums.
        arm(d, dollar_ceiling=1.0)
        bts = load_budget(d)["start_ts"]
        _led.append(d, "activity-fail", {"kind": "agent", "id": "headless-claude"}, {"cell": "spec.task.s3"},
                    "worker failed: no artifact", metrics={"activity": "a", "cost_usd": 1.5, "tokens": 9000},
                    ts=bts)
        expect(_cost_since(d, bts) >= 1.5, "_cost_since must sum FAILURE-path cost_usd (H5-C1: the ceiling must see failed-run spend)")
        ex, why = budget_exhausted(d)
        expect(ex and "dollar ceiling" in (why or ""), f"dollar ceiling did not halt on failure-path spend: {why}")

        # an armed window is NEVER unbounded (H5): arming with NO operator ceiling stamps a safety deadline, so the
        # only-the-per-dispatch-$-cap hazard can't exist; an explicit ceiling is left as the sole bound.
        b_default = arm(d)
        expect(b_default["deadline_ts"] is not None and b_default["max_dispatches"] is None,
               "arm() with no ceilings must stamp a safety deadline (never a fully unbounded window)")
        b_explicit = arm(d, max_dispatches=3)
        expect(b_explicit["deadline_ts"] is None and b_explicit["max_dispatches"] == 3,
               "arm() with an explicit ceiling must NOT force a safety deadline")
        # falsy-guard (re-audit 2): a ZERO ceiling is not a bound — arm(deadline_s=0) must still get the safety deadline
        expect(arm(d, deadline_s=0)["deadline_ts"] is not None,
               "arm(deadline_s=0) is a zero ceiling, NOT a bound — must still stamp the safety deadline (no unbounded window)")

        # H1 — when a depends_on CYCLE starves the frontier, on_tick NAMES it (never a silent idle tick)
        with tempfile.TemporaryDirectory() as croot:
            cd = os.path.join(croot, ".factory")
            _api.init_instance(cd)
            _api.seed_cell(cd, "rubric", "task", "r", maturity="validated", signal_refs=["signals/rubric.task.r/s.json"])
            for a, b in (("cyca", "cycb"), ("cycb", "cyca")):
                _api.seed_cell(cd, "spec", "task", a, maturity="instantiated", asset_ref=f"spec/{a}.md",
                               depends_on=[f"spec.task.{b}"])
                ct = _api.create_ticket(cd, "feature", a, target_cell=f"spec.task.{a}",
                                        target_transition={"from": "instantiated", "to": "validated"},
                                        acceptance={"rubric_cell": "rubric.task.r"}, budget={"iterations": 1, "tokens": 100})
                _api.transition_ticket(cd, ct["id"], "active", srv)
            arm(cd, max_dispatches=5, deadline_s=3600)
            cs = on_tick(cd, tier=1)
            expect(cs.get("cycle") and set(cs["cycle"]) == {"spec.task.cyca", "spec.task.cycb"},
                   f"on_tick must NAME a dependency cycle that starves the frontier, got {cs.get('cycle')}")
            expect(any((e.get("metrics") or {}).get("cycle") for e in _led.read(cd, event="block")),
                   "the cycle must be ledgered (the operator/arbiter sees the loop to break, not a silent idle)")
    if fails:
        sys.stderr.write("heartbeat selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("heartbeat selftest: OK (UNARMED fails closed; an armed tick drives a ready slice to done unattended "
          "via the compass+dispatcher; an exhausted window — past deadline — HALTS dispatch rather than burning "
          "through it; the budget lives under the worker-protected run/ perimeter)")
    return 0


def _arg(argv, flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


def main(argv):
    if not argv or argv[0] == "selftest":
        return selftest()
    d = _arg(argv, "--dir", ".factory")
    if argv[0] == "arm":
        b = arm(d, deadline_s=int(_arg(argv, "--deadline-s", "0")) or None,
                max_dispatches=int(_arg(argv, "--max-dispatches", "0")) or None,
                token_ceiling=int(_arg(argv, "--token-ceiling", "0")) or None,
                dollar_ceiling=float(_arg(argv, "--dollar-ceiling", "0")) or None)
        print(json.dumps(b))
        return 0
    if argv[0] == "tick":
        print(json.dumps(on_tick(d, tier=int(_arg(argv, "--tier", "1")),
                                 max_concurrency=int(_arg(argv, "--max-concurrency", "2")))))
        return 0
    print(f"heartbeat.py: unknown verb {argv[0]}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
