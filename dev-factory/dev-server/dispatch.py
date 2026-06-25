#!/usr/bin/env python3
"""dispatch.py — the dispatcher: provision, launch, supervise, validate (the engine's outer mechanics).

The heartbeat selects (compass) and this dispatches: it provisions a hermetic git worktree, sets
`claimed` (single-writer, so the classic claim race is designed out, not mitigated — §7.2), launches a
worker through a `DispatchAdapter`, supervises its lease, then runs the critic (the validation path) and
drives the ticket to `done`. A dead worker is recovered by lease expiry, not by reconciling competing
claims (§15).

The `DispatchAdapter` is the integration seam (§9.2, OD-003): the kernel defines the contract; the
concrete binding to a headless agent runtime is pinned against current product docs. This module ships
the deterministic **MockAdapter** (a real subprocess, no live model) so the whole loop is CI-verifiable;
the live `headless-claude` binding lands as a sibling adapter once its invocation is confirmed.

Stdlib only; Python 3.8+. (Part of dev-server; not a plugin.)
"""
import datetime
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import api as _api          # noqa: E402  (single-writer ops)
sys.path.insert(0, _api._store._KERNEL_BIN)
import lattice as _lat      # noqa: E402
import lifecycle as _lc     # noqa: E402
import ledger as _led       # noqa: E402
import execplan as _ep      # noqa: E402  (the deterministic execution-plan assembly)
import autonomy as _auto    # noqa: E402  (the trust trajectory — record_incident demotes on a caught false pass)
import distill as _distill  # noqa: E402  (the regeneration loop's deterministic scan — ledger → pattern candidates)
import verify_gen as _vg    # noqa: E402  (the critic-harness generator + the self-heal fold/re-arm transforms)

LEASE_TTL_S = 900           # a worker lease; exceeded → the worker is presumed dead (reconcile_leases)
MAX_WORKER_ATTEMPTS = 3     # consecutive worker failures on one cell before it blocks (a transient hiccup retries)


def _last_failure(d, tid):
    """The most recent failure rationale for a ticket SINCE its last success — fed back into the retry prompt so a
    re-authored attempt fixes the SPECIFIC failure (a missing export, a behavioral assertion) instead of re-reading
    the contract blind. Read from the append-only ledger; resets on any activity-complete."""
    last = None
    for e in _led.read(d):
        if (e.get("subject") or {}).get("ticket") != tid:
            continue
        ev = e.get("event")
        if ev == "activity-complete":
            last = None
        elif ev == "activity-fail":
            last = e.get("rationale")
    return last


def _consecutive_fails(d, tid):
    """The current failure STREAK for a ticket — count `activity-fail` events since its last `activity-complete`
    (any success resets the streak). The retry budget: a transient failure retries; a persistently-stuck cell
    blocks. Read from the append-only ledger, so it survives a crash + needs no schema change to the ticket."""
    n = 0
    for e in _led.read(d):
        if (e.get("subject") or {}).get("ticket") != tid:
            continue
        ev = e.get("event")
        if ev == "activity-fail":
            n += 1
        elif ev == "activity-complete":
            n = 0
    return n

# Roster mapping: which worker role advances a cell of a given layer (the critic is always cell-validator —
# the separate skeptic). The execution plan decides HOW the unit runs; this decides WHO. A regenerating cell
# is advanced by the spec-regenerator. Defaults to the generic cell-advancer.
ROSTER = {
    "ontology": "lattice-architect", "spec": "spec-architect", "rubric": "rubric-architect",
    "pattern": "pattern-distiller", "policy": "cell-advancer", "capability": "cell-advancer",
    "methodology": "cell-advancer", "protocol": "cell-advancer", "ledger": "cell-advancer",
}
# A single-pass plan for instances with no kit policy bound (the irreducible default).
DEFAULT_PLAN = {"orchestration_shape": "single-pass", "loop_strategy": "single",
                "context_plan": {"retrieval": "minimal"}, "effort": {"model_tier": "small", "reasoning_effort": "low", "max_iterations": 2},
                "delegation": {"mode": "none", "max_depth": 0}}


def agent_for(cell, to_mat):
    if to_mat == "regenerating":
        return "spec-regenerator"
    return ROSTER.get((cell or {}).get("layer"), "cell-advancer")


def resolve_policy(d, kit_dir=None):
    """The kit's DispatchPolicy (the family bound to this instance). Resolved from DEV_FACTORY_KIT or a passed
    kit dir; a permissive single-pass default if none is bound."""
    kit_dir = kit_dir or os.environ.get("DEV_FACTORY_KIT")
    if kit_dir:
        try:
            kit = json.load(open(os.path.join(kit_dir, "kit.json"), encoding="utf-8"))
            return _ep.load_policy(os.path.join(kit_dir, kit.get("dispatch_policy", "dispatch-policy.json")))
        except (OSError, ValueError, KeyError):
            pass
    return {"family": "default", "rules": [], "default": DEFAULT_PLAN}


def _now():
    return datetime.datetime.now().astimezone()


def _asset_fingerprint(d, asset_ref):
    """A content hash of a cell's asset (one file, or every non-verifier file in a multi-file dir) — used to detect a
    NO-OP dispatch (a worker that ran but changed nothing) adapter-agnostically, so 'Done — no change' is honest on
    the headless loop (real tokens, no diff), not only on mock. Returns None if the asset is absent/unreadable (so a
    fresh cell with no prior asset reads as 'changed', never a false no-op)."""
    if not asset_ref:
        return None
    import hashlib
    p = os.path.join(d, asset_ref)
    h = hashlib.md5()
    try:
        if os.path.isdir(p):
            seen = False
            for root, _dirs, files in os.walk(p):
                for fn in sorted(files):
                    if fn == "verify.mjs" or fn.startswith("."):   # the critic harness isn't the worker's product
                        continue
                    seen = True
                    h.update(fn.encode())
                    h.update(open(os.path.join(root, fn), "rb").read())
            return h.hexdigest() if seen else None
        if os.path.isfile(p):
            h.update(open(p, "rb").read())
            return h.hexdigest()
    except OSError:
        return None
    return None


def _iso(dt):
    return dt.isoformat(timespec="seconds")


# ─────────────────────────────────── hermetic worktrees ───────────────────────────────────

def _repo_root(d):
    """The enclosing git repo root (nearest ancestor holding `.git`), found by walking UP from the instance
    dir. The instance now nests as `src/{project}/.factory`, so the old fixed-depth grandparent lands on
    `src/` (no `.git`) and would lose worktree isolation. The walk finds the NEAREST `.git` — the project's
    own repo (a real user repo, or the harness's per-run `git init`) — and falls back to the grandparent when
    none is found (a non-repo instance → the plain-dir worktree)."""
    cur = os.path.abspath(d.rstrip("/"))
    while True:
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        if os.path.isdir(os.path.join(parent, ".git")):
            return parent
        cur = parent
    return os.path.dirname(os.path.dirname(d.rstrip("/"))) or "."


def provision_worktree(d, cell_id, worker_id, repo_root=None):
    """A hermetic workspace for one unit. A real git worktree when the instance lives in a repo (so
    parallel workers on different cells never collide); a plain isolated dir otherwise. Returns the path."""
    wt = os.path.join(d, "run", "worktrees", f"{cell_id}--{worker_id}")
    os.makedirs(os.path.dirname(wt), exist_ok=True)
    repo = repo_root or _repo_root(d)   # nearest enclosing git repo (walk up from src/{project}/.factory)
    if os.path.isdir(os.path.join(repo, ".git")):
        try:
            subprocess.run(["git", "-C", repo, "worktree", "add", "--detach", wt, "HEAD"],
                           capture_output=True, check=True)
            return wt, True
        except (subprocess.CalledProcessError, OSError):
            pass
    os.makedirs(wt, exist_ok=True)   # fallback: a plain isolated dir
    return wt, False


def teardown_worktree(d, wt, repo_root=None):
    repo = repo_root or _repo_root(d)
    if os.path.isdir(os.path.join(repo, ".git")):
        subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", wt], capture_output=True)
    shutil.rmtree(wt, ignore_errors=True)


# ─────────────────────────────────── the DispatchAdapter contract ───────────────────────────────────

class DispatchAdapter:
    """dispatch(unit) -> result. Runtime guarantees (§9.2): runs in the hermetic worktree, gates active,
    emits events the dispatcher tees into the ledger, terminates on a stop condition. Subclasses bind a
    concrete runtime."""
    name = "abstract"

    def dispatch(self, d, unit):
        raise NotImplementedError


