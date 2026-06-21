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


def _invokes_export(a, names):
    """True if assertion `a` calls a declared export as a function (`compute(`) at a word boundary (not `xcompute(`)."""
    for e in names:
        i = a.find(e + "(")
        while i >= 0:
            before = a[i - 1] if i > 0 else " "
            if not (before.isalnum() or before == "_"):
                return True
            i = a.find(e + "(", i + 1)
    return False


def is_behavioral(assertions, exports):
    """True iff some assertion both INVOKES a declared export AND can actually DISAGREE — it asserts a VALUE, not a
    tautology. Invocation alone is insufficient (harness-council re-audit 2): `compute(1)===compute(1)` (a determinism
    check any deterministic overfit passes) and `typeof compute(0)==='number'` (a shape check, not a value check) both
    invoke `compute` yet cannot disagree with a gate-passing module. So an invoking assertion is rejected when it is a
    trivial tautology — identical operands across `===`/`!==`, or a `typeof` probe. A refute set with no behavioral
    assertion does NOT count as a false-pass measurement (the cell stays honestly `unmeasured` → Tier 1). Over-rejection
    is fail-SAFE: a wrongly-rejected refuter just doesn't earn Tier 2, it never falsely grants it."""
    names = [e for e in (exports or []) if isinstance(e, str) and e.strip()]
    for a in (assertions or []):
        if not isinstance(a, str) or not _invokes_export(a, names):
            continue
        norm = a.strip()
        if "typeof" in norm:                                   # a shape probe, not a value assertion
            continue
        tautology = False
        for op in ("===", "!==", "==", "!="):                  # identical operands → can't disagree (e.g. determinism)
            if op in norm:
                lhs, _, rhs = norm.partition(op)
                if lhs.strip() and lhs.strip() == rhs.strip():
                    tautology = True
                break
        if not tautology:
            return True
    return False


def _norm(s):
    """Whitespace-stripped form for a textual independence test — `add(7, 8) === 15` and `add(7,8)===15` compare
    equal, so a copy can't slip past on reformatting alone."""
    return "".join((s or "").split())


