#!/usr/bin/env python3
"""check-integration-contract.py — the catalog's plugin INTEGRATION CONTRACT, as a checked property.

Every nonoun-plugins plugin integrates with a host harness (Claude Code) through the five primitives. The
catalog's integration invariants have been held by *convention + author discipline*; this gate mechanizes
the two that no other gate covers, so "a hardened, reliable, token-efficient integration" is **verified**,
not merely disciplined (the gap audit: validate_plugin/context-cost/trust-boundary/mcp-liveness/manifest-sync
already cover layout, the token budget, the trust guard, MCP liveness, and description sync — this gate fills
the rest).

  H · ENTRY/ROUTER THINNESS — a command is a thin typed entry point that ROUTES to a skill/agent/bin/
      references, and never re-contains methodology (the five-primitive law). Mechanized as: the body
      (frontmatter stripped) must (R) route — reference a real skill/agent on disk, a `${CLAUDE_PLUGIN_ROOT}/
      bin/` script, or a `references/` doc — AND (S) stay under the size budget (FAIL ≥ 4000 chars, WARN ≥
      2800). Calibrated on the real catalog: 37 commands, max body 3269; the skills they point at are ≥6993,
      so a re-contained method lands in skill territory and fails. Reinforces context-cost.py's token budget
      at the structural/routing level.

  I · ADVISORY BUNDLED HOOK — a plugin's OWN hooks.json hook must be advisory (it can never DENY a general
      tool call), with ONE exception: a NARROW-PERIMETER state gate. Only a PreToolUse hook can deny, so a
      bundled PreToolUse is deny-capable; it FAILS unless the plugin declares a `stateNamespace` (.factory/ ·
      .agents/) and the gate denies ONLY writes to that perimeter — a kernel-managed verifier substrate no
      human hand-edits — never the operator's real work. That lets a plugin mechanically protect its own
      substrate in-session (app-factory's gate-protect) without being hostile. STATIC: bundled PreToolUse +
      declared namespace → permitted (WARN); + no namespace → FAIL (broad blocking — legal only by consent-
      wiring, harness-forge's wire.py). BEHAVIORAL (--trusted-source, executes plugin code → rides the
      check-mcp-liveness interlock): a PostToolUse hook must exit 0 + emit no block under a finding; a bundled
      PreToolUse gate must ALLOW a general write AND deny a write to its declared namespace (narrow, not broad).

Modes:
  check-integration-contract.py plugin <dir>          # one plugin
  check-integration-contract.py marketplace <dir>     # every plugin in <dir>/.claude-plugin/marketplace.json
  check-integration-contract.py selftest              # prove the gate bites

Exit 0 = pass (WARNs allowed) · 1 = a contract violation · 2 = usage. Stdlib only; Python 3.8+. Clean-checkout-true.
"""
import json
import os
import re
import sys

# H — router thinness
ROUTER_SIZE_FAIL = 4000        # body chars; real catalog max is 3269, the skills they point at are >=6993
ROUTER_SIZE_WARN = 2800        # just above p90 (2711) — the four legitimately-heavy commands land here
_BIN_RE = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/bin/|(?<![\w./-])bin/[\w./-]+")
_REFS_RE = re.compile(r"(?:skills/[a-z0-9-]+/)?references/\S+")
_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)

# I — advisory hook (structural): only PreToolUse can DENY a tool call, so a bundled PreToolUse is blocking —
# EXCEPT a NARROW-PERIMETER state gate: one that denies only writes to the plugin's DECLARED stateNamespace
# (.factory/ · .agents/ — a kernel-managed perimeter no human hand-edits) and never blocks a general tool call.
# That is permitted (a plugin can mechanically protect its own verifier substrate in-session); its narrowness is
# proven behaviorally (--trusted-source: allows a general write, denies a namespace write). A bundled PreToolUse
# with NO declared namespace, or one that blocks general work, is broad blocking and still FAILS.
DENYING_EVENTS = {"PreToolUse"}
# The durable-state umbrellas a stateNamespace may sit under (distinct from the .claude/ config namespace).
_STATE_ROOTS = (".agents/", ".factory/")


def _declared_namespace(plugin_dir):
    """The plugin's declared `stateNamespace` (a non-empty string), else None."""
    pj = os.path.join(plugin_dir, ".claude-plugin", "plugin.json")
    try:
        ns = json.load(open(pj, encoding="utf-8")).get("stateNamespace")
    except (OSError, json.JSONDecodeError):
        return None
    return ns if isinstance(ns, str) and ns else None

