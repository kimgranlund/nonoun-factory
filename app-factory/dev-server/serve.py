#!/usr/bin/env python3
"""serve.py — a ZERO-DEPENDENCY productivity shell over app-factory project corpora.

Stdlib `http.server` only (no FastAPI; app-factory stays self-contained). Read endpoints are a pure
projection over git-tracked state. The two write paths invoke GATED tooling server-side, never mutate
state directly:
  - POST /api/project/<name>/loop  → an async "validate frontier" run (app-loop.py), per-project locked,
    streaming step progress over SSE. (Building with AI agents is NOT something the stdlib server can do —
    that is `/app-loop` in a Claude Code session; the UI is honest about the split.)
  - POST /api/project/<name>/reset → app-reset.py, re-arming the frontier.

API:
  GET  /                                 the shell
  GET  /app.js /styles.css               static assets
  GET  /api/projects                     [{name, stage, tier, tickets_done, tickets_total, running}]
  GET  /api/project/<name>               full detail (docs, specs, tickets[+built/reason], builds, run, trust)
  GET  /api/project/<name>/run           {running, steps[], result}
  GET  /api/project/<name>/file?path=..  read-only file content (allowlisted, traversal-guarded)
  GET  /api/stream?project=<name>        SSE: {type:change|step|done|ping ...}
  POST /api/project/<name>/loop          202 started | 409 already running
  POST /api/project/<name>/reset         200 reset    | 409 running

  serve.py [--root DIR] [--port N]       DIR=./projects (default), N=8765 (auto-advances)
"""
import datetime
import http.server
import json
import os
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL = os.path.join(os.path.dirname(HERE), "kernel")
BIN = os.path.join(os.path.dirname(HERE), "bin")
UI = os.path.join(HERE, "ui")
sys.path.insert(0, KERNEL)
import ledger as _led   # noqa: E402
import lattice as _lat  # noqa: E402

ROOT = "projects"
LOOP_CAPS = ["--max-iterations", "12", "--max-cells", "8", "--wall-clock-s", "120"]


# ---- paths -----------------------------------------------------------------
def _state(name):
    return os.path.join(ROOT, name, ".factory", "state")


def _rundir(name):
    return os.path.join(_state(name), "run")


def _lock(name):
    return os.path.join(_rundir(name), "ui-run.lock")


def _progress(name):
    return os.path.join(_rundir(name), "progress.jsonl")


def _running(name):
    return os.path.isfile(_lock(name))


def _now():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


# ---- reads -----------------------------------------------------------------
def _version(name):
    """Newest mtime across everything a viewer cares about — lattice, ledger, the authored docs, and the
    run dir — so any change (a validated ticket, an edited spec, a run starting/finishing) refreshes the UI."""
    v = 0.0
    paths = [os.path.join(_state(name), "lattice.json"), os.path.join(_state(name), "ledger", "events.jsonl"),
             _rundir(name)]
    for d in ("idea.md", "prd.md", "qa.md"):
        paths.append(os.path.join(ROOT, name, d))
    sp = os.path.join(ROOT, name, "spec")
    if os.path.isdir(sp):
        paths += [os.path.join(sp, f) for f in os.listdir(sp) if f.endswith(".md")]
    for p in paths:
        try:
            v = max(v, os.path.getmtime(p))
        except OSError:
            pass
    return round(v, 3)


def _frontmatter(path):
    if not os.path.isfile(path):
        return {}
    t = open(path, encoding="utf-8").read()
    if not t.startswith("---"):
        return {}
    end = t.find("\n---", 3)
    out = {}
    for line in (t[3:end] if end > 0 else "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _ls(name, sub):
    d = os.path.join(ROOT, name, sub)
    return sorted(f for f in os.listdir(d) if f.endswith(".md")) if os.path.isdir(d) else []


def _projects():
    return sorted(n for n in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, n, ".factory"))) if os.path.isdir(ROOT) else []


