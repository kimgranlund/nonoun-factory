#!/usr/bin/env python3
"""app.py — the dev-factory server: a thin FastAPI/uvicorn transport over the tested operations layer.

All coordination logic lives in api.py (stdlib, CI-tested); this module is *only* transport + the
heartbeat scheduler + the SSE stream. The same `api.transition_ticket` a human drag calls is what the
heartbeat will call in Walk — the loop is not a separate code path, it is the scheduler calling the API.

Crawl posture: the heartbeat is DISABLED (`HEARTBEAT_ENABLED = False`). Walk flips it on at Tier 1.

Run:  pip install fastapi uvicorn   &&   DEV_FACTORY_DIR=/path/.factory uvicorn app:app
The operations layer needs no FastAPI — `python3 api.py selftest` verifies the whole path headless.

Python 3.8+. FastAPI/uvicorn are the server's only non-stdlib deps (it is NOT a plugin — plugins are
stdlib-only; the server is a separately-distributed app, per the architecture).
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import api  # noqa: E402  (the tested operations layer — stdlib)
import store as _store  # noqa: E402  (for the boot re-projection, DF-2)
import dispatch as _dispatch  # noqa: E402  (adapter selection — mock vs headless)

DIR = os.environ.get("DEV_FACTORY_DIR", ".factory")
HEARTBEAT_ENABLED = os.environ.get("DEV_FACTORY_HEARTBEAT") == "1"   # OFF in Crawl; Walk sets it
SERVER_ACTOR = {"kind": "server", "id": "dev-server"}


def _run_budget():
    """The bounded-loop gauge for the cockpit's analysis rail: dispatches-so-far / cap + the wall-clock deadline,
    read from the armed window (run/heartbeat.json) and the ledger's dispatch count. None when no window is armed
    (Crawl). Honest + cheap — the same numbers the wired gate-budget enforces, surfaced read-only."""
    import heartbeat as _hb
    b = _hb.load_budget(DIR)
    if not b:
        return None
    start = b.get("start_ts")
    return {"dispatches": _hb._dispatches_since(DIR, start) if start else 0,
            "max_dispatches": b.get("max_dispatches"), "deadline_ts": b.get("deadline_ts"),
            "ticks": b.get("ticks", 0), "start_ts": start, "token_ceiling": b.get("token_ceiling")}

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, HTMLResponse
    from fastapi.staticfiles import StaticFiles
    _HAVE_FASTAPI = True
except ImportError:
    _HAVE_FASTAPI = False


def _product_root():
    """The clean PRODUCT tree (src/<project>/) — the parent of the .factory/ instance dir. The factory builds
    runnable code here; .factory/ holds only state. dispatch.py computes the same grandparent as the worker cwd."""
    return os.path.dirname(os.path.realpath(DIR.rstrip("/")))


def _project_info():
    """Which project this server is building + the sibling projects under src/ (forward-looking for the multi-run
    switcher; one server per instance today, so the list is usually a single entry). `entry`/`has_entry` tell the
    Preview tab whether a bootable browser shell (index.html) exists yet."""
    root = _product_root()
    name = os.path.basename(root) or "project"
    src_root = os.path.dirname(root)            # the src/ dir holding sibling project folders
    projects = []
    try:
        for d in sorted(os.listdir(src_root)):
            if os.path.isdir(os.path.join(src_root, d, ".factory")):
                projects.append(d)
    except OSError:
        pass
    if name not in projects:
        projects.insert(0, name)
    entry = next((e for e in ("index.html", "index.htm") if os.path.isfile(os.path.join(root, e))), None)
    return {"project": name, "current": name, "projects": projects,
            "product_root": root, "entry": entry, "has_entry": bool(entry)}


# media types so the served ESM app actually loads in the Preview iframe (.mjs must be a JS type, not octet-stream)
_PREVIEW_MEDIA = {".mjs": "text/javascript", ".js": "text/javascript", ".css": "text/css", ".html": "text/html",
                  ".json": "application/json", ".map": "application/json", ".wasm": "application/wasm",
                  ".svg": "image/svg+xml", ".ico": "image/x-icon", ".png": "image/png", ".jpg": "image/jpeg",
                  ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp", ".woff2": "font/woff2",
                  ".woff": "font/woff", ".ttf": "font/ttf"}


def _preview_placeholder(root, factory_abs):
    """When no bootable index.html exists yet, Preview shows the built product files (never .factory/) + how to add
    a browser shell — so the tab is informative, not a blank 404."""
    items = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(".") and os.path.realpath(os.path.join(dirpath, d)) != factory_abs]
        for f in sorted(filenames):
            if not f.startswith("."):
                items.append(os.path.relpath(os.path.join(dirpath, f), root))
    items.sort()
    lis = "\n".join(f'<li><a href="/preview/{p}" target="_blank" rel="noopener">{p}</a></li>'
                    for p in items) or "<li>(no product files built yet)</li>"
    name = os.path.basename(root)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{name} — build preview</title>
<style>body{{font:15px/1.6 system-ui,sans-serif;max-width:46rem;margin:7vh auto;padding:0 1.5rem;color:#dfe3ea;background:#16181d}}
h1{{font-size:1.25rem}} code{{background:rgba(127,127,127,.22);padding:.1em .35em;border-radius:4px}}
a{{color:#7db4ff}} ul{{columns:2;gap:1.4rem}} li{{margin:.12em 0;break-inside:avoid}}
.note{{color:#aab;border-left:3px solid #4a5568;padding:.5em .9em;margin:1.1em 0;background:rgba(127,127,127,.07);border-radius:0 6px 6px 0}}</style></head>
<body><h1>▶ {name} — build preview</h1>
<div class="note">No bootable entry (<code>index.html</code>) in this build yet. The factory produced the modules below,
but the lattice didn't spec a browser <em>shell</em> that imports + mounts them. Add a <code>shell</code>/html
capability to the kit (or drop an <code>index.html</code> at the product root) and this tab loads the running app directly.</div>
<p><strong>Built product files</strong> — the clean tree, served live (<code>.factory/</code> state is never exposed):</p>
<ul>{lis}</ul></body></html>"""