def _authoring_for(cell, kit_dir=None):
    """The bound kit's AUTHORING declaration for this cell's layer, or None (→ single-`.md` authoring). A kit
    declares multi-file CODE authoring per layer via a top-level `authoring` list, so dev-kit-corpus (doc cells)
    stays single-file while dev-kit-app (capability code) opts into a multi-file directory. The kernel/dispatch
    stay generic — the kit names the shape; check-kit-conform ignores the (kit-local) `authoring` field."""
    kit_dir = kit_dir or os.environ.get("DEV_FACTORY_KIT")
    if not kit_dir:
        return None
    try:
        kit = json.load(open(os.path.join(kit_dir, "kit.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return None
    # match by layer; a slug-specific entry (e.g. capability.*.shell → a single-file root entry) wins over the
    # layer-default, regardless of list order — mirrors _kit_verifier's slug-specificity.
    chosen = None
    for a in kit.get("authoring", []):
        if a.get("layer") != cell["layer"]:
            continue
        if a.get("slug"):
            if a["slug"] == cell.get("slug"):
                return a
        elif chosen is None:
            chosen = a
    return chosen


def _asset_rel(layer, slug, authoring):
    """A cell's asset path RELATIVE TO THE INSTANCE DIR (`.factory/`): a DIRECTORY for multi-file authoring,
    else {layer}/{slug}.md. A kit's `output_root` re-roots the multi-file directory — `..` escapes `.factory/`
    so product CODE lands at the project root (`src/{project}/{slug}/`) beside its sibling verify.mjs as a
    clean runnable tree, while the default (the layer name) keeps the asset inside `.factory/`. Either way
    `os.path.join(d, asset_rel)` resolves to the on-disk asset (the `..` is normalized on resolution)."""
    if authoring and authoring.get("mode") == "single-file":
        # a single runnable ENTRY FILE at output_root (e.g. the integration shell `index.html` at the product
        # root) — NOT a ../{slug}/ module dir. Resolves to `<output_root>/<entry>` (e.g. `../index.html`).
        root = authoring.get("output_root", layer)
        entry = authoring.get("entry") or f"{slug}.html"
        return os.path.join(root, entry) if root else entry
    if authoring and authoring.get("mode") == "multi-file":
        root = authoring.get("output_root", layer)
        return os.path.join(root, slug) if root else slug
    return os.path.join(layer, f"{slug}.md")


class MockAdapter(DispatchAdapter):
    """Deterministic runtime for CI/Crawl→Walk: a real subprocess that plays the worker role — it authors
    (or refines) the target cell's asset, writes nothing to a protected path, and reports metrics. No live
    model, so the whole dispatch loop is reproducible and gate-bounded."""
    name = "mock"

    def dispatch(self, d, unit):
        layer, slug = unit["layer"], unit["slug"]
        if unit.get("kind") == "verifier":
            # author the cell's critic harness (#2). The mock writes a SMOKE check (loads + ready) — lenient so
            # mock-built modules still pass in CI; a headless rubric-architect writes the real spec-conformance
            # test (see HeadlessClaudeAdapter._verifier_prompt). Either way the FACTORY authors the gate, not a seed.
            dir_abs = os.path.join(d, _asset_rel("capability", slug, _authoring_for({"layer": "capability", "slug": slug})))
            os.makedirs(dir_abs, exist_ok=True)
            vpath = os.path.join(dir_abs, "verify.mjs")
            open(vpath, "w", encoding="utf-8").write(
                "// critic harness authored by the (mock) rubric-architect — a smoke check; a headless\n"
                f"// rubric-architect authors a real spec-conformance test against the module's contract. {_MOCK_VERIFIER_MARK}\n"
                "import * as m from './index.mjs';\n"
                "if (m.ready !== true) { console.error('FAIL: index.mjs must export ready=true'); process.exit(1); }\n"
                "console.log('pass'); process.exit(0);\n")
            return {"ok": True, "asset_ref": os.path.relpath(vpath, d), "metrics": {"tokens": 4000, "iterations": 1}}
        if unit.get("kind") == "refute-author":
            # HONEST no-op: a mock cannot synthesize a real DOMAIN oracle (it does not know what the module SHOULD
            # compute), so it authors NO behavioral refute set — the cell stays liveness-only / UNMEASURED, exactly the
            # honest outcome (a headless rubric-architect reading the spec is required to mint a measuring oracle, just
            # as the mock verifier writes only a smoke stub). It records the no-op so the producer leaves the cell at
            # Tier 1, never faking measurement. Returns ok (the dispatch succeeded) without touching the verify-spec.
            cell_id = unit["target_cell"]
            return {"ok": True, "asset_ref": f"coordination/verify-spec/{cell_id}.json", "mock_no_oracle": True,
                    "metrics": {"tokens": 2000, "iterations": 1}}
        if unit.get("kind") == "triage":
            # HONEST no-op: a mock cannot READ a free-text prompt and reason about which lattice cell, transition,
            # and validated rubric should bind it (judgment, not a deterministic transform) — so it proposes NOTHING.
            # In practice triage_intake never dispatches on mock (it returns early on the headless gate); this branch
            # only guards a stray direct call, ensuring the mock never authors a bogus proposal a tick would apply.
            return {"ok": False, "mock_no_triage": True, "metrics": {"tokens": 0, "iterations": 0}}
        authoring = _authoring_for({"layer": layer, "slug": slug})
        if authoring and authoring.get("mode") == "single-file":
            # the integration shell: a single runnable entry at the product root (e.g. index.html). The mock
            # authors a minimal bootstrap that imports a sibling module + mounts DOM — enough to clear both the
            # static (imports a product module) and render (mounts a frame) gates deterministically. A real
            # worker authors the actual integration; this keeps mock builds + evals of the shell cell green.
            asset_rel = _asset_rel(layer, slug, authoring)
            asset_abs = os.path.join(d, asset_rel)
            os.makedirs(os.path.dirname(asset_abs), exist_ok=True)
            wrote = not os.path.exists(asset_abs) or os.path.getsize(asset_abs) == 0  # noop iff a real asset already exists
            if wrote:
                # Import an ACTUAL built sibling module (the first product dir with an index.mjs), NOT a hardcoded
                # `./core/` — that only resolves for a decomposition that happens to name a module `core`, so a mock
                # shell over any other module set (e.g. osc-303/viz-renderer/…) produced an import that the static +
                # render gates correctly REFUSE. The shell is built after the modules, so a sibling exists; fall back
                # to a self-contained mount only when none is built yet.
                root = os.path.dirname(asset_abs)
                sib = next((n for n in sorted(os.listdir(root)) if not n.startswith(".")
                            and os.path.isfile(os.path.join(root, n, "index.mjs"))), None) if os.path.isdir(root) else None
                open(asset_abs, "w", encoding="utf-8").write(
                    "<!doctype html><meta charset=utf-8><title>app</title><main id=app></main>\n"
                    '<script type="module">\n'
                    + (f"  import './{sib}/index.mjs';\n" if sib else "") +
                    "  document.getElementById('app').appendChild(document.createElement('div'));\n"
                    "</script>\n")
            # noop = the mock did NOT author new content (a real hand-authored asset was already there) — the honest
            # signal so the board never claims fresh work it didn't do (P3): "Done — no change" not implied success.
            return {"ok": True, "asset_ref": asset_rel, "noop": not wrote, "metrics": {"tokens": 6000, "iterations": 1}}
        if authoring and authoring.get("mode") == "multi-file":
            # multi-file CODE authoring (the worker's GENERATOR side): author source files into the cell's dir
            # (the kit's output_root may re-root it OUT of .factory/ to the product tree — _asset_rel resolves it).
            # The per-cell verify.mjs is the CRITIC's gate — authored by the planner, write-protected from the
            # worker — so the mock never writes it (a real cold-start seeds the real harness; a trivial stub here).
            asset_rel = _asset_rel(layer, slug, authoring)
            asset_abs = os.path.join(d, asset_rel)
            os.makedirs(asset_abs, exist_ok=True)
            src = os.path.join(asset_abs, "index.mjs")
            wrote = not os.path.exists(src)
            if wrote:
                open(src, "w", encoding="utf-8").write(
                    f"// {layer}.{unit['scope']}.{slug} — authored by the {self.name} worker for {unit['ticket']}\n"
                    "export const ready = true;\n")
            return {"ok": True, "asset_ref": asset_rel, "noop": not wrote, "metrics": {"tokens": 9000, "iterations": 1}}
        asset_dir = os.path.join(d, layer)
        os.makedirs(asset_dir, exist_ok=True)
        asset_rel = os.path.join(layer, f"{slug}.md")
        asset_abs = os.path.join(d, asset_rel)
        existing = open(asset_abs, encoding="utf-8", errors="replace").read() if os.path.exists(asset_abs) else ""
        # a STRUCTURED asset (JSON / a ```json block) is already authored — confirm it, don't clobber it
        # (so a kit's structured-asset verifier still validates after the worker runs).
        if existing.lstrip()[:1] == "{" or "```json" in existing:
            return {"ok": True, "asset_ref": asset_rel, "noop": True, "metrics": {"tokens": 3000, "iterations": 1}}
        # else the worker authors prose (rewritable side — gate-verifier permits spec/ etc.)
        body = f"# {layer}.{unit['scope']}.{slug}\n\nAuthored by the {self.name} worker for {unit['ticket']}.\n"
        with open(asset_abs, "a" if existing else "w", encoding="utf-8") as f:
            f.write(body)
        return {"ok": True, "asset_ref": asset_rel, "metrics": {"tokens": 8000, "iterations": 1}}


def wire_gates(worktree, kernel_bin, allow_verify=False, allow_refute=False, allow_triage=False):
    """Make the immutable boundary ACTIVE inside the worker's worktree: write a .claude/settings.json that
    runs the dev-kernel gates as PreToolUse(Write|Edit) hooks. A worker that tries to forge a signal or
    rewrite the lattice/ledger is denied in-process (gate-verifier emits permissionDecision: deny). This is
    the §9.2 'gates active inside the worktree' guarantee — wired per dispatch, never bundled.

    `allow_verify` wires the verifier-author boundary (`gate-verifier --allow-verify`): the rubric-architect
    authoring a cell's verify.mjs may write it (it IS the gate), while signals/lattice/ledger/rubric stay
    denied. `allow_refute` wires the INVERSE refute-author boundary (`--allow-refute`): the refute-author
    authoring the verify-spec's behavioral oracle may write `coordination/verify-spec/*` while verify.mjs, the
    refuter sidecars, signals, the lattice/ledger, and the product barrel stay denied. `allow_triage` wires the
    triage-author boundary (`--allow-triage`): the ticket-triager turning a prompt into a bound ticket may write
    ONLY `coordination/triage/*` (its proposal) while ALL state — verify.mjs, verify-spec, refuters, signals,
    rubric, the lattice/ledger, and run/ — stays denied. The three are mutually exclusive (gate-verifier rejects
    more than one). The module worker is wired with NONE, so it can write neither the gate it must pass, the
    oracle that re-checks it, nor a triage proposal."""
    cfg_dir = os.path.join(worktree, ".claude")
    os.makedirs(cfg_dir, exist_ok=True)
    gv = f"{os.path.join(kernel_bin, 'gate-verifier')} --hook" + (
        " --allow-verify" if allow_verify else " --allow-refute" if allow_refute
        else " --allow-triage" if allow_triage else "")
    settings = {"hooks": {"PreToolUse": [
        {"matcher": "Write|Edit|MultiEdit", "hooks": [
            {"type": "command", "command": gv},
            {"type": "command", "command": f"{os.path.join(kernel_bin, 'gate-ledger')} --hook"},
            {"type": "command", "command": f"{os.path.join(kernel_bin, 'gate-naming')} --hook"},
        ]},
    ]}}
    json.dump(settings, open(os.path.join(cfg_dir, "settings.json"), "w"), indent=2)
    return os.path.join(cfg_dir, "settings.json")


def _result_spend(ev):
    """Extract (cost_usd, total_tokens) from a `claude` stream-json `result` event. Cost is `total_cost_usd`
    (older CLIs emitted `cost_usd`). Tokens = the sum of the top-level `*_tokens` scalars in `usage`
    (input + output + cache read + cache creation) — the nested `cache_creation`/`server_tool_use` objects are
    dicts, so they're skipped. Pure + total-shape-faithful so the dispatch selftest proves it against the REAL
    event shape without spending a token. Returns (None, None) when the fields are absent."""
    cost = ev.get("total_cost_usd")
    if cost is None:
        cost = ev.get("cost_usd")
    usage = ev.get("usage") or {}
    tokens = sum(v for k, v in usage.items()
                 if k.endswith("_tokens") and isinstance(v, (int, float))) or None
    return cost, tokens


class HeadlessClaudeAdapter(DispatchAdapter):
    """The live OD-003 binding: launches headless Claude Code (`claude -p`) as a subprocess in the hermetic
    worktree, gates wired active, streaming tool events into the ledger, bounded by the unit's budget.

    Pinned against the June-2026 Claude Code docs (cli-reference / headless): `-p` headless; `--add-dir`
    the worktree; `--allowedTools`; `--permission-mode acceptEdits`; `--max-turns` (iterations) and
    `--max-budget-usd` (dollars) as hard stops; `--output-format stream-json` for the teeable event log;
    `--settings` to load the gate hooks. Not exercised in CI (it spends real tokens); the MockAdapter is
    the deterministic stand-in. Requires the `claude` CLI on PATH.
    """
    name = "headless-claude"

    def __init__(self, model=None, allowed_tools="Read,Edit,Write,Glob,Grep"):
        self.model = model
        self.allowed_tools = allowed_tools

    def _allowed_tools(self, unit):
        """The worker's tool scope. NO headless worker — neither the product-authoring cell-advancer NOR the
        verifier-author (rubric-architect) — carries Bash: workers author via Write/Edit, and the gate's signal-forge
        floor RESTS on that tool-scope. The redirect heuristic (_gates._BASH_WRITE_VERBS) deliberately ignores inline
        interpreters (`python3 -c open(…,'w')`) to avoid false-denying a reader's legitimate reads, so the only real
        defense against an inline-interpreter forge is that no forging worker has Bash at all (harness-council H3-C1).
        The verifier-author was the last residual surface — it kept Bash to self-calibrate the harness it writes, but
        its calibration is the downstream loop: the module is built against the verify.mjs and a broken gate fails
        validation → re-author. So it too authors blind (Write-only, denied signals/ledger/lattice AND the product
        barrel `index.mjs` via _gates.VERIFIER_AUTHOR) — zero forge surface. A `team` delegation plan adds Task to
        spawn the planned sub-agent team (the one capability a worker can't forge state through)."""
        tools = self.allowed_tools
        if ((unit.get("plan") or {}).get("delegation") or {}).get("mode") == "team":
            tools = tools + ",Task"
        return tools

    def _prompt(self, d, unit, project_root):
        tt = unit.get("transition") or {}
        # Fold the operator's recent steering guidance (the 5s channel) into THIS dispatch. A running one-shot
        # `claude -p` worker cannot receive mid-flight input, so guidance reaches the NEXT worker dispatched —
        # which is this one. Latest-last; advisory context, never a substitute for the cell's acceptance.
        guide = _api.recent_guidance(d, n=5)
        gtxt = ("\n\nRecent operator guidance (advisory context, fold in where relevant; latest last):\n"
                + "\n".join(f"- {g}" for g in guide)) if guide else ""
        # Smart retry: fold the SPECIFIC failure from a prior attempt on this cell into the prompt, so a re-authored
        # attempt fixes exactly what the critic refused instead of re-reading the contract blind (fewer attempts to
        # converge). Read from the ledger (no schema change); resets on any success.
        last_fail = _last_failure(d, unit.get("ticket"))
        ftxt = (f"\n\nYour PREVIOUS attempt on this cell FAILED its gate:\n  {last_fail}\nRe-read `verify.mjs` and make "
                "THAT specific check pass — do not repeat the same mistake.") if last_fail else ""

        # VERIFIER-AUTHORING (#2): the rubric-architect authors the cell's REAL critic harness from the spec — a
        # spec-conformance test, not a mock `ready` presence check — so reaching `validated` means the module
        # implements its contract. The module worker is gate-denied from writing verify.mjs; THIS authors it.
        if unit.get("kind") == "verifier":
            return self._verifier_prompt(d, unit, project_root, gtxt, ftxt)
        if unit.get("kind") == "refute-author":
            return self._refute_author_prompt(d, unit, project_root, gtxt, ftxt)
        if unit.get("kind") == "triage":
            return self._triage_prompt(d, unit, project_root, gtxt)

        authoring = _authoring_for({"layer": unit["layer"], "slug": unit["slug"]})
        # the INTEGRATION SHELL (a single-file root entry): the capability modules are ALREADY separate cells —
        # the shell is a thin bootstrap that imports + mounts them, authored at the product root, NOT a re-author
        # of the whole assembly. (Distinct from the legacy `is_integrator` prompt, which assumed one cell built
        # the lot — the lattice-vs-integrator mismatch that blocked the shell.)
        if authoring and authoring.get("mode") == "single-file":
            entry_rel = os.path.relpath(os.path.join(d, _asset_rel(unit["layer"], unit["slug"], authoring)), project_root)
            _cell = _lat.find(_lat.load(d), f"{unit['layer']}.{unit['scope']}.{unit['slug']}") or {}
            sibs = ", ".join(sorted({str(dep).split(".")[-1] for dep in (_cell.get("depends_on") or []) if str(dep).startswith("capability.")}))
            return (f"You are a dev-factory worker authoring the INTEGRATION SHELL at `{entry_rel}` — the product's "
                    f"runnable browser entry, at the PROJECT ROOT. The capability MODULES are ALREADY BUILT as sibling "
                    f"directories ({sibs or 'at the product root'}); do NOT re-implement them. Author a thin, runnable "
                    f"`{entry_rel}`: (a) a render surface — a `<main id=\"app\">` for a DOM app OR a `<canvas>` for a "
                    f"WebGL app; (b) a `<script type=\"module\">` that IMPORTS the modules' public API from `./<module>/…` "
                    f"(e.g. a `mount(root)` the ui module exports, or the renderer + editor) and MOUNTS the app into the "
                    f"surface ON LOAD; (c) CSS (inline or a sibling styles.css) so it looks like a real app. It MUST run "
                    f"+ render on load — the critic executes it headlessly and requires a real frame (a WebGL draw OR DOM "
                    f"mounted). Every `./…` import MUST resolve to a real sibling file. Do NOT touch `.factory/` state or "
                    f"any verify.mjs.{gtxt}{ftxt}")

        # multi-file CODE authoring (a kit's capability/code layer): author N source files to a directory, graded
        # by the cell's per-cell critic harness verify.mjs — the worker may READ its contract but CANNOT write it.
        if authoring and authoring.get("mode") == "multi-file":
            dir_rel = os.path.relpath(os.path.join(d, _asset_rel(unit["layer"], unit["slug"], authoring)), project_root)
            plan = unit.get("plan") or {}
            dele = plan.get("delegation") or {}
            # NO integrator branch. Integration is the single-file SHELL cell (authored at the product root — see
            # the single-file path above), so a capability MODULE that merely depends on another capability
            # (e.g. ui → core) is STILL just a module, not the app assembler. The old `is_integrator` prompt told
            # such modules to author index.html + main.mjs + mount(root), conflicting with the modular lattice —
            # the shell-authoring build campaign surfaced this as harmful (ui got the integrator prompt); removed.
            team = ""
            if dele.get("mode") == "team":   # the planned orchestrator-workers team (execplan) — execute it, don't just record it
                par = (plan.get("effort") or {}).get("parallelism", 1)
                team = (f" You are the ORCHESTRATOR ({plan.get('orchestration_shape', 'orchestrator-workers')} / "
                        f"{plan.get('loop_strategy', 'tracer-bullet')}): decompose this capability into independent sub-tasks "
                        f"and DELEGATE each to a sub-agent via the Task tool — to a maximum delegation depth of "
                        f"{dele.get('max_depth', 1)}, up to {par} in parallel. Each sub-agent authors part of the source; you "
                        f"integrate them and ensure the harness passes. Use the team only where it earns its keep.")
            return (f"You are a dev-factory worker building ONE capability of a shippable app: "
                    f"{unit['layer']}.{unit['scope']}.{unit['slug']}. Author its source as multiple files under "
                    f"`{dir_rel}/` to INDUSTRIAL standards: clear module boundaries, named exports, descriptive "
                    f"naming, proper levels of abstraction, no dead code. Put the testable LOGIC in pure ES modules "
                    f"the harness can import headlessly; keep rendering/DOM/canvas in a thin shell. "
                    f"REQUIRED: author an `{dir_rel}/index.mjs` ENTRY POINT that re-exports the capability's full "
                    f"public API (a barrel, e.g. `export * from './foo.mjs';`) — the critic harness imports the API "
                    f"from `./index.mjs`, so that file MUST exist and surface every declared export no matter how you "
                    f"split the internals. It MUST pass its critic harness `{dir_rel}/verify.mjs` — READ it for the "
                    f"exact contract, but you CANNOT write it (it is the critic's gate; your write is denied).{team} "
                    f"Do NOT touch the `.factory/` instance state (signals/, the ledger, rubric/, lattice.json) or any verify.mjs. "
                    f"Produce the source files INCLUDING index.mjs.{gtxt}{ftxt}")

        asset_abs = os.path.join(d, unit["layer"], f"{unit['slug']}.md")
        rel = os.path.relpath(asset_abs, project_root)             # the asset's path FROM the worker's cwd (project root)
        cur = ("\n\nCurrent asset:\n" + open(asset_abs, encoding="utf-8").read()[:4000]) if os.path.exists(asset_abs) else ""
        fmt = ""
        if unit["layer"] == "spec":
            fmt = (f' Author it as a fenced ```json block declaring: "title", "cell" ("{unit["layer"]}.{unit["scope"]}.{unit["slug"]}"), '
                   '"acceptance_criteria" (a list of {"id", and EITHER "check": an executable assertion OR "rubric_cell"}), '
                   '"non_goals" (a non-empty list), and "binds_rubric" (the bound rubric cell id). Zero prose-only criteria.')
        return (f"You are a dev-factory worker advancing exactly one lattice cell: "
                f"{unit['layer']}.{unit['scope']}.{unit['slug']} (transition {tt.get('from')} -> {tt.get('to')}). "
                f"Write its asset to the file `{rel}` (relative to your working directory).{fmt} "
                f"Do NOT touch the `.factory/` instance state (signals/, the ledger, rubric/, lattice.json) — those are "
                f"protected and your write will be denied. Produce ONLY the asset.{cur}{gtxt}{ftxt}")

    def _verifier_prompt(self, d, unit, project_root, gtxt, ftxt):
        """The RUBRIC-ARCHITECT authors a cell's REAL critic harness (verify.mjs) from the spec — a spec-
        conformance test, not a `ready` presence check (closes the presence-predicate-verifier weakness). The
        module worker is gate-denied from writing verify.mjs; this authors the CONTRACT the worker must pass."""
        slug = unit["slug"]
        dir_rel = os.path.relpath(os.path.join(d, _asset_rel("capability", slug,
                  _authoring_for({"layer": "capability", "slug": slug}))), project_root)
        spec_abs = os.path.join(d, "spec", "app.md")
        spec_txt = ("\n\nTHE SPEC (this cell's contract — author the harness to test it):\n"
                    + open(spec_abs, encoding="utf-8").read()[:4000]) if os.path.exists(spec_abs) else ""
        return (f"You are the dev-factory RUBRIC-ARCHITECT authoring the CRITIC HARNESS for the capability "
                f"`{unit['layer']}.{unit['scope']}.{slug}`. Write ONLY `{dir_rel}/verify.mjs` — a REAL "
                f"spec-conformance test (Node builtins only, an ES module). It MUST `import * as m from "
                f"'./index.mjs';` and assert the module actually IMPLEMENTS its contract: the named exports the "
                f"spec requires exist and are the right kind, AND — where the logic is pure + testable — that they "
                f"produce CORRECT results on concrete inputs (known values, round-trips, immutability, edge cases). "
                f"Do NOT settle for `ready === true` — a presence check is exactly what this REPLACES. On any "
                f"failure `console.error('FAIL: …'); process.exit(1)`; on success `console.log('pass — …'); "
                f"process.exit(0)`. The module may not exist yet — you author the GATE it must pass, so test the "
                f"CONTRACT (the spec), not one implementation, and don't over-fit to internals. "
                f"If the module RENDERS to the DOM (functions that take a root element, or that use `document`), Node "
                f"has NO DOM — author a minimal shim at the top of verify.mjs: set `globalThis.document` to a stub "
                f"whose `createElement` returns a RECORDING element (tracks `appendChild`/`append`/`textContent`/"
                f"`innerHTML`/`addEventListener`/`setAttribute`), plus `getElementById`/`querySelector`; then CALL each "
                f"render function with a mock root + the callbacks it expects and ASSERT it actually mounted something "
                f"(appended children or set content) and wired its handlers. Do NOT skip DOM functions with a bare "
                f"`ready` check — that punt is exactly the presence-predicate this replaces. "
                f"Author ONLY `{dir_rel}/verify.mjs`; do NOT author the module or touch `.factory/` state.{spec_txt}{gtxt}{ftxt}")

    def _refute_author_prompt(self, d, unit, project_root, gtxt, ftxt):
        """The REFUTE-AUTHOR (a rubric-architect role, BLIND TO THE GATE) authors the cell's behavioral REFUTE set —
        the HIDDEN independent oracle that re-checks a validated module on inputs its gate never used. This is the
        producer that makes Tier 2 AUTONOMOUSLY earnable: until now the measuring refute set was hand-authored, so a
        cell stayed `unmeasured` (Tier 1) until a human wrote one. The dispatch is wired with gate-verifier
        --allow-refute: it may write ONLY `coordination/verify-spec/<cell>.json`; verify.mjs (the gate), the refuter
        sidecars, signals, the lattice/ledger, and the product barrel are all denied. INDEPENDENCE is the whole point
        — it derives from the SPEC, not the gate (which it is not shown), on DIFFERENT inputs, or the server's
        calibration (is_behavioral · _refuter_discriminates · independent_of_gate) rejects the set and the cell stays
        honestly unmeasured. No claim of doneness is the author's; the calibration + the live re-check decide."""
        cell_id = unit["target_cell"]
        spec_path = os.path.join(d, "coordination", "verify-spec", f"{cell_id}.json")
        exports = []
        if os.path.isfile(spec_path):
            try:
                exports = (json.load(open(spec_path, encoding="utf-8")) or {}).get("exports") or []
            except (OSError, ValueError):
                pass
        spec_abs = os.path.join(d, "spec", "app.md")
        spec_txt = ("\n\nTHE SPEC (the cell's contract — derive EVERY refute check from THIS, never from the gate):\n"
                    + open(spec_abs, encoding="utf-8").read()[:4000]) if os.path.exists(spec_abs) else ""
        spec_rel = os.path.relpath(spec_path, project_root)
        exp_txt = (" The cell exports: " + ", ".join(f"`{e}`" for e in exports if isinstance(e, str)) + ".") if exports else ""
        return (f"You are the dev-factory REFUTE-AUTHOR for the capability `{cell_id}` — you author the HIDDEN "
                f"INDEPENDENT ORACLE that re-checks this module AFTER it has passed its own gate.{exp_txt} Edit ONLY "
                f"the JSON file `{spec_rel}`: set its `refute` field to a JSON array of 3-6 BEHAVIORAL boolean "
                f"JavaScript assertion STRINGS over the exports, preserving the other fields (`exports`, `acceptance`, "
                f"`generation`, `history`). Each assertion MUST (a) CALL an export with CONCRETE inputs and assert a "
                f"SPECIFIC VALUE (e.g. `\"createDeck().length === 52\"`, `\"add(7, 8) === 15\"`, "
                f"`\"reverse([1,2,3])[0] === 3\"`) — never a `typeof`/shape probe, never identical operands "
                f"(`x()===x()`); (b) hold for a SPEC-CONFORMANT module and FAIL for a wrong one.\n"
                f"CRITICAL — INDEPENDENCE: you are deliberately NOT shown `verify.mjs` (the gate). Derive every check "
                f"from THE SPEC and choose DIFFERENT concrete inputs than an obvious gate would pick — the oracle's "
                f"job is to catch a module that OVERFIT to the gate's exact inputs, so a check that merely restates "
                f"the gate measures nothing and is rejected. Do NOT read or guess at verify.mjs; do NOT author the "
                f"module, signals, the refuter, or any other file. The server independently calibrates your set (it "
                f"must genuinely disagree with a wrong module) — a vacuous or gate-copying set earns nothing and the "
                f"cell stays at Tier 1.{spec_txt}{gtxt}{ftxt}")

    def _triage_prompt(self, d, unit, project_root, gtxt):
        """The TICKET-TRIAGER turns a free-text intake (a prompt/issue) into a BOUND, dispatchable ticket — the
        producer that lets a prompt move the loop forward with no human triage. It is pure JUDGMENT: it reads the
        intake + the lattice and PROPOSES a binding (target_cell + a legal transition + a VALIDATED rubric_cell),
        writing ONLY `coordination/triage/<tid>.json`. It has zero authority over state — the single-writer server
        reads the proposal and applies it, and `gate-ticket-ready` decides legality (an illegal transition or an
        unvalidated rubric is REFUSED server-side and the ticket parks; the triager never forces anything)."""
        intake = unit.get("intake") or {}
        tid = unit["ticket"]
        title = intake.get("title") or ""
        body = (intake.get("body") or "")[:2000]
        proposal_rel = os.path.relpath(os.path.join(d, "coordination", "triage", f"{tid}.json"), project_root)
        lattice_rel = os.path.relpath(os.path.join(d, "lattice.json"), project_root)
        return (f"You are the dev-factory TICKET-TRIAGER. Turn this free-text intake into ONE well-formed, "
                f"dispatchable ticket binding — do NOT write any product code.\n\n"
                f"INTAKE (ticket {tid}):\n  title: {title}\n  body: {body}\n\n"
                f"Read the lattice at `{lattice_rel}` (READ-only — your write to it is denied). Pick the SINGLE "
                f"thinnest EXISTING cell whose advancement satisfies this intake (prefer the cell that already "
                f"OWNS the asset the intake is about; do not invent a new cell). Choose a LEGAL maturity "
                f"transition for it: a cell's maturity advances absent->defined->instantiated->validated->"
                f"operating, plus the rework edge validated->regenerating and the re-validation regenerating->"
                f"validated. The `from` MUST equal the cell's CURRENT maturity in the lattice. Bind acceptance to "
                f"an EXISTING rubric cell that is already `validated` (doneness is a validated rubric, never prose). "
                f"If you cannot bind this intake to ONE cell (it needs decomposition into many), or no validated "
                f"rubric fits, write a proposal whose `target_cell` is null with a `reason` — it will park for a "
                f"human rather than bind something wrong.\n\n"
                f"Write your proposal as JSON to `{proposal_rel}` and NOTHING else (every other write is denied). "
                f"Shape:\n"
                f'{{"new_type": "feature"|"task"|"bug", "target_cell": "<layer>.<scope>.<slug>", '
                f'"target_transition": {{"from": "<current maturity>", "to": "<legal next maturity>"}}, '
                f'"acceptance": {{"rubric_cell": "rubric.<scope>.<slug>"}}, '
                f'"budget": {{"iterations": 3, "tokens": 60000}}, '
                f'"dependencies": {{"cells": []}}, "priority": {{"risk": 0.5, "unlock": 0.5}}}}\n'
                f"`gate-ticket-ready` will reject an illegal transition, a missing/non-validated rubric, or an "
                f"unknown cell — so bind something REAL and LEGAL, or park it with target_cell null.{gtxt}")

    def dispatch(self, d, unit):
        if shutil.which("claude") is None:
            return {"ok": False, "error": "the `claude` CLI is not on PATH", "metrics": {}}
        # the worker runs from the PROJECT ROOT so the product lands in the clean tree the critic validates,
        # and the gates' protected `.factory/` globs match the worker's writes.
        project_root = os.path.dirname(os.path.dirname(d.rstrip("/")))
        settings = wire_gates(unit["worktree"], _api._store._KERNEL_BIN,
                              allow_verify=(unit.get("kind") == "verifier"),
                              allow_refute=(unit.get("kind") == "refute-author"),
                              allow_triage=(unit.get("kind") == "triage"))
        budget = unit.get("budget") or {}
        effort = (unit.get("plan") or {}).get("effort") or {}          # the assembled execution plan's effort ladder
        max_turns = effort.get("max_iterations") or budget.get("iterations", 10)
        model = self.model or {"small": "haiku", "mid": "sonnet", "large": "opus"}.get(effort.get("model_tier"))
        # DF-4: the kit's bin/ holds the real meta-verifiers (rubric-check / spec-quality-check / doc-check) the
        # worker must RUN, not eyeball — but it lives in the plugin source, outside project_root. Grant read
        # access so an agent can locate + execute its gate instead of self-attesting (the generator/critic split
        # the kernel exists to enforce). The worker reads `${DEV_FACTORY_KIT}/bin/…`; project writes still land
        # in the instance (only the asset dir is writable; the kit is read-only here).
        kit_dir = os.environ.get("DEV_FACTORY_KIT")
        kit_add = ["--add-dir", os.path.abspath(kit_dir)] if kit_dir and os.path.isdir(kit_dir) else []
        cmd = ["claude", "-p", self._prompt(d, unit, project_root),
               "--add-dir", project_root,                        # the project (incl. the instance) the worker reads/writes
               *kit_add,                                         # the bound kit (its bin/ verifiers), read-only — DF-4
               "--allowedTools", self._allowed_tools(unit),
               "--permission-mode", "acceptEdits",
               "--max-turns", str(max_turns),
               "--output-format", "stream-json", "--verbose",
               "--settings", settings]
        # ALWAYS pass a per-dispatch dollar cap — a single headless run is never unbounded. The ticket's `dollars`
        # wins; absent it, DEV_FACTORY_DISPATCH_USD (default $10) is the per-dispatch ceiling (H5-C3: the cap used to
        # be appended ONLY when a ticket set `dollars`, and the default ticket budget sets none → uncapped by default).
        per_dispatch_usd = budget.get("dollars") or float(os.environ.get("DEV_FACTORY_DISPATCH_USD", "10"))
        cmd += ["--max-budget-usd", str(per_dispatch_usd)]
        if model:
            cmd += ["--model", model]
        try:
            proc = subprocess.run(cmd, cwd=project_root, capture_output=True, text=True,
                                  timeout=budget.get("wallclock_seconds", 600))
        except (OSError, subprocess.SubprocessError) as e:
            return {"ok": False, "error": str(e), "metrics": {}}
        cost, tokens = None, None
        for line in (proc.stdout or "").splitlines():       # tee the stream-json events into the ledger
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            et = ev.get("type")
            if et in ("tool_use", "tool_result", "assistant"):
                _led.append(d, "activity-start" if et == "tool_use" else "handoff",
                            {"kind": "agent", "id": "headless-claude"}, {"ticket": unit["ticket"], "cell": unit["target_cell"]},
                            f"{et}: {ev.get('tool_name', '')}".strip()[:200] or et)
            if et == "result":
                cost, tokens = _result_spend(ev)
        # Success is "the worker PRODUCED an artifact", NOT "claude exited 0". A real authoring run very often
        # exits non-zero (it hits --max-turns, or errors late AFTER writing a valid asset) — gating on the exit
        # code wrongly marks that a failure and blocks the cell, even though the artifact is on disk and the REAL
        # gate (validate.py running the cell's verifier) would pass it. The verdict belongs to the external critic,
        # not the worker's process code — so `ok` means "an asset exists to validate"; the exit code is advisory
        # metrics. (A crash that writes nothing → no asset → correctly failed.) Authoring-aware: a multi-file
        # capability produces a DIRECTORY of source (anything but its critic harness), a doc/spec a single `.md`.
        if unit.get("kind") == "refute-author":
            # produced = the verify-spec now carries a NON-EMPTY behavioral refute set (the oracle's source). The
            # server still independently CALIBRATES it (produce_refuter); authoring it is not the same as it MEASURING.
            asset_rel = os.path.join("coordination", "verify-spec", f"{unit['target_cell']}.json")
            try:
                refute = (json.load(open(os.path.join(d, asset_rel), encoding="utf-8")) or {}).get("refute") or []
            except (OSError, ValueError):
                refute = []
            produced = bool(refute)
            err = None if produced else f"no refute set authored into the verify-spec (claude exited {proc.returncode})"
            return {"ok": produced, "asset_ref": asset_rel, "error": err,
                    "metrics": {"cost_usd": cost, "tokens": tokens, "exit": proc.returncode}}
        if unit.get("kind") == "verifier":
            asset_rel = os.path.join(_asset_rel("capability", unit["slug"],                # the critic harness FILE
                        _authoring_for({"layer": "capability", "slug": unit["slug"]})), "verify.mjs")
            asset_abs = os.path.join(d, asset_rel)
            produced = os.path.isfile(asset_abs) and os.path.getsize(asset_abs) > 0
            err = None if produced else f"no verify.mjs authored (claude exited {proc.returncode})"
            return {"ok": produced, "asset_ref": asset_rel, "error": err,
                    "metrics": {"cost_usd": cost, "tokens": tokens, "exit": proc.returncode}}
        if unit.get("kind") == "triage":
            # produced = the triager wrote a parseable proposal carrying a target_cell. The server (triage_intake →
            # _apply_triage_proposal) still validates + applies it through gate-ticket-ready; producing it is not the
            # same as it being LEGAL. A `target_cell: null` park-proposal is a valid (ok) outcome — the triager
            # honestly declined to bind — so `ok` means "a proposal exists to act on", not "a binding was made".
            asset_rel = os.path.join("coordination", "triage", f"{unit['ticket']}.json")
            try:
                prop = json.load(open(os.path.join(d, asset_rel), encoding="utf-8"))
                produced = isinstance(prop, dict)
            except (OSError, ValueError):
                produced = False
            err = None if produced else f"no triage proposal authored (claude exited {proc.returncode})"
            return {"ok": produced, "asset_ref": asset_rel, "error": err,
                    "metrics": {"cost_usd": cost, "tokens": tokens, "exit": proc.returncode}}
        authoring = _authoring_for({"layer": unit["layer"], "slug": unit["slug"]})
        if authoring and authoring.get("mode") == "single-file":
            asset_rel = _asset_rel(unit["layer"], unit["slug"], authoring)              # the entry FILE (e.g. ../index.html)
            asset_abs = os.path.join(d, asset_rel)
            produced = os.path.isfile(asset_abs) and os.path.getsize(asset_abs) > 0
        elif authoring and authoring.get("mode") == "multi-file":
            asset_rel = _asset_rel(unit["layer"], unit["slug"], authoring)              # a source DIRECTORY (kit-rooted)
            asset_abs = os.path.join(d, asset_rel)
            produced = os.path.isdir(asset_abs) and any(
                f != "verify.mjs" and not f.startswith(".") for f in os.listdir(asset_abs))
        else:
            asset_rel = os.path.join(unit["layer"], f"{unit['slug']}.md")
            asset_abs = os.path.join(d, asset_rel)
            produced = os.path.exists(asset_abs) and os.path.getsize(asset_abs) > 0
        err = None if produced else f"no artifact (claude exited {proc.returncode}, asset {asset_rel} absent/empty)"
        return {"ok": produced, "asset_ref": asset_rel, "error": err,
                "metrics": {"cost_usd": cost, "tokens": tokens, "exit": proc.returncode}}


def resolve_adapter(name=None, model=None):
    """Select the dispatch adapter the server's heartbeat runs. `DEV_FACTORY_ADAPTER=headless` picks the LIVE
    `claude -p` worker (real tokens, gated on the armed run budget + the per-cell gates); the default `mock` is
    deterministic + free. Default mock so a Walk loop NEVER spends tokens unless the operator explicitly opts in."""
    name = (name or os.environ.get("DEV_FACTORY_ADAPTER") or "mock").lower()
    if name == "headless":
        return HeadlessClaudeAdapter(model=model)
    return MockAdapter()


def adapter_name():
    """The adapter the server would dispatch with — surfaced to the dashboard so the operator knows whether a run
    spends real tokens (`headless`) or is the free mock loop (`mock`)."""
    return "headless" if (os.environ.get("DEV_FACTORY_ADAPTER") or "mock").lower() == "headless" else "mock"


def _verifier_for(unit):
    """The asset-exists default verifier (exit 0 iff the worker produced the artifact) — used when no kit is
    bound. A kit's validation adapter supplies the real verifier; see _kit_verifier."""
    if unit.get("verifier"):
        return unit["verifier"]
    asset_abs = os.path.join(unit["dir"], unit["layer"], f"{unit['slug']}.md")
    return ["python3", "-c", f"import os,sys; sys.exit(0 if os.path.exists({asset_abs!r}) else 1)"]


def _kit_verifier(d, cell, unit, kit_dir=None):
    """Resolve the bound kit's validation-adapter verifier for this cell's layer, with {asset}/{worktree}/
    {cell}/${CLAUDE_PLUGIN_ROOT} substituted. None when no kit is bound (DEV_FACTORY_KIT unset) or no
    adapter matches the layer — the dispatcher then falls back to the asset-exists default. This is what
    makes 'validated' MEAN the family's real rubric (e.g. spec-quality-check), not just 'a file exists'."""
    kit_dir = kit_dir or os.environ.get("DEV_FACTORY_KIT")
    if not kit_dir:
        return None
    try:
        kit = json.load(open(os.path.join(kit_dir, "kit.json"), encoding="utf-8"))
    except (OSError, ValueError):
        return None
    asset = os.path.normpath(os.path.join(d, cell.get("asset_ref")
                             or _asset_rel(cell["layer"], cell["slug"], _authoring_for(cell, kit_dir))))
    # Match by layer; a slug-specific adapter (e.g. the app-shell coherence gate for capability.*.shell) is
    # MORE SPECIFIC and wins over the layer-default (the generic capability-harness), regardless of list order.
    chosen = None
    for a in kit.get("adapters", []):
        if a.get("kind") != "validation":
            continue
        tgt = a.get("target") or {}
        if tgt.get("layer") != cell["layer"]:
            continue
        if tgt.get("slug"):
            if tgt["slug"] == cell["slug"]:
                chosen = a
                break
        elif chosen is None:
            chosen = a
    if chosen:
        return [tok.replace("${CLAUDE_PLUGIN_ROOT}", kit_dir).replace("{asset}", asset)
                .replace("{worktree}", unit.get("worktree", "")).replace("{cell}", _lat.cid(cell))
                for tok in chosen.get("verifier", [])]
    return None


def author_verifier(d, cell, adapter, repo_root=None):
    """Author a capability cell's critic harness via the FACTORY (the rubric-architect role) — a real
    spec-conformance `verify.mjs`, not a mock `ready` stub nor an operator-hand-authored one. The mock adapter
    writes a smoke check; a headless worker writes a real test FROM THE SPEC (HeadlessClaudeAdapter._verifier_
    prompt). The module worker stays gate-denied from writing verify.mjs. This is the #2 fix: the loop's
    legitimacy stops resting on a seeded presence-predicate; the factory authors the contract-as-test. Run it
    BEFORE the capability cell builds, so the worker's module is graded against a real gate. Returns the
    dispatch result {ok, asset_ref, ...}."""
    unit = {"layer": cell["layer"], "scope": cell["scope"], "slug": cell["slug"], "kind": "verifier",
            "target_cell": f"{cell['layer']}.{cell['scope']}.{cell['slug']}",   # the ledger-tee keys off this
            "ticket": cell.get("ticket", "rubric-author"), "dir": d, "worktree": cell.get("worktree", repo_root or d)}
    return adapter.dispatch(d, unit)


def author_app_verifiers(d, slugs, adapter, repo_root=None, scope="system"):
    """The VERIFIER-AUTHOR PASS: run the rubric-architect over each capability cell's critic harness BEFORE the
    modules build, each in its own provisioned worktree (gate-permitted to write verify.mjs). After this, every
    listed cell is graded against a real, spec-derived gate instead of a mock `ready` stub — so a module that
    deviates from its spec'd contract is REFUSED, not rubber-stamped (#2). Run it ahead of the build tickets.
    Returns {slug: ok}."""
    results = {}
    for slug in slugs:
        wt, _ = provision_worktree(d, f"capability.{scope}.{slug}", "rubric-architect", repo_root)
        try:
            r = author_verifier(d, {"layer": "capability", "scope": scope, "slug": slug, "worktree": wt,
                                    "ticket": f"verifier-{slug}"}, adapter, repo_root)
            results[slug] = bool(r.get("ok"))
        finally:
            teardown_worktree(d, wt, repo_root)
    return results


def author_refuter(d, cell, adapter, repo_root=None):
    """Author a validated cell's behavioral REFUTE set via the FACTORY (the rubric-architect role, BLIND TO THE
    GATE) — the autonomous producer that makes Tier 2 EARNABLE without a human. It writes the verify-spec's `refute`
    field (gate-verifier --allow-refute boundary); the server's produce_refuter then independently CALIBRATES it
    (is_behavioral · _refuter_discriminates · independent_of_gate) and only a set that clears all three UPGRADES the
    cell's liveness floor to a MEASURING oracle. A vacuous or gate-copying set changes nothing — the cell stays
    honestly unmeasured. Run it on a validated CODE cell whose refuter is still liveness-only. Returns the dispatch
    result {ok, asset_ref, ...}."""
    unit = {"layer": cell["layer"], "scope": cell["scope"], "slug": cell["slug"], "kind": "refute-author",
            "target_cell": f"{cell['layer']}.{cell['scope']}.{cell['slug']}",
            "ticket": cell.get("ticket", "refute-author"), "dir": d, "worktree": cell.get("worktree", repo_root or d)}
    return adapter.dispatch(d, unit)


def author_refuters(d, adapter, repo_root=None, scope="system", limit=None):
    """The REFUTE-AUTHOR PASS: run the gate-blind refute-author over validated CODE cells whose refuter is still
    LIVENESS-only (`refute_author_frontier`), each in its own worktree, then re-run produce_refuter so a set that
    passes calibration upgrades the cell to MEASURING. After this pass the cells that earned a real behavioral oracle
    count toward `false_pass` — the missing producer that lets the factory earn Tier 2 autonomously. Mock authors no
    oracle (it cannot synthesize a domain contract), so this is a real-build (headless) step. `limit` caps how many
    cells are authored this call (the heartbeat passes 1 — one dispatch per tick keeps the loop cheap + budget-bounded).
    Returns {cell: newly_measuring?}."""
    results = {}
    frontier = refute_author_frontier(d)
    if limit is not None:
        frontier = frontier[:limit]
    for cell_id in frontier:
        cell = _lat.find(_lat.load(d), cell_id)
        if not cell:
            continue
        wt, _ = provision_worktree(d, cell_id, "refute-author", repo_root)
        snap = _verify_spec_hashes(d)   # snapshot BEFORE the dispatch, to register what it actually WROTE
        try:
            rr = author_refuter(d, {**cell, "worktree": wt, "ticket": f"refute-{cell.get('slug')}"}, adapter, repo_root) or {}
        finally:
            teardown_worktree(d, wt, repo_root)
        # COUNT the refute-author dispatch's spend against the armed window — same H5-C1 class as triage / the
        # verifier-author pass: the adapter returns cost_usd/tokens; ledger them so the token/dollar ceiling sees them
        # (a real `claude -p` refute-author per tick was otherwise an uncounted spend the budget never saw).
        if rr.get("metrics"):
            _led.append(d, "handoff", {"kind": "agent", "id": "refute-author"}, {"cell": cell_id},
                        "refute-author dispatch spend", metrics={"refute_author": True, **rr["metrics"]})
        # Register EVERY cell whose verify-spec the dispatch CREATED OR CHANGED — NOT just the nominal target. The
        # --allow-refute gate permits writing ANY `coordination/verify-spec/*` (the per-cell scope is prompt-only), so
        # a dispatch targeting X could write a SIBLING Y's verify-spec to LAUNDER a machine-authored oracle onto an
        # unregistered (→ "trusted") cell (harness-council round 6 CRITICAL). Diffing what was written closes it: the
        # module worker is gate-denied verify-spec entirely, so the ONLY worker writes here are this dispatch's — every
        # one is provenance-stamped autonomous, wherever its measuring upgrade later lands.
        after = _verify_spec_hashes(d)
        for changed in [c for c in after if after[c] != snap.get(c)]:
            _register_autonomous(d, changed)
        before = _measuring_now(d, cell_id)
        produce_refuter(d, cell_id)   # stamps autonomous:true from the registry if it upgrades to measuring
        results[cell_id] = _measuring_now(d, cell_id) and not before
    return results


def _triage_attempts(d, tid):
    """How many times the auto-triager has already FAILED to produce a usable/legal binding for this intake —
    counted from `triage-attempt` ledger entries. The anti-livelock bound: a prompt the triager genuinely cannot
    bind parks for a human after a couple of tries instead of burning a dispatch every tick."""
    return sum(1 for e in _led.read(d) if e.get("event") == "triage-attempt"
               and (e.get("subject") or {}).get("ticket") == tid)


def triage_frontier(d):
    """Oldest-first untriaged INTAKE awaiting auto-triage: type in {issue, prompt} (NOT `instruction` — those fold
    into operator guidance, not a cell binding), no `target_cell`, still in `draft`. Skips a ticket with >= 2 prior
    `triage-attempt` entries (it parks for a human). This is the producer frontier the loop's auto-triage consumes —
    the missing wire that lets a free-text prompt become a dispatchable ticket without a human filling the form."""
    out = [t for t in _api.list_tickets(d)
           if t.get("type") in ("issue", "prompt") and not t.get("target_cell")
           and t.get("state") == "draft" and _triage_attempts(d, t["id"]) < 2]
    out.sort(key=lambda t: (t.get("timestamps") or {}).get("created") or "")
    return [t["id"] for t in out]


def _apply_triage_proposal(d, tid):
    """Read the triage-author's PROPOSAL (`coordination/triage/<tid>.json`) and apply it through the single-writer
    server (`api.triage_issue`), then attempt draft->active. The proposal is JUDGMENT with no authority: a
    missing/malformed proposal, a `target_cell: null` park, an applier rejection, OR a `gate-ticket-ready` refusal
    all leave the ticket PARKED and ledger a `triage-attempt` (never a crash, never an in-tick retry). Returns a
    summary {applied, active, reason}."""
    p = os.path.join(d, "coordination", "triage", f"{tid}.json")
    try:
        prop = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        prop = None
    def _park(reason):
        _led.append(d, "triage-attempt", {"kind": "agent", "id": "ticket-triager"}, {"ticket": tid},
                    f"triage parked: {reason}")
        return {"applied": False, "active": False, "reason": reason}
    if not isinstance(prop, dict) or not prop.get("target_cell"):
        # no proposal, or the triager honestly DECLINED to bind (target_cell null) — park for a human
        return _park((prop or {}).get("reason") if isinstance(prop, dict) else "no usable proposal authored")
    t, msg = _api.triage_issue(d, tid, prop.get("new_type", "feature"), prop["target_cell"],
                               prop.get("target_transition"), prop.get("acceptance"),
                               budget=prop.get("budget"), dependencies=prop.get("dependencies"),
                               priority=prop.get("priority"))
    if t is None:
        return _park(f"applier rejected the proposal: {msg}")
    ok, _t, amsg = _api.transition_ticket(d, tid, "active", {"kind": "agent", "id": "ticket-triager"})
    if not ok:
        # bound (the type/cell changed, so it leaves the triage frontier) but gate-ticket-ready refused active:
        # an illegal transition / non-validated rubric. It rests as a typed draft for a human, not re-triaged.
        _led.append(d, "triage-attempt", {"kind": "agent", "id": "ticket-triager"},
                    {"ticket": tid, "cell": prop["target_cell"]},
                    f"triaged but gate-ticket-ready refused active (parked): {amsg}")
        return {"applied": True, "active": False, "reason": amsg}
    _led.append(d, "transition", {"kind": "agent", "id": "ticket-triager"},
                {"ticket": tid, "cell": prop["target_cell"]},
                f"auto-triaged {tid} -> active, bound to {prop['target_cell']}")
    return {"applied": True, "active": True, "reason": "active"}


def triage_intake(d, adapter, repo_root=None, limit=1):
    """The AUTO-TRIAGE PASS: run the gate-blind ticket-triager over the oldest untriaged prompt/issue intake
    (`triage_frontier`), each in its own worktree, to PROPOSE a binding (target_cell + a legal transition + a
    validated rubric); the server then applies it via `_apply_triage_proposal` (api.triage_issue + draft->active,
    gate-ticket-ready deciding). This is the producer that makes a free-text prompt MOVE THE LOOP with no human
    triage. Mock cannot read a prompt and reason about which cell/rubric binds it (judgment, not a transform), so —
    exactly like `author_refuters` — it is a real-build (headless) step and a HARD no-op on mock. `limit` caps how
    many intakes are triaged per call (the heartbeat passes 1 — one judgment per tick keeps the loop cheap +
    budget-bounded). Returns {tid: {applied, active, reason}}."""
    if getattr(adapter, "name", "mock") == "mock":
        return {}                       # belt-and-suspenders to the heartbeat call-site headless gate
    results = {}
    for tid in triage_frontier(d)[:limit]:
        t = _api.get_ticket(d, tid)
        if not t:
            continue
        # Only THIS dispatch's write may be applied: clear any stale/planted proposal for tid FIRST, so a triage
        # dispatch for a SIBLING ticket that wrote coordination/triage/<tid>.json cannot launder a binding onto tid
        # (the --allow-triage gate permits writing any coordination/triage/*; the per-tid scope is prompt-only, so
        # this server-side clear is what makes every applied proposal one THIS dispatch authored — the same
        # provenance discipline author_refuters enforces by diffing what it wrote).
        prop_path = os.path.join(d, "coordination", "triage", f"{tid}.json")
        if os.path.exists(prop_path):
            os.remove(prop_path)
        wt, _ = provision_worktree(d, f"triage--{tid}", "ticket-triager", repo_root)
        unit = {"kind": "triage", "ticket": tid, "target_cell": None, "intake": t,
                "worktree": wt, "dir": d}
        try:
            res = adapter.dispatch(d, unit) or {}
        finally:
            teardown_worktree(d, wt, repo_root)
        # COUNT the triage dispatch's spend against the armed window (H5-C1): a `claude -p` triager spends real tokens;
        # the adapter returns cost_usd/tokens — ledger them on a metrics-bearing event so heartbeat._tokens_since /
        # _cost_since see them (exactly as the verifier-author pass does). Else triage burned tokens the budget never saw.
        if res.get("metrics"):
            _led.append(d, "handoff", {"kind": "agent", "id": "ticket-triager"}, {"ticket": tid},
                        "triage dispatch spend", metrics={"triage": True, **res["metrics"]})
        results[tid] = _apply_triage_proposal(d, tid)
    return results


def _verify_spec_hashes(d):
    """{cell_id: content-hash} for every verify-spec on disk — a snapshot to diff what a refute-author dispatch wrote,
    so provenance is registered for the cells actually AUTHORED, not the loop's nominal target (closes the cross-cell
    laundering forge)."""
    import hashlib
    out = {}
    vdir = os.path.join(d, "coordination", "verify-spec")
    try:
        names = os.listdir(vdir)
    except OSError:
        return out
    for n in names:
        if n.endswith(".json"):
            try:
                out[n[:-5]] = hashlib.md5(open(os.path.join(vdir, n), "rb").read()).hexdigest()
            except OSError:
                pass
    return out


def _autonomous_registry_path(d):
    return os.path.join(d, "run", "autonomous-oracles.json")


def _is_autonomous_cell(d, cell_id):
    """True iff this cell's refute oracle was AUTONOMOUSLY authored (recorded in the server-owned registry). Drives
    the sidecar's `autonomous` stamp → the human-glance gate. Reads a worker-PROTECTED file (run/* ∈ VERIFIER), so a
    worker cannot clear its own autonomous mark to dodge the gate."""
    try:
        return cell_id in set(json.load(open(_autonomous_registry_path(d), encoding="utf-8")) or [])
    except (OSError, ValueError):
        return False


def _register_autonomous(d, cell_id):
    """Record (server-side, in the worker-protected run/ perimeter) that this cell's refute oracle is AUTONOMOUSLY
    authored — so produce_refuter stamps `autonomous: true` no matter WHERE the measuring upgrade lands (the author
    pass OR a later sweep). SERVER-determined (only author_refuters calls this), never a worker claim; the verify-spec
    is worker-writable, this registry is not."""
    p = _autonomous_registry_path(d)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    try:
        cur = set(json.load(open(p, encoding="utf-8")) or [])
    except (OSError, ValueError):
        cur = set()
    cur.add(cell_id)
    json.dump(sorted(cur), open(p, "w", encoding="utf-8"), indent=2)


def _measuring_now(d, cell_id):
    """True iff the cell's refuter sidecar is currently a MEASURING oracle — the post-calibration state, read from
    disk (never the author's claim)."""
    side = os.path.join(d, "coordination", "refuters", f"{cell_id}.json")
    try:
        return bool((json.load(open(side, encoding="utf-8")) or {}).get("measuring"))
    except (OSError, ValueError):
        return False


_MOCK_VERIFIER_MARK = "dev-factory:mock-verifier"  # sentinel every seed/mock-authored stub stamps; a real harness omits it


def _exercises_export(src):
    """True if a verify.mjs CALLS a module export other than `ready` (`m.saveForge(…)`, `m.createGallery()`) —
    the behavioral signature of a real spec-conformance harness. A presence stub only READS `m.ready`/`ready`,
    so it never matches. The rubric-architect prompt mandates the `import * as m` namespace form, so a real
    harness's exercises always surface as `m.<name>(`."""
    for seg in src.split("m.")[1:]:
        name = ""
        for ch in seg:
            if ch.isalnum() or ch == "_":
                name += ch
            else:
                break
        if name and name != "ready" and seg[len(name):].lstrip().startswith("("):
            return True
    return False


def _is_mock_verifier(d, cell):
    """True iff a multi-file capability cell's per-cell verify.mjs is still a SEED/mock stub (a presence check),
    or is missing — i.e. not yet a real, spec-derived harness. Detection is the explicit `_MOCK_VERIFIER_MARK`
    sentinel OR a behavioral test (imports the product but never CALLS an export) — NOT the old `import { ready }`
    + `<6 lines` heuristic, which missed the MockAdapter's `import * as m` smoke stub (so a mock build's gate
    posed as 'real' on the next headless run) and waved through any long-but-vacuous harness (harness-council
    H2-M2). The shell (single-file, render-gated) and doc cells return False. Drives the verifier-author DEFAULT."""
    authoring = _authoring_for(cell)
    if not authoring or authoring.get("mode") != "multi-file":
        return False
    vpath = os.path.normpath(os.path.join(d, _asset_rel(cell["layer"], cell["slug"], authoring), "verify.mjs"))
    try:
        src = open(vpath, encoding="utf-8").read()
    except OSError:
        return True
    if _MOCK_VERIFIER_MARK in src:
        return True
    if "index.mjs" not in src and "./" not in src:   # doesn't even import the product — not a recognizable harness
        return True
    return not _exercises_export(src)


# ─────────────────────────────────── the dispatch loop ───────────────────────────────────

def _activity_kind(to_mat):
    return {"defined": "define", "instantiated": "create", "validated": "validate",
            "regenerating": "regenerate", "operating": "author"}.get(to_mat, "author")


def dispatch_unit(d, ticket, adapter, actor, tier=1, repo_root=None, auto_validate=True, policy=None):
    """Drive one ticket active→done. ASSEMBLE the execution plan from the kit's dispatch policy (execplan),
    pick the worker by roster, provision a worktree, claim (single-writer), run the worker, emit the activity
    span (the agent/activity lens), then let the critic validate. Returns (ok, ticket, msg). At Tier 1 a human
    reviews at in-review; Tier 2+ runs to done unattended."""
    tid = ticket["id"]
    cell = _lat.find(_lat.load(d), ticket["target_cell"])
    if cell is None:
        return False, ticket, f"target_cell {ticket['target_cell']} missing"
    to_mat = (ticket.get("target_transition") or {}).get("to")
    # OVERWRITE GUARD (adapter-independent, fires BEFORE any worker runs): the loop must never silently
    # re-author a SETTLED cell. Re-dispatching a `validated`/`operating` cell would clobber a hand-authored,
    # already-shipped asset — e.g. a real `index.html` shell — with a fresh (or mock-stub) author. The ONLY
    # legal re-author of a settled cell is a deliberate un-ship (-> regenerating) or the operating promotion;
    # any other target on a settled cell is refused and the ticket is BLOCKED so it drops out of the frontier
    # and surfaces to the operator (who un-ships the cell to `regenerating` first if a real rework is intended).
    # This is what lets the autonomous loop be pointed at a real product without destroying it (and it closes
    # the lease-reaper re-activation of an already-validated ticket as a re-clobber path).
    if cell.get("maturity") in _lat.SETTLED and to_mat not in ("regenerating", "operating"):
        _api.transition_ticket(d, tid, "blocked", actor,
                               reason=f"overwrite guard: {ticket['target_cell']} is {cell['maturity']} — "
                                      "un-ship it to regenerating before re-authoring")
        _api._store.rebuild(d)
        return False, _api.get_ticket(d, tid), (f"refusing to re-author {ticket['target_cell']}: cell is "
                f"{cell['maturity']} — un-ship it to regenerating to re-author (overwrite guard)")
    policy = policy if policy is not None else resolve_policy(d)
    plan, plan_src = _ep.plan_for(policy, ticket, cell, tier)     # HOW the unit runs — deterministic policy
    agent = agent_for(cell, to_mat)                              # WHO advances it — roster
    worker_id = _led.ulid("wrk-")
    act_id = _led.ulid("act-")
    wt, hermetic = provision_worktree(d, ticket["target_cell"], worker_id, repo_root)
    unit = {"ticket": tid, "target_cell": ticket["target_cell"], "layer": cell["layer"],
            "scope": cell["scope"], "slug": cell["slug"], "worktree": wt, "dir": d,
            "transition": ticket.get("target_transition"), "budget": ticket.get("budget"),
            "plan": plan, "agent": agent, "activity": act_id}

    # claimed (single-writer) + the lease
    ok, ticket, msg = _api.transition_ticket(d, tid, "claimed", actor)
    if not ok:
        teardown_worktree(d, wt, repo_root)
        return False, ticket, f"dispatch: {msg}"
    ticket["claim"] = {"worker_id": worker_id, "worktree": wt, "claimed_at": _iso(_now()),
                       "lease_expiry": _iso(_now() + datetime.timedelta(seconds=LEASE_TTL_S))}
    _lc.save_ticket(d, ticket)
    _eff = plan.get("effort") or {}
    _dele = plan.get("delegation") or {}
    _led.append(d, "dispatch", {"kind": "server", "id": "dispatcher"}, {"ticket": tid, "cell": ticket["target_cell"]},
                f"dispatched {agent} as {plan['orchestration_shape']}/{plan['loop_strategy']} "
                f"({plan_src}) in {'hermetic worktree' if hermetic else 'isolated dir'}",
                metrics={"hermetic": hermetic, "plan_source": plan_src})
    # the activity span begins — the agent/activity lens + the monitor materialize from these ledger events. The
    # delegation DEPTH is the plan's (the planned orchestrator-workers team), and the model tier + effort travel
    # with the span so token spend can be attributed per model + effort downstream.
    _led.append(d, "activity-start", {"kind": "agent", "id": agent}, {"ticket": tid, "cell": ticket["target_cell"]},
                f"{agent} {_activity_kind(to_mat)} {ticket['target_cell']}",
                metrics={"activity": act_id, "agent": agent, "kind": _activity_kind(to_mat),
                         "orchestration_shape": plan["orchestration_shape"], "loop_strategy": plan["loop_strategy"],
                         "delegation_mode": _dele.get("mode", "none"), "depth": _dele.get("max_depth", 0),
                         "parallelism": _eff.get("parallelism", 1), "model_tier": _eff.get("model_tier"),
                         "reasoning_effort": _eff.get("reasoning_effort"), "worktree": wt})

    # the VERIFIER-AUTHOR DEFAULT (#2): on a REAL (headless) build of a capability MODULE whose critic harness is
    # still a mock `ready` stub, the rubric-architect authors the cell's REAL verifier FIRST — so the module the
    # worker is about to build is graded against a real, spec-derived gate, automatically, with no operator pass.
    # Mock builds (CI/Crawl) keep their deterministic stub (the eval suite is unaffected); the run's token ceiling
    # bounds the extra spend. A non-stub verifier (already real, or hand-authored) is left untouched.
    if isinstance(adapter, HeadlessClaudeAdapter) and to_mat in _lc.SIGNAL_BEARING and _is_mock_verifier(d, cell):
        vwt, _vh = provision_worktree(d, f"verifier--{ticket['target_cell']}", worker_id, repo_root)
        try:
            vr = author_verifier(d, {"layer": cell["layer"], "scope": cell["scope"], "slug": cell["slug"],
                                     "worktree": vwt, "ticket": f"verifier-{tid}"}, adapter, repo_root)
            # attach the pass's spend so it COUNTS against the run's token ceiling (heartbeat._tokens_since sums
            # metrics.tokens from any event) — else the auto verifier-author burned tokens the budget never saw.
            _led.append(d, "handoff", {"kind": "agent", "id": "rubric-architect"},
                        {"ticket": tid, "cell": ticket["target_cell"]},
                        f"verifier-author pass: real critic harness authored (ok={bool(vr.get('ok'))})",
                        metrics={"activity": act_id, "verifier_author": True, **(vr.get("metrics") or {})})
        finally:
            teardown_worktree(d, vwt, repo_root)

    # worker starts → authors the asset. Fingerprint the asset BEFORE so a no-op is detected ADAPTER-AGNOSTICALLY
    # (council CRITICAL: "Done — no change" must be honest on the LIVE loop too — a headless worker can burn tokens
    # and produce no diff; the mock-only file-exists check missed that). before_fp is the cell's current asset hash.
    before_fp = _asset_fingerprint(d, cell.get("asset_ref"))
    _api.transition_ticket(d, tid, "in-progress", actor)
    result = adapter.dispatch(d, unit)
    if not result.get("ok"):
        # ATTACH the failed run's spend (the adapter reports cost/tokens even when it produced no artifact) so it
        # COUNTS against the run's token/dollar ceiling — a failure-then-retry that burns tokens the budget never
        # saw was the H5-C1 leak (a stuck cell could spend past the ceiling, one uncounted failed dispatch at a time).
        _led.append(d, "activity-fail", {"kind": "agent", "id": agent}, {"ticket": tid, "cell": ticket["target_cell"]},
                    f"{agent} failed: {result.get('error', 'no artifact')}",
                    metrics={"activity": act_id, **(result.get("metrics") or {})})
        # RETRY, don't dead-end: most worker failures are transient (a flaky tool call, a `claude` that errored
        # late, an operator interruption). Returning the ticket to `active` lets the next tick re-dispatch it; only
        # after MAX_WORKER_ATTEMPTS consecutive failures (a genuinely stuck cell) does it `block` and drop out of
        # rank. Without this a single hiccup wedged the whole build behind one cell, needing a manual reopen — the
        # opposite of an autonomous loop. The streak resets on any success; the global run budget still bounds total
        # dispatches, so retries can't run away.
        teardown_worktree(d, wt, repo_root)
        fails = _consecutive_fails(d, tid)
        # Two backstops bound retries: the attempt COUNT (many distinct failures) AND the kernel's signature-based
        # no-progress detector (the SAME failure repeating — a deterministically stuck cell that retrying won't fix).
        # The signature detector blocks EARLY, before the full attempt budget is burned on a futile loop (H5: the
        # shipped ledger.no_progress was never called from the dispatch loop).
        stuck, sreason = _led.no_progress(d, ticket["target_cell"], n=2)
        if fails < MAX_WORKER_ATTEMPTS and not stuck:
            _api.transition_ticket(d, tid, "active", actor,
                                   reason=f"worker failed (attempt {fails}/{MAX_WORKER_ATTEMPTS}) — retrying next tick")
            _api._store.rebuild(d)
            return False, _api.get_ticket(d, tid), f"worker failed; retrying ({fails}/{MAX_WORKER_ATTEMPTS})"
        _api.transition_ticket(d, tid, "blocked", actor,
                               reason=(sreason if stuck else f"worker failed {fails}× consecutively") + " — blocked")
        _api._store.rebuild(d)
        return False, _api.get_ticket(d, tid), "worker did not complete — blocked (" + ("no-progress" if stuck else "retries exhausted") + ")"
    # the server records the authored asset on the cell (workers cannot write lattice.json)
    _api.seed_cell(d, cell["layer"], cell["scope"], cell["slug"], maturity=cell["maturity"],
                   asset_ref=result.get("asset_ref"), depends_on=cell.get("depends_on", []),
                   signal_refs=cell.get("signal_refs", []))
    _api.transition_ticket(d, tid, "in-review", actor)
    # carry the model tier + effort with the spend metrics so token burn can be charted per model + effort
    _spend = {"model_tier": _eff.get("model_tier"), "reasoning_effort": _eff.get("reasoning_effort"),
              **(result.get("metrics") or {})}
    # P3 — NO-OP HONESTY: the worker confirmed an existing asset but authored no NEW content. The cell legitimately
    # re-validates, but the board must NOT imply fresh work was done. A no-op is whichever of (a) the adapter said so
    # (mock skipping an existing file) OR (b) the asset's content is BYTE-IDENTICAL before vs after the dispatch — the
    # adapter-agnostic check, so a HEADLESS worker that ran, spent tokens, and produced no diff is ledgered honestly
    # too (the council CRITICAL: "Done" must be honest on the loop the operator pays for, not only on free mock).
    after_fp = _asset_fingerprint(d, result.get("asset_ref"))
    unchanged = before_fp is not None and after_fp is not None and before_fp == after_fp
    noop = bool(result.get("noop")) or unchanged
    _led.append(d, "activity-complete", {"kind": "agent", "id": agent}, {"ticket": tid, "cell": ticket["target_cell"]},
                (f"{agent}: no change — the asset is byte-identical to before (no new work authored; run a live "
                 f"build or edit the file for a real change)" if noop else f"{agent} produced the artifact"),
                metrics={"activity": act_id, "budget_fraction": 1.0, "noop": noop, **_spend})

    if not auto_validate:
        # Tier 1 gates only ACCEPTANCE, never verification. The critic STILL runs here, so the lattice gets its
        # unforgeable signal and the produce→validate→iterate loop runs at EVERY tier: a signal-bearing cell is
        # critic-validated now (the operator's later plain `done` approval then passes gate-signal with no verifier
        # to hand-supply), and a critic refusal re-authors against the feedback (bounded) exactly as the unattended
        # path does — so a single in-review cell can no longer livelock the whole partial order at Tier 1.
        if to_mat in _lc.SIGNAL_BEARING:
            verifier = _kit_verifier(d, cell, unit) or _verifier_for(unit)
            rt = _api.get_ticket(d, tid)
            crit_ok, crit_msg = _lc.run_critic(d, rt, verifier, {"kind": "agent", "id": "cell-validator"})
            if not crit_ok:
                teardown_worktree(d, wt, repo_root)
                _led.append(d, "activity-fail", {"kind": "agent", "id": agent}, {"ticket": tid, "cell": ticket["target_cell"]},
                            f"critic refused: {crit_msg}"[:200], metrics={"activity": act_id})
                t = _api.get_ticket(d, tid); t["claim"] = None; _lc.save_ticket(d, t)
                fails = _consecutive_fails(d, tid)
                if fails < MAX_WORKER_ATTEMPTS:
                    _api.transition_ticket(d, tid, "in-progress", actor)
                    _api.transition_ticket(d, tid, "active", actor,
                                           reason=f"critic refused (attempt {fails}/{MAX_WORKER_ATTEMPTS}) — re-authoring against the gate")
                else:
                    _api.transition_ticket(d, tid, "blocked", actor,
                                           reason=f"critic refused {fails}× consecutively — blocked (retries exhausted)")
                _api._store.rebuild(d)
                return False, _api.get_ticket(d, tid), crit_msg
            _lc.save_ticket(d, rt)   # persist the cell's signal_refs mirror onto the ticket-of-record
        # in-review at Tier 1 is awaiting-HUMAN acceptance, not a live worker. Drop the lease now that the
        # worker has handed off and the critic has validated, so reconcile_leases (which keys off a still-present
        # lease_expiry) cannot reap completed, sign-off-pending work back to `active` after LEASE_TTL_S — a stale
        # lease must never outlive the worker that held it. A genuinely crashed dispatch leaves the lease set.
        _rt = _api.get_ticket(d, tid)
        if _rt.get("claim"):
            _rt["claim"] = None
            _lc.save_ticket(d, _rt)
        teardown_worktree(d, wt, repo_root)
        _api._store.rebuild(d)
        mark = "critic-validated; awaiting human sign-off" if to_mat in _lc.SIGNAL_BEARING else "awaiting human sign-off"
        return True, _api.get_ticket(d, tid), f"in-review (Tier {tier}: {mark})"

    # Tier 2+: auto-accept. The critic validates (or an authoring advance applies) → done. The kit's validation
    # adapter supplies the verifier; the asset-exists default applies when no kit is bound.
    verifier = (_kit_verifier(d, cell, unit) or _verifier_for(unit)) if to_mat in _lc.SIGNAL_BEARING else None
    ok, ticket, msg = _api.transition_ticket(d, tid, "done", actor, verifier=verifier)
    teardown_worktree(d, wt, repo_root)
    if ok:
        t = _api.get_ticket(d, tid)
        t["claim"] = None
        _lc.save_ticket(d, t)
        _led.append(d, "signal", {"kind": "server", "id": "dispatcher"}, {"ticket": tid, "cell": ticket["target_cell"]},
                    "probe cost recorded", metrics=result.get("metrics", {}))
        _api._store.rebuild(d)
        return ok, ticket, msg
    # the critic GATE REFUSED the artifact (the worker produced something, but it doesn't pass verify — e.g. a
    # missing export, a broken contract). Without recovery the ticket sticks in `in-review` forever (the verifier
    # dead-end that stalled a build). Retry like an authoring failure: clear the claim, count it, return to active
    # so the next dispatch re-authors against the gate's feedback; block after MAX_WORKER_ATTEMPTS. (in-review has
    # no direct edge to active, so step through in-progress — both transitions are ungated.)
    _led.append(d, "activity-fail", {"kind": "agent", "id": agent}, {"ticket": tid, "cell": ticket["target_cell"]},
                f"critic refused: {msg}"[:200], metrics={"activity": act_id})
    t = _api.get_ticket(d, tid); t["claim"] = None; _lc.save_ticket(d, t)
    fails = _consecutive_fails(d, tid)
    if fails < MAX_WORKER_ATTEMPTS:
        _api.transition_ticket(d, tid, "in-progress", actor)
        _api.transition_ticket(d, tid, "active", actor,
                               reason=f"critic refused (attempt {fails}/{MAX_WORKER_ATTEMPTS}) — re-authoring against the gate")
    else:
        _api.transition_ticket(d, tid, "blocked", actor,
                               reason=f"critic refused {fails}× consecutively — blocked (retries exhausted)")
    _api._store.rebuild(d)
    return False, _api.get_ticket(d, tid), msg


# ─────────────────────────────────── crash recovery (lease reconciliation) ───────────────────────────────────

def reconcile_leases(d, now=None):
    """Expire dead workers: a claimed/in-progress/in-review ticket whose lease has passed returns to `active`
    for re-dispatch (a worker that died mid-author OR mid-validation must not wedge the build). Idempotent — runs
    each tick (§8.1, §15). in-review has no direct edge to active, so it steps through in-progress.

    The lease is the discriminator: a CLEANLY-completed in-review ticket (worker handed off, critic validated,
    awaiting human sign-off) has had its lease cleared at the in-review hand-off, so a missing lease skips it here — a
    pending human approval is NOT a dead worker and must not be reaped. Only an in-review ticket still HOLDING a
    lease (i.e. the process genuinely died mid-dispatch before clearing it) is presumed dead and re-queued.

    But a `claimed`/`in-progress` ticket with NO (or a corrupt) lease is the OPPOSITE case — a dead worker, not a
    clean hand-off: the dispatch died after the state transition but before establishing the lease, so reconcile
    could never expire it and it wedges FOREVER (observed live: a ticket claimed with an empty claim, unreapable for
    hours while the loop ran). A laceless claimed/in-progress ticket is therefore reaped to active too."""
    now = now or _now()
    reclaimed = []
    for t in _api.list_tickets(d):
        if t.get("state") not in ("claimed", "in-progress", "in-review"):
            continue
        full = _api.get_ticket(d, t["id"])
        claim = full.get("claim") or {}
        exp = claim.get("lease_expiry")
        in_review = t.get("state") == "in-review"
        if not exp:
            # No lease. For in-review this is the CLEAN hand-off (worker done, critic validated, awaiting human
            # sign-off — the lease was cleared on purpose), NOT a dead worker → skip. But a `claimed`/`in-progress`
            # ticket without a lease is a WEDGE: the dispatch died after the state transition but before establishing
            # the lease (or the claim object was lost), so reconcile could never expire it and it sticks FOREVER
            # (observed live: a ticket claimed with an empty claim object, unreapable for hours, the loop running).
            # Treat a laceless claimed/in-progress ticket as a dead worker and return it to active.
            if in_review:
                continue
            dead = True
        else:
            try:
                dead = datetime.datetime.fromisoformat(exp) < now
            except ValueError:
                dead = not in_review   # a corrupt lease also wedges a claimed/in-progress ticket → reap; leave in-review
        if dead:
            full["claim"] = None
            _lc.save_ticket(d, full)
            rec = {"kind": "server", "id": "lease-reconciler"}
            if t.get("state") == "in-review":
                _api.transition_ticket(d, t["id"], "in-progress", rec)
            _api.transition_ticket(d, t["id"], "active", rec,
                                   reason=f"lease expired ({exp}); worker presumed dead — returned to active")
            reclaimed.append(t["id"])
    return reclaimed


# ─────────────────────── the independent refuter (false-pass measurement → earned autonomy) ───────────────────────

def refute_frontier(d):
    """Validated cells with a refuter harness that have not been independently re-checked SINCE their last
    validation — the refuter's work-list. Each VALIDATION epoch gets one independent re-check: a cell self-healed
    after a caught false pass (folded gate + re-armed fresh oracle) is re-authored → re-validated → re-enters here,
    so the FRESH oracle re-measures it. (Before the self-heal loop this was 'checked once, ever'.)"""
    # Walk the append-only ledger in ORDER (robust to second-precision ts ties): per cell, the LAST relevant event
    # decides — a validation makes it 'needs a re-check', a refuter check marks it 'checked for this epoch'. A cell
    # self-healed then re-validated has a validation as its last relevant event → it re-enters with the fresh oracle.
    state = {}
    for e in _led.read(d):
        cell = (e.get("subject") or {}).get("cell")
        if not cell:
            continue
        if e.get("event") == "transition" and e.get("to") == "validated":
            state[cell] = "needs-refute"
        elif e.get("event") == "signal" and (e.get("metrics") or {}).get("refuter"):
            state[cell] = "refuted"
    out = []
    for c in _lat.load(d).get("cells", []):
        cid = _lat.cid(c)
        if c.get("maturity") in ("validated", "operating") \
                and state.get(cid) != "refuted" \
                and os.path.isfile(os.path.join(d, "coordination", "refuters", f"{cid}.json")):
            out.append(cid)   # never refuted, OR re-validated since its last re-check
    return out


def refute_author_frontier(d):
    """The REFUTE-AUTHOR's work-list: validated multi-file CODE cells whose refuter is still LIVENESS-only (or
    absent) — i.e. the cell is `unmeasured` and a behavioral oracle would let it EARN Tier 2. A cell already armed
    with a MEASURING oracle is excluded (nothing to author), and presence-stub-validated / non-code cells are skipped
    (no real contract to refute). This is what `author_refuters` iterates — the producer half of autonomous Tier 2."""
    out = []
    for c in _lat.load(d).get("cells", []):
        if c.get("maturity") not in ("validated", "operating"):
            continue
        authoring = _authoring_for(c)
        if not authoring or authoring.get("mode") != "multi-file":
            continue
        cid = _lat.cid(c)
        if _measuring_now(d, cid):   # already a measuring oracle → nothing to author
            continue
        # the gate must be a REAL spec-conformance harness, not a mock/presence stub — resolve verify.mjs the SAME
        # asset_ref-aware way produce_refuter does (NOT _is_mock_verifier, which resolves via _asset_rel and so
        # disagrees when asset_ref points elsewhere), then inline the real-gate test: a stub with no contract gives
        # nothing to write an INDEPENDENT oracle against (the verifier-author must run first).
        vpath = os.path.normpath(os.path.join(d, c.get("asset_ref")
                                 or _asset_rel(c["layer"], c["slug"], authoring), "verify.mjs"))
        try:
            src = open(vpath, encoding="utf-8").read()
        except OSError:
            continue   # no gate authored yet
        if _MOCK_VERIFIER_MARK in src or not _exercises_export(src):
            continue   # mock smoke stub / presence check → premature to author an oracle
        out.append(cid)   # validated, real gate, still unmeasured → a behavioral oracle would let it earn Tier 2
    return out


def _exports_from_verify(src):
    """Recover a cell's exported API from its `verify.mjs` — the `required = [ ... ]` array a generated gate embeds,
    plus any `m.<name>` the harness exercises (a hand-authored real harness). `ready`/`m.ready` (the seed-stub
    presence flag) is excluded. Best-effort, stable-deduped; drives the refuter producer. Returns [] for a presence
    stub (no real contract → no refuter armed, which is the honest outcome — a mock-validated cell stays unmeasured)."""
    exports = []
    arr = re.search(r"required\s*=\s*\[([^\]]*)\]", src)
    if arr:
        exports += re.findall(r'"([^"\\]+)"', arr.group(1))
    for mm in re.finditer(r"\bm\.([A-Za-z_]\w*)", src):
        if mm.group(1) != "ready":
            exports.append(mm.group(1))
    seen, out = set(), []
    for e in exports:
        if e and e != "ready" and e not in seen:
            seen.add(e); out.append(e)
    return out


def _refuter_discriminates(refute, exports):
    """A positive CAN-DISAGREE proof (harness-council re-audit 3 → 4): run the refute harness against TWO
    deliberately-wrong stubs whose exports return distinct, randomly-keyed POISON values — one a NUMBER, one a STRING
    — and require it to DISAGREE (exit ≠ 0) with BOTH. A real value assertion (`compute(7,8)===15`) disagrees with
    every wrong value; a tautology (`compute(1)===compute(1)`, `[compute(1)].length===1`) AGREES with both; and a
    type-coercion annihilator (`compute(1)*0===0`, which `NaN`s a string but holds for a number) AGREES with the
    number poison — so a single string poison would have leaked it (re-audit 4). Requiring disagreement with both
    types closes that class. This is the semantic check a syntactic denylist (`verify_gen.is_behavioral`) only
    approximates. The poison stubs are server-authored — the graded worker module is NOT in this loop. Fail-CLOSED:
    no node / any error / agrees with either poison → not discriminating (→ the cell stays unmeasured)."""
    names = [e for e in (exports or []) if isinstance(e, str) and e.strip()]
    if not refute or not names or shutil.which("node") is None:
        return False
    poisons = [str(int.from_bytes(os.urandom(5), "big")),          # a random NUMBER
               "'__df_poison_" + os.urandom(6).hex() + "__'"]      # a random STRING
    for poison in poisons:
        stub = "".join(f"export const {e} = (...a) => ({poison});\n" for e in names)
        sdir = tempfile.mkdtemp(prefix="df-calib-")
        try:
            spath = os.path.join(sdir, "index.mjs")
            open(spath, "w", encoding="utf-8").write(stub)
            abs_stub = pathlib.Path(os.path.abspath(spath)).as_uri()
            harness = _vg.gen_cap_verify(names, refute).replace("'./index.mjs'", f"'{abs_stub}'")
            rc = subprocess.run(["node", "--input-type=module", "-e", harness],
                                cwd=sdir, capture_output=True, text=True, timeout=30).returncode
            if rc == 0:        # the refute set AGREED with a deliberately-wrong module → it is vacuous on this type
                return False
        except (OSError, subprocess.SubprocessError):
            return False
        finally:
            shutil.rmtree(sdir, ignore_errors=True)
    return True   # disagreed with BOTH wrong stubs → it can genuinely disagree → measuring


def _mutants(src, k=20):
    """Generate up to `k` single-edit TEXT mutants of a module source — server-side, deterministic. Operator swaps,
    integer-literal bumps, and boolean flips. A mutant that is a syntax error simply fails the gate (exit ≠ 0) and is
    skipped, so the menu can be liberal. Used by `_mutation_independent` to search for a gate-PASSING defect the
    refuter catches."""
    out = []
    for old, new in [("===", "!=="), ("!==", "==="), ("&&", "||"), ("||", "&&"),
                     ("<=", "<"), (">=", ">"), ("*", "+")]:   # symbol swaps (multi-char first; avoid === vs ==)
        i = src.find(old)
        while i != -1 and len(out) < k:
            out.append(src[:i] + new + src[i + len(old):])
            i = src.find(old, i + len(old))
    for old in ("+", "-"):                                    # arithmetic, but not ++ -- += -= etc.
        i = src.find(old)
        while i != -1 and len(out) < k:
            prev = src[i - 1] if i > 0 else " "
            nxt = src[i + 1] if i + 1 < len(src) else " "
            if prev not in "+-*/=<>" and nxt not in "+-*/=<>":
                out.append(src[:i] + ("-" if old == "+" else "+") + src[i + 1:])
            i = src.find(old, i + 1)
    for m in re.finditer(r"(?<![\w.])\d+(?![\w.])", src):     # bump an integer literal
        if len(out) >= k:
            break
        out.append(src[:m.start()] + str(int(m.group()) + 1) + src[m.end():])
    for old, new in (("true", "false"), ("false", "true")):
        i = src.find(old)
        while i != -1 and len(out) < k:
            out.append(src[:i] + new + src[i + len(old):])
            i = src.find(old, i + len(old))
    return out[:k]


def _run_stdin_harness(harness_src, abs_index, iso):
    """Run a harness against a module via STDIN-piped node, returning the exit code (or None on error). The harness
    text — G's or R's — is in NO readable channel (not argv/-e/a file), so a graded module cannot read it to tell the
    gate from the refuter and selectively fake a witness (harness-council re-audit 4, reused for calibration). The
    module's `'./index.mjs'` import is rewritten to the absolute mutant URL; sibling deps resolve from `iso`."""
    rewritten = harness_src.replace("'./index.mjs'", f"'{abs_index}'")
    try:
        return subprocess.run(["node", "--input-type=module", "-"], input=rewritten,
                              cwd=iso, capture_output=True, text=True, timeout=20).returncode
    except (OSError, subprocess.SubprocessError):
        return None


_JS_CALL_GLOBALS = {"Math", "JSON", "Object", "Array", "Number", "String", "Boolean", "parseInt", "parseFloat",
                    "isNaN", "isFinite", "Map", "Set", "BigInt", "Symbol"}   # free-call identifiers an honest refute may use


def _gate_scoped_refute(refute, exports):
    """Keep only refute assertions whose every FREE function-call identifier is a GATE-DECLARED export (or a JS
    global) — so the mutation proof's witness cannot ride on a NON-spec export the gate never covers. Closes the
    decoy/tripwire forge (harness-council round 7 CRITICAL): a worker plants `_k = () => 7` in index.mjs + a refute
    `_k() === 7`, then a `7`→`8` mutant makes the gate (which ignores `_k`) PASS but the refuter FAIL on the worker's
    own dead export — a false witness. Confining the proof to the gate's contract surface defeats it: `_k` ∉ the
    gate's exports, so that assertion is dropped and the `_k`-mutant no longer fails the refuter. Method calls
    (`x.foo(`) don't count — only free identifiers (`foo(`), i.e. the export/global calls. A genuine independence
    check on a real export at a NEW input (`compute(7,8)`) is kept; only off-contract references are dropped."""
    allowed = {e for e in (exports or []) if isinstance(e, str)} | _JS_CALL_GLOBALS
    out = []
    for r in (refute or []):
        if not isinstance(r, str):
            continue
        calls = set(re.findall(r"(?<![\w.$])([A-Za-z_$][\w$]*)\s*\(", r))   # free-identifier calls only (not `.foo(`)
        if calls and calls <= allowed:    # ≥1 call, and every free call is a gate export or a global
            out.append(r)
    return out


def _mutation_independent(cell_dir, exports, refute, gate_src):
    """The gate-AGNOSTIC independence proof (task #23) — the trust upgrade for an autonomously-authored oracle. A
    refute set R catches something the gate G does NOT iff there EXISTS a text-mutant M' of the REAL module where
    G(M') PASSES but R(M') FAILS (a gate-PASSING defect R caught). A gate-COPY R agrees with G on every mutant → no
    such witness → not proven (so it stays provenance-gated — fail-safe). This is what `independent_of_gate`'s static
    textual arm cannot do for an opaque data-driven/negative-form gate: it RUNS the real gate, never parses it.

    Forge-resistant: G and R both run via STDIN-piped node, so the (worker-authored) module cannot read the harness
    source to distinguish them — it can only make BOTH pass or BOTH fail (suppressing a witness, which is fail-safe),
    never selectively fake G-pass + R-fail. R is confined to the gate's CONTRACT surface (`_gate_scoped_refute`), so
    the witness cannot ride on a worker-invented non-spec export (round-7 decoy forge). Server-run over
    server-generated mutants; the worker controls only the module + R, both of which are exactly what is being graded.

    The BAR is honest and bounded: a witness proves R is INDEPENDENT of the gate (it catches ≥1 gate-passing defect
    the gate misses, on the contract surface) — a strictly stronger property than the bare human-authored `trusted`
    path, which proves nothing. It does NOT prove R is an EXHAUSTIVE oracle against every adversarial special-case
    overfit (no static check can, for an opaque gate; the mutants are single-edit perturbations, not wholesale
    gaming rewrites). So `mutation_verified` is a sound basis to treat an autonomous oracle as trusted at the same
    bar the human path uses — not a competence guarantee. Fail-CLOSED (no node / no module / no on-contract refute /
    no witness)."""
    if shutil.which("node") is None or not refute or not exports:
        return False
    scoped = _gate_scoped_refute(refute, exports)   # only checks on the gate's CONTRACT surface count (round-7 fix)
    if not scoped:
        return False                                 # every refute assertion was off-contract → no proof, fail-safe
    try:
        real = open(os.path.join(cell_dir, "index.mjs"), encoding="utf-8").read()
    except OSError:
        return False
    r_harness = _vg.gen_cap_verify(exports, scoped)
    iso = tempfile.mkdtemp(prefix="df-mut-")
    try:
        for n in os.listdir(cell_dir):                       # copy the cell so sibling deps resolve
            sp = os.path.join(cell_dir, n)
            if os.path.isfile(sp):
                shutil.copy(sp, os.path.join(iso, n))
        abs_index = pathlib.Path(os.path.join(iso, "index.mjs")).as_uri()
        for mut in _mutants(real):
            open(os.path.join(iso, "index.mjs"), "w", encoding="utf-8").write(mut)
            if _run_stdin_harness(gate_src, abs_index, iso) != 0:   # mutant must SURVIVE the gate to be a witness
                continue
            r = _run_stdin_harness(r_harness, abs_index, iso)
            if r is not None and r != 0:                     # gate PASSES the mutant, refuter FAILS it → witness
                return True
        return False
    finally:
        shutil.rmtree(iso, ignore_errors=True)


def produce_refuter(d, cell_id):
    """The LIVE refuter PRODUCER (harness-council H6). When a cell first reaches `validated`, arm an independent
    refuter sidecar so the false-pass oracle (`refute_frontier` → `run_refuter`) has a work-item the next tick.

    MEASURING vs LIVENESS (the keystone correction — harness-council re-audit). A refuter counts toward `false_pass`
    (and thus toward Tier 2) ONLY if it can actually DISAGREE with a module that passed its gate — i.e. it EXERCISES
    behavior on inputs the gate did not use (`verify_gen.is_behavioral`). So:
      - if the cell's verify-spec carries a BEHAVIORAL `refute` set (planner/operator-authored domain edge cases,
        independent of the gate), arm a MEASURING refuter from it (`measuring: true`);
      - otherwise arm only `fresh_refute`'s generic floor as a NON-measuring LIVENESS check (`measuring: false`): it
        catches a module that throws on load, but it is TAUTOLOGICAL against any loading module, so it must NOT mint a
        measured 0.0 false-pass (the prior bug auto-granted Tier 2 from exactly this vacuous oracle). A cell with no
        behavioral refute set therefore stays HONESTLY `unmeasured` (Tier 1) until a real oracle is authored.
    UPGRADE path (the autonomous refute-author): a sidecar already armed as a LIVENESS floor is re-evaluated — if a
    behavioral refute set has SINCE been authored into the verify-spec (by `author_refuter`, the headless rubric-
    architect), this upgrades it liveness→MEASURING. A sidecar that is ALREADY measuring is never clobbered, and a
    still-liveness cell with no measuring candidate is left as-is (no churn). So the deterministic sweep arming a
    liveness floor first does NOT strand a later-authored behavioral oracle.
    Returns the cell_id if it armed/upgraded an oracle, else None. Idempotent; multi-file CODE cells only."""
    side = os.path.join(d, "coordination", "refuters", f"{cell_id}.json")
    existing = None
    if os.path.isfile(side):
        try:
            existing = json.load(open(side, encoding="utf-8")) or {}
        except (OSError, ValueError):
            existing = {}
        if existing.get("measuring"):
            return None   # already a MEASURING oracle — never clobber it (a re-arm could only weaken)
        # else: a LIVENESS-only sidecar — fall through to re-evaluate, and UPGRADE if a behavioral set now exists
    cell = _lat.find(_lat.load(d), cell_id)
    if not cell:
        return None
    authoring = _authoring_for(cell)
    if not authoring or authoring.get("mode") != "multi-file":
        return None
    vpath = os.path.normpath(os.path.join(d, cell.get("asset_ref")
                             or _asset_rel(cell["layer"], cell["slug"], authoring), "verify.mjs"))
    try:
        gate_src = open(vpath, encoding="utf-8").read()
        exports = _exports_from_verify(gate_src)
    except OSError:
        return None
    # PREFER a real behavioral refute set authored into the verify-spec; fall back to the generic liveness floor.
    # `measuring` records which — it is the only thing `false_pass` is allowed to count.
    spec_path = os.path.join(d, "coordination", "verify-spec", f"{cell_id}.json")
    refute, measuring = None, False
    if os.path.isfile(spec_path):
        try:
            sdata = json.load(open(spec_path, encoding="utf-8")) or {}
            cand = sdata.get("refute") or []
            # MEASURING requires THREE proofs, none the author's say-so: (1) is_behavioral — invokes an export, no
            # obvious tautology; (2) _refuter_discriminates — actually disagrees with a typed poison; (3)
            # independent_of_gate — carries a behavioral check the gate does NOT already enforce, so it can catch an
            # overfit the gate waved through (the gate-COPY hole the auto-author opens). The independence baseline is
            # the SERVER-READ gate SOURCE (`gate_src`), NOT the verify-spec's `acceptance` — that field is
            # WORKER-WRITABLE under --allow-refute, so trusting it would let a refute-author declare `acceptance: []`
            # and disarm the structured arm (harness-council round 6 CRITICAL). We pass [] for acceptance here; the
            # server-trusted structured arm applies only on the self-heal path, where `fold` computes it. NOTE: the
            # gate-source arm is itself PARTIAL for opaque data-driven/negative-form gates, so a passing autonomous
            # oracle is additionally provenance-gated — it measures but does not earn unattended Tier 2 (see tier_for).
            if (_vg.is_behavioral(cand, exports) and _refuter_discriminates(cand, exports)
                    and _vg.independent_of_gate(cand, [], exports, gate_src=gate_src)):
                refute, measuring = cand, True
        except (OSError, ValueError):
            pass
    if refute is None:
        # no measuring candidate. If a liveness sidecar already exists, leave it (no churn — the upgrade only
        # fires when a behavioral set appears); only ARM a fresh liveness floor when there is no sidecar yet.
        if existing is not None:
            return None
        refute = _vg.fresh_refute(exports, [], 0)   # generic liveness floor (cannot disagree → non-measuring)
        if not refute:
            return None
        for sub in ("verify-spec", "refuters"):
            os.makedirs(os.path.join(d, "coordination", sub), exist_ok=True)
        json.dump(_vg.new_spec(exports, [], refute), open(spec_path, "w", encoding="utf-8"), indent=2)
    os.makedirs(os.path.join(d, "coordination", "refuters"), exist_ok=True)
    # PROVENANCE stamped HERE (not only in author_refuters), from the server-owned registry — so an oracle whose
    # MEASURING upgrade lands in the deterministic sweep (not the author pass) is still marked autonomous (round 6:
    # closing the stamp-gap). The registry lives under the worker-protected run/ perimeter → untamperable.
    autonomous = _is_autonomous_cell(d, cell_id)
    # The TRUST UPGRADE for an autonomous oracle (task #23): a measuring set authored by the refute-author is
    # provenance-gated (can't earn unattended Tier 2) UNLESS it PROVES it catches a gate-passing defect the gate
    # misses — `_mutation_independent` runs the real gate + the refuter against server-generated mutants of the real
    # module and finds a witness (G-pass, R-fail). A gate-copy yields no witness → stays untrusted. Only worth the
    # cost for a MEASURING + AUTONOMOUS oracle (a non-autonomous oracle is already trusted; a non-measuring one
    # doesn't count). Server-run + forge-resistant (stdin-piped harnesses); the result is the trust signal `tier_for`
    # reads via `trusted_refuter_checks`.
    cell_dir = os.path.dirname(vpath)
    mutation_verified = bool(measuring and autonomous
                             and _mutation_independent(cell_dir, exports, refute, gate_src))
    json.dump({"harness": _vg.gen_cap_verify(exports, refute), "refute": refute, "measuring": measuring,
               "autonomous": autonomous, "mutation_verified": mutation_verified},
              open(side, "w", encoding="utf-8"), indent=2)
    upgraded = existing is not None and measuring   # a liveness floor promoted by a now-authored behavioral set
    _led.append(d, "signal", {"kind": "server", "id": "refuter-producer"}, {"cell": cell_id},
                f"{'UPGRADED to a MEASURING' if upgraded else 'armed a ' + ('MEASURING' if measuring else 'liveness-only (NON-measuring)')} "
                f"refuter for {cell_id} ({len(exports)} export(s), {len(refute)} check(s))"
                + ("" if measuring else " — the generic floor cannot disagree, so the cell stays UNMEASURED until a "
                   "behavioral refute set is authored (it will NOT earn Tier 2 on this)"),
                metrics={"refuter_armed": True, "exports": len(exports), "measuring": measuring, "upgraded": upgraded})
    return cell_id


def produce_refuters(d):
    """Sweep: arm an independent refuter for every validated CODE cell that lacks one. The heartbeat runs this each
    tick BEFORE the refuter frontier, so a cell that reached `validated` this epoch — at Tier 1 (human-accepted) or
    Tier 2 (auto) — becomes MEASURABLE the next tick. Idempotent (the per-cell producer skips non-code cells,
    presence-stub-validated cells, and any already armed). This is the live producer half of H6; `run_refuter` is the
    consumer half. Returns the cell ids newly armed."""
    return [r for c in _lat.load(d).get("cells", [])
            if c.get("maturity") in ("validated", "operating")
            for r in [produce_refuter(d, _lat.cid(c))] if r]


def self_heal_cell(d, cell_id):
    """The 'full self-heal + new oracle' remediation for a caught false pass (decision #123). A cell that passed its
    own gate but FAILED the independent refuter is repaired in code, no human in the path:
      1. FOLD   — the refuter's failing checks are merged INTO the cell's gate (`verify.mjs`), so the strengthened
                  gate now enforces exactly what the worker was gaming (server-side write — the worker is gate-denied
                  from verify.mjs, so it cannot pre-empt this).
      2. RE-ARM — a FRESH, independent refuter is generated (the 'new oracle') so the cell stays measurable; if the
                  oracle is EXHAUSTED, the sidecar is retired and the exhaustion is ledgered (escalate, don't churn).
      3. STALE  — the cell drops validated→regenerating, so the bounded loop re-authors it against the tougher gate.
      4. UN-SHIP— staleness propagates to every dependent validated against this cell (the app integrator), so a
                  hollow capability can't keep a 'shipped' app standing.
    Bounded by the existing no-progress→block breaker: a cell that can't pass the strengthened gate stops, it never
    loops forever. Best-effort: an instance with no verify-spec (pre-self-heal) records the incident + leaves the
    cell flagged (the old behavior). Returns a summary dict."""
    spec_path = os.path.join(d, "coordination", "verify-spec", f"{cell_id}.json")
    if not os.path.isfile(spec_path):
        return {"healed": False, "reason": "no verify-spec — incident recorded, cell left flagged"}
    try:
        spec = json.load(open(spec_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"healed": False, "reason": "verify-spec unreadable"}
    verify_js, refuter_harness, new_spec, n_folded = _vg.fold(spec)
    if verify_js is None:
        return {"healed": False, "reason": "no refute set to fold"}
    cell = _lat.find(_lat.load(d), cell_id)
    if not cell:
        return {"healed": False, "reason": "cell not found"}
    # the strengthened gate must land where the validator runs it — beside the product source (the cell's
    # asset_ref), which a kit's output_root may have rooted OUT of .factory/ into the product tree.
    cell_dir = os.path.normpath(os.path.join(d, cell.get("asset_ref")
                                or _asset_rel(cell["layer"], cell["slug"], _authoring_for(cell))))
    gen = new_spec["generation"]
    # 1. FOLD — strengthen the gate + persist the new spec
    os.makedirs(cell_dir, exist_ok=True)
    open(os.path.join(cell_dir, "verify.mjs"), "w", encoding="utf-8").write(verify_js)
    json.dump(new_spec, open(spec_path, "w", encoding="utf-8"), indent=2)
    # 2. RE-ARM the fresh oracle, or retire it on exhaustion. The re-arm is MEASURING only if `fold` produced a
    # BEHAVIORAL fresh refute (planner edge cases); the deterministic floor's generic invariants re-arm a
    # liveness-only oracle (keystone: a folded-then-generically-re-armed cell stays unmeasured until a real refute set
    # is authored — it does NOT silently re-earn Tier 2 on a tautology).
    sidecar = os.path.join(d, "coordination", "refuters", f"{cell_id}.json")
    if refuter_harness:
        _rf, _ex, _acc = new_spec.get("refute") or [], new_spec.get("exports") or [], new_spec.get("acceptance") or []
        # re-armed `measuring` requires the SAME three-proof AND-gate the live produce_refuter uses — the syntactic
        # pre-filter, the poison calibration, AND independence from the (just-strengthened) gate (re-audit 4 N: a fold
        # must not certify an invoking-but-vacuous re-arm; the fold FOLDS the old refute INTO acceptance, so a fresh
        # refuter that only re-states a folded check is now a gate-copy and independent_of_gate correctly rejects it).
        rearm_measuring = (_vg.is_behavioral(_rf, _ex) and _refuter_discriminates(_rf, _ex)
                           and _vg.independent_of_gate(_rf, _acc, _ex, gate_src=verify_js))
        json.dump({"harness": refuter_harness, "refute": _rf, "measuring": rearm_measuring},
                  open(sidecar, "w", encoding="utf-8"), indent=2)
    elif os.path.isfile(sidecar):
        os.remove(sidecar)
    # 3. STALE the cell → regenerating (the loop re-authors against the strengthened gate)
    lat = _lat.load(d)
    c = _lat.find(lat, cell_id)
    frm = c["maturity"]
    c["maturity"] = "regenerating"
    _lat.save(d, lat)
    _led.append(d, "regenerate", {"kind": "server", "id": "self-heal"}, {"cell": cell_id},
                f"self-heal: folded {n_folded} refuter check(s) into the gate; "
                + (f"re-armed a fresh independent refuter (gen {gen})" if refuter_harness else "oracle EXHAUSTED — retired the refuter, escalate"),
                frm=frm, to="regenerating",
                metrics={"folded": n_folded, "generation": gen, "rearmed": bool(refuter_harness)})
    # 4. UN-SHIP — propagate staleness TRANSITIVELY to every dependent validated (directly OR via a chain) against
    # this cell. The kernel's propagate_staleness is one-hop; loop it to a FIXPOINT so a grandchild integrator
    # (core ← ui ← shell: a self-heal on `core` must un-ship `ui` AND `shell`) cannot survive stale-but-trusted
    # (harness-council re-audit 2: propagate_staleness was one-hop, the "transitive" claim was false).
    lat = _lat.load(d)
    marker = f"self-heal-{gen}"
    flipped, frontier, seen = [], [cell_id], {cell_id}
    while frontier:
        nxt = []
        for cid in frontier:
            for f in _lat.propagate_staleness(lat, cid, marker):
                if f not in seen:
                    seen.add(f); flipped.append(f); nxt.append(f)
        frontier = nxt
    if flipped:
        _lat.save(d, lat)
        _led.append(d, "stale-propagated", {"kind": "server", "id": "self-heal"}, {"cell": cell_id},
                    f"self-heal un-shipped dependent(s) validated against the hollow cell: {flipped}",
                    metrics={"flipped": flipped})
    return {"healed": True, "folded": n_folded, "rearmed": bool(refuter_harness),
            "generation": gen, "stale_dependents": flipped}


def run_refuter(d, cell_id):
    """INDEPENDENT post-validation re-check. A validated cell is re-tested against a HIDDEN refuter harness — the
    planner's `refute` assertions, DIFFERENT from the `verify.mjs` gate the worker saw and coded to, materialized
    only now (the worker never saw it). The check is recorded as the false-pass denominator (`signal` ·
    metrics.refuter); a DISAGREEMENT (the cell passed its own gate but FAILS the independent re-check) is a caught
    FALSE PASS → `record_incident` → mechanical demotion (the rubric verifiers go `stale`, the tier re-derives
    lower, no human in the path). This is the PRODUCER the autonomy trajectory was built to consume — it read
    `unmeasured` because nothing recorded a refuter check. Returns True (agreed), False (false-pass caught), or
    None (no refuter / not applicable)."""
    sidecar = os.path.join(d, "coordination", "refuters", f"{cell_id}.json")
    if not os.path.isfile(sidecar):
        return None
    cell = _lat.find(_lat.load(d), cell_id)
    if not cell or cell.get("maturity") not in ("validated", "operating"):
        return None
    try:
        sdata = json.load(open(sidecar, encoding="utf-8")) or {}
    except (json.JSONDecodeError, OSError):
        return None
    harness = sdata.get("harness")
    # MEASURING vs liveness (keystone): a check counts toward false_pass / Tier 2 ONLY if its sidecar EXPLICITLY
    # declares `measuring: true` — which the production writers (`produce_refuter`, `self_heal_cell`) do only after the
    # `_refuter_discriminates` poison calibration passes. The default is FAIL-SAFE False (harness-council re-audit 5):
    # a keyless sidecar (a hand-seeded fixture, or — on an UNWIRED instance where `coordination/refuters/` is not yet
    # gate-protected — anything a non-server writer drops) is LIVENESS-ONLY and can never mint a measured 0.0 →
    # auto-Tier-2. It still records its agree/disagree (a disagreement demotes via the incident path either way); it
    # just does not earn the denominator. Fail-safe by construction, independent of whether the wiring is installed.
    measuring = sdata.get("measuring", False)
    # PROVENANCE (the human-glance gate, harness-council round 6): an oracle AUTONOMOUSLY authored by the refute-author
    # is recorded `autonomous: true` (server-stamped, in a worker-protected sidecar). It still MEASURES — it builds the
    # visible false-pass rate — but `tier_for` does not let an all-autonomous measurement earn UNATTENDED Tier 2: the
    # current independence calibration is partial for opaque gates, so a self-authored oracle cannot self-promote the
    # loop to lights-out. A human-vetted / server-folded oracle (autonomous absent/false) is the trusted denominator.
    autonomous = bool(sdata.get("autonomous"))
    # an autonomous oracle that PROVED gate-agnostic independence (a witness mutant: G-pass, R-fail) is TRUSTED
    # despite being machine-authored (task #23) — `trusted_refuter_checks` reads this off the metric.
    mutation_verified = bool(sdata.get("mutation_verified"))
    if not harness or shutil.which("node") is None:
        return None
    # The refuter must IMPORT the product source (the cell's asset_ref) — a kit's output_root may have rooted it OUT
    # of .factory/ into the product tree (src/{project}/{slug}/), where index.mjs actually lives — but it must RUN in
    # a dir the worker does NOT control (harness-council re-audit H3: the old path wrote .refute.mjs INTO cell_dir and
    # ran node there, so the graded module could shadow the refuter's node environment). It now runs in a temp dir and
    # imports index.mjs by an absolute file:// URL; the module's own relative deps still resolve from cell_dir.
    cell_dir = os.path.normpath(os.path.join(d, cell.get("asset_ref")
                                or _asset_rel(cell["layer"], cell["slug"], _authoring_for(cell))))
    abs_index = pathlib.Path(os.path.abspath(os.path.join(cell_dir, "index.mjs"))).as_uri()
    # AGREE requires proof the harness ran its checks to a genuine SUCCESS. A per-run NONCE is printed ONLY at the
    # harness's success path; AGREE requires it in stdout. Two structural defenses make it unforgeable by the
    # worker-authored module (which executes in this process at IMPORT, before the harness's checks):
    #   (a) the harness is piped over STDIN (`node -`), NOT argv/`-e` — so the nonce-bearing program text is in
    #       neither process.argv, process.execArgv, /proc/self/cmdline, nor `ps`; the module cannot READ the nonce
    #       (harness-council re-audit 4: the `-e` program text was readable via process.execArgv[2]).
    #   (b) failures THROW (not `process.exit(1)`), so a module that overrides `process.exit` or handles
    #       `uncaughtException` cannot fall through to the success line that emits the nonce — a thrown failure never
    #       reaches it. The module can neither read the nonce nor make the harness emit it without the checks passing.
    # cwd is an empty temp dir (the module's own relative deps still resolve from cell_dir via the absolute URL).
    nonce = "RF-" + os.urandom(16).hex()
    rewritten = (harness.replace("'./index.mjs'", f"'{abs_index}'")
                        .replace("process.exit(1)", "throw new Error('RF_REFUTE_FAIL')")
                        .replace("process.exit(0)", f"console.log('{nonce}');process.exit(0)"))
    iso = tempfile.mkdtemp(prefix="df-refute-")
    try:
        proc = subprocess.run(["node", "--input-type=module", "-"], input=rewritten,
                              cwd=iso, capture_output=True, text=True, timeout=60)
        rc, out = proc.returncode, (proc.stdout or "")
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        shutil.rmtree(iso, ignore_errors=True)
    agreed = (rc == 0 and nonce in out)
    _led.append(d, "signal", {"kind": "server", "id": "refuter"}, {"cell": cell_id},
                f"independent refuter {'AGREED' if agreed else 'DISAGREED — FALSE PASS caught'} on {cell_id}"
                + ("" if measuring else " (liveness-only — NOT a false-pass measurement)")
                + (" [autonomously-authored oracle — measures, but does not earn unattended Tier 2]" if measuring and autonomous and not mutation_verified else "")
                + (" [autonomous + MUTATION-VERIFIED — proved independent of the gate (caught a gate-passing defect on contract surface); trusted]" if measuring and autonomous and mutation_verified else ""),
                metrics={"refuter": True, "agreed": agreed, "measuring": measuring,
                         "autonomous": autonomous, "mutation_verified": mutation_verified})
    if not agreed:
        _auto.record_incident(d, cell_id, f"refuter caught a false pass: {cell_id} validated against its gate but "
                              "fails an independent re-check (overfit / gamed)")
        # #123 — full self-heal: fold the refuter into the gate, re-arm a fresh oracle, stale the cell + un-ship
        # dependents, so the loop re-authors against the strengthened gate (not just flag-and-demote).
        self_heal_cell(d, cell_id)
        _api._store.rebuild(d)   # sync the store mirror with the lattice.json the incident + self-heal mutated
    return agreed


def distill_to_patterns(d, min_occurrences=2):
    """Close the regeneration loop's distill→PATTERNS step in code: turn the ledger's recurring SUCCESS signatures
    (a cell TYPE that validated reliably, min_occurrences+) into seeded `pattern.system.<type>` cells WITH provenance
    (the ledger refs distilled from — a pattern without provenance is a guess). The 'is this a real, reusable
    pattern?' judgment is the harness-distiller agent's; this is the mechanical scan + materialization, so the
    `pattern` layer — the ONE layer a build never seeds (it is EMERGENT, distilled from operating, not given) —
    populates from real OPERATING evidence. Idempotent (skips already-distilled). Returns the pattern cell ids."""
    created = []
    for c in _distill.distill_patterns(d, min_occurrences=min_occurrences):
        if c.get("kind") != "success":
            continue
        # the pattern layer is EMERGENT from operating the substantive layers — it must never distill from ITSELF
        # (two patterns validating is not evidence of a reusable `pattern.system.pattern-system` meta-pattern; that's
        # a regress that fills the lattice with noise). Surfaced by the live breakout run.
        if str(c["cell_type"]).startswith("pattern."):
            continue
        slug = str(c["cell_type"]).replace(".", "-")
        pid = f"pattern.system.{slug}"
        if _lat.find(_lat.load(d), pid):
            continue
        path = os.path.join(d, "pattern", f"{slug}.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").write(
            f"# Pattern — {c['signature']}\n\nDistilled from {c['occurrences']} occurrences of `{c['cell_type']}` "
            f"reaching validated/operating.\n\n## Provenance (ledger)\n"
            + "\n".join(f"- {r}" for r in c.get("evidence", [])) + "\n")
        # mint a REAL signal on disk — the distillation IS the cell's evidence (its operating-evidence provenance),
        # so `lattice check` sees an earned signal, not a phantom signal_ref ("asserted, not earned").
        sig_rel = f"signals/{pid}/distilled.json"
        os.makedirs(os.path.join(d, "signals", pid), exist_ok=True)
        json.dump({"cell_id": pid, "kind": "distill", "result": "pass",
                   "evidence": f"{c['occurrences']}x {c['cell_type']} reached validated/operating: {c['signature']}",
                   "validated_against": {}, "ledger_refs": c.get("evidence", [])},
                  open(os.path.join(d, sig_rel), "w", encoding="utf-8"), indent=2)
        _api.seed_cell(d, "pattern", "system", slug, maturity="validated",
                       asset_ref=f"pattern/{slug}.md", signal_refs=[sig_rel])
        _led.append(d, "transition", {"kind": "server", "id": "distiller"}, {"cell": pid},
                    f"distilled pattern: {c['signature']} ({c['occurrences']}x)", frm="absent", to="validated",
                    metrics={"distilled": True, "evidence": c.get("evidence")})
        created.append(pid)
    return created


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
        _api.seed_cell(d, "spec", "task", "slice", maturity="instantiated", asset_ref="spec/slice.md")
        os.makedirs(os.path.join(d, "spec"), exist_ok=True)
        open(os.path.join(d, "spec", "slice.md"), "w").write("# slice\n")

        t = _api.create_ticket(d, "feature", "the vertical slice", target_cell="spec.task.slice",
                               target_transition={"from": "instantiated", "to": "validated"},
                               acceptance={"rubric_cell": "rubric.task.r"}, budget={"iterations": 2, "tokens": 50000})
        _api.transition_ticket(d, t["id"], "active", srv)

        # the dispatcher drives the slice to done UNATTENDED via the mock adapter
        ok, ticket, msg = dispatch_unit(d, _api.get_ticket(d, t["id"]), MockAdapter(), srv, tier=1, repo_root=root)
        expect(ok and ticket["state"] == "done", f"unattended dispatch did not reach done: {msg}")
        cell = _lat.find(_lat.load(d), "spec.task.slice")
        expect(cell["maturity"] == "validated", "dispatched slice cell not validated")
        expect(cell.get("signal_refs"), "no signal minted by the dispatched critic")
        expect(_api.get_ticket(d, t["id"]).get("claim") is None, "claim not cleared after done")
        # the worktree was torn down
        expect(not os.path.isdir(os.path.join(d, "run", "worktrees")) or
               not os.listdir(os.path.join(d, "run", "worktrees")), "worktree not torn down")

        # P3 — NO-OP HONESTY: a mock dispatch over an asset that ALREADY exists authors nothing new; the cell
        # legitimately re-validates, but the completion must be ledgered noop=true so the board reads "no change",
        # never a false "Done" implying fresh work (the richer-colors / add-808 trust trap).
        _api.seed_cell(d, "spec", "task", "exists", maturity="instantiated", asset_ref="spec/exists.md")
        open(os.path.join(d, "spec", "exists.md"), "w").write('{"already":"authored"}\n')  # structured → mock confirms, never clobbers
        te = _api.create_ticket(d, "task", "noop", target_cell="spec.task.exists",
                                target_transition={"from": "instantiated", "to": "validated"},
                                acceptance={"rubric_cell": "rubric.task.r"}, budget={"iterations": 1, "tokens": 1000})
        _api.transition_ticket(d, te["id"], "active", srv)
        okn, _tn, _mn = dispatch_unit(d, _api.get_ticket(d, te["id"]), MockAdapter(), srv, tier=2, repo_root=root)
        expect(okn, f"a no-op dispatch should still complete (the cell re-validates): {_mn}")
        expect(any(e.get("event") == "activity-complete" and (e.get("metrics") or {}).get("noop") is True
                   and (e.get("subject") or {}).get("ticket") == te["id"] for e in _led.read(d)),
               "a mock dispatch over an EXISTING asset must ledger activity-complete noop=true (no false 'Done')")
        expect(any(e.get("event") == "activity-complete" and (e.get("metrics") or {}).get("noop") is False
                   and (e.get("subject") or {}).get("ticket") == t["id"] for e in _led.read(d)),
               "a real authoring dispatch (the slice) must ledger noop=false — the honest signal discriminates")
        # ADAPTER-AGNOSTIC (the council CRITICAL): a NON-mock worker that runs but writes NOTHING (byte-identical
        # asset before/after) is also a no-op — so "Done — no change" is honest on the headless loop too, not only mock.
        class _NoWriteOk(DispatchAdapter):
            name = "nowrite-ok"
            def dispatch(self, d, unit):
                return {"ok": True, "asset_ref": "spec/exists.md", "metrics": {"tokens": 5000}}  # ran, wrote nothing
        _api.seed_cell(d, "spec", "task", "exists", maturity="instantiated", asset_ref="spec/exists.md")  # re-arm to instantiated
        tw2 = _api.create_ticket(d, "task", "headless-noop", target_cell="spec.task.exists",
                                 target_transition={"from": "instantiated", "to": "validated"},
                                 acceptance={"rubric_cell": "rubric.task.r"}, budget={"iterations": 1, "tokens": 1000})
        _api.transition_ticket(d, tw2["id"], "active", srv)
        dispatch_unit(d, _api.get_ticket(d, tw2["id"]), _NoWriteOk(), srv, tier=2, repo_root=root)
        expect(any(e.get("event") == "activity-complete" and (e.get("metrics") or {}).get("noop") is True
                   and (e.get("subject") or {}).get("ticket") == tw2["id"] for e in _led.read(d)),
               "a NON-mock worker that wrote nothing (byte-identical asset) must ledger noop=true — Done is honest on headless too")

        # lease reconciliation: a claimed ticket with an EXPIRED lease returns to active
        t2 = _api.create_ticket(d, "task", "stuck", target_cell="spec.task.slice",
                                target_transition={"from": "validated", "to": "operating"},
                                acceptance={"rubric_cell": "rubric.task.r"}, budget={"iterations": 1, "tokens": 1000})
        _api.transition_ticket(d, t2["id"], "active", srv)
        _api.transition_ticket(d, t2["id"], "claimed", srv)
        stuck = _api.get_ticket(d, t2["id"])
        stuck["claim"] = {"worker_id": "wrk-dead", "worktree": "x",
                          "lease_expiry": _iso(_now() - datetime.timedelta(seconds=10))}
        _lc.save_ticket(d, stuck)
        reclaimed = reconcile_leases(d)
        expect(t2["id"] in reclaimed, "expired-lease ticket not reclaimed")
        expect(_api.get_ticket(d, t2["id"])["state"] == "active", "reclaimed ticket not returned to active")

        # in-review awaiting HUMAN sign-off (Tier 1, auto_validate=False) must survive lease reconciliation:
        # the worker handed off and the critic validated, so the lease is cleared at the in-review hand-off and
        # reconcile_leases skips it (a pending human approval is not a dead worker). Regression for the reaper
        # that bounced completed, critic-validated work back to `active` after LEASE_TTL_S.
        _api.seed_cell(d, "spec", "task", "review", maturity="instantiated", asset_ref="spec/review.md")
        open(os.path.join(d, "spec", "review.md"), "w").write("# review\n")
        tr = _api.create_ticket(d, "feature", "awaiting sign-off", target_cell="spec.task.review",
                                target_transition={"from": "instantiated", "to": "validated"},
                                acceptance={"rubric_cell": "rubric.task.r"}, budget={"iterations": 2, "tokens": 50000})
        _api.transition_ticket(d, tr["id"], "active", srv)
        ok, ticket, msg = dispatch_unit(d, _api.get_ticket(d, tr["id"]), MockAdapter(), srv,
                                        tier=1, repo_root=root, auto_validate=False)
        expect(ok and ticket["state"] == "in-review", f"Tier-1 gated dispatch did not reach in-review: {msg}")
        expect(_api.get_ticket(d, tr["id"]).get("claim") is None,
               "lease not cleared at in-review hand-off — reconcile_leases would reap awaiting-human work")
        reclaimed2 = reconcile_leases(d)
        expect(tr["id"] not in reclaimed2, "in-review ticket awaiting human sign-off was wrongly reaped")
        expect(_api.get_ticket(d, tr["id"])["state"] == "in-review",
               "awaiting-human ticket bounced off in-review by the lease reaper")
        # P2 — ACCEPTANCE: the operator's accept_reviewed transitions the critic-validated in-review ticket to done
        # through the same gate-signal path a manual drag uses (the human sign-off; auto-accept calls this each tick).
        accepted = _api.accept_reviewed(d, srv)
        expect(tr["id"] in accepted and _api.get_ticket(d, tr["id"])["state"] == "done",
               "accept_reviewed must close a critic-validated in-review ticket to done (the human-acceptance gate)")

        # WEDGE FIX: a CLAIMED ticket with NO lease (an empty/missing claim — the dispatch died after the claimed
        # transition but before establishing the lease) is a permanent wedge the reaper could never expire (observed
        # live: a ticket claimed with `claim: {}`, unreapable for hours while the loop ran). It must be reaped to
        # active — distinct from the in-review hand-off above, which (also laceless) is correctly LEFT for the human.
        _api.seed_cell(d, "spec", "task", "wedge", maturity="instantiated", asset_ref="spec/wedge.md")
        open(os.path.join(d, "spec", "wedge.md"), "w").write("# wedge\n")
        tw = _api.create_ticket(d, "task", "laceless claim", target_cell="spec.task.wedge",
                                target_transition={"from": "instantiated", "to": "validated"},
                                acceptance={"rubric_cell": "rubric.task.r"}, budget={"iterations": 1, "tokens": 1000})
        _api.transition_ticket(d, tw["id"], "active", srv)
        okc, _tw, _mc = _api.transition_ticket(d, tw["id"], "claimed", srv)   # claimed, but NO claim object is written
        expect(okc and (_api.get_ticket(d, tw["id"]).get("claim") or {}).get("lease_expiry") is None,
               "setup: the ticket must be claimed with a laceless claim")
        reclaimed3 = reconcile_leases(d)
        expect(tw["id"] in reclaimed3, "a CLAIMED ticket with NO lease must be reaped (the unreapable-wedge fix)")
        expect(_api.get_ticket(d, tw["id"])["state"] == "active",
               "the laceless-claim ticket was not returned to active by the reaper")

        # retry-then-block, TWO backstops: a transient worker failure RETRIES (self-recovers instead of wedging the
        # build), but the kernel's signature detector (ledger.no_progress, n=2) blocks a DETERMINISTICALLY stuck cell
        # EARLY — two IDENTICAL failure signatures → block at attempt 2 (don't burn the 3rd on a futile loop), while
        # DISTINCT failures retry up to the attempt cap (they might be transient). The failed run's spend is counted.
        def _drive_to_block(slug, adapter):
            _api.seed_cell(d, "spec", "task", slug, maturity="instantiated", asset_ref=f"spec/{slug}.md")
            open(os.path.join(d, "spec", f"{slug}.md"), "w").write(f"# {slug}\n")
            tk = _api.create_ticket(d, "task", slug, target_cell=f"spec.task.{slug}",
                                    target_transition={"from": "instantiated", "to": "validated"},
                                    acceptance={"rubric_cell": "rubric.task.r"}, budget={"iterations": 1, "tokens": 1000})
            _api.transition_ticket(d, tk["id"], "active", srv)
            states = []
            for _ in range(MAX_WORKER_ATTEMPTS + 1):
                if _api.get_ticket(d, tk["id"])["state"] == "blocked":
                    break
                dispatch_unit(d, _api.get_ticket(d, tk["id"]), adapter, srv, tier=1, repo_root=root)
                states.append(_api.get_ticket(d, tk["id"])["state"])
            return tk, states
        class _AlwaysFail(DispatchAdapter):
            name = "always-fail"
            def dispatch(self, d, unit):
                return {"ok": False, "error": "boom (test)", "metrics": {"tokens": 500}}
        class _VaryFail(DispatchAdapter):
            name = "vary-fail"
            _i = 0
            def dispatch(self, d, unit):
                _VaryFail._i += 1
                return {"ok": False, "error": f"distinct failure {_VaryFail._i}", "metrics": {"tokens": 500}}
        tf, seen = _drive_to_block("flaky", _AlwaysFail())
        expect(seen == ["active", "blocked"],
               f"two IDENTICAL failure signatures must BLOCK early (no-progress detector), got {seen}")
        _tv, seenv = _drive_to_block("flaky2", _VaryFail())
        expect(seenv == ["active", "active", "blocked"],
               f"DISTINCT failures must retry to the attempt cap, not early-block, got {seenv}")
        # smart retry: after a failure, the next dispatch's prompt folds the SPECIFIC gate failure (so the worker
        # fixes that, not re-reads the contract blind) — and it resets on a success.
        expect(_last_failure(d, tf["id"]) is not None, "_last_failure surfaces the prior gate failure for the retry prompt")
        fp = HeadlessClaudeAdapter()._prompt(d, {"layer": "spec", "scope": "task", "slug": "flaky", "ticket": tf["id"],
                                                 "transition": {"from": "instantiated", "to": "validated"}}, root)
        expect("PREVIOUS attempt" in fp and "boom (test)" in fp, "the retry prompt folds the specific prior failure")

        # Feature A: the HeadlessClaudeAdapter folds the operator's recent guidance into a NEWLY dispatched
        # worker's prompt (a running one-shot worker can't be steered mid-flight; the NEXT dispatch is).
        unit = {"layer": "spec", "scope": "task", "slug": "slice", "transition": {"from": "instantiated", "to": "validated"}}
        hca = HeadlessClaudeAdapter()
        expect("Recent operator guidance" not in hca._prompt(d, unit, root), "guidance clause must be absent on an empty buffer")
        _api.enqueue_input(d, "make the leaderboard top-10 only", source="operator")
        _api.drain_input(d)
        expect("make the leaderboard top-10 only" in hca._prompt(d, unit, root),
               "a newly dispatched worker's prompt must fold the latest operator guidance")

        # DF-9 (Phase 1): a kit that DECLARES multi-file authoring makes a code cell author a DIRECTORY of
        # source (not one {slug}.md), and the worker prompt demands industrial multi-file code graded by the
        # cell's per-cell verify.mjs critic harness. Hermetic: a temp kit, no env, no node.
        kitdir = os.path.join(root, "kitx"); os.makedirs(kitdir, exist_ok=True)
        json.dump({"name": "dev-kit-x", "family": "x", "authoring": [{"layer": "capability", "mode": "multi-file"}]},
                  open(os.path.join(kitdir, "kit.json"), "w"))
        capcell = {"layer": "capability", "slug": "deck"}
        auth = _authoring_for(capcell, kit_dir=kitdir)
        expect(auth and auth.get("mode") == "multi-file", "kit-declared multi-file authoring not detected")
        expect(_asset_rel("capability", "deck", auth) == os.path.join("capability", "deck"),
               "a multi-file capability's asset must be a DIRECTORY, not {slug}.md")
        expect(_asset_rel("spec", "s", None) == os.path.join("spec", "s.md"), "doc cells must stay single-file")
        capunit = {"layer": "capability", "scope": "system", "slug": "deck", "transition": {"from": "instantiated", "to": "validated"}}
        os.environ["DEV_FACTORY_KIT"] = kitdir
        try:
            p = hca._prompt(d, capunit, root)
        finally:
            del os.environ["DEV_FACTORY_KIT"]
        expect("multiple files under" in p and "verify.mjs" in p and "CANNOT write it" in p,
               "the multi-file worker prompt must demand source files + name the worker-protected verify.mjs gate")

        # the shell-authoring gap fix: a slug-specific SINGLE-FILE authoring entry routes the integration SHELL
        # to a root index.html (NOT a ../shell/ dir) and gives it a bootstrap prompt that imports+mounts the
        # already-built modules — so the factory can author the shell, not just the modules.
        kits = os.path.join(root, "kits"); os.makedirs(kits, exist_ok=True)
        json.dump({"name": "dev-kit-s", "family": "s", "authoring": [
            {"layer": "capability", "slug": "shell", "mode": "single-file", "output_root": "..", "entry": "index.html"},
            {"layer": "capability", "mode": "multi-file"}]}, open(os.path.join(kits, "kit.json"), "w"))
        ashell = _authoring_for({"layer": "capability", "slug": "shell"}, kit_dir=kits)
        acore = _authoring_for({"layer": "capability", "slug": "core"}, kit_dir=kits)
        expect(ashell and ashell.get("mode") == "single-file", "the slug-specific shell entry must win over the multi-file layer-default")
        expect(acore and acore.get("mode") == "multi-file", "a non-shell capability must still get the multi-file layer-default")
        expect(_asset_rel("capability", "shell", ashell) == os.path.join("..", "index.html"),
               "the shell's asset must be a single index.html at the product ROOT, not a ../shell/ dir")
        os.environ["DEV_FACTORY_KIT"] = kits
        try:
            ps = hca._prompt(d, {"layer": "capability", "scope": "system", "slug": "shell", "transition": {"from": "regenerating", "to": "validated"}}, root)
        finally:
            del os.environ["DEV_FACTORY_KIT"]
        expect("INTEGRATION SHELL" in ps and "index.html" in ps and "ALREADY BUILT" in ps,
               "the shell prompt must be a root-entry bootstrap that imports+mounts the already-built modules")
        # the MockAdapter shell BUILD must import the first REAL built sibling module, never a hardcoded ./core/
        # (else a mock shell over a non-`core` decomposition emits an import the render gate correctly refuses).
        proot = os.path.dirname(d)
        os.makedirs(os.path.join(proot, "engine"), exist_ok=True)
        open(os.path.join(proot, "engine", "index.mjs"), "w").write("export const ready = true;\n")
        os.environ["DEV_FACTORY_KIT"] = kits
        try:
            MockAdapter().dispatch(d, {"layer": "capability", "scope": "system", "slug": "shell", "ticket": "t"})
        finally:
            del os.environ["DEV_FACTORY_KIT"]
        shell_html = open(os.path.join(proot, "index.html"), encoding="utf-8").read()
        expect("import './engine/index.mjs'" in shell_html and "./core/" not in shell_html,
               "the mock shell must import the first BUILT sibling module (./engine/), not a hardcoded ./core/")

        # #2 (factory-authored verifiers): a kind=verifier dispatch authors the cell's REAL critic harness, not
        # a `ready` stub. The headless prompt is the rubric-architect's (tests the SPEC); the mock writes a smoke
        # check via author_verifier. Also confirms the obsolete is_integrator branch is GONE from the module prompt.
        os.environ["DEV_FACTORY_KIT"] = kits
        try:
            vp = hca._prompt(d, {"layer": "capability", "scope": "system", "slug": "core", "kind": "verifier"}, root)
            # a multi-file MODULE that depends on another capability is still just a module — no integrator prompt
            modp = hca._prompt(d, {"layer": "capability", "scope": "system", "slug": "core", "transition": {"from": "regenerating", "to": "validated"}}, root)
        finally:
            del os.environ["DEV_FACTORY_KIT"]
        expect("RUBRIC-ARCHITECT" in vp and "verify.mjs" in vp and "ready === true" in vp and "spec-conformance" in vp,
               "the verifier prompt must task the rubric-architect with a REAL spec-conformance verify.mjs (not a ready check)")
        expect("INTEGRATOR" not in modp and "mount(document.getElementById" not in modp,
               "the obsolete is_integrator branch must be GONE from the module prompt (integration is the shell cell)")
        # author_verifier via the mock writes a verify.mjs at the cell dir (the factory authors the gate)
        os.makedirs(os.path.join(d, "vf", "core"), exist_ok=True)
        kitv = os.path.join(d, "vf", "kit.json")
        json.dump({"name": "k", "authoring": [{"layer": "capability", "mode": "multi-file", "output_root": "."}]}, open(kitv, "w"))
        os.environ["DEV_FACTORY_KIT"] = os.path.join(d, "vf")
        try:
            r = author_verifier(os.path.join(d, "vf"), {"layer": "capability", "scope": "system", "slug": "core"}, MockAdapter())
        finally:
            del os.environ["DEV_FACTORY_KIT"]
        expect(r.get("ok") and os.path.isfile(os.path.join(d, "vf", "core", "verify.mjs")),
               "author_verifier must make the factory author the cell's verify.mjs critic harness")
        # the verifier-author PASS authors a harness for every listed cell (run before the modules build)
        os.environ["DEV_FACTORY_KIT"] = os.path.join(d, "vf")
        try:
            passres = author_app_verifiers(os.path.join(d, "vf"), ["core", "store"], MockAdapter(), repo_root=os.path.join(d, "vf"))
        finally:
            del os.environ["DEV_FACTORY_KIT"]
        expect(passres == {"core": True, "store": True}
               and os.path.isfile(os.path.join(d, "vf", "store", "verify.mjs")),
               "author_app_verifiers must author a real verify.mjs for EVERY listed capability cell")
        # _is_mock_verifier drives the verifier-author DEFAULT: a seeded `ready` stub → True; a real harness →
        # False; the single-file shell (render-gated) → False; a missing harness → True.
        vfd = os.path.join(d, "vf")
        os.environ["DEV_FACTORY_KIT"] = vfd
        try:
            corecell = {"layer": "capability", "scope": "system", "slug": "core"}
            vp = os.path.join(vfd, "core", "verify.mjs")
            open(vp, "w").write("import { ready } from './index.mjs';\nif(!ready)process.exit(1);\n")
            expect(_is_mock_verifier(vfd, corecell), "_is_mock_verifier must flag a seeded ready-stub (named-import form)")
            # the MockAdapter SMOKE stub (`import * as m`, only READS m.ready) — the old `import { ready }` heuristic
            # MISSED this, so a mock build's gate posed as 'real' on the next headless run (H2-M2 regression guard):
            open(vp, "w").write("import * as m from './index.mjs';\nif (m.ready !== true) process.exit(1);\nconsole.log('pass');\n")
            expect(_is_mock_verifier(vfd, corecell), "_is_mock_verifier must flag the import-* smoke stub (reads m.ready only)")
            # length-independence: a long but vacuous harness carrying the mock sentinel is still a stub:
            open(vp, "w").write(f"// {_MOCK_VERIFIER_MARK}\nimport * as m from './index.mjs';\n" + "// pad\n" * 20 + "console.log('pass');\n")
            expect(_is_mock_verifier(vfd, corecell), "_is_mock_verifier must flag any harness carrying the mock sentinel, regardless of length")
            # a REAL harness EXERCISES an export (calls it) — that is the behavioral discriminator, not line count:
            open(vp, "w").write("import * as m from './index.mjs';\nconst r = m.compute(2, 3);\nif (r !== 5) { console.error('FAIL'); process.exit(1); }\nconsole.log('pass');\n")
            expect(not _is_mock_verifier(vfd, corecell), "_is_mock_verifier must NOT flag a real harness that exercises a module export")
            expect(not _is_mock_verifier(vfd, {"layer": "spec", "scope": "system", "slug": "app"}),
                   "_is_mock_verifier must skip non-multi-file cells (doc/spec, or the render-gated shell)")
            # H6 producer: _exports_from_verify recovers the API; produce_refuter arms an INDEPENDENT oracle for a
            # validated code cell so the false-pass oracle can MEASURE it (without it Tier 2 is unreachable).
            expect(_exports_from_verify('const required = ["a", "b"];\nm.foo(1);\nm.ready;') == ["a", "b", "foo"],
                   "_exports_from_verify must recover the required[] array + m.<call> exports, excluding ready")
            _api.seed_cell(vfd, "capability", "system", "core", maturity="validated", asset_ref="core")
            open(vp, "w").write("import * as m from './index.mjs';\nif (m.deal(3).length !== 3) process.exit(1);\nconsole.log('ok');\n")
            side = os.path.join(vfd, "coordination", "refuters", "capability.system.core.json")
            expect(produce_refuter(vfd, "capability.system.core") == "capability.system.core" and os.path.isfile(side),
                   "produce_refuter must arm an independent refuter sidecar for a validated code cell (H6 producer)")
            # KEYSTONE: with no behavioral refute set, the armed oracle is the generic floor → measuring=False, so
            # it can NEVER mint a measured false-pass / auto-grant Tier 2 (the tautological-refuter bug).
            expect(json.load(open(side)).get("measuring") is False,
                   "produce_refuter must arm a NON-measuring liveness floor when no behavioral refute set exists")
            expect(produce_refuter(vfd, "capability.system.core") is None,
                   "produce_refuter must be idempotent — never clobber an existing/self-heal-re-armed oracle")
            # a pre-authored BEHAVIORAL refute set → a MEASURING refuter
            _api.seed_cell(vfd, "capability", "system", "store", maturity="validated", asset_ref="store")
            os.makedirs(os.path.join(vfd, "store"), exist_ok=True)
            open(os.path.join(vfd, "store", "verify.mjs"), "w").write("import * as m from './index.mjs';\nif (!m.save) process.exit(1);\n")
            os.makedirs(os.path.join(vfd, "coordination", "verify-spec"), exist_ok=True)
            json.dump({"exports": ["save"], "acceptance": [], "refute": ["save(1) === 1"], "generation": 0, "history": []},
                      open(os.path.join(vfd, "coordination", "verify-spec", "capability.system.store.json"), "w"))
            produce_refuter(vfd, "capability.system.store")
            sside = os.path.join(vfd, "coordination", "refuters", "capability.system.store.json")
            expect(json.load(open(sside)).get("measuring") is True,
                   "produce_refuter must arm a MEASURING refuter from a behavioral refute set (save(1) invokes the export)")
            # the REFUTE-AUTHOR producer (task #20 — autonomous Tier 2):
            #  · the frontier lists the validated, real-gated, still-UNMEASURED cell (core, liveness-only) and EXCLUDES
            #    the already-measuring one (store) — the gate-blind author's work-list.
            front = refute_author_frontier(vfd)
            expect("capability.system.core" in front and "capability.system.store" not in front,
                   f"refute_author_frontier must list the unmeasured real-gated cell, not the measuring one (got {front})")
            #  · the MOCK refute-author is an HONEST no-op (it cannot synthesize a domain oracle) — it fabricates no
            #    measurement, so core stays liveness-only after a mock author pass (only a headless author measures).
            mr = MockAdapter().dispatch(vfd, {"kind": "refute-author", "target_cell": "capability.system.core",
                                              "layer": "capability", "scope": "system", "slug": "core"})
            expect(mr.get("ok") and mr.get("mock_no_oracle") is True,
                   "the mock refute-author must be an honest no-op (ok, mock_no_oracle) — it never fabricates measurement")
            #  · the UPGRADE path: a behavioral set authored into core's verify-spec promotes its liveness floor to
            #    MEASURING (produce_refuter re-evaluates a liveness-only sidecar — the autonomous author's landing point).
            json.dump({"exports": ["deal"], "acceptance": ["deal(3).length === 3"], "refute": ["deal(5).length === 5"],
                       "generation": 0, "history": []},
                      open(os.path.join(vfd, "coordination", "verify-spec", "capability.system.core.json"), "w"))
            expect(produce_refuter(vfd, "capability.system.core") == "capability.system.core"
                   and json.load(open(side)).get("measuring") is True,
                   "produce_refuter must UPGRADE a liveness floor to MEASURING once a behavioral refute set is authored")
            #  · a POSITIVE-FORM gate-copy is REJECTED by the SERVER-trusted gate-SOURCE arm — produce_refuter does NOT
            #    trust the verify-spec's worker-writable `acceptance` (round 6 CRITICAL); independence is from the gate.
            _api.seed_cell(vfd, "capability", "system", "copycell", maturity="validated", asset_ref="copycell")
            os.makedirs(os.path.join(vfd, "copycell"), exist_ok=True)
            open(os.path.join(vfd, "copycell", "verify.mjs"), "w").write(
                "import * as m from './index.mjs';\nconst ok = (m.f(2) === 4);\nif (!ok) process.exit(1);\nconsole.log('ok');\n")
            json.dump({"exports": ["f"], "acceptance": [], "refute": ["f(2) === 4"], "generation": 0, "history": []},
                      open(os.path.join(vfd, "coordination", "verify-spec", "capability.system.copycell.json"), "w"))
            produce_refuter(vfd, "capability.system.copycell")
            expect(json.load(open(os.path.join(vfd, "coordination", "refuters", "capability.system.copycell.json"))).get("measuring") is False,
                   "produce_refuter must REJECT a positive-form gate-copy via the server-trusted gate-SOURCE arm (not the worker's acceptance)")
            #  · provenance (the human-glance gate): produce_refuter stamps a non-registered (human-authored) oracle
            #    autonomous:false → TRUSTED; the server-owned, worker-protected registry marks an autonomous cell so a
            #    measuring upgrade in EITHER the author pass OR a later sweep is stamped. (The full register→stamp→tier
            #    chain — autonomous measures but caps at Tier 1 — is exercised end-to-end by the earned-autonomy eval H7.)
            expect(json.load(open(sside)).get("autonomous") is False and not _is_autonomous_cell(vfd, "capability.system.store"),
                   "produce_refuter must stamp a non-registered (human-authored) oracle autonomous:false → trusted")
            _register_autonomous(vfd, "capability.system.store")
            expect(_is_autonomous_cell(vfd, "capability.system.store"),
                   "_register_autonomous records the cell in the server-owned registry (untamperable provenance)")
            # _gate_scoped_refute (the round-7 decoy close, node-free): the mutation proof's witness must be on the
            # gate's CONTRACT surface. A refute riding a NON-spec export (`_k()`) is dropped; a real-export check at a
            # new input is kept; a method call (`.foo(`) doesn't disqualify; a no-call reference is dropped.
            expect(_gate_scoped_refute(["compute(7,8) === 15", "_k() === 7"], ["compute"]) == ["compute(7,8) === 15"],
                   "_gate_scoped_refute must DROP an assertion that calls a non-gate export (the decoy tripwire)")
            expect(_gate_scoped_refute(["deal(5).length === 5"], ["deal"]) == ["deal(5).length === 5"],
                   "_gate_scoped_refute must KEEP a real gate-export call at a new input (method `.length` is not a free call)")
            expect(_gate_scoped_refute(["Math.max(compute(1,2), 0) === compute(1,2)"], ["compute"]) == ["Math.max(compute(1,2), 0) === compute(1,2)"],
                   "_gate_scoped_refute must KEEP a JS global (Math) + a gate-export call")
            expect(_gate_scoped_refute(["_k === 7", "secret() === 1"], ["compute"]) == [],
                   "_gate_scoped_refute must DROP a no-call reference and a non-gate-export call (no on-contract assertion remains)")
        finally:
            del os.environ["DEV_FACTORY_KIT"]

        # team EXECUTION: a delegation=team plan makes the worker an ORCHESTRATOR that spawns the planned sub-agent
        # team (the Task tool is added; the prompt names the depth) — so 'team, depth 2' is executed, not just ledgered.
        team_unit = dict(capunit, plan={"orchestration_shape": "orchestrator-workers", "loop_strategy": "tracer-bullet",
                                        "effort": {"parallelism": 2, "model_tier": "mid"},
                                        "delegation": {"mode": "team", "max_depth": 2}})
        os.environ["DEV_FACTORY_KIT"] = kitdir
        try:
            tp = hca._prompt(d, team_unit, root)
        finally:
            del os.environ["DEV_FACTORY_KIT"]
        expect("ORCHESTRATOR" in tp and "Task tool" in tp and "depth of 2" in tp,
               "a team-delegation plan must produce an orchestrator prompt that delegates to the planned depth")
        expect("Task" in hca._allowed_tools(team_unit), "delegation=team must add the Task tool to the worker scope")
        expect("Task" not in hca._allowed_tools(capunit), "a non-delegating plan must NOT add the Task tool")
        # the signal-forge floor (H3-C1): NO headless worker carries Bash — not the module worker, not the
        # verifier-author — so no worker can shell an inline-interpreter write past the gate's redirect heuristic.
        for u in (capunit, dict(capunit, kind="verifier"), team_unit):
            expect("Bash" not in hca._allowed_tools(u).split(","),
                   f"a headless worker must NEVER carry Bash (the inline-interpreter forge floor); unit kind={u.get('kind')}")

        # adapter selection: DEV_FACTORY_ADAPTER=headless picks the LIVE worker; default is the free mock loop
        expect(isinstance(resolve_adapter("mock"), MockAdapter) and isinstance(resolve_adapter("headless"), HeadlessClaudeAdapter),
               "resolve_adapter must select mock|headless by name")
        expect(adapter_name() == "mock", "adapter_name defaults to mock (free) when DEV_FACTORY_ADAPTER is unset")
        os.environ["DEV_FACTORY_ADAPTER"] = "headless"
        try:
            expect(adapter_name() == "headless" and isinstance(resolve_adapter(), HeadlessClaudeAdapter),
                   "DEV_FACTORY_ADAPTER=headless selects the live adapter (real workers, opt-in)")
        finally:
            del os.environ["DEV_FACTORY_ADAPTER"]

    # token/cost attribution: the REAL `claude` stream-json result shape (captured live) — cost is `total_cost_usd`,
    # tokens are the summed top-level `*_tokens` scalars in `usage`. Guards the false-frugal $0.00 blind spot.
    real_result = {"type": "result", "total_cost_usd": 0.277625, "usage": {
        "input_tokens": 16244, "cache_creation_input_tokens": 18792, "cache_read_input_tokens": 15626,
        "output_tokens": 4, "server_tool_use": {"web_search_requests": 0}, "service_tier": "standard",
        "cache_creation": {"ephemeral_1h_input_tokens": 18792, "ephemeral_5m_input_tokens": 0}}}
    rc, rt = _result_spend(real_result)
    expect(rc == 0.277625, "result spend reads cost from `total_cost_usd` (not the dropped `cost_usd`)")
    expect(rt == 16244 + 18792 + 15626 + 4, "result spend sums the top-level *_tokens (skips nested cache_creation/server_tool_use dicts)")
    expect(_result_spend({"type": "result", "cost_usd": 0.5})[0] == 0.5, "result spend falls back to legacy `cost_usd`")
    expect(_result_spend({"type": "result"}) == (None, None), "result spend is (None, None) when usage/cost absent")

    # distill→patterns: the emergent pattern layer must NOT distill from itself (no pattern.system.pattern-system regress)
    with tempfile.TemporaryDirectory() as td:
        di = os.path.join(td, ".agents", "dev-factory"); _api.init_instance(di)
        _api.seed_cell(di, "ledger", "system", "provenance", maturity="validated", signal_refs=["s/x"])
        for sl in ("a", "b"):
            _led.append(di, "transition", {"kind": "server", "id": "s"}, {"cell": f"spec.system.{sl}"}, "adv", frm="instantiated", to="validated")
        for sl in ("p", "q", "r"):
            _led.append(di, "transition", {"kind": "server", "id": "s"}, {"cell": f"capability.system.{sl}"}, "adv", frm="instantiated", to="validated")
        pats = set()
        for _ in range(4):                                   # run to fixpoint — a regress would mint pattern-from-pattern
            pats |= set(distill_to_patterns(di))
        expect("pattern.system.spec-system" in pats and "pattern.system.capability-system" in pats,
               "distill→patterns mints a pattern per recurring substantive cell-type (spec, capability)")
        expect("pattern.system.pattern-system" not in pats,
               "distill→patterns NEVER distills the pattern layer from itself (no meta-pattern regress)")

    # ── AUTO-TRIAGE (prompt → bound ticket, no human) + the OVERWRITE GUARD ──────────────────────────────────
    with tempfile.TemporaryDirectory() as troot:
        td = os.path.join(troot, "src", "demo", ".factory")
        _api.init_instance(td)
        tsrv = {"kind": "server", "id": "dev-server"}
        _api.seed_cell(td, "rubric", "system", "ship", maturity="validated", signal_refs=["signals/rubric.system.ship/s.json"])
        _api.seed_cell(td, "spec", "system", "feature-x", maturity="instantiated", asset_ref="spec/feature-x.md")
        os.makedirs(os.path.join(td, "spec"), exist_ok=True)
        open(os.path.join(td, "spec", "feature-x.md"), "w").write("# feature-x\n")

        # a free-text PROMPT intake lands parked + untriaged, ON the triage frontier
        pr = _api.create_ticket(td, "prompt", "add feature X", body="please add feature X to the spec")
        expect(pr["id"].startswith("iss-") and pr["state"] == "draft", "a prompt intake is a parked iss- draft")
        expect(triage_frontier(td) == [pr["id"]], "the untriaged prompt is on the triage frontier")

        # MOCK is a HARD no-op — the loop cannot triage on mock (binding a prompt is judgment, not a transform)
        expect(triage_intake(td, MockAdapter()) == {}, "triage_intake must be a hard no-op on mock")
        expect(_api.get_ticket(td, pr["id"])["state"] == "draft", "mock triage left the intake untriaged")

        # a stub headless adapter writes the triager's PROPOSAL (a valid binding) — the server applies + activates it
        class _TriageStub(DispatchAdapter):
            name = "triage-stub"
            proposal = None
            def dispatch(self, d, unit):
                p = os.path.join(d, "coordination", "triage", f"{unit['ticket']}.json")
                os.makedirs(os.path.dirname(p), exist_ok=True)
                json.dump(_TriageStub.proposal, open(p, "w"))
                return {"ok": True, "asset_ref": os.path.relpath(p, d), "metrics": {"tokens": 1000}}
        _TriageStub.proposal = {"new_type": "feature", "target_cell": "spec.system.feature-x",
                                "target_transition": {"from": "instantiated", "to": "validated"},
                                "acceptance": {"rubric_cell": "rubric.system.ship"},
                                "budget": {"iterations": 2, "tokens": 50000}, "dependencies": {"cells": []}}
        res = triage_intake(td, _TriageStub(), repo_root=troot)
        expect(res.get(pr["id"], {}).get("active"), f"a valid proposal must auto-triage the prompt to active: {res}")
        tt = _api.get_ticket(td, pr["id"])
        expect(tt["state"] == "active" and tt.get("target_cell") == "spec.system.feature-x",
               "the auto-triaged ticket is active + bound to the proposed cell (zero human triage)")
        expect(pr["id"] not in triage_frontier(td), "a triaged ticket leaves the triage frontier")
        expect(any(e.get("event") == "handoff" and (e.get("metrics") or {}).get("triage")
                   and (e.get("metrics") or {}).get("tokens") == 1000 for e in _led.read(td)),
               "the triage dispatch's spend (tokens/cost) must be LEDGERED so the armed window's ceiling sees it (H5-C1)")

        # an ILLEGAL proposal (unvalidated rubric) PARKS (no crash): triage_issue binds it, gate-ticket-ready refuses
        # active. Run while the frontier holds ONLY pr2 (pr is already active) so triage_intake(limit=1) targets it.
        _api.seed_cell(td, "rubric", "system", "draftrub", maturity="instantiated")          # NOT validated
        _api.seed_cell(td, "spec", "system", "feature-y", maturity="instantiated", asset_ref="spec/feature-y.md")
        open(os.path.join(td, "spec", "feature-y.md"), "w").write("# y\n")
        pr2 = _api.create_ticket(td, "prompt", "add feature Y", body="...")
        _TriageStub.proposal = {"new_type": "feature", "target_cell": "spec.system.feature-y",
                                "target_transition": {"from": "instantiated", "to": "validated"},
                                "acceptance": {"rubric_cell": "rubric.system.draftrub"}}
        res2 = triage_intake(td, _TriageStub(), repo_root=troot)
        expect(res2.get(pr2["id"], {}).get("active") is False, "an unvalidated-rubric proposal must NOT reach active")
        expect(_api.get_ticket(td, pr2["id"])["state"] != "active", "the illegally-bound ticket parks (not active)")
        expect(any(e.get("event") == "triage-attempt" and (e.get("subject") or {}).get("ticket") == pr2["id"]
                   for e in _led.read(td)), "a parked triage ledgers a triage-attempt (anti-livelock)")

        # cross-ticket PROVENANCE: a PLANTED proposal for an intake is cleared before that intake's own triage
        # dispatch, so a stub that writes nothing leaves it PARKED — only THIS dispatch's write is ever applied
        # (closes the laundering vector the --allow-triage dir-wide write would otherwise open). pr2 is now a typed
        # `feature` (off the frontier), so the frontier holds ONLY pr3 and triage_intake(limit=1) targets it.
        pr3 = _api.create_ticket(td, "prompt", "planted", body="...")
        os.makedirs(os.path.join(td, "coordination", "triage"), exist_ok=True)
        json.dump({"new_type": "feature", "target_cell": "spec.system.feature-x",
                   "target_transition": {"from": "instantiated", "to": "validated"},
                   "acceptance": {"rubric_cell": "rubric.system.ship"}},
                  open(os.path.join(td, "coordination", "triage", f"{pr3['id']}.json"), "w"))
        class _NoWrite(DispatchAdapter):
            name = "no-write"
            def dispatch(self, d, unit):
                return {"ok": False}        # writes nothing — the planted proposal must already have been cleared
        res3 = triage_intake(td, _NoWrite(), repo_root=troot)
        expect(res3.get(pr3["id"], {}).get("applied") is False,
               "a PLANTED proposal must be cleared before the dispatch — a no-write triage leaves it parked (no laundering)")
        expect(_api.get_ticket(td, pr3["id"])["state"] == "draft", "the planted-but-cleared intake stays an untriaged draft")

        # the OVERWRITE GUARD: a SETTLED cell's hand-authored asset is never re-clobbered by a (re-)dispatch.
        # Simulate the lease-reaper case: the ticket went active while the cell was instantiated, then the cell
        # validated; a re-dispatch must refuse rather than stub over the real asset.
        _api.seed_cell(td, "spec", "system", "shipped", maturity="instantiated", asset_ref="spec/shipped.md")
        real = os.path.join(td, "spec", "shipped.md")
        open(real, "w").write("# shipped\n\nHAND-AUTHORED content the loop must NOT clobber.\n")
        before = open(real, encoding="utf-8").read()
        og = _api.create_ticket(td, "task", "re-author shipped", target_cell="spec.system.shipped",
                                target_transition={"from": "instantiated", "to": "validated"},
                                acceptance={"rubric_cell": "rubric.system.ship"})
        _api.transition_ticket(td, og["id"], "active", tsrv)                                  # legal while instantiated
        _api.seed_cell(td, "spec", "system", "shipped", maturity="validated", asset_ref="spec/shipped.md")  # now SETTLED
        ok_g, _tg, msg_g = dispatch_unit(td, _api.get_ticket(td, og["id"]), MockAdapter(), tsrv, tier=2, repo_root=troot)
        expect(not ok_g and "overwrite guard" in (msg_g or ""), f"the guard must refuse re-authoring a settled cell: {msg_g}")
        expect(open(real, encoding="utf-8").read() == before, "the hand-authored asset was NOT clobbered by the guarded dispatch")
        expect(_api.get_ticket(td, og["id"])["state"] == "blocked", "the guarded ticket is blocked (surfaces to the operator)")
        # the guard EXEMPTS the deliberate promotion — validated->operating is a legal re-dispatch, not a clobber
        op = _api.create_ticket(td, "task", "promote", target_cell="spec.system.shipped",
                                target_transition={"from": "validated", "to": "operating"},
                                acceptance={"rubric_cell": "rubric.system.ship"})
        _api.transition_ticket(td, op["id"], "active", tsrv)
        _okp, _tp2, msg_p = dispatch_unit(td, _api.get_ticket(td, op["id"]), MockAdapter(), tsrv, tier=2, repo_root=troot)
        expect("overwrite guard" not in (msg_p or ""), f"the guard must NOT fire on a validated->operating promotion: {msg_p}")

    if fails:
        sys.stderr.write("dispatch selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("dispatch selftest: OK (provision worktree -> claimed(single-writer)+lease -> worker authors -> "
          "critic validates -> done, UNATTENDED, with the worktree torn down and the claim cleared; an expired "
          "lease returns a stuck ticket to active — crash recovery without reconciling competing claims; a newly "
          "dispatched worker's prompt folds the operator's recent 5s guidance; a kit that declares multi-file "
          "authoring routes a code cell to a source DIRECTORY graded by its worker-protected verify.mjs [DF-9]; "
          "AUTO-TRIAGE turns a free-text prompt into a bound active ticket via a gate-blind proposal — a hard "
          "no-op on mock, parking on an illegal binding; the OVERWRITE GUARD refuses to re-author a settled cell, "
          "so a hand-authored asset is never stubbed over)")
    return 0


def main(argv):
    if not argv or argv[0] == "selftest":
        return selftest()
    sys.stderr.write("dispatch.py is a library (use selftest; the heartbeat drives it)\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
