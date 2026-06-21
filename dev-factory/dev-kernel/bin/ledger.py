#!/usr/bin/env python3
"""ledger.py — dev-factory's append-only provenance ledger (the event-sourced spine).

The ledger is the SOURCE OF TRUTH for every state transition (harness-and-storage.md): git-native
JSONL at `.factory/ledger/events.jsonl`, append-only, never mutated. Current operational
state — ticket lifecycle, cell maturity, leases, metrics, the grid — is a materialized *fold* over
this log; the SQLite index the server keeps is downstream and rebuildable by replay. Provenance
cannot be retrofitted, so the ledger is authoritative and the database is never ahead of it.

This module is dev-native (the coordination event vocabulary — dispatch/claim/transition/signal/
block/demote/... — is dev-factory's; the vendored harness-forge kernel carries a different one). It
borrows harness-forge's proven discipline: append via a single path, no-progress as a failure-loop
detector in code, and false-pass returning `unmeasured` (not a misleading 0.0%) until an independent
refuter exists — autonomy is earned by a measured rate, never asserted.

Usage:
  ledger.py append --dir DIR --event E --actor-kind K --actor-id ID [--ticket T] [--cell C] \
            [--from S] [--to S] --rationale "why"
  ledger.py read   --dir DIR [--cell C] [--ticket T] [--event E] [--since ISO]
  ledger.py tail   --dir DIR [-n N]
  ledger.py no-progress --dir DIR --cell C [-n 3]      # exit 0 if a no-progress loop is detected
  ledger.py selftest
Stdlib only; Python 3.8+.
"""
import datetime
import hashlib
import json
import os
import sys
import time

_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EVENTS = ["dispatch", "claim", "transition", "signal", "block", "unblock",
          "demote", "promote", "regenerate", "stale-propagated", "cancel", "incident",
          "activity-start", "handoff", "activity-complete", "activity-fail"]
ACTOR_KINDS = ["human", "server", "agent"]

# Crockford base32, ULID alphabet (excludes I, L, O, U).
_B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ulid(prefix=""):
    """A lexicographically-sortable ULID: 48-bit ms timestamp + 80 bits randomness, Crockford base32."""
    ms = int(time.time() * 1000)
    rnd = int.from_bytes(os.urandom(10), "big")
    n = (ms << 80) | rnd
    out = []
    for _ in range(26):
        out.append(_B32[n & 31])
        n >>= 5
    body = "".join(reversed(out))
    return f"{prefix}{body}" if prefix else body