# ─────────────────────────── the live stream (single-writer pushes diffs to UIs) ───────────────────────────

class Stream:
    """The server sees every committed write and pushes it over SSE — no DB change-feed needed."""
    def __init__(self):
        self._subs = []

    def publish(self, kind, payload):
        for q in list(self._subs):
            q.append({"kind": kind, "payload": payload})

    def subscribe(self):
        q = []
        self._subs.append(q)
        return q


STREAM = Stream()


def build_app():
    if not _HAVE_FASTAPI:
        return None
    app = FastAPI(title="dev-factory", version="0.1.0")
    api.init_instance(DIR)
    # DF-2: re-project lattice.json + the ledger into the grid on boot. init_instance scaffolds but does not
    # re-derive cell maturity from a lattice.json that may have been advanced out-of-band (e.g. `validate.py`
    # drove a cell to `validated` while the server was down). Without this the cell stays stale on the board
    # until a manual `store.py rebuild` — this makes the RUNBOOK's "reboot re-materializes the index" literal.
    _store.rebuild(DIR)

    @app.get("/api/tickets")
    def list_tickets(state: str = None):
        return api.list_tickets(DIR, state=state)

    @app.post("/api/tickets")
    async def create_ticket(req: Request):
        b = await req.json()
        t = api.create_ticket(DIR, b.get("type", "task"), b.get("title", ""), b.get("body", ""),
                              target_cell=b.get("target_cell"), target_transition=b.get("target_transition"),
                              acceptance=b.get("acceptance"), budget=b.get("budget"),
                              dependencies=b.get("dependencies"), priority=b.get("priority"),
                              created_by=b.get("created_by", "human"))
        STREAM.publish("ticket", t)
        # INSTRUCTION intake (Feature B): a literal directive is ALSO folded into the loop's guidance buffer so
        # the next dispatched worker sees it. A PROMPT intake parks for the cold-start planner (no auto-fold).
        if t.get("type") == "instruction" and (t.get("body") or t.get("title")):
            api.enqueue_input(DIR, f"[instruction {t['id']}] {t.get('body') or t.get('title')}",
                              kind="instruction", source=t["id"])
            api.drain_input(DIR)
            STREAM.publish("guidance", api.read_guidance(DIR))
        return t

    @app.get("/api/tickets/{tid}")
    def get_ticket(tid: str):
        t = api.get_ticket(DIR, tid)
        if t is None:
            raise HTTPException(404, "no such ticket")
        return t

    @app.patch("/api/tickets/{tid}")
    async def edit_ticket(tid: str, req: Request):
        t, msg = api.edit_ticket(DIR, tid, await req.json())
        if t is None:
            raise HTTPException(409, msg)
        STREAM.publish("ticket", t)
        return t

    @app.post("/api/tickets/{tid}/transition")
    async def transition(tid: str, req: Request):
        b = await req.json()
        # a UI drag is a transition REQUEST — the gate runs server-side; an illegal one is refused with a reason
        ok, t, msg = api.transition_ticket(DIR, tid, b.get("to"), SERVER_ACTOR, verifier=b.get("verifier"))
        STREAM.publish("ticket", t)
        STREAM.publish("lattice", api.lattice_grid(DIR))
        if not ok:
            return JSONResponse({"ok": False, "reason": msg, "ticket": t}, status_code=409)
        return {"ok": True, "message": msg, "ticket": t}

    @app.delete("/api/tickets/{tid}")
    def cancel(tid: str):
        ok, t, msg = api.cancel_ticket(DIR, tid, SERVER_ACTOR)
        STREAM.publish("ticket", t)
        return {"ok": ok, "message": msg}

    @app.get("/api/lattice")
    def lattice():
        return api.lattice_grid(DIR)

    @app.get("/api/ledger")
    def ledger(cell: str = None, since: str = None):
        return api.ledger_query(DIR, cell=cell, since=since)

    @app.get("/api/roadmap")
    def roadmap():
        return api.roadmap(DIR)

    @app.post("/api/roadmap")
    async def create_epic(req: Request):
        b = await req.json()
        return api.create_epic(DIR, b.get("title", ""), b.get("body", ""), b.get("target_cell"),
                              b.get("tickets"), b.get("created_by", "human"))

    @app.get("/api/activities")
    def activities(status: str = None):
        return api.list_activities(DIR, status=status)

    @app.get("/api/agents/running")
    def agents_running():
        return api.agents_running(DIR)

    @app.get("/api/issues")
    def issues():
        return api.list_issues(DIR)

    @app.post("/api/issues")
    async def create_issue(req: Request):
        b = await req.json()
        return api.create_issue(DIR, b.get("title", ""), b.get("body", ""), b.get("created_by", "human"))

    @app.post("/api/issues/{iss_id}/triage")
    async def triage(iss_id: str, req: Request):
        b = await req.json()
        t, msg = api.triage_issue(DIR, iss_id, b.get("type", "task"), b.get("target_cell"),
                                  b.get("target_transition"), b.get("acceptance"), budget=b.get("budget"),
                                  dependencies=b.get("dependencies"), priority=b.get("priority"))
        if t is None:
            raise HTTPException(409, msg)
        STREAM.publish("ticket", t)
        return t

    @app.post("/api/input")
    async def enqueue_input(req: Request):
        # the 5s operator-steering channel: enqueue a message; it folds into the guidance buffer the loop reads
        b = await req.json()
        rec = api.enqueue_input(DIR, b.get("text", ""), kind=b.get("kind", "steer"), source=b.get("source", "operator"))
        if rec is None:
            raise HTTPException(400, "empty input text")
        api.drain_input(DIR)                       # fold now so a fast GET sees it; the 5s poll also streams it
        STREAM.publish("guidance", api.read_guidance(DIR))
        return rec

    @app.get("/api/guidance")
    def guidance():
        return api.read_guidance(DIR)

    @app.get("/api/tokens")
    def tokens():
        # the token-burn timeseries (cumulative spend by model + effort) for the realtime graph
        return api.token_series(DIR)

    @app.get("/api/status")
    def status_view():
        # + the factory-state headline (UI-3): is it working, and what is it doing — the thing the SSE 'live'
        # dot does not answer. HEARTBEAT_ENABLED is the transport's posture; the rest is derived from state.
        # + run_budget: the bounded-loop gauge (dispatches-so-far / cap / deadline) the cockpit's analysis rail
        # draws, read from the armed window (run/heartbeat.json) + the ledger's dispatch count — never inferred.
        return {**api.status(DIR), "factory": api.factory_state(DIR, HEARTBEAT_ENABLED),
                "milestones": api.milestones(DIR), "adapter": _dispatch.adapter_name(),
                "run_budget": _run_budget()}

    @app.get("/api/project")
    def project_info():
        # which project this factory is building + sibling projects under src/ (the header selector reads this).
        return _project_info()

    @app.post("/api/project")
    async def switch_project(req: Request):
        # Re-point the running server at a SIBLING project's instance (src/<name>/.factory) — the header
        # selector's switch. Everything (api/store/heartbeat) reads DIR dynamically and opens the index per
        # call, so re-projecting the new instance is all it takes; no restart. Guarded: refuse mid-build (a
        # live worker would be orphaned), reject a name that escapes src/, and LAND PAUSED so a switched-to
        # project never auto-dispatches — the operator arms/resumes it deliberately (each project's run budget
        # is its own, on disk under its .factory/run/).
        global DIR, HEARTBEAT_ENABLED
        b = await req.json()
        name = (b.get("project") or b.get("name") or "").strip()
        src_root = os.path.realpath(os.path.dirname(_product_root()))
        target = os.path.realpath(os.path.join(src_root, name, ".factory"))
        if not name or not target.startswith(src_root + os.sep) or not os.path.isdir(target):
            raise HTTPException(404, f"no such project: {name!r}")
        if target == os.path.realpath(DIR):
            return {**_project_info(), "switched": False}
        running = api.agents_running(DIR)
        n = len(running) if isinstance(running, (list, tuple)) else (running or 0)
        if n:
            raise HTTPException(409, f"a worker is running ({n}) — pause or let it finish before switching projects")
        DIR = target
        HEARTBEAT_ENABLED = False            # land paused; the new project is armed/resumed deliberately
        api.init_instance(DIR)
        _store.rebuild(DIR)
        STREAM.publish("lattice", api.lattice_grid(DIR))
        return {**_project_info(), "switched": True, "paused": True}

    @app.get("/preview")
    @app.get("/preview/")
    @app.get("/preview/{path:path}")
    def preview(path: str = ""):
        # Serve the CLEAN product tree (src/<project>/) so the Preview tab loads the built app directly. NEVER
        # serves the .factory/ state (guarded). Falls back to a file-listing placeholder when no index.html exists.
        root = _product_root()
        factory_abs = os.path.realpath(DIR)
        rel = path or "index.html"
        absp = os.path.realpath(os.path.join(root, rel))
        if absp != root and not absp.startswith(root + os.sep):
            raise HTTPException(400, "path escapes the product root")
        if absp == factory_abs or absp.startswith(factory_abs + os.sep):
            raise HTTPException(403, "the .factory/ state is not browsable")
        if os.path.isfile(absp):
            return FileResponse(absp, media_type=_PREVIEW_MEDIA.get(os.path.splitext(absp)[1].lower()))
        if not path or rel == "index.html":
            return HTMLResponse(_preview_placeholder(root, factory_abs))
        raise HTTPException(404, f"no such product file: {rel}")

    @app.get("/api/cells/{cell_id}/asset")
    def cell_asset(cell_id: str):
        # The inspector's ASSET tab: read a cell's authored artifact (the PRD / SPEC / source the worker wrote),
        # read-only + path-guarded to the instance. A multi-file capability returns its dir listing; a doc/spec the
        # text (capped). This is how the cockpit shows the *shippable software*, not just the lattice metadata.
        c = next((x for x in api.lattice_grid(DIR) if x["id"] == cell_id), None)
        if not c:
            raise HTTPException(404, f"no such cell: {cell_id}")
        ref = c.get("asset_ref")
        if not ref:
            return {"cell": cell_id, "asset_ref": None, "kind": "none"}
        # The asset may be machinery under the `.factory/` instance (DIR) OR product CODE at the project root
        # (a kit's output_root roots a capability OUT of .factory/, e.g. asset_ref "../snake"). Both live under
        # the project root, so guard against escapes ABOVE the project, not above the instance.
        base = os.path.dirname(os.path.realpath(DIR.rstrip("/")))
        absp = os.path.realpath(os.path.join(DIR, ref))
        if absp != base and not absp.startswith(base + os.sep):
            raise HTTPException(400, "asset path escapes the project")
        if os.path.isdir(absp):
            files = sorted(f for f in os.listdir(absp) if not f.startswith("."))
            return {"cell": cell_id, "asset_ref": ref, "kind": "dir", "files": files}
        if os.path.isfile(absp):
            return {"cell": cell_id, "asset_ref": ref, "kind": "file",
                    "content": open(absp, encoding="utf-8", errors="replace").read(20000)}
        return {"cell": cell_id, "asset_ref": ref, "kind": "missing"}

    @app.get("/api/reports/{name}")
    def reports(name: str, family: str = None, window: int = None):
        kw = {k: v for k, v in (("family", family), ("window", window)) if v is not None}
        try:
            return api.report(DIR, name, **kw)
        except (ValueError, KeyError) as e:
            raise HTTPException(404, f"unknown report: {name} ({e})")

    @app.post("/api/control/demote/{family}")
    async def demote(family: str, req: Request):
        b = await req.json()
        r = api.demote(DIR, family, b.get("cell"), b.get("reason", "manual demotion"))
        STREAM.publish("lattice", api.lattice_grid(DIR))
        return {"family": family, "demoted_to_tier": r}

    @app.post("/api/control/pause")
    def pause():
        global HEARTBEAT_ENABLED
        HEARTBEAT_ENABLED = False
        return {"paused": True}

    @app.post("/api/control/resume")
    def resume():
        global HEARTBEAT_ENABLED
        HEARTBEAT_ENABLED = True
        return {"paused": False}

    @app.get("/api/stream")
    def stream():
        q = STREAM.subscribe()
        def gen():
            import time
            while True:
                while q:
                    yield f"data: {json.dumps(q.pop(0))}\n\n"
                time.sleep(0.5)
        return StreamingResponse(gen(), media_type="text/event-stream")

    # Walk: the 30s heartbeat is wired here, calling the SAME api as a human drag. OFF in Crawl.
    if HEARTBEAT_ENABLED:
        _wire_heartbeat(app)
    # the 5s operator-input poll runs ALWAYS — steering must work in Crawl too, independent of the dispatch loop
    _wire_input_poll(app)
    # the 15s token-spend snapshot poll — drives the realtime token-burn graph (per model + effort)
    _wire_token_poll(app)
    # the buildless web UI (the five views over SSE) — mounted LAST so /api/* stays ahead of the catch-all
    ui_dir = os.path.join(_HERE, "ui")
    if os.path.isdir(ui_dir):
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
    return app