def _lattice(name):
    p = os.path.join(_state(name), "lattice.json")
    return json.load(open(p)) if os.path.isfile(p) else {"cells": []}


def _block_reasons(name):
    """Latest fail rationale per cell, for friendly blocked cards."""
    out = {}
    for e in _led.read(_state(name)):
        if e.get("operation") == "validate" and e.get("result") == "fail" and e.get("cell_id"):
            out[e["cell_id"]] = e.get("rationale", "a check failed")
    return out


def summary(name):
    proj = {}
    pj = os.path.join(ROOT, name, ".factory", "project.json")
    if os.path.isfile(pj):
        proj = json.load(open(pj))
    caps = [c for c in _lattice(name)["cells"] if c.get("layer") == "capability"]
    done = sum(1 for c in caps if c.get("maturity") == "validated")
    return {"name": name, "stage": proj.get("stage", "?"), "tier": _led.trust_tier(_led.read(_state(name)))[0],
            "tickets_done": done, "tickets_total": len(caps), "running": _running(name)}


def detail(name):
    proj = {}
    pj = os.path.join(ROOT, name, ".factory", "project.json")
    if os.path.isfile(pj):
        proj = json.load(open(pj))
    cells = _lattice(name)["cells"]
    by_cell = {_lat.cid(c): c for c in cells}
    reasons = _block_reasons(name)
    docs = {k: _frontmatter(os.path.join(ROOT, name, f"{k}.md")).get("maturity", "—") for k in ("idea", "prd", "qa")}
    specs = []
    for s in _ls(name, "spec"):
        cell = by_cell.get(f"spec.task.{s[:-3]}")
        specs.append({"file": s, "maturity": (cell or {}).get("maturity",
                      _frontmatter(os.path.join(ROOT, name, "spec", s)).get("maturity", "draft"))})
    tickets, dispatchable = [], 0
    for t in _ls(name, "tickets"):
        fm = _frontmatter(os.path.join(ROOT, name, "tickets", t))
        cell = by_cell.get(fm.get("target_cell", ""), {})
        status = "blocked" if _lat.is_blocked(cell) else cell.get("maturity", "draft")
        built = bool(cell.get("asset_ref")) and os.path.isfile(os.path.join(ROOT, name, cell.get("asset_ref", "x")))
        if status in ("defined", "instantiated") and not _lat.is_blocked(cell) and built:
            dispatchable += 1   # ready to VALIDATE = built; unbuilt tickets need AI building, not this loop
        tickets.append({"id": t[:-3], "target": fm.get("target_cell", ""), "status": status,
                        "covers": fm.get("covers", ""), "built": built, "asset": cell.get("asset_ref", ""),
                        "reason": (reasons.get(fm.get("target_cell", "")) or _lat.block_reason(cell)) if status == "blocked" else None})
    builds = []
    bd = os.path.join(ROOT, name, "build")
    if os.path.isdir(bd):
        for f in sorted(os.listdir(bd)):
            fp = os.path.join(bd, f)
            if os.path.isfile(fp) and not f.startswith("."):
                builds.append({"path": f"build/{f}", "size": os.path.getsize(fp)})
    hist = {}
    for c in cells:
        m = "blocked" if _lat.is_blocked(c) else c.get("maturity", "absent")
        hist[m] = hist.get(m, 0) + 1
    evs = _led.read(_state(name))
    tier, label, rate, reason = _led.trust_tier(evs)
    ledger = [{"op": e.get("operation"), "cell": e.get("cell_id", ""), "result": e.get("result", "")} for e in evs[-10:]]
    return {"name": name, "stage": proj.get("stage", "?"), "version": _version(name),
            "lifecycle": proj.get("lifecycle", []), "docs": docs, "specs": specs, "tickets": tickets,
            "dispatchable": dispatchable, "builds": builds, "histogram": hist, "ledger": ledger,
            "run": run_state(name),
            "trust": {"tier": tier, "label": label, "rate": None if rate is None else round(rate, 4), "reason": reason}}