def _path(d):
    return os.path.join(d, "ledger", "events.jsonl")


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def _chain_hash(prev_h, entry):
    """Each entry binds the previous via a hash of (prev_hash + the entry body). A tampered or reordered
    entry breaks every hash after it — the tamper-evident audit trail Tier 3 lights-out requires."""
    body = json.dumps(entry, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256((prev_h + body).encode("utf-8")).hexdigest()[:16]


def _last_hash(d):
    if not os.path.isfile(_path(d)):
        return ""
    last = ""
    for line in open(_path(d), encoding="utf-8"):
        if line.strip():
            try:
                last = json.loads(line).get("h", "")
            except json.JSONDecodeError:
                pass
    return last


def verify_chain(d):
    """Re-walk the ledger, recomputing each entry's chain hash. Returns (ok, broken_at_line|None). The
    derived input for autonomy's tamper_evident: an edited, reordered, or truncated history is detectable."""
    p = _path(d)
    if not os.path.isfile(p):
        return True, None
    prev_h = ""
    for i, line in enumerate((l for l in open(p, encoding="utf-8")), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            return False, i
        body = {k: v for k, v in e.items() if k != "h"}
        if _chain_hash(prev_h, body) != e.get("h"):
            return False, i
        prev_h = e.get("h")
    return True, None


def append(d, event, actor, subject, rationale, frm=None, to=None, hashes=None, metrics=None, ts=None):
    """Append one entry. Returns its ledger ref (the 1-based line number as 'ledger:N'). The ONLY writer
    of the ledger file; every state change in dev-factory terminates here — no silent work."""
    if event not in EVENTS:
        raise ValueError(f"unknown event: {event} (not in {EVENTS})")
    if not isinstance(actor, dict) or actor.get("kind") not in ACTOR_KINDS or not actor.get("id"):
        raise ValueError("actor must be {kind: human|server|agent, id}; tool output is never an actor")
    if not rationale or not str(rationale).strip():
        raise ValueError("rationale is required — a record without a why is useless for regeneration")
    if not (subject.get("ticket") or subject.get("cell")):
        raise ValueError("subject must name at least one of ticket/cell")
    entry = {"ts": ts or _now(), "event": event, "actor": actor, "subject": subject, "rationale": rationale}
    if frm is not None:
        entry["from"] = frm
    if to is not None:
        entry["to"] = to
    if hashes:
        entry["hashes"] = hashes
    if metrics:
        entry["metrics"] = metrics
    os.makedirs(os.path.dirname(_path(d)), exist_ok=True)
    entry["h"] = _chain_hash(_last_hash(d), entry)   # bind the previous entry → a tamper-evident chain
    with open(_path(d), "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    n = sum(1 for _ in open(_path(d), encoding="utf-8"))
    return f"ledger:{n}"


def read(d, cell=None, ticket=None, event=None, since=None):
    p = _path(d)
    if not os.path.isfile(p):
        return []
    out = []
    for line in open(p, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if cell and e.get("subject", {}).get("cell") != cell:
            continue
        if ticket and e.get("subject", {}).get("ticket") != ticket:
            continue
        if event and e.get("event") != event:
            continue
        if since and e.get("ts", "") < since:
            continue
        out.append(e)
    return out


def tail(d, n=20):
    return read(d)[-n:]


def no_progress(d, cell, n=3):
    """A no-progress loop = the last `n` FAILURE events on `cell` carry the SAME signature (the deterministic
    failure-loop detector, in code, not the agent's counting). Only failure events count — an `activity-fail`, a
    fail signal, or a `block`/`→blocked` — so the retry transitions that interleave them (a failed dispatch returns
    the ticket to `active`) cannot mask a genuine repeated failure (which the old all-events tail did). Returns
    (bool, reason)."""
    import re
    def _is_fail(e):
        ev = e.get("event")
        return (ev in ("activity-fail", "block")
                or (ev == "signal" and (e.get("to") == "fail" or (e.get("metrics") or {}).get("result") == "fail"))
                or (ev == "transition" and e.get("to") == "blocked"))
    def _sig(r):
        # normalize INCIDENTAL variance so the same root failure with a different temp path / return code / clock
        # reads as one signature (harness-council H5: error-string variance must not bypass the early block). Strips
        # paths, `exited N`, and clock timestamps ONLY — bare semantic content (e.g. a distinct error name) is kept,
        # so genuinely-different failures still look different and retry to the attempt cap instead of early-blocking.
        r = r or ""
        r = re.sub(r"/[\w.+/-]+", " PATH ", r)          # absolute/relative file paths (temp dirs vary run-to-run)
        r = re.sub(r"\bexited \d+", "exited N", r)       # process return codes
        r = re.sub(r"\b\d{1,2}:\d{2}(:\d{2})?\b", "TS", r)  # clock-ish timestamps
        return " ".join(r.split()).lower()
    # signature = the normalized rationale tail of the FAILURE events; N identical = a stuck loop retrying won't break
    rats = [_sig(e.get("rationale", "")) for e in read(d, cell=cell) if _is_fail(e)][-n:]
    if len(rats) >= n and len(set(rats)) == 1 and rats[0]:
        return True, f"no-progress: last {n} failures on {cell} share one signature"
    return False, "progressing"


def _family_match(e, family):
    return family is None or (e.get("metrics") or {}).get("family") == family


def refuter_checks(d, family=None):
    """Independent re-validations recorded (the denominator of the false-pass rate). Counts ONLY checks EXPLICITLY
    marked `measuring is True` — a real behavioral oracle that ran and could have DISAGREED. Anything else does not
    count: the generic liveness floor (`measuring: false`), AND — critically — a check with NO `measuring` field.
    Absence must mean NON-counting (harness-council re-audit 2: the old `is not False` default let
    `record_refuter_check(agreed=True)` — which runs no oracle — mint a measured 0.0 false-pass and auto-grant Tier 2,
    the exact fake, reachable from the `autonomy refuter` CLI). Fail-CLOSED: a check earns the denominator only by
    proving it measured, never by omission."""
    return [e for e in read(d, event="signal")
            if (e.get("metrics") or {}).get("refuter") and (e.get("metrics") or {}).get("measuring") is True
            and _family_match(e, family)]


def trusted_refuter_checks(d, family=None):
    """Measuring checks from a TRUSTED (non-autonomous) oracle — the denominator that may earn UNATTENDED Tier 2.
    A check whose oracle was AUTONOMOUSLY authored by the refute-author is recorded `autonomous: true`; it still
    MEASURES (it's in `refuter_checks`, so it builds the visible false-pass rate) but it does NOT count here,
    because the current independence calibration is partial for opaque gates — a self-authored oracle must not
    self-promote the loop to lights-out (harness-council round 6, the human-glance gate). A human-vetted or
    server-folded oracle (autonomous absent/false) is trusted. Autonomous provenance is SERVER-stamped into a
    worker-protected sidecar, never a worker claim, so this cannot be dodged by a verify-spec edit."""
    return [e for e in refuter_checks(d, family)
            if (e.get("metrics") or {}).get("autonomous") is not True]


def false_pass_rate(d, family=None):
    """THE canonical false-pass computation — `autonomy.false_pass` delegates here, so the formula the
    autonomy policy docs cite and the formula `tier_for` consumes can never fork again (one source of
    truth). Refuter-disagreements / independent-refuter-checks. Returns 'unmeasured' until at least one
    refuter has re-checked — a 0.0% with no refuter is a LIE that would auto-promote a never-checked family.
    The denominator is independent refuter checks, NOT raw passes: a rate never measured against an
    independent refuter is not a rate the trust ladder may consume."""
    checks = refuter_checks(d, family)
    if not checks:
        return "unmeasured"
    bad = sum(1 for c in checks if (c.get("metrics") or {}).get("agreed") is False)
    return bad / len(checks)


def selftest():
    import tempfile
    fails = []
    def expect(c, m):
        if not c:
            fails.append(m)
    with tempfile.TemporaryDirectory() as d:
        # ulid shape
        u = ulid("tkt-")
        expect(u.startswith("tkt-") and len(u) == 30, f"bad ulid: {u}")
        import re
        expect(re.match(r"^tkt-[0-9A-HJKMNP-TV-Z]{26}$", u) is not None, f"ulid not Crockford-base32: {u}")
        # append requires a rationale + a real actor
        try:
            append(d, "transition", {"kind": "server", "id": "s"}, {"ticket": "tkt-x"}, "")
            expect(False, "empty rationale was accepted")
        except ValueError:
            pass
        try:
            append(d, "transition", {"kind": "toolresult", "id": "x"}, {"ticket": "t"}, "why")
            expect(False, "tool-output actor accepted")
        except ValueError:
            pass
        # a real append + read-back
        ref = append(d, "transition", {"kind": "server", "id": "srv"}, {"ticket": "tkt-1", "cell": "spec.task.x"},
                     "draft->active by triager", frm="draft", to="active")
        expect(ref == "ledger:1", f"first append ref wrong: {ref}")
        got = read(d, ticket="tkt-1")
        expect(len(got) == 1 and got[0]["to"] == "active", "read-back failed")
        # append-only: a second append does not rewrite the first
        append(d, "signal", {"kind": "server", "id": "srv"}, {"cell": "spec.task.x"}, "pass", to="pass")
        expect(len(read(d)) == 2, "second append lost an entry")
        # no-progress detector
        for _ in range(3):
            append(d, "block", {"kind": "server", "id": "srv"}, {"cell": "spec.task.y"}, "verifier failed: 3 type errors")
        np, _r = no_progress(d, "spec.task.y", n=3)
        expect(np, "no-progress loop not detected on 3 identical failure signatures")
        np2, _ = no_progress(d, "spec.task.x", n=3)
        expect(not np2, "no-progress false-positive on a progressing cell")
        # signature normalization (H5): the SAME root failure with a varying temp path / return code reads as one
        # signature (caught), but genuinely DISTINCT errors do not (they retry to the attempt cap, not early-block)
        for p in ("/tmp/run-a/x", "/tmp/run-b/y"):
            append(d, "activity-fail", {"kind": "agent", "id": "w"}, {"cell": "spec.task.norm"},
                   f"worker failed: no artifact (claude exited 1, asset {p} absent)")
        expect(no_progress(d, "spec.task.norm", n=2)[0], "no-progress must NORMALIZE path/exit variance to one signature")
        for i in (1, 2):
            append(d, "activity-fail", {"kind": "agent", "id": "w"}, {"cell": "spec.task.distinct"}, f"distinct failure {i}")
        expect(not no_progress(d, "spec.task.distinct", n=2)[0],
               "no-progress must NOT conflate genuinely distinct errors (they retry to the attempt cap)")
        # false-pass is unmeasured until a refuter incident exists
        expect(false_pass_rate(d) == "unmeasured", "false-pass not 'unmeasured' without a refuter")
        # tamper-evident chain: intact after honest appends; a single edit is detected
        ok_chain, broken = verify_chain(d)
        expect(ok_chain, f"chain should verify after honest appends (broke at line {broken})")
        lines = open(_path(d), encoding="utf-8").readlines()
        e0 = json.loads(lines[0]); e0["rationale"] = "TAMPERED-AFTER-THE-FACT"
        lines[0] = json.dumps(e0, ensure_ascii=False) + "\n"
        open(_path(d), "w", encoding="utf-8").writelines(lines)
        bad_chain, at = verify_chain(d)
        expect(not bad_chain and at == 1, f"a tampered entry was not detected by the chain (verify={bad_chain}, at={at})")
    if fails:
        sys.stderr.write("ledger selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("ledger selftest: OK (ULID shape; rationale + real-actor required; append-only read-back; "
          "no-progress detects an N-identical failure loop; false-pass is 'unmeasured' until a refuter exists)")
    return 0


def _arg(argv, flag, default=None):
    return argv[argv.index(flag) + 1] if flag in argv else default


def main(argv):
    if not argv or argv[0] == "selftest":
        return selftest()
    verb = argv[0]
    d = _arg(argv, "--dir", ".factory")
    if verb == "append":
        actor = {"kind": _arg(argv, "--actor-kind", "server"), "id": _arg(argv, "--actor-id", "server")}
        subject = {}
        if _arg(argv, "--ticket"):
            subject["ticket"] = _arg(argv, "--ticket")
        if _arg(argv, "--cell"):
            subject["cell"] = _arg(argv, "--cell")
        try:
            ref = append(d, _arg(argv, "--event"), actor, subject, _arg(argv, "--rationale", ""),
                         frm=_arg(argv, "--from"), to=_arg(argv, "--to"))
        except ValueError as e:
            print(f"ledger.py: {e}", file=sys.stderr)
            return 2
        print(ref)
        return 0
    if verb == "read":
        for e in read(d, cell=_arg(argv, "--cell"), ticket=_arg(argv, "--ticket"),
                      event=_arg(argv, "--event"), since=_arg(argv, "--since")):
            print(json.dumps(e, ensure_ascii=False))
        return 0
    if verb == "tail":
        for e in tail(d, int(_arg(argv, "-n", "20"))):
            print(json.dumps(e, ensure_ascii=False))
        return 0
    if verb == "no-progress":
        np, reason = no_progress(d, _arg(argv, "--cell"), int(_arg(argv, "-n", "3")))
        print(reason)
        return 0 if np else 1
    if verb == "verify":
        ok, at = verify_chain(d)
        if ok:
            print(f"ledger verify: OK — the tamper-evident hash-chain is intact ({len(read(d))} entries)")
            return 0
        sys.stderr.write(f"ledger verify: TAMPERED — the hash-chain breaks at line {at}\n")
        return 1
    print(f"ledger.py: unknown verb {verb}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
