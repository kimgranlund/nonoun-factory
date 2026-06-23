#!/usr/bin/env python3
"""serve.py — a ZERO-DEPENDENCY productivity shell over app-factory project corpora.

A simple operator surface for the work that matters: cultivating better specs + inputs so the
loop builds more reliably. Stdlib `http.server` only (app-factory stays self-contained — no
FastAPI), serving a buildless vanilla UI and a small JSON API over a projects root.

Read endpoints are a pure projection over git-tracked state. The ONE write path —
`POST /api/project/<name>/loop` — does not mutate anything itself; it invokes the GATED
controller (`app-loop.py run`, server-mediated and ledgered), exactly as dev-factory's UI routes
a drag through `POST /transition`. The UI shows the factory; it never bypasses the gates.

  serve.py [--root DIR] [--port N]     # DIR = the projects root (default ./projects), N default 8765 (auto-advances)
"""
import http.server
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KERNEL = os.path.join(os.path.dirname(HERE), "kernel")
BIN = os.path.join(os.path.dirname(HERE), "bin")
UI = os.path.join(HERE, "ui")
sys.path.insert(0, KERNEL)
import ledger as _led   # noqa: E402
import lattice as _lat  # noqa: E402

ROOT = "projects"


def _state(name):
    return os.path.join(ROOT, name, ".factory", "state")


def _version(name):
    """A cheap change token: the newest mtime across the lattice + ledger. Changes the instant the loop validates."""
    v = 0.0
    for rel in ("lattice.json", "ledger/events.jsonl"):
        p = os.path.join(_state(name), rel)
        if os.path.isfile(p):
            v = max(v, os.path.getmtime(p))
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
    if not os.path.isdir(ROOT):
        return []
    return sorted(n for n in os.listdir(ROOT) if os.path.isdir(os.path.join(ROOT, n, ".factory")))


def _lattice(name):
    p = os.path.join(_state(name), "lattice.json")
    return json.load(open(p)) if os.path.isfile(p) else {"cells": []}


def summary(name):
    proj = {}
    pj = os.path.join(ROOT, name, ".factory", "project.json")
    if os.path.isfile(pj):
        proj = json.load(open(pj))
    caps = [c for c in _lattice(name)["cells"] if c.get("layer") == "capability"]
    done = sum(1 for c in caps if c.get("maturity") == "validated")
    tier = _led.trust_tier(_led.read(_state(name)))[0]
    return {"name": name, "stage": proj.get("stage", "?"), "tier": tier,
            "tickets_done": done, "tickets_total": len(caps)}


def detail(name):
    proj = {}
    pj = os.path.join(ROOT, name, ".factory", "project.json")
    if os.path.isfile(pj):
        proj = json.load(open(pj))
    cells = _lattice(name)["cells"]
    by_cell = {_lat.cid(c): c for c in cells}
    docs = {k: _frontmatter(os.path.join(ROOT, name, f"{k}.md")).get("maturity", "—")
            for k in ("idea", "prd", "qa")}
    specs = []
    for s in _ls(name, "spec"):
        fm = _frontmatter(os.path.join(ROOT, name, "spec", s))
        cell = by_cell.get(f"spec.task.{s[:-3]}")
        specs.append({"file": s, "maturity": (cell or {}).get("maturity", fm.get("maturity", "draft"))})
    tickets = []
    for t in _ls(name, "tickets"):
        fm = _frontmatter(os.path.join(ROOT, name, "tickets", t))
        cell = by_cell.get(fm.get("target_cell", ""), {})
        status = "blocked" if cell.get("blocked") else cell.get("maturity", "draft")
        tickets.append({"id": t[:-3], "target": fm.get("target_cell", ""), "status": status, "covers": fm.get("covers", "")})
    hist = {}
    for c in cells:
        m = "blocked" if c.get("blocked") else c.get("maturity", "absent")
        hist[m] = hist.get(m, 0) + 1
    evs = _led.read(_state(name))
    tier, label, rate, reason = _led.trust_tier(evs)
    ledger = [{"op": e.get("operation"), "cell": e.get("cell_id", ""), "result": e.get("result", "")}
              for e in evs[-10:]]
    return {"name": name, "stage": proj.get("stage", "?"), "version": _version(name),
            "lifecycle": proj.get("lifecycle", []), "docs": docs, "specs": specs,
            "tickets": tickets, "histogram": hist, "ledger": ledger,
            "trust": {"tier": tier, "label": label, "rate": None if rate is None else round(rate, 4), "reason": reason}}


class Handler(http.server.BaseHTTPRequestHandler):
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
        """Stream a change event whenever the project's lattice/ledger mtime advances (live kanban)."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        last = None
        try:
            for i in range(1200):                     # ~10 min then the client EventSource auto-reconnects
                v = _version(name)
                if v != last:
                    last = v
                    self.wfile.write(f"data: {json.dumps({'project': name, 'version': v})}\n\n".encode())
                    self.wfile.flush()
                elif i % 20 == 0:
                    self.wfile.write(b": ping\n\n")    # heartbeat — also surfaces a client disconnect
                    self.wfile.flush()
                time.sleep(0.5)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return

    def do_GET(self):
        p, _, q = self.path.partition("?")
        params = dict(kv.split("=", 1) for kv in q.split("&") if "=" in kv)
        try:
            if p == "/":
                return self._file(os.path.join(UI, "index.html"), "text/html; charset=utf-8")
            if p == "/app.js":
                return self._file(os.path.join(UI, "app.js"), "text/javascript")
            if p == "/styles.css":
                return self._file(os.path.join(UI, "styles.css"), "text/css")
            if p == "/api/projects":
                return self._send(200, json.dumps([summary(n) for n in _projects()]))
            if p == "/api/stream":
                name = params.get("project", "")
                return self._sse(name) if name in _projects() else self._send(404, "no project", "text/plain")
            if p.startswith("/api/project/"):
                name = p[len("/api/project/"):]
                if name not in _projects():
                    return self._send(404, json.dumps({"error": "no such project"}))
                return self._send(200, json.dumps(detail(name)))
            return self._send(404, "not found", "text/plain")
        except Exception as e:  # noqa: BLE001
            return self._send(500, json.dumps({"error": str(e)}))

    def do_POST(self):
        p = self.path.split("?")[0]
        if p.startswith("/api/project/") and p.endswith("/loop"):
            name = p[len("/api/project/"):-len("/loop")]
            if name not in _projects():
                return self._send(404, json.dumps({"error": "no such project"}))
            # server-mediated, GATED, ledgered — invoke the controller, never mutate state directly
            r = subprocess.run([sys.executable, os.path.join(BIN, "app-loop.py"), "run",
                                "--dir", _state(name), "--project", os.path.join(ROOT, name),
                                "--max-iterations", "12", "--max-cells", "8", "--wall-clock-s", "120"],
                               capture_output=True, text=True)
            return self._send(200, json.dumps({"report": (r.stdout or r.stderr).strip()}))
        return self._send(404, json.dumps({"error": "unknown action"}))

    def log_message(self, *a):
        pass


def main(argv):
    global ROOT
    if "--root" in argv:
        ROOT = argv[argv.index("--root") + 1]
    base = int(argv[argv.index("--port") + 1]) if "--port" in argv else 8765
    ROOT = os.path.abspath(ROOT)
    srv = None
    for port in range(base, base + 12):               # tolerate an occupied port — find a free one
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
