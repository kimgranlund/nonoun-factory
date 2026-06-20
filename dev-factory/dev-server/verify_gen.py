#!/usr/bin/env python3
"""verify_gen.py — the per-cell critic-harness generator + the self-heal FOLD/RE-ARM transforms (pure, stdlib).

One home for the JS the planner and the server both need to emit:

  - `gen_cap_verify(exports, acceptance)` — the per-cell `verify.mjs` gate: assert the declared exports exist and
    that the planner's BEHAVIORAL acceptance (boolean JS expressions over the exports) holds. The worker reads it,
    authors code to pass it, and is gate-denied from writing it; validate.py mints the signal from its exit status.
    (Moved here from the cold-start planner so the runtime server can regenerate it during self-heal — ONE source.)

  - `fold(spec)` — the self-heal transform for a caught false pass (the "full self-heal + new oracle" decision):
    the refuter's hidden checks are FOLDED into the gate (acceptance ∪ refute → the strengthened gate enforces
    exactly what was failing), and a FRESH independent refuter is generated so the cell stays measurable. Returns
    the new verify.mjs, the new refuter harness, and the new spec — pure; the caller writes them + stales the cell.

A cell's verify-spec (`coordination/verify-spec/<cell>.json` = {exports, acceptance, refute, generation, history})
is the regeneration substrate: without it the generated harnesses are opaque JS that can't be folded.

Python 3.8+, stdlib only. No kernel imports — pure generation; orchestration (stale/propagate/write) is the server's.
"""
import json


def gen_cap_verify(exports, acceptance=None):
    """A REAL critic harness from the planner's contract: the worker's code must (1) export the declared API,
    (2) load without throwing, and (3) pass the BEHAVIORAL acceptance — executable boolean expressions over the
    exports that EXERCISE the logic ("createDeck().length === 52"), not just check shape. Representative, not
    exhaustive: passing should imply general correctness; a stub can't."""
    exports = [e for e in (exports or []) if isinstance(e, str) and e.strip()]
    accept = [a for a in (acceptance or []) if isinstance(a, str) and a.strip()]
    req = ", ".join(json.dumps(e) for e in exports)
    acc_arr = ", ".join(json.dumps(a) for a in accept)
    return (
        "// per-cell critic harness — API surface + BEHAVIORAL acceptance. The planner declares the contract;\n"
        "// the worker authors code that satisfies it and is gate-denied from writing this file.\n"
        "import * as m from './index.mjs';\n"
        f"const required = [{req}];\n"
        "const missing = required.filter((e) => !(e in m));\n"
        "if (missing.length) { console.error('FAIL: index.mjs missing exports: ' + missing.join(', ')); process.exit(1); }\n"
        "const notDefined = required.filter((e) => typeof m[e] === 'undefined');\n"
        "if (notDefined.length) { console.error('FAIL: undefined exports: ' + notDefined.join(', ')); process.exit(1); }\n"
        f"const ACCEPT = [{acc_arr}];\n"
        "const names = Object.keys(m);\n"
        "const failed = [];\n"
        "for (const a of ACCEPT) {\n"
        "  try {\n"
        "    const fn = new Function(...names, 'return (' + a + ');');\n"
        "    if (!fn(...names.map((n) => m[n]))) failed.push(a);\n"
        "  } catch (e) { failed.push(a + '  (threw: ' + (e && e.message) + ')'); }\n"
        "}\n"
        "if (failed.length) { console.error('FAIL: behavioral acceptance not met:\\n  ' + failed.join('\\n  ')); process.exit(1); }\n"
        "console.log('pass: API surface (' + required.length + ') + ' + ACCEPT.length + ' behavioral assertion(s)'); process.exit(0);\n"
    )


def new_spec(exports, acceptance, refute):
    """The cell's verify-spec at cold-start. `generation` counts self-heal cycles; `history` records each fold."""
    return {
        "exports": [e for e in (exports or []) if isinstance(e, str)],
        "acceptance": [a for a in (acceptance or []) if isinstance(a, str)],
        "refute": [r for r in (refute or []) if isinstance(r, str)],
        "generation": 0,
        "history": [],
    }


def fresh_refute(exports, folded, generation):
    """Generate a generic LIVENESS floor over the exports — NOT a false-pass measurement (harness-council).

    HONEST SCOPE (corrected): these invariants are export-PRESENCE / self-stability probes (`typeof e === 'function'`,
    `JSON.stringify(e) === JSON.stringify(e)`). They do NOT invoke the export, so they are TAUTOLOGICAL for any module
    that already passed its gate (the gate already exits on an undefined export) — they cannot DISAGREE, so a refuter
    built only from them must NOT mint a measured false-pass rate (`is_behavioral` returns False → the dev-server arms
    it as a non-measuring liveness check that still catches a module that throws on load). A real MEASURING refuter
    needs behavioral assertions on inputs the gate did not use — planner/operator-authored, see dispatch.produce_refuter
    + the verify-spec `refute` set. Returns [] when there is nothing left to probe (escalate rather than churn)."""
    fns = [e for e in (exports or []) if isinstance(e, str) and e.strip()]
    if not fns:
        return []
    folded = set(folded or [])
    # a rotating menu of liveness probes, so successive re-arms differ generation-to-generation
    menu = []
    for e in fns:
        menu.append(f"typeof {e} === 'function' || {e} !== undefined")                 # export is real (loads)
        menu.append(f"(() => {{ try {{ return JSON.stringify({e}) === JSON.stringify({e}); }} catch (_) {{ return true; }} }})()")  # serializable w/o throwing
    # rotate the menu by generation so each fresh floor is a different slice
    rotated = menu[generation % len(menu):] + menu[:generation % len(menu)]
    out = [c for c in rotated if c not in folded][:3]
    return out