def independent_of_gate(refute, acceptance, exports, gate_src=None):
    """The MEASURING calibration the poison test (`dispatch._refuter_discriminates`) CANNOT supply, and the hole the
    autonomous refute-author opens: a refute set that merely RE-RUNS the gate's own checks still disagrees with a
    random-scalar poison (so it passes discrimination) — yet it can never catch a module that PASSED the gate, because
    it IS the gate. A gate-passing module trivially 'agrees', so `false_pass` is pinned at 0.0 on a measurement that
    measures NOTHING → a false Tier 2. True iff the set carries at least one BEHAVIORAL assertion the gate does NOT
    already enforce — absent from BOTH the gate's structured `acceptance` AND (when supplied) the literal gate SOURCE
    (`gate_src`, whitespace-normalized substring test). That novel check is what lets the refuter catch an overfit the
    gate waved through (H2/H3 — the gate uses (2,3),(10,0); the refute uses (7,8), an input the gate never saw).

    The `gate_src` arm moves part of the independence check SERVER-SIDE, not blindness-dependent: even a refute-author
    that READ verify.mjs (its blindness is only prompt-level — it runs in the project root) cannot mint a measuring
    oracle by copying a gate assertion VERBATIM, because the trusted server rejects any refute string that textually
    appears in the gate — including an opaque gate with no structured `acceptance`. This arm is PARTIAL by nature: it
    catches a positive-form literal copy (`compute(2,3)===5`), not a semantic copy of a negative-form (`if (compute
    (2,3)!==5) exit`) or data-driven (`for ([a,b,w] of [[2,3,5]])`) gate — for those, independence still rests on the
    structured-`acceptance` arm (populated for the gen_cap_verify gates dev-kit-app emits), the author's prompt-level
    blindness, and the OPERATIONAL catch (`run_refuter` → incident → demote a weak oracle that lets an overfit through).
    Over-rejection is fail-SAFE throughout (a wrongly-rejected refuter just doesn't earn Tier 2; it never falsely
    grants it). The remaining residual — a systematically weak oracle for an opaque negative-form gate — is the
    documented limit on fully unattended Tier 2 (see docs; the council adjudicates whether it blocks lights-out)."""
    acc = {_norm(a) for a in (acceptance or []) if isinstance(a, str)}
    gate = _norm(gate_src) if isinstance(gate_src, str) else ""
    for r in (refute or []):
        if not isinstance(r, str) or not is_behavioral([r], exports):
            continue
        nr = _norm(r)
        if nr in acc:
            continue                       # a structured-acceptance copy — the gate already enforces it
        if gate and nr and nr in gate:
            continue                       # a literal gate-SOURCE copy (closes the opaque-gate hole, server-side)
        return True                        # a genuinely novel behavioral check the gate does not contain
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
    # value-free invocations must be REJECTED (re-audit 2): a determinism check (identical operands) and a typeof
    # shape probe both INVOKE the export yet cannot disagree with a gate-passing module
    if is_behavioral(["compute(1, 1) === compute(1, 1)"], ["compute"]):
        fails.append("is_behavioral wrongly accepted a determinism tautology (compute(1,1)===compute(1,1))")
    if is_behavioral(["typeof compute(0) === 'number'"], ["compute"]):
        fails.append("is_behavioral wrongly accepted a typeof shape-probe invocation")
    if not is_behavioral(["compute(7, 8) === compute(8, 7)"], ["compute"]):
        fails.append("is_behavioral rejected a real metamorphic check (commutativity — distinct operands, both invoke)")
    # independent_of_gate: the gate-COPY hole — a refute set that only re-runs the gate's checks must NOT measure
    if independent_of_gate(["compute(2, 3) === 5"], ["compute(2, 3) === 5"], ["compute"]):
        fails.append("independent_of_gate accepted a pure gate-COPY (refute ⊆ acceptance) — it would measure nothing")
    if not independent_of_gate(["compute(2, 3) === 5", "compute(7, 8) === 15"], ["compute(2, 3) === 5"], ["compute"]):
        fails.append("independent_of_gate rejected a set with a NOVEL behavioral check beyond the gate")
    if not independent_of_gate(["compute(7, 8) === 15"], [], ["compute"]):
        fails.append("independent_of_gate must pass when acceptance is empty (opaque gate — partial guard reduces to is_behavioral)")
    # a NOVEL but non-behavioral check does not count — the independence must be a real value assertion, not a probe
    if independent_of_gate(["compute(2, 3) === 5", "typeof compute === 'function'"], ["compute(2, 3) === 5"], ["compute"]):
        fails.append("independent_of_gate counted a novel-but-NON-behavioral probe as independence")
    # the gate-SOURCE arm: acceptance EMPTY but the refute copies a positive-form gate assertion VERBATIM → still
    # rejected (server-enforced, whitespace-normalized), so a refute-author that read the gate can't mint that copy
    POS_GATE = "import * as m from './index.mjs';\nconst ok = (m.compute(2, 3) === 5);\nif (!ok) process.exit(1);\n"
    if independent_of_gate(["compute(2,3) === 5"], [], ["compute"], gate_src=POS_GATE):
        fails.append("independent_of_gate accepted a refute that copies a positive-form gate assertion (acceptance empty)")
    if not independent_of_gate(["compute(7, 8) === 15"], [], ["compute"], gate_src=POS_GATE):
        fails.append("independent_of_gate rejected a genuinely novel check absent from the gate source")
    if fails:
        import sys
        sys.stderr.write("verify_gen selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("verify_gen selftest: OK (gate generation; fold strengthens the gate + re-arms an independent fresh refuter; "
          "exhaustion escalates; independent_of_gate rejects a gate-copy refute set)")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(selftest() if (len(sys.argv) > 1 and sys.argv[1] == "selftest") else selftest())
