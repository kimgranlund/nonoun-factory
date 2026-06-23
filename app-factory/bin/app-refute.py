#!/usr/bin/env python3
"""app-refute.py — the trust SENSOR's recorder (the refute/corroborate ledger convention).

The harness-council found app-factory shipped a trust GAUGE (`ledger.py trust`) with no
SENSOR: `false_pass_rate` is UNMEASURED until an independent `refute` event exists, so the
autonomy ladder had no first rung. This script is the sensor's hand — the independent
`app-refuter` audits a PASSED ticket and records its verdict here, in the exact shape
`ledger.py` reads:

  - refute      → {operation: refute, cell_id: <the passed cell>}   ⇒ a FALSE PASS — counts against the rate
  - corroborate → {operation: refute, cell_id: "audit:<cell>"}      ⇒ the refuter RAN and found nothing —
                                                                       flips the rate to MEASURED with 0 false

Either verdict makes the rate MEASURED (the ladder gets a first rung); only a real `refute`
raises it. The refuter is an INDEPENDENT family (never the worker, validator, or acceptance
deriver); this script only RECORDS the verdict — it does not judge. Stdlib, Python 3.8+.

  app-refute.py <cell-id> --dir D --verdict {refute|corroborate} [--why TEXT]
  app-refute.py selftest
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "kernel"))
import ledger as _led  # noqa: E402  the vendored kernel (append / read / trust_tier)


def record(d, cell_id, verdict, why):
    if verdict not in ("refute", "corroborate"):
        raise ValueError("verdict must be 'refute' or 'corroborate'")
    # A refute marks the REAL cell (counts as a false pass); a corroborate marks an `audit:` sentinel
    # that can never collide with a pass cell_id, so it registers "the refuter ran" without false-flagging.
    target = cell_id if verdict == "refute" else f"audit:{cell_id}"
    prefix = "FALSE PASS: " if verdict == "refute" else "corroborated: "
    _led.append(d, {"operation": "refute", "actor": "app-refuter", "cell_id": target,
                    "result": "fail" if verdict == "refute" else "pass",
                    "rationale": prefix + (why or "(no detail)"), "kind": "independent-recheck"})
    return target


def _flag(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    pos = [a for a in argv if not a.startswith("--")]
    d = _flag(argv, "--dir", ".agents/harness")
    verdict = _flag(argv, "--verdict")
    if not pos or not verdict:
        print("usage: app-refute.py <cell-id> --dir D --verdict {refute|corroborate} [--why TEXT]", file=sys.stderr)
        return 2
    try:
        target = record(d, pos[0], verdict, _flag(argv, "--why"))
    except ValueError as e:
        print(e, file=sys.stderr)
        return 2
    tier, label, rate, _reason = _led.trust_tier(_led.read(d))
    rate_s = "unmeasured" if rate is None else f"{rate:.1%}"
    print(f"recorded {verdict} on {pos[0]} (ledger cell: {target})")
    print(f"  → earned autonomy tier: {tier} ({label}) — false-pass {rate_s}")
    return 0


def selftest():
    import tempfile
    fails = []
    def expect(c, m):
        if not c:
            fails.append(m)
    with tempfile.TemporaryDirectory() as d:
        # baseline — one validated pass, no refuter → UNMEASURED → Tier 0
        _led.append(d, {"operation": "validate", "actor": "app-validator", "cell_id": "capability.task.s0", "result": "pass"})
        expect(_led.trust_tier(_led.read(d))[0] == 0, "before any refuter: must be Tier 0 (unmeasured)")
        # corroborate it → MEASURED, but a single pass is too short a track record → Tier 1
        record(d, "capability.task.s0", "corroborate", "re-ran sealed acceptance under perturbation; held")
        t, _, rate, _ = _led.trust_tier(_led.read(d))
        expect(t == 1 and rate == 0.0, f"one corroborated pass → measured 0% but Tier 1 (short track), got tier={t} rate={rate}")
        # five corroborated passes under 5% → Tier 2 (the first real rung above attended)
        for i in range(1, 5):
            _led.append(d, {"operation": "validate", "actor": "app-validator", "cell_id": f"capability.task.s{i}", "result": "pass"})
            record(d, f"capability.task.s{i}", "corroborate", "held")
        t, _, rate, _ = _led.trust_tier(_led.read(d))
        expect(t == 2 and rate == 0.0, f"five corroborated passes <5% → Tier 2, got tier={t} rate={rate}")
        # a FALSE PASS discovered → refute → rate rises → AUTO-DEMOTE
        _led.append(d, {"operation": "validate", "actor": "app-validator", "cell_id": "capability.task.bad", "result": "pass"})
        record(d, "capability.task.bad", "refute", "sealed acceptance was a presence-check; a hollow impl passed it")
        t, _, rate, _ = _led.trust_tier(_led.read(d))
        expect(t <= 1 and rate and rate > 0, f"a refuted false pass must raise the rate and auto-demote, got tier={t} rate={rate}")
    if fails:
        sys.stderr.write("app-refute selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("app-refute selftest: OK (no refuter → Tier 0 unmeasured; corroborate flips to MEASURED; ≥5 corroborated "
          "passes <5% → Tier 2; a refuted false pass raises the rate and auto-demotes — the ladder has a first rung)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