def is_behavioral(assertions, exports):
    """True iff some assertion INVOKES a declared export as a function (`compute(7, 8) === 15`, `deal()[0] !== deal()[1]`,
    `m.deal(3).length === 52`) — exercising the module's BEHAVIOR, not merely probing presence (`typeof x`,
    `x !== undefined`, `JSON.stringify(x) === JSON.stringify(x)`). A refuter built only from non-behavioral invariants
    CANNOT disagree with any module that already passed its gate, so it must NOT count as a false-pass MEASUREMENT
    (harness-council: the tautological refuter that auto-granted Tier 2). Drives the measuring/non-measuring split."""
    names = [e for e in (exports or []) if isinstance(e, str) and e.strip()]
    for a in (assertions or []):
        if not isinstance(a, str):
            continue
        for e in names:
            i = a.find(e + "(")
            while i >= 0:
                before = a[i - 1] if i > 0 else " "
                if not (before.isalnum() or before == "_"):   # a real `e(` call at a word boundary, not `xe(`
                    return True
                i = a.find(e + "(", i + 1)
    return False


def fold(spec):
    """The self-heal transform: fold the refuter into the gate + re-arm a fresh refuter. PURE — returns
    (verify_js, refuter_harness, new_spec, folded_count). The caller writes verify.mjs, the refuter sidecar, and
    the spec, then stales the cell. `verify_js is None` means nothing to fold (no refute set) — caller skips.
    `refuter_harness is None` means the oracle is EXHAUSTED (no fresh checks left) — caller should block + escalate
    rather than re-arm, so the loop can't churn forever (the bounded backstop the decision requires)."""
    exports = [e for e in (spec.get("exports") or []) if isinstance(e, str)]
    acceptance = [a for a in (spec.get("acceptance") or []) if isinstance(a, str)]
    refute = [r for r in (spec.get("refute") or []) if isinstance(r, str)]
    if not refute:
        return None, None, spec, 0
    gen = int(spec.get("generation", 0)) + 1
    folded_acceptance = acceptance + [r for r in refute if r not in acceptance]   # ∪, order-stable
    fresh = fresh_refute(exports, folded_acceptance, gen)
    out_spec = {
        "exports": exports,
        "acceptance": folded_acceptance,
        "refute": fresh,
        "generation": gen,
        "history": list(spec.get("history") or []) + [{"generation": gen, "folded": refute, "rearmed": fresh}],
    }
    verify_js = gen_cap_verify(exports, folded_acceptance)
    refuter_harness = gen_cap_verify(exports, fresh) if fresh else None
    return verify_js, refuter_harness, out_spec, len(refute)


def selftest():
    fails = []
    # gen_cap_verify shape
    js = gen_cap_verify(["a", "b"], ["a() === 1"])
    if "required = [\"a\", \"b\"]" not in js or "a() === 1" not in js:
        fails.append("gen_cap_verify did not embed exports/acceptance")
    # fold: refute moves into the gate, a fresh (different) refuter is armed, generation++
    spec = new_spec(["deal"], ["deal().length === 52"], ["deal()[0] !== deal()[1]"])
    v, h, s2, n = fold(spec)
    if n != 1:
        fails.append(f"fold reported {n} folded, expected 1")
    if "deal()[0] !== deal()[1]" not in (v or ""):
        fails.append("fold did NOT strengthen the gate with the refute check")
    if s2["acceptance"] != ["deal().length === 52", "deal()[0] !== deal()[1]"]:
        fails.append(f"fold acceptance wrong: {s2['acceptance']}")
    if s2["generation"] != 1 or not s2["history"]:
        fails.append("fold did not bump generation / record history")
    if h is None or "ACCEPT" not in h:
        fails.append("fold did not re-arm a fresh refuter harness")
    if set(s2["refute"]) & set(spec["refute"]):
        fails.append("fresh refuter REUSES the consumed (folded) checks — not independent")
    # fold with no refute → nothing to fold
    v0, h0, _, n0 = fold(new_spec(["x"], ["x===1"], []))
    if v0 is not None or n0 != 0:
        fails.append("fold with empty refute should be a no-op")
    # oracle exhaustion → refuter_harness None (escalate, don't churn) when exports give no fresh checks
    vE, hE, _, _ = fold(new_spec([], [], ["1===1"]))
    if hE is not None:
        fails.append("fold with no exports should EXHAUST the oracle (None harness → escalate)")
    # is_behavioral: the measuring/non-measuring split — an assertion that INVOKES an export is behavioral; the
    # generic fresh_refute floor (typeof / JSON.stringify, no call) is NOT (it cannot disagree → must not measure)
    if not is_behavioral(["compute(7, 8) === 15"], ["compute"]):
        fails.append("is_behavioral missed an export INVOCATION (compute(7,8))")
    if not is_behavioral(["deal()[0] !== deal()[1]"], ["deal"]):
        fails.append("is_behavioral missed a no-arg export invocation (deal())")
    if is_behavioral(fresh_refute(["compute"], [], 0), ["compute"]):
        fails.append("is_behavioral wrongly flagged the generic fresh_refute floor as behavioral (it must be non-measuring)")
    if is_behavioral(["typeof compute === 'function'", "compute !== undefined"], ["compute"]):
        fails.append("is_behavioral wrongly flagged a presence probe as behavioral")
    if is_behavioral(["xcompute(1) === 1"], ["compute"]):
        fails.append("is_behavioral matched a non-word-boundary substring (xcompute vs compute)")
    if fails:
        import sys
        sys.stderr.write("verify_gen selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("verify_gen selftest: OK (gate generation; fold strengthens the gate + re-arms an independent fresh refuter; exhaustion escalates)")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if (len(sys.argv) > 1 and sys.argv[1] == "selftest") else selftest())