def _wire_heartbeat(app):
    """Walk: an asyncio interval task that runs one heartbeat tick (compass → dispatcher) every period.
    The loop calls the SAME api a human drag does — it is not a separate code path. Armed on startup; an
    exhausted window halts dispatch (heartbeat.budget_exhausted)."""
    import asyncio
    import heartbeat

    @app.on_event("startup")
    async def _start_heartbeat():
        heartbeat.arm(DIR,
                      deadline_s=int(os.environ.get("DEV_FACTORY_DEADLINE_S", "0")) or None,
                      max_dispatches=int(os.environ.get("DEV_FACTORY_MAX_DISPATCHES", "0")) or None,
                      token_ceiling=int(os.environ.get("DEV_FACTORY_TOKEN_CEILING", "0")) or None)
        tier = int(os.environ.get("DEV_FACTORY_TIER", "1"))
        conc = int(os.environ.get("DEV_FACTORY_CONCURRENCY", "2"))
        period = int(os.environ.get("DEV_FACTORY_PERIOD", "30"))
        strict = os.environ.get("DEV_FACTORY_TIER1_STRICT") == "1"   # opt-in: Tier-1 waits for human acceptance cell-by-cell

        import functools

        async def loop():
            evloop = asyncio.get_event_loop()
            while HEARTBEAT_ENABLED:
                # A headless tick blocks for MINUTES (each `claude -p` worker is a synchronous subprocess). Running
                # it inline would freeze the event loop — the API + SSE stream would stall and the dashboard would
                # go dark for the whole dispatch. Offload the tick to a worker thread so the server stays live and
                # watchable while real workers run. (run_in_executor, not asyncio.to_thread — 3.8 target.)
                summ = await evloop.run_in_executor(
                    None, functools.partial(heartbeat.on_tick, DIR, tier=tier, max_concurrency=conc, strict_accept=strict))
                STREAM.publish("tick", {"summary": summ, "lattice": api.lattice_grid(DIR)})
                await asyncio.sleep(period)
        asyncio.create_task(loop())