# I — advisory hook (BEHAVIORAL): execute each --hook on finding-triggering input; it must exit 0 AND emit no
# block/deny decision. Executes plugin code, so it rides the I-12 exec interlock (the check-mcp-liveness pattern).
TRUST_FLAG = "--trusted-source"
TRUST_ENV = "PLUGINS_FACTORY_TRUST_EXEC"
_BLOCK_RE = re.compile(r'"(?:decision|permissionDecision)"\s*:\s*"(?:block|deny)"|"continue"\s*:\s*false')
# per-plugin worst-case fixture: (filename, content, file_path_override). Each hook reads differently — content,
# disk, or just the path string — so one payload can't trigger a finding in all; an unknown plugin gets the generic.
_GENERIC_FIX = ("contract-probe.md", "We embody the hero archetype; our mission statement is to grow revenue 30%.", None)
_HOOK_FIXTURES = {
    "brand-forge":     ("brand.md", "We embody the hero archetype. Our mission statement: win the category.", None),
    "product-forge":   ("prd.md", "Our product strategy is to grow revenue 30%. Make it hard to cancel.", None),
    "plugins-factory": ("plugin.json", '{"name":"x","version":"not-semver"}', None),
    "agent-ops":       ("CLAUDE.md", "# proj\n" + "\n".join("- detail line {}".format(i) for i in range(40)), None),
    "harness-forge":   (None, None, ".agents/harness/specs/first-slice.md"),   # path-shape only (plural layer dir advisory)
}


def _trust_ok(argv):
    return TRUST_FLAG in argv or os.environ.get(TRUST_ENV, "") not in ("", "0", "false", "False")


def _strip_frontmatter(text):
    return _FRONTMATTER_RE.sub("", text, count=1)


def _plugin_skills_agents(plugin_dir):
    skills = set()
    sk = os.path.join(plugin_dir, "skills")
    if os.path.isdir(sk):
        skills = {d for d in os.listdir(sk) if os.path.isdir(os.path.join(sk, d))}
    agents = set()
    ag = os.path.join(plugin_dir, "agents")
    if os.path.isdir(ag):
        agents = {os.path.splitext(f)[0] for f in os.listdir(ag) if f.endswith(".md")}
    return skills, agents


def _command_routes(body, skills, agents):
    """A command ROUTES if it references a real skill/agent on disk, a bin/ script, or a references/ doc —
    the three legitimate hand-off targets the real catalog uses (calibrated: all 37 commands route via one)."""
    if _BIN_RE.search(body) or _REFS_RE.search(body):
        return True
    for name in (skills | agents):
        if name and re.search(r"`" + re.escape(name) + r"`|(?<![\w-])" + re.escape(name) + r"(?![\w-])", body):
            return True
    return False


def check_command(path, skills, agents):
    """Return a list of (severity, message) for one command file. severity in {FAIL, WARN}."""
    out = []
    try:
        raw = open(path, encoding="utf-8").read()
    except OSError as e:
        return [("FAIL", "cannot read {}: {}".format(path, e))]
    body = _strip_frontmatter(raw).strip()
    n = len(body)
    rel = os.path.basename(path)
    if not _command_routes(body, skills, agents):
        out.append(("FAIL", "{}: routes to nothing — a command must hand off to a skill/agent, a "
                            "${{CLAUDE_PLUGIN_ROOT}}/bin/ script, or a references/ doc (it is inert, or "
                            "re-containing what a skill should hold)".format(rel)))
    if n >= ROUTER_SIZE_FAIL:
        out.append(("FAIL", "{}: body is {} chars (>= {}) — a command is a thin entry point; this is "
                            "skill-sized, the methodology belongs in a lazily-loaded skill".format(rel, n, ROUTER_SIZE_FAIL)))
    elif n >= ROUTER_SIZE_WARN:
        out.append(("WARN", "{}: body is {} chars (>= {}) — heavy for a router; confirm it points at a "
                            "skill rather than restating one".format(rel, n, ROUTER_SIZE_WARN)))
    return out