def run_state(name):
    steps = []
    if os.path.isfile(_progress(name)):
        for line in open(_progress(name), encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    steps.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    result = next((s for s in reversed(steps) if s.get("type") == "done"), None)
    return {"running": _running(name), "steps": [s for s in steps if s.get("type") == "step"], "result": result}


SAFE_PREFIXES = ("build/", "spec/", ".factory/acceptance/")
SAFE_FILES = ("idea.md", "prd.md", "qa.md")


def read_file(name, rel):
    rel = (rel or "").replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        return 403, {"error": "path traversal denied"}
    if not (rel in SAFE_FILES or rel.startswith(SAFE_PREFIXES)):
        return 403, {"error": "file is not in the viewable set (build/, spec/, .factory/acceptance/, idea/prd/qa)"}
    fp = os.path.join(ROOT, name, rel)
    if not os.path.isfile(fp):
        return 404, {"error": "no such file"}
    try:
        return 200, {"path": rel, "content": open(fp, encoding="utf-8").read()[:200000]}
    except (OSError, UnicodeDecodeError) as e:
        return 500, {"error": str(e)}


# ---- the async run ---------------------------------------------------------
def _parse_step(line):
    s = line.strip()
    if s.startswith("· advance ") and " → " in s:
        cell, res = s[len("· advance "):].split(" → ", 1)
        return {"type": "step", "phase": "advance", "cell": cell.strip(), "result": res.strip(), "text": s}
    if s.startswith("armed:"):
        return {"type": "step", "phase": "armed", "text": s}
    if s.startswith("· check"):
        return {"type": "step", "phase": "check", "text": s}
    if "STOP" in s or s.startswith("· next"):
        return {"type": "step", "phase": "stop", "text": s}
    return {"type": "step", "phase": "info", "text": s}


def _do_run(name):
    state, prog = _state(name), _progress(name)
    open(prog, "w").close()

    def emit(ev):
        ev["ts"] = _now()
        with open(prog, "a", encoding="utf-8") as f:
            f.write(json.dumps(ev) + "\n")

    try:
        emit({"type": "step", "phase": "start", "text": "validate-frontier run started"})
        proc = subprocess.Popen([sys.executable, os.path.join(BIN, "app-loop.py"), "run",
                                 "--dir", state, "--project", os.path.join(ROOT, name)] + LOOP_CAPS,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            if line.strip():
                emit(_parse_step(line))
        proc.wait()
        caps = [c for c in _lattice(name)["cells"] if c.get("layer") == "capability"]
        validated = [_lat.cid(c) for c in caps if c.get("maturity") == "validated"]
        blocked = [_lat.cid(c) for c in caps if _lat.is_blocked(c)]
        pending = [_lat.cid(c) for c in caps if c.get("maturity") != "validated" and not _lat.is_blocked(c)]
        emit({"type": "done", "ok": not blocked, "validated": len(validated), "blocked": len(blocked),
              "pending": len(pending),
              "message": f"validated {len(validated)}, blocked {len(blocked)}, pending {len(pending)}"})
    except Exception as e:  # noqa: BLE001
        emit({"type": "done", "ok": False, "validated": 0, "blocked": 0, "pending": 0, "message": f"run error: {e}"})
    finally:
        try:
            os.remove(_lock(name))
        except OSError:
            pass


# ---- HTTP ------------------------------------------------------------------
class Handler(http.server.BaseHTTPRequestHandler):
    def _json(self, code, obj):
        self._send(code, json.dumps(obj), "application/json")

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path, ctype):
        if not os.path.isfile(path):
            return self._send(404, "not found", "text/plain")
        self._send(200, open(path, "rb").read(), ctype)

    def _sse(self, name):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        last_v, cursor = None, 0
        try:
            for i in range(1800):
                if os.path.isfile(_progress(name)):
                    lines = [l for l in open(_progress(name), encoding="utf-8").read().splitlines() if l.strip()]
                    while cursor < len(lines):
                        self.wfile.write(f"data: {lines[cursor]}\n\n".encode())
                        cursor += 1
                    self.wfile.flush()
                v = _version(name)
                if v != last_v:
                    last_v = v
                    self.wfile.write(f"data: {json.dumps({'type': 'change', 'version': v})}\n\n".encode())
                    self.wfile.flush()
                elif i % 25 == 0:
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                time.sleep(0.4)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_GET(self):
        p, _, q = self.path.partition("?")
        params = dict(kv.split("=", 1) for kv in q.split("&") if "=" in kv)
        try:
            if p == "/":
                return self._file(os.path.join(UI, "index.html"), "text/html; charset=utf-8")
            if p in ("/app.js", "/styles.css"):
                return self._file(os.path.join(UI, p.lstrip("/")), "text/javascript" if p.endswith(".js") else "text/css")
            if p == "/api/projects":
                return self._json(200, [summary(n) for n in _projects()])
            if p == "/api/stream":
                name = params.get("project", "")
                return self._sse(name) if name in _projects() else self._send(404, "no project", "text/plain")
            if p.startswith("/api/project/"):
                rest = p[len("/api/project/"):]
                name = rest.split("/")[0]
                if name not in _projects():
                    return self._json(404, {"error": "no such project"})
                if rest == name:
                    return self._json(200, detail(name))
                if rest == f"{name}/run":
                    return self._json(200, run_state(name))
                if rest == f"{name}/file":
                    code, obj = read_file(name, params.get("path", ""))
                    return self._json(code, obj)
            return self._send(404, "not found", "text/plain")
        except Exception as e:  # noqa: BLE001 — never 500 with a stack to the browser
            return self._json(500, {"error": str(e)})

    def do_POST(self):
        p = self.path.split("?")[0]
        try:
            if not p.startswith("/api/project/"):
                return self._json(404, {"error": "unknown action"})
            rest = p[len("/api/project/"):]
            name = rest.split("/")[0]
            if name not in _projects():
                return self._json(404, {"error": "no such project"})
            if rest == f"{name}/loop":
                if _running(name):
                    return self._json(409, {"error": "a validate run is already in progress"})
                os.makedirs(_rundir(name), exist_ok=True)
                json.dump({"started": _now()}, open(_lock(name), "w"))
                threading.Thread(target=_do_run, args=(name,), daemon=True).start()
                return self._json(202, {"status": "started", "project": name})
            if rest == f"{name}/reset":
                if _running(name):
                    return self._json(409, {"error": "cannot reset while a run is in progress"})
                r = subprocess.run([sys.executable, os.path.join(BIN, "app-reset.py"), os.path.join(ROOT, name)],
                                   capture_output=True, text=True)
                if r.returncode != 0:
                    return self._json(500, {"error": (r.stderr or r.stdout).strip()})
                return self._json(200, {"status": "reset", "message": r.stdout.strip()})
            return self._json(404, {"error": "unknown action"})
        except Exception as e:  # noqa: BLE001
            return self._json(500, {"error": str(e)})

    def log_message(self, *a):
        pass


def main(argv):
    global ROOT
    if "--root" in argv:
        ROOT = argv[argv.index("--root") + 1]
    base = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
    ROOT = os.path.abspath(ROOT)
    srv = None
    for port in range(base, base + 12):
        try:
            srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            srv = None
    if srv is None:
        print(f"no free port in {base}..{base + 11}", file=sys.stderr)
        return 1
    print(f"app-factory dev-server — http://127.0.0.1:{port}  (projects root: {ROOT})", flush=True)
    print(f"  projects: {', '.join(_projects()) or '(none — run /app-new first)'}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
