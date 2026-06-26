#!/usr/bin/env python3
"""_gates.py — shared machinery for dev-factory's protective PreToolUse gates (private lib).

The immutable/rewritable boundary (TDD §14.1) is realized by hooks that DENY a worker's write to
verifier assets — not by a sentence in a doc. Published reward-hacking rates run to double-digit
percentages of rollouts; the first and strongest defense is mechanical: signals, rubrics, the ledger,
the hooks, and the kernel schemas are deny-on-write to worker agents, so a worker cannot grade its own
homework or rewrite the audit trail. This module carries the protected-path matching, the PreToolUse
payload parsing, and the deny mechanism the four gate scripts (gate-signal / gate-verifier / gate-ledger
/ gate-naming) share.

These gates are NEVER bundled as a plugin PreToolUse hook (that would block a shared session — the
integration-contract law). They are CONSENT-WIRED into the user's autonomous worker loop / each worker
worktree by the server's wiring, where a non-zero exit denies the write.

Stdlib only; Python 3.8+.
"""
import fnmatch
import json
import os
import sys

# The factory STATE namespace, project-relative. An instance lives at `src/{project}/.factory/`, so the
# protected machinery is `.factory`-anchored — the is_protected() anchor-tail logic matches the segment
# regardless of which `src/{project}/` prefixes it (one boundary protects every project's instance).
NS = ".factory"

# The immutable side of the boundary (§14.1), path-segment-anchored. `signals/` is THE reward-hack
# defense; the ledger is append-only audit; the wiring (.claude/settings.json) is protected so a wired
# worker cannot unwire its own gate.
SIGNALS = [f"{NS}/signals/*"]
VERIFIER = [
    f"{NS}/signals/*",
    f"{NS}/rubric/*",
    f"{NS}/hooks/*",
    f"{NS}/run/*",
    "*/verify.mjs",            # a cell's per-cell critic harness, now BESIDE its product source
                               # (src/{project}/{slug}/verify.mjs) — the gate a worker authors code to PASS
                               # but must never write (else it grades its own homework). `verify.mjs` is a
                               # reserved critic-harness basename, so protect it wherever it lives.
    f"{NS}/coordination/refuters/*",  # the HIDDEN independent refuter (false-pass oracle) — a worker must not be
    f"{NS}/coordination/verify-spec/*",  # the verify-spec (exports/acceptance/refute) the gate + self-heal fold derive from
    f"{NS}/coordination/triage/*",  # the ticket-triager's PROPOSAL (target_cell/transition/rubric) — a plain worker
                               # cannot write it (only the gate-blind triage-author may, via TRIAGE_AUTHOR); the
                               # server reads it and applies via api.triage_issue (judgment proposes; the gate decides)
    f"{NS}/lattice.json",       # able to forge/disable it
    f"{NS}/*.schema.json",
    ".claude/settings.json",
]
LEDGER = [f"{NS}/ledger/*", f"{NS}/coordination/index.jsonl"]

# The RUBRIC-ARCHITECT's boundary: everything VERIFIER protects EXCEPT `*/verify.mjs`, PLUS the product barrel
# (`*/index.mjs`). The verifier-author (the critic side) MUST write a cell's verify.mjs — it is authoring the
# gate — but must still NOT forge signals, rewrite the lattice/ledger/rubric, unwire its hooks, OR author the
# product barrel the critic imports (`./index.mjs`): denying the barrel means one verifier-author dispatch
# cannot author BOTH the gate and a module that trivially passes it (harness-council H3-C2 — the permit was
# barred only by the prompt, not the gate). The separate module worker (VERIFIER scope) still writes index.mjs.
VERIFIER_AUTHOR = [g for g in VERIFIER if g != "*/verify.mjs"] + ["*/index.mjs"]

# The REFUTE-AUTHOR's boundary: everything VERIFIER protects EXCEPT the verify-spec (`coordination/verify-spec/*`),
# PLUS the product barrel (`*/index.mjs`). The autonomous refute-author (the path to autonomously-earned Tier 2)
# writes ONE thing — the verify-spec's `refute` set (the behavioral oracle the server's produce_refuter calibrates) —
# and must NOT: forge signals, rewrite the lattice/ledger/rubric, unwire its hooks, write the GATE it is meant to be
# independent of (`*/verify.mjs` stays denied — authoring the gate would let it tune the gate to its refute), drop a
# refuter sidecar directly (`coordination/refuters/*` stays denied — the server PRODUCES that, post-calibration), OR
# author the product barrel the refuter imports (`*/index.mjs` — so one dispatch can't author both an oracle and a
# module that trivially passes it). The asymmetry with VERIFIER_AUTHOR: the verifier-author may write verify.mjs and
# is denied verify-spec; the refute-author is the inverse — may write verify-spec and is denied verify.mjs.
REFUTE_AUTHOR = [g for g in VERIFIER if g != f"{NS}/coordination/verify-spec/*"] + ["*/index.mjs"]