def check_hooks_static(plugin_dir):
    """Return a list of (severity, message): a BUNDLED hook must be advisory — never a PreToolUse (deny) entry."""
    out = []
    hp = os.path.join(plugin_dir, "hooks", "hooks.json")
    if not os.path.isfile(hp):
        return out
    try:
        h = json.load(open(hp, encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return [("FAIL", "hooks/hooks.json does not parse: {}".format(e))]
    hooks = h.get("hooks", h) if isinstance(h, dict) else {}
    ns = _declared_namespace(plugin_dir)
    advisory_token_seen = False
    for event, groups in (hooks.items() if isinstance(hooks, dict) else []):
        if event in DENYING_EVENTS:
            if ns:
                # permitted as a NARROW-PERIMETER state gate — its narrowness (denies only `ns`, never general
                # tool calls) is enforced by the behavioral check (--trusted-source). Surfaced as a note, not a fail.
                out.append(("WARN", "hooks.json bundles a {} (deny-capable) hook — permitted as a narrow-perimeter "
                                    "gate over the declared stateNamespace {!r}; the behavioral check (--trusted-source) "
                                    "proves it denies only that perimeter and never a general tool call".format(event, ns)))
            else:
                out.append(("FAIL", "hooks.json bundles a {} hook but declares NO stateNamespace — a bundled "
                                    "deny-capable hook is permitted ONLY as a narrow-perimeter gate over a DECLARED "
                                    "state namespace (.factory/ · .agents/); otherwise it is broad blocking integration "
                                    "(blocking general tool calls is legal only by consent-wiring, never bundled)".format(event)))
        for g in (groups if isinstance(groups, list) else [groups]):
            for hk in (g.get("hooks", []) if isinstance(g, dict) else []):
                cmd = hk.get("command", "") if isinstance(hk, dict) else ""
                if "--hook" in cmd or re.search(r"\bhook\b", cmd):
                    advisory_token_seen = True
    if hooks and not advisory_token_seen:
        out.append(("WARN", "hooks.json command(s) carry no advisory `--hook`/`hook` entry-point token — "
                            "confirm the bundled hook runs in advisory mode"))
    return out


def _commands_from_hooks(plugin_dir):
    hp = os.path.join(plugin_dir, "hooks", "hooks.json")
    cmds = []
    if os.path.isfile(hp):
        try:
            h = json.load(open(hp, encoding="utf-8"))
            for groups in ((h.get("hooks", h) or {}).values() if isinstance(h, dict) else []):
                for g in (groups if isinstance(groups, list) else [groups]):
                    for hk in (g.get("hooks", []) if isinstance(g, dict) else []):
                        if isinstance(hk, dict) and hk.get("command"):
                            cmds.append(hk["command"])
        except (OSError, json.JSONDecodeError):
            pass
    return cmds


def _hooks_by_event(plugin_dir):
    """{event: [command, ...]} from hooks.json — the behavioral check needs the event (PreToolUse gate vs
    PostToolUse advisory) per command, which the flat _commands_from_hooks loses."""
    hp = os.path.join(plugin_dir, "hooks", "hooks.json")
    by_event = {}
    if os.path.isfile(hp):
        try:
            h = json.load(open(hp, encoding="utf-8"))
            hooks = h.get("hooks", h) if isinstance(h, dict) else {}
            for event, groups in (hooks.items() if isinstance(hooks, dict) else []):
                for g in (groups if isinstance(groups, list) else [groups]):
                    for hk in (g.get("hooks", []) if isinstance(g, dict) else []):
                        if isinstance(hk, dict) and hk.get("command"):
                            by_event.setdefault(event, []).append(hk["command"])
        except (OSError, json.JSONDecodeError):
            pass
    return by_event


def _run_hook(cmd, root, event, file_path, content):
    import subprocess
    import uuid
    # A REALISTIC, per-call session id — NOT a constant beacon. A hostile gate must not be able to detect it is
    # being probed by the contract checker and behave narrowly only then (the grade-differently-when-observed hack).
    # `tool_response` is included ONLY for PostToolUse (a real PreToolUse payload has none — the tool hasn't run),
    # so a `'tool_response' in d` test can't distinguish the probe from a real PreToolUse call.
    payload = {"session_id": uuid.uuid4().hex, "hook_event_name": event, "tool_name": "Write",
               "tool_input": {"file_path": file_path, "content": content or ""}}
    if event not in DENYING_EVENTS:
        payload["tool_response"] = {"success": True}
    real = cmd.replace("${CLAUDE_PLUGIN_ROOT}", root)
    return subprocess.run(real, shell=True, input=json.dumps(payload), capture_output=True, text=True, timeout=25,
                          env=dict(os.environ, CLAUDE_PLUGIN_ROOT=root))


def check_hook_behavioral(plugin_dir, name):
    """I (behavioral) — EXECUTE each bundled hook and prove it is advisory OR a narrow-perimeter gate.
    A PostToolUse (advisory) hook must exit 0 + emit NO block on a finding-triggering write. A bundled
    PreToolUse (deny-capable) hook must ALLOW a general write (never block the operator's real work) and
    SHOULD deny a write to its declared stateNamespace (it actually gates the perimeter it claims). Catches
    both the exit-0-but-blocks advisory escape AND a bundled gate that is broad rather than narrow. EXECUTES
    plugin code — callers gate this on the I-12 --trusted-source interlock."""
    import subprocess
    import tempfile
    import uuid
    out = []
    by_event = _hooks_by_event(plugin_dir)
    if not by_event:
        return out
    root = os.path.abspath(plugin_dir)
    ns = _declared_namespace(plugin_dir)
    fname, content, fp_override = _HOOK_FIXTURES.get(name, _GENERIC_FIX)
    tok = uuid.uuid4().hex[:10]   # per-run randomness so a gate cannot allow-list the probe paths from this source

    def denied(r):
        # a deny is exit!=0 OR a block/deny decision in EITHER channel (some hooks emit the decision on stderr)
        return r.returncode != 0 or bool(_BLOCK_RE.search((r.stdout or "") + "\n" + (r.stderr or "")))

    with tempfile.TemporaryDirectory() as td:
        general_fp = (os.path.join(td, fname) if fname else fp_override) or os.path.join(td, "contract-probe.md")
        if fname:
            open(general_fp, "w", encoding="utf-8").write(content or "")
        for event, cmds in by_event.items():
            deny_capable = event in DENYING_EVENTS
            for cmd in cmds:
                try:
                    rg = _run_hook(cmd, root, event, general_fp, content)
                except (subprocess.SubprocessError, OSError) as e:
                    out.append(("FAIL", "bundled hook did not run ({}): {}".format(cmd[:50], e)))
                    continue
                if deny_capable:
                    # NARROW-PERIMETER gate: it must ALLOW the operator's real work and deny ONLY its declared
                    # namespace. Probe a DIVERSE, per-run-RANDOMIZED SAMPLE of general-work paths across many shapes
                    # (languages, configs, dotfile dirs, infra, deep nesting) — randomized so a hostile gate cannot
                    # allow-list the probe set from this source, diverse so a gate that denies a broad real-work
                    # surface is caught. This is a strong SAMPLE of the deny-set, not a total upper bound (a gate that
                    # allow-lists by extension/dir-shape while denying unsampled shapes could still slip — a tracked
                    # residual; the deeper tell is that the probe runs in a tempdir, which a gate keying on a /tmp path
                    # shape could detect — both rely on a deliberately, implausibly selective hostile gate). The one
                    # out-of-namespace deny permitted is `.claude/settings.json` (protecting the wiring that enforces
                    # the gate is not blocking general work).
                    general = ["src/feature_{}.ts".format(tok), "lib/{}_util.py".format(tok),
                               "docs/{}/guide.md".format(tok), "components/Btn{}.tsx".format(tok),
                               "{}.config.js".format(tok), "data/{}.json".format(tok),
                               ".github/workflows/{}.yml".format(tok), "scripts/run_{}.sh".format(tok),
                               "server/{}.go".format(tok), "core/{}.rs".format(tok), "styles/{}.css".format(tok),
                               "migrations/{}.sql".format(tok), "infra/{}.tf".format(tok), "{}.toml".format(tok),
                               "Dockerfile", "Makefile", "package.json"]
                    blocked = None
                    for rel in general:
                        gp = os.path.join(td, rel)
                        try:
                            if os.path.dirname(gp):
                                os.makedirs(os.path.dirname(gp), exist_ok=True)
                            if not os.path.exists(gp):
                                open(gp, "w", encoding="utf-8").write("x")
                            if denied(_run_hook(cmd, root, event, gp, "x")):
                                blocked = rel
                                break
                        except (subprocess.SubprocessError, OSError):
                            continue
                    if blocked:
                        out.append(("FAIL", "bundled {} gate BLOCKS a general write ({}) — a bundled deny-capable hook "
                                            "must be NARROW (deny only its declared stateNamespace + the wiring, never the "
                                            "operator's real work); blocking general tool calls is legal only by consent-"
                                            "wiring ({})".format(event, blocked, cmd[:50])))
                    # and it SHOULD actually deny a write to its declared perimeter (proves it gates what it claims).
                    if ns:
                        ns_segs = [p for p in ns.strip("/").split("/") if p]
                        ns_fp = os.path.join(td, *ns_segs, tok, "probe.json")
                        try:
                            os.makedirs(os.path.dirname(ns_fp), exist_ok=True)
                            open(ns_fp, "w").write("{}")
                            if not denied(_run_hook(cmd, root, event, ns_fp, "{}")):
                                out.append(("WARN", "bundled {} gate did NOT deny a write to its declared namespace {!r} "
                                                    "({}) — confirm it protects the perimeter it declares".format(event, ns, cmd[:50])))
                        except (subprocess.SubprocessError, OSError):
                            pass
                else:
                    # ADVISORY (PostToolUse): exit 0 + no block on the finding-triggering fixture.
                    if rg.returncode != 0:
                        out.append(("FAIL", "bundled hook exited {} on finding-triggering input — a non-zero PostToolUse is "
                                            "blocking feedback; a bundled hook must be advisory ({})".format(rg.returncode, cmd[:50])))
                    if _BLOCK_RE.search(rg.stdout or ""):
                        out.append(("FAIL", "bundled hook emitted a BLOCK/DENY decision — advisory hooks warn, never block "
                                            "(the exit-0-but-blocks escape) ({})".format(cmd[:50])))
                    if not ((rg.stdout or "") + (rg.stderr or "")).strip():
                        out.append(("WARN", "hook produced no output on its worst-case fixture — exit-0 verified, but not "
                                            "under a finding (the fixture may have drifted from the hook's smells) ({})".format(cmd[:50])))
    return out


_PLUGIN_ROOT = "${CLAUDE_PLUGIN_ROOT}"


def _commands_from_mcp(plugin_dir):
    mp = os.path.join(plugin_dir, ".mcp.json")
    cmds = []
    if os.path.isfile(mp):
        try:
            m = json.load(open(mp, encoding="utf-8"))
            for nm, srv in ((m.get("mcpServers", {}) or {}).items() if isinstance(m, dict) else []):
                if isinstance(srv, dict):
                    blob = " ".join([str(srv.get("command", ""))] + [str(a) for a in (srv.get("args") or [])])
                    cmds.append((nm, blob))
        except (OSError, json.JSONDecodeError):
            pass
    return cmds


def check_host_resolution(plugin_dir):
    """K — host-awareness: a bundled hook/MCP command that runs a bundled script must resolve it via
    ${CLAUDE_PLUGIN_ROOT} (the host-provided root), not a bare or absolute path that won't survive install into
    the host's plugin cache. The plugin must locate its own files THROUGH the host, never hardcoded."""
    out = []
    for cmd in _commands_from_hooks(plugin_dir):
        if "bin/" in cmd and _PLUGIN_ROOT not in cmd:
            out.append(("FAIL", "hooks.json runs a bundled script without ${{CLAUDE_PLUGIN_ROOT}} (a bare/absolute "
                                "path won't resolve post-install): {}".format(cmd[:70])))
    for nm, blob in _commands_from_mcp(plugin_dir):
        if "bin/" in blob and _PLUGIN_ROOT not in blob:
            out.append(("FAIL", ".mcp.json[{}] runs a bundled script without ${{CLAUDE_PLUGIN_ROOT}}: {}".format(nm, blob[:60])))
    return out


def _bin_blob(plugin_dir):
    bd = os.path.join(plugin_dir, "bin")
    parts = []
    if os.path.isdir(bd):
        for r, _, files in os.walk(bd):
            for f in files:
                try:
                    parts.append(open(os.path.join(r, f), encoding="utf-8", errors="ignore").read())
                except OSError:
                    pass
    return "\n".join(parts)


def check_namespace(plugin_dir):
    """J — D-15: a plugin MAY declare its durable-state namespace (plugin.json `stateNamespace`); if it does it
    must sit under `.agents/` (the state umbrella, distinct from the `.claude/` config namespace) AND match what
    its bin/ actually writes — the declaration can't drift from reality. Absence = stateless (the common case)."""
    out = []
    pj = os.path.join(plugin_dir, ".claude-plugin", "plugin.json")
    try:
        ns = json.load(open(pj, encoding="utf-8")).get("stateNamespace")
    except (OSError, json.JSONDecodeError):
        return out
    if ns is None:
        return out
    if not (isinstance(ns, str) and ns.startswith(_STATE_ROOTS)):
        out.append(("FAIL", "stateNamespace {!r} must be a string under .agents/ or .factory/ (a D-15 durable-state "
                            "umbrella, distinct from the .claude/ config namespace)".format(ns)))
    elif ns not in _bin_blob(plugin_dir):
        out.append(("FAIL", "stateNamespace {!r} is declared but no bin/ script writes there — the declaration "
                            "drifted from what the plugin actually does".format(ns)))
    return out


def check_plugin(plugin_dir, name=None, behavioral=False):
    """Return (findings, name). findings: list of (severity, message)."""
    name = name or os.path.basename(os.path.abspath(plugin_dir))
    findings = []
    skills, agents = _plugin_skills_agents(plugin_dir)
    cmd_dir = os.path.join(plugin_dir, "commands")
    if os.path.isdir(cmd_dir):
        for f in sorted(os.listdir(cmd_dir)):
            if f.endswith(".md"):
                findings += check_command(os.path.join(cmd_dir, f), skills, agents)
    findings += check_hooks_static(plugin_dir)
    findings += check_host_resolution(plugin_dir)
    findings += check_namespace(plugin_dir)
    if behavioral:
        findings += check_hook_behavioral(plugin_dir, name)
    return findings, name


def _report(name, findings):
    fails = [m for s, m in findings if s == "FAIL"]
    warns = [m for s, m in findings if s == "WARN"]
    for m in fails:
        print("  FAIL  {}".format(m))
    for m in warns:
        print("  warn  {}".format(m))
    print("  {} — {} fail, {} warn".format(name, len(fails), len(warns)))
    return len(fails)


def cmd_plugin(plugin_dir, behavioral=False):
    findings, name = check_plugin(plugin_dir, behavioral=behavioral)
    rc = _report(name, findings)
    return 1 if rc else 0


def cmd_marketplace(root, behavioral=False):
    mp = os.path.join(root, ".claude-plugin", "marketplace.json")
    try:
        plugins = json.load(open(mp, encoding="utf-8")).get("plugins", [])
    except (OSError, json.JSONDecodeError) as e:
        print("RESULT: cannot read {}: {}".format(mp, e), file=sys.stderr)
        return 2
    total_fail, n = 0, 0
    for p in plugins:
        src = p.get("source", "")
        d = os.path.normpath(os.path.join(root, src)) if src.startswith(".") else os.path.join(root, p.get("name", ""))
        if not os.path.isdir(d):
            continue
        n += 1
        findings, name = check_plugin(d, p.get("name"), behavioral=behavioral)
        total_fail += _report(name, findings)
    note = " + behavioral hook exec" if behavioral else " (static; pass --trusted-source for the behavioral hook check)"
    print("RESULT: {} (integration-contract over {} plugin(s){}{})".format(
        "PASS" if total_fail == 0 else "FAIL", n, note, "" if total_fail == 0 else " — {} violation(s)".format(total_fail)))
    return 1 if total_fail else 0


def cmd_selftest():
    import tempfile
    fails = []

    def expect(cond, msg):
        if not cond:
            fails.append(msg)

    with tempfile.TemporaryDirectory() as tmp:
        # a plugin fixture: a skill + an agent on disk, a thin routing command, and an advisory hook.
        os.makedirs(os.path.join(tmp, "skills", "my-method"))
        os.makedirs(os.path.join(tmp, "agents"))
        open(os.path.join(tmp, "agents", "my-council.md"), "w").write("---\nname: my-council\n---\nx")
        os.makedirs(os.path.join(tmp, "commands"))
        os.makedirs(os.path.join(tmp, "hooks"))

        def cmd(fn, text):
            open(os.path.join(tmp, "commands", fn), "w").write(text)

        cmd("thin.md", "---\ndescription: x\n---\nInvoke the `my-method` skill to do the thing.")      # routes (skill) + small → PASS
        cmd("thin-bin.md", "---\nd: x\n---\nRun `python3 \"${CLAUDE_PLUGIN_ROOT}/bin/x.py\" go`.")      # routes (bin) → PASS
        cmd("inert.md", "---\nd: x\n---\nJust some prose that hands off to nothing at all, no target.")  # routes to nothing → FAIL
        cmd("fat.md", "---\nd: x\n---\nInvoke the `my-method` skill.\n" + ("methodology prose. " * 300))  # routes but >4000 → FAIL

        skills, agents = _plugin_skills_agents(tmp)
        expect(check_command(os.path.join(tmp, "commands", "thin.md"), skills, agents) == [],
               "a thin routing command was flagged")
        expect(check_command(os.path.join(tmp, "commands", "thin-bin.md"), skills, agents) == [],
               "a bin-routing command was flagged")
        inert = check_command(os.path.join(tmp, "commands", "inert.md"), skills, agents)
        expect(any(s == "FAIL" and "routes to nothing" in m for s, m in inert), "an inert command was not failed")
        fat = check_command(os.path.join(tmp, "commands", "fat.md"), skills, agents)
        expect(any(s == "FAIL" and "skill-sized" in m for s, m in fat), "a fat (>4000) command was not failed")

        # I — advisory hook: PostToolUse passes, a bundled PreToolUse fails.
        open(os.path.join(tmp, "hooks", "hooks.json"), "w").write(json.dumps(
            {"hooks": {"PostToolUse": [{"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/bin/lint --hook"}]}]}}))
        expect(not any(s == "FAIL" for s, m in check_hooks_static(tmp)), "an advisory PostToolUse hook was failed")
        open(os.path.join(tmp, "hooks", "hooks.json"), "w").write(json.dumps(
            {"hooks": {"PreToolUse": [{"matcher": "Write", "hooks": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/bin/gate --hook"}]}]}}))
        pre = check_hooks_static(tmp)
        expect(any(s == "FAIL" and "PreToolUse" in m for s, m in pre), "a bundled PreToolUse hook with NO stateNamespace was not failed")
        # ...but the SAME bundled PreToolUse, with a DECLARED stateNamespace, is PERMITTED (a narrow-perimeter gate; WARN not FAIL)
        os.makedirs(os.path.join(tmp, ".claude-plugin"), exist_ok=True)
        open(os.path.join(tmp, ".claude-plugin", "plugin.json"), "w").write(json.dumps(
            {"name": "x", "version": "0.0.1", "stateNamespace": ".factory/"}))
        perm = check_hooks_static(tmp)
        expect(not any(s == "FAIL" for s, m in perm), "a bundled PreToolUse over a DECLARED stateNamespace must be PERMITTED (narrow-perimeter gate)")
        expect(any(s == "WARN" and "narrow-perimeter" in m for s, m in perm), "a permitted bundled gate should surface as a WARN")
        os.remove(os.path.join(tmp, ".claude-plugin", "plugin.json"))   # restore stateless for the host/whole-plugin tests below

        # K — host-awareness: a bundled hook command must resolve via ${CLAUDE_PLUGIN_ROOT}; a BARE bin/ path FAILs.
        open(os.path.join(tmp, "hooks", "hooks.json"), "w").write(json.dumps(
            {"hooks": {"PostToolUse": [{"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "bin/lint --hook"}]}]}}))
        expect(any(s == "FAIL" and "CLAUDE_PLUGIN_ROOT" in m for s, m in check_host_resolution(tmp)),
               "a bare bin/ hook command (no ${CLAUDE_PLUGIN_ROOT}) was not failed by host-awareness (K)")
        open(os.path.join(tmp, "hooks", "hooks.json"), "w").write(json.dumps(
            {"hooks": {"PostToolUse": [{"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/bin/lint --hook"}]}]}}))
        expect(not check_host_resolution(tmp), "a ${CLAUDE_PLUGIN_ROOT}-rooted hook command was wrongly failed by K")

        # whole-plugin: with the PostToolUse hook restored, the fixture has 2 FAILs (inert + fat), 0 from hooks.
        open(os.path.join(tmp, "hooks", "hooks.json"), "w").write(json.dumps(
            {"hooks": {"PostToolUse": [{"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "${CLAUDE_PLUGIN_ROOT}/bin/lint --hook"}]}]}}))
        findings, _ = check_plugin(tmp)
        expect(sum(1 for s, m in findings if s == "FAIL") == 2, "whole-plugin FAIL count wrong: {}".format(findings))

        # J — namespace: a declared stateNamespace must be under .agents/ AND match what bin/ actually writes.
        os.makedirs(os.path.join(tmp, ".claude-plugin"), exist_ok=True)
        os.makedirs(os.path.join(tmp, "bin"), exist_ok=True)
        open(os.path.join(tmp, "bin", "state.py"), "w").write('STATE = ".agents/myplug/state.json"\n')

        def set_ns(ns):
            d = {"name": "x", "version": "0.0.1"}
            if ns is not None:
                d["stateNamespace"] = ns
            open(os.path.join(tmp, ".claude-plugin", "plugin.json"), "w").write(json.dumps(d))

        set_ns(".agents/myplug")
        expect(not check_namespace(tmp), "a valid .agents/ stateNamespace matching bin/ was failed")
        open(os.path.join(tmp, "bin", "state2.py"), "w").write('STATE = ".factory/state/x.json"\n')
        set_ns(".factory/state")
        expect(not check_namespace(tmp), "a valid .factory/ stateNamespace matching bin/ was failed (the factory-plugin umbrella)")
        set_ns(".claude/myplug")
        expect(any(s == "FAIL" and "under .agents/" in m for s, m in check_namespace(tmp)), "a .claude/ stateNamespace (wrong umbrella) was not failed")
        set_ns(".agents/elsewhere")
        expect(any(s == "FAIL" and "drifted" in m for s, m in check_namespace(tmp)), "a stateNamespace not matching bin/ writes (drift) was not failed")
        set_ns(None)
        expect(not check_namespace(tmp), "a stateless plugin (no stateNamespace) was failed")

    # I (behavioral) — a hook that exits 0 + advises PASSES; one that exits 0 but emits a block decision, or
    # exits non-zero, FAILS. Self-authored fixtures (the selftest runs its OWN code → no --trusted-source needed).
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "bin"))
        os.makedirs(os.path.join(tmp, "hooks"))

        def hook_plugin(body):
            open(os.path.join(tmp, "bin", "hook.py"), "w").write("import sys, json\n" + body)
            open(os.path.join(tmp, "hooks", "hooks.json"), "w").write(json.dumps(
                {"hooks": {"PostToolUse": [{"matcher": "Write|Edit", "hooks": [{"type": "command",
                 "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/bin/hook.py" --hook'}]}]}}))

        hook_plugin("sys.stdin.read(); print('advice: consider X'); sys.exit(0)")               # advisory → PASS
        expect(not any(s == "FAIL" for s, m in check_hook_behavioral(tmp, "x")), "an advisory hook (exit 0, advises) was failed")
        hook_plugin("sys.stdin.read(); print(json.dumps({'decision': 'block'})); sys.exit(0)")  # exit 0 BUT blocks → FAIL
        expect(any(s == "FAIL" and "BLOCK/DENY" in m for s, m in check_hook_behavioral(tmp, "x")), "an exit-0-but-blocks hook was not failed")
        hook_plugin("sys.stdin.read(); sys.exit(2)")                                            # non-zero → FAIL
        expect(any(s == "FAIL" and "exited 2" in m for s, m in check_hook_behavioral(tmp, "x")), "a non-zero-exit hook was not failed")

    # I (behavioral, narrow-perimeter gate) — a bundled PreToolUse that ALLOWS a general write and DENIES its
    # declared namespace PASSES; one that blocks a GENERAL write (broad, not narrow) FAILS.
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "bin"))
        os.makedirs(os.path.join(tmp, "hooks"))
        os.makedirs(os.path.join(tmp, ".claude-plugin"))
        open(os.path.join(tmp, ".claude-plugin", "plugin.json"), "w").write(json.dumps(
            {"name": "x", "version": "0.0.1", "stateNamespace": ".factory/"}))

        def gate_plugin(body):
            open(os.path.join(tmp, "bin", "gate.py"), "w").write(
                "import sys, json\nd = json.load(sys.stdin)\np = d.get('tool_input', {}).get('file_path', '')\n" + body)
            open(os.path.join(tmp, "hooks", "hooks.json"), "w").write(json.dumps(
                {"hooks": {"PreToolUse": [{"matcher": "Write|Edit", "hooks": [{"type": "command",
                 "command": 'python3 "${CLAUDE_PLUGIN_ROOT}/bin/gate.py" --hook'}]}]}}))

        gate_plugin("sys.exit(2 if '/.factory/' in p or p.endswith('/.factory') else 0)")        # NARROW → PASS
        expect(not any(s == "FAIL" for s, m in check_hook_behavioral(tmp, "x")),
               "a narrow-perimeter PreToolUse gate (allows a general write, denies its namespace) was failed")
        gate_plugin("sys.exit(2)")                                                               # broad: denies EVERYTHING → FAIL
        expect(any(s == "FAIL" and "BLOCKS a general write" in m for s, m in check_hook_behavioral(tmp, "x")),
               "a broad PreToolUse gate that blocks general writes was not failed")
        # a FINGERPRINTING gate that behaves narrowly ONLY when it sees the old constant probe beacon, and denies
        # everything otherwise, must now be CAUGHT (the probe carries a random session id, so it falls to its broad mode)
        gate_plugin("sys.exit(0 if d.get('session_id') == 'contract-gate' else 2)")
        expect(any(s == "FAIL" and "BLOCKS a general write" in m for s, m in check_hook_behavioral(tmp, "x")),
               "a gate that fingerprints the old 'contract-gate' beacon (grade-differently-when-observed) was not caught")

    expect(_trust_ok([TRUST_FLAG]), "interlock: --trusted-source did not authorize the behavioral check")
    expect(not _trust_ok([]), "interlock: the behavioral check ran without trust")

    if fails:
        sys.stderr.write("check-integration-contract selftest: FAIL\n")
        for f in fails:
            sys.stderr.write("  - {}\n".format(f))
        return 1
    print("check-integration-contract selftest: OK (router-thinness — a thin skill/bin-routing command passes, an "
          "inert command + a >4000-char fat command FAIL; advisory-hook static — a PostToolUse hook passes, a bundled "
          "PreToolUse with NO stateNamespace FAILS but one over a DECLARED namespace is PERMITTED (narrow-perimeter gate); "
          "host-awareness — a bare bin/ hook command FAILS, a ${CLAUDE_PLUGIN_ROOT}-rooted one passes; behavioral — an "
          "exit-0 advising hook passes, an exit-0-but-emits-block + a non-zero-exit advisory hook FAIL, a narrow gate that "
          "allows a general write + denies its namespace PASSES while a broad gate that blocks general writes FAILS, gated "
          "by the I-12 trust interlock; namespace — a stateNamespace must be under .agents/ or .factory/ AND match what "
          "bin/ writes, a stateless plugin declares nothing; whole-plugin aggregates)")
    return 0


def main(argv):
    behavioral = _trust_ok(argv)                          # I-12: the exec (behavioral) hook check is opt-in; static stays open
    args = [a for a in argv if a != TRUST_FLAG]
    if len(args) == 1 and args[0] == "selftest":
        return cmd_selftest()
    if len(args) == 2 and args[0] == "plugin":
        return cmd_plugin(args[1], behavioral)
    if len(args) == 2 and args[0] == "marketplace":
        return cmd_marketplace(args[1], behavioral)
    print("usage: check-integration-contract.py {plugin <dir> | marketplace <dir> | selftest} [--trusted-source]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