def _wire_input_poll(app):
    """The 5-second operator-input poll: drains run/input.jsonl into the active guidance buffer and streams it
    to every UI. Independent of HEARTBEAT_ENABLED (steering must work in Crawl) and of the 30s dispatch tick.
    Deterministic, no model — it only folds intake the operator already wrote, which the next worker reads."""
    import asyncio

    @app.on_event("startup")
    async def _start_input_poll():
        period = int(os.environ.get("DEV_FACTORY_INPUT_PERIOD", "5"))

        async def loop():
            while True:
                if api.drain_input(DIR):
                    STREAM.publish("guidance", api.read_guidance(DIR))
                await asyncio.sleep(period)
        asyncio.create_task(loop())


def _wire_token_poll(app):
    """The 15-second token-spend snapshot: append a cumulative snapshot (tokens by model + effort) and stream it,
    so the dashboard can draw a realtime token-burn graph. Deterministic — it only sums the ledger's recorded
    spend. Independent of the dispatch loop (runs in Crawl too, where it just records zero)."""
    import asyncio

    @app.on_event("startup")
    async def _start_token_poll():
        period = int(os.environ.get("DEV_FACTORY_TOKEN_PERIOD", "15"))

        async def loop():
            while True:
                STREAM.publish("tokens", api.token_snapshot(DIR))
                await asyncio.sleep(period)
        asyncio.create_task(loop())