# The TRIAGE-AUTHOR's boundary: everything VERIFIER protects EXCEPT the triage proposals dir
# (`coordination/triage/*`). The autonomous ticket-triager (the producer that turns a free-text prompt into a
# bound, dispatchable ticket without a human) writes ONE thing — its PROPOSAL
# (`coordination/triage/<tid>.json`: target_cell + a legal transition + a validated rubric_cell) — which the
# single-writer server reads and applies via api.triage_issue, then `gate-ticket-ready` decides legality. It
# must NOT: forge signals, rewrite the lattice/ledger/rubric, unwire its hooks, write any verify.mjs/verify-spec
# or refuter (the verification surface it has no business near), touch the run/ budget+posture perimeter, OR author
# the product barrel (`*/index.mjs`, denied like VERIFIER_AUTHOR/REFUTE_AUTHOR so one triage dispatch can't also plant
# product code in the live tree). So the triage-author is pure JUDGMENT with ZERO authority over state — it proposes;
# the gate disposes. The only surface it may write is its own proposal under `coordination/triage/*`.
TRIAGE_AUTHOR = [g for g in VERIFIER if g != f"{NS}/coordination/triage/*"] + ["*/index.mjs"]


def _kit_roots():
    """The bound KIT source tree(s), RAW as the worker references them — the verifier SUBSTRATE (gate scripts in
    bin/, the rubrics + their calibration exemplars, kit.json, the schemas) a worker READS to RUN its gates but
    must never WRITE. From DEV_FACTORY_KIT, the same env that gates the worker's `--add-dir <kit>` (dispatch) — so
    this deny is active exactly when the kit is reachable, and absent (harmlessly) when no kit is bound. Raw (not
    realpath'd) so command substring matching sees the path as the worker wrote it; _under_kit realpaths for
    containment. May be os.pathsep-joined."""
    raw = os.environ.get("DEV_FACTORY_KIT") or ""
    return [k for k in raw.split(os.pathsep) if k.strip()]


def _under_kit(path):
    """True iff a write target resolves INSIDE a bound kit tree. The kit is `--add-dir`'d to the worker for READ
    (DF-4: run the real gate, don't self-attest) under `acceptEdits`, but no worker authors the kit — so a write
    there is a worker filing the teeth off its own verifier (rubric-check.py / the gate scripts / the exemplars).
    Resolved against cwd (the worker runs in project_root); both sides realpath'd so a symlinked root matches."""
    if not path:
        return False
    ap = os.path.realpath(path if os.path.isabs(path) else os.path.join(os.getcwd(), path))
    for root in _kit_roots():
        try:
            rroot = os.path.realpath(root)
            if os.path.commonpath([rroot, ap]) == rroot:
                return True
        except ValueError:        # different drives / mixed abs+rel
            continue
    return False


def is_protected(path, globs):
    """True if `path` matches a protected glob at a path-segment boundary (root-relative or after any
    `/`) — never on a bare basename, so a user's own docs/lattice.json stays writable."""
    if not path:
        return False
    p = path.replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    # normalize an absolute path that contains the namespace to its repo-relative tail
    for glob in globs:
        anchor = glob.split("/")[0]
        idx = p.find(anchor + "/") if anchor.endswith("*") is False else -1
        cand = p
        if (anchor + "/") in p:
            cand = p[p.index(anchor + "/"):]
        if fnmatch.fnmatch(cand, glob) or fnmatch.fnmatch(p, glob) or fnmatch.fnmatch(p, "*/" + glob):
            return True
    return False


def read_payload():
    """Parse a PreToolUse hook payload from stdin. Returns (tool_name, path, command). On an UNPARSEABLE
    payload returns (None, None, None) — `tool is None` is the parse-failure sentinel callers MUST treat as
    fail-CLOSED (deny): a malformed payload is the one case where the gate is blind to the write target, so
    it must never allow. (A successfully parsed payload always yields a string tool, possibly "".)"""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None, None, None
    tool = data.get("tool_name") or data.get("tool") or ""
    ti = data.get("tool_input") or data.get("toolInput") or {}
    path = ti.get("file_path") or ti.get("path") or ti.get("notebook_path") or ""
    command = ti.get("command") or ""
    return tool, path, command


def deny(reason):
    """Emit the PreToolUse deny, maximally compatible across hook regimes: the structured JSON decision
    on stdout (the form current headless Claude reads — verified against the June-2026 docs) AND exit 2
    with the reason on stderr (the exit-code convention the catalog gates + selftests use). A worker's
    protected write is blocked under either runtime."""
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                              "permissionDecision": "deny", "permissionDecisionReason": reason}}))
    sys.stderr.write(reason + "\n")
    return 2


