#!/usr/bin/env python3
"""tier-gate.py — the autonomy ACTUATOR (a dispatch-time trust-tier consumer).

A trust gauge nobody reads changes nothing. The harness-council's fix needs three parts:
a SENSOR (the refuter → `app-refute.py`), a GAUGE (`ledger.py trust_tier`), and an
ACTUATOR — a check at dispatch that REFUSES autonomy above what the ledger has earned. This
is the actuator: `/app-loop` / `/app-goal` call it before running at a requested tier; it
exits 0 only if the earned tier covers the request, else nonzero (the loop then runs attended
or stops). Earned tier is computed from the ledger, never declared. Stdlib, Python 3.8+.

  tier-gate.py --request N --dir D   # exit 0 iff earned tier ≥ N, else 1
  tier-gate.py selftest
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "kernel"))
import ledger as _led  # noqa: E402


def _flag(argv, name, default=None):
    return argv[argv.index(name) + 1] if name in argv and argv.index(name) + 1 < len(argv) else default


def check(d, request):
    tier, label, rate, reason = _led.trust_tier(_led.read(d))
    return tier >= request, tier, label, rate, reason


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    d = _flag(argv, "--dir", ".agents/harness")
    try:
        request = int(_flag(argv, "--request", "0"))
    except ValueError:
        print("--request must be an integer tier (0-3)", file=sys.stderr)
        return 2
    ok, tier, label, rate, reason = check(d, request)
    rate_s = "unmeasured" if rate is None else f"{rate:.1%}"
    print(f"requested Tier {request}; earned Tier {tier} ({label}, false-pass {rate_s}) → {'ALLOW' if ok else 'DENY'}")
    if not ok:
        print(f"  {reason}", file=sys.stderr)
        print(f"  run attended (Tier 0) or earn the tier first (independent refuter checks via app-refute.py).", file=sys.stderr)
    return 0 if ok else 1


def selftest():
    import tempfile
    fails = []
    def expect(c, m):
        if not c:
            fails.append(m)
    with tempfile.TemporaryDirectory() as d:
        # unmeasured ledger → Tier 0 earned: a request for unattended (Tier 2) is DENIED, attended (Tier 0) ALLOWED
        _led.append(d, {"operation": "validate", "actor": "v", "cell_id": "capability.task.x", "result": "pass"})
        expect(check(d, 2)[0] is False, "unmeasured ledger must DENY a Tier-2 request")
        expect(check(d, 0)[0] is True, "Tier-0 (attended) is always allowed")
        # earn Tier 2: five corroborated passes under 5%
        for i in range(5):
            _led.append(d, {"operation": "validate", "actor": "v", "cell_id": f"capability.task.c{i}", "result": "pass"})
            _led.append(d, {"operation": "refute", "actor": "app-refuter", "cell_id": f"audit:c{i}", "result": "pass"})
        expect(check(d, 2)[0] is True, "five corroborated clean passes must ALLOW Tier 2")
        expect(check(d, 3)[0] is False, "Tier 3 needs a human-attested sandbox — the rate alone never allows it")
    if fails:
        sys.stderr.write("tier-gate selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("tier-gate selftest: OK (unmeasured → deny unattended, allow attended; an earned Tier 2 allows Tier 2 but "
          "never Tier 3 — the rate alone can't attest a sandbox)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