app = build_app()


def main(argv):
    if argv and argv[0] == "selftest":
        # the transport is thin; the logic is api.py. Here we only assert wiring is importable/consistent.
        if not _HAVE_FASTAPI:
            print("app selftest: SKIP (FastAPI not installed) — the operations layer is tested by `api.py selftest`. "
                  "Install: pip install fastapi uvicorn")
            return 0
        routes = sorted({r.path for r in app.routes if r.path.startswith("/api")})
        expected = {"/api/tickets", "/api/tickets/{tid}", "/api/tickets/{tid}/transition",
                    "/api/lattice", "/api/ledger", "/api/roadmap", "/api/stream", "/api/project",
                    "/api/input", "/api/guidance", "/api/tokens", "/api/cells/{cell_id}/asset"}
        missing = expected - set(routes)
        if missing:
            print(f"app selftest: FAIL — missing routes: {missing}", file=sys.stderr)
            return 1
        print(f"app selftest: OK ({len(routes)} /api routes wired over the tested operations layer; heartbeat "
              f"{'ON' if HEARTBEAT_ENABLED else 'OFF (Crawl)'})")
        return 0
    if not _HAVE_FASTAPI:
        print("dev-factory server needs FastAPI: pip install fastapi uvicorn, then `uvicorn app:app`", file=sys.stderr)
        return 2
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8731")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