# Bash verbs that MUTATE a file. The redirect heuristic is BEST-EFFORT defense-in-depth — robust shell
# analysis is undecidable, so the real floor is that the looping worker (cell-advancer) carries no Bash tool
# at all (frontmatter tool-scope). This list is deliberately the genuine file-MUTATING verbs only: it does
# NOT include interpreter flags like `-c`/`-e`, which over-match legitimate READS a Bash-carrying agent
# (cell-validator shelling a verifier) runs over protected paths — e.g. `python3 -c 'open("…/lattice.json").read()'`
# or `grep -e validated …/signals/…`. A false-deny on the validator's reads is worse than the residual
# inline-interpreter-write evasion, which the no-Bash tool-scope on the *forging* worker already closes.
_BASH_WRITE_VERBS = (">", "tee ", "rm ", "cp ", "mv ", "dd ", "sed -i", "install ", "truncate", "ln ")


def path_gate_verdict(tool, path, command, globs, what):
    """Pure verdict for a protected-path gate: returns (allow: bool, reason: str|None). Separated from
    stdin/emission so the selftest can prove the fail-closed + Bash-evasion behavior without a subprocess.
    Fails CLOSED on an unparseable payload (`tool is None`) — the gate must never allow a write it cannot
    inspect."""
    if tool is None:
        return False, "unparseable PreToolUse payload; failing closed (the gate cannot verify the write target, so it must not allow)"
    # The bound KIT is read-only to every worker boundary (it RUNS the gates, never edits them) — checked first +
    # universally, so a worker cannot neuter rubric-check.py / a gate script / an exemplar manifest to forge a pass.
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit") and _under_kit(path):
        return False, (f"{path} is inside the bound KIT verifier substrate (gate scripts, rubrics, calibration "
                       f"exemplars, schemas). The kit is read-only to a worker — it runs the gates, never edits them")
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit") and is_protected(path, globs):
        return False, (f"{path} is a protected {what} (immutable boundary). "
                       f"Only the validation path / single-writer server may write it")
    if tool == "Bash" and command:
        for root in _kit_roots():
            if root in command and any(v in command for v in _BASH_WRITE_VERBS):
                return False, f"shell command writes inside the bound KIT ({root}) — the verifier substrate is read-only"
        for g in globs:
            base = g.replace("/*", "").replace("*", "")
            if base and base in command and any(v in command for v in _BASH_WRITE_VERBS):
                return False, f"shell command touches protected {what} ({base})"
    return True, None


def run_path_gate(name, globs, argv, what):
    """The standard --hook / check / selftest dispatch for a protected-path gate."""
    if argv and argv[0] == "selftest":
        return _selftest_path_gate(name, globs, what)
    if argv and argv[0] == "--hook":
        tool, path, command = read_payload()
        allow, reason = path_gate_verdict(tool, path, command, globs, what)
        return 0 if allow else deny(f"{name}: DENIED — {reason}.")
    if argv and argv[0] == "check":
        path = argv[1] if len(argv) > 1 else ""
        return 1 if is_protected(path, globs) else 0
    sys.stderr.write(f"usage: {name} --hook | check <path> | selftest\n")
    return 2


def _selftest_path_gate(name, globs, what):
    fails = []
    # a protected path is caught; a sibling user path is not
    protected_example = globs[0].replace("/*", "/x.json").replace("*.schema.json", "cell.schema.json")
    if not is_protected(protected_example, globs):
        fails.append(f"missed a protected {what}: {protected_example}")
    if is_protected("src/app/main.ts", globs):
        fails.append("false-positive on a user source path")
    if is_protected("docs/examples/lattice.json", globs) and "lattice.json" not in name:
        # docs/examples/lattice.json must NOT be protected (only the real .agents/.../lattice.json is)
        fails.append("false-positive on a user doc that merely shares a basename")
    # fail-CLOSED on a malformed payload (the gate is blind to the target → must deny, never allow)
    if path_gate_verdict(None, None, None, globs, what)[0]:
        fails.append("FAIL-OPEN on an unparseable payload (must fail closed)")
    # a well-formed non-write tool (Read) on a protected path is still allowed (no false-deny)
    if not path_gate_verdict("Read", protected_example, "", globs, what)[0]:
        fails.append("false-deny on a Read of a protected path")
    # a Bash evasion (cp/mv/sed -i) that mutates a protected path is caught (not just >/tee/rm)
    base0 = globs[0].replace("/*", "").replace("*", "")
    if base0 and path_gate_verdict("Bash", None, f"cp /tmp/forged {base0}x", globs, what)[0]:
        fails.append("Bash cp-evasion into a protected path was allowed")
    # but a legitimate READ of a protected path via an interpreter flag is NOT a write — must be allowed
    if base0 and not path_gate_verdict("Bash", None, f"python3 -c 'open(\"{base0}x\").read()'", globs, what)[0]:
        fails.append(f"false-deny on a Bash READ of a protected path ({base0}x)")
    if base0 and not path_gate_verdict("Bash", None, f"grep -e validated {base0}x", globs, what)[0]:
        fails.append("false-deny on a `grep -e` read of a protected path")
    # boundary ASYMMETRY — verify.mjs (the gate) vs the verify-spec (the oracle source). The verifier-author and the
    # refute-author are inverses: each may write exactly ONE of the two and is denied the other; a plain worker is
    # denied both. (Identity compares against the module-level glob lists, which are passed by reference.)
    vmjs, vspec, barrel = "src/p/x/verify.mjs", f"{NS}/coordination/verify-spec/cap.json", "src/p/x/index.mjs"
    refsc, sig = f"{NS}/coordination/refuters/cap.json", f"{NS}/signals/x.json"
    triage = f"{NS}/coordination/triage/iss-7.json"
    if globs is VERIFIER and not (is_protected(vmjs, globs) and is_protected(vspec, globs) and is_protected(triage, globs)):
        fails.append("VERIFIER must deny verify.mjs, the verify-spec, AND the triage proposal to a plain worker")
    if globs is TRIAGE_AUTHOR:
        if is_protected(triage, globs):
            fails.append("TRIAGE_AUTHOR must ALLOW the triage proposal (coordination/triage/*) — it writes only that")
        if not (is_protected(vmjs, globs) and is_protected(vspec, globs) and is_protected(refsc, globs)
                and is_protected(sig, globs) and is_protected(f"{NS}/run/heartbeat.json", globs)
                and is_protected(f"{NS}/lattice.json", globs) and is_protected(barrel, globs)):
            fails.append("TRIAGE_AUTHOR must still deny verify.mjs/verify-spec/refuters/signals/run/lattice/barrel (zero authority over state)")
    if globs is VERIFIER_AUTHOR:
        if is_protected(vmjs, globs) or not is_protected(vspec, globs):
            fails.append("VERIFIER_AUTHOR must ALLOW verify.mjs and DENY the verify-spec (it writes the gate, not the oracle source)")
        if not is_protected(barrel, globs):
            fails.append("VERIFIER_AUTHOR must deny the product barrel index.mjs (no authoring both the gate and a passing module)")
    if globs is REFUTE_AUTHOR:
        if not is_protected(vmjs, globs) or is_protected(vspec, globs):
            fails.append("REFUTE_AUTHOR must ALLOW the verify-spec and DENY verify.mjs (it writes the oracle source, never the gate)")
        if not (is_protected(barrel, globs) and is_protected(refsc, globs) and is_protected(sig, globs)):
            fails.append("REFUTE_AUTHOR must still deny the barrel, the refuter sidecars, and signals")
    # the bound KIT is read-only to a worker — a write under DEV_FACTORY_KIT is denied (the verifier substrate
    # can't be tampered to forge a pass), while a write OUTSIDE it (and with no kit bound) is unaffected.
    import tempfile
    saved_kit = os.environ.get("DEV_FACTORY_KIT")
    try:
        with tempfile.TemporaryDirectory() as kit:
            os.environ["DEV_FACTORY_KIT"] = kit
            if path_gate_verdict("Edit", os.path.join(kit, "bin", "rubric-check.py"), "", globs, what)[0]:
                fails.append("a worker Edit INSIDE the bound kit (a verifier script) was allowed — the kit must be read-only")
            if path_gate_verdict("Bash", None, f"sed -i s/x/y/ {os.path.join(kit, 'bin', 'g.py')}", globs, what)[0]:
                fails.append("a Bash write inside the bound kit was allowed")
            if not path_gate_verdict("Edit", os.path.join(os.path.dirname(kit), "outside.py"), "", globs, what)[0] \
                    and not is_protected(os.path.join(os.path.dirname(kit), "outside.py"), globs):
                fails.append("a write OUTSIDE the kit (and not otherwise protected) was wrongly denied as kit")
        os.environ.pop("DEV_FACTORY_KIT", None)
        if not path_gate_verdict("Edit", "/some/plugin/bin/x.py", "", globs, what)[0] \
                and not is_protected("/some/plugin/bin/x.py", globs):
            fails.append("with NO kit bound, a non-protected path was wrongly denied (kit deny must be inert)")
    finally:
        if saved_kit is None:
            os.environ.pop("DEV_FACTORY_KIT", None)
        else:
            os.environ["DEV_FACTORY_KIT"] = saved_kit

    if fails:
        sys.stderr.write(f"{name} selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print(f"{name} selftest: OK (denies a worker write to a protected {what} AND to the bound kit verifier substrate; "
          "leaves user paths writable)")
    return 0
