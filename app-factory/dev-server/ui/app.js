// app-factory productivity shell — buildless, foolproof. No framework.
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "onClick") n.addEventListener("click", v);
    else if (k === "html") n.innerHTML = v;
    else n.setAttribute(k, v);
  }
  for (const k of kids) if (k != null) n.append(k.nodeType ? k : document.createTextNode(k));
  return n;
};
const MAT = { validated: "ok", operating: "ok", committed: "ok", cultivated: "mid", defined: "mid",
  instantiated: "mid", draft: "low", absent: "low", blocked: "bad" };
const cls = (m) => MAT[m] || "low";
const chip = (m, label) => el("span", { class: "chip " + cls(m) }, label || m);
const $ = (id) => document.getElementById(id);

let current = null, es = null, refreshT = null, liveSteps = [];

// ── connection state ──────────────────────────────────────────────────────
function setConn(state) {
  const pill = $("conn");
  const labels = { live: "● live", connecting: "connecting…", reconnecting: "● reconnecting…", offline: "● disconnected" };
  if (pill) { pill.textContent = labels[state] || state; pill.className = "conn " + state; }
  let b = $("offline");
  if (state === "offline" && !b) {
    document.body.append(el("div", { id: "offline", class: "offline-banner" },
      "⚠ Can't reach the dev-server — is it still running? Retrying… ",
      el("button", { class: "link", onClick: () => { loadDrawer(); if (current) select(current); } }, "retry now")));
  } else if (state !== "offline" && b) { b.remove(); }
}

async function api(path) {
  try {
    const r = await fetch(path);
    if ($("conn") && $("conn").className.includes("offline")) setConn("live");
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) { setConn("offline"); throw e; }
}
async function post(path) {
  try {
    const r = await fetch(path, { method: "POST" });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) { setConn("offline"); return { status: 0, body: { error: "offline" } }; }
}

// ── toast ─────────────────────────────────────────────────────────────────
function toast(msg, kind) {
  let t = $("toast");
  if (!t) { t = el("div", { id: "toast" }); document.body.append(t); }
  t.textContent = msg; t.className = "show " + (kind || "");
  clearTimeout(t._timer); t._timer = setTimeout(() => (t.className = ""), 7000);
}

// ── drawer ────────────────────────────────────────────────────────────────
async function loadDrawer() {
  let ps;
  try { ps = (await api("/api/projects")).body; } catch { return; }
  const nav = $("projects");
  nav.innerHTML = "";
  if (!Array.isArray(ps) || !ps.length) {
    nav.append(el("div", { class: "muted pad" }, "No projects yet."),
      el("div", { class: "muted pad mono small" }, "create one:  /app-new <name>"));
    return;
  }
  for (const p of ps) {
    nav.append(el("button", { class: "proj" + (p.name === current ? " active" : ""), onClick: () => select(p.name) },
      el("span", { class: "proj-name" }, p.name, p.running ? el("span", { class: "spin" }, " ⟳") : ""),
      el("span", { class: "proj-sub" }, `${p.stage} · ${p.tickets_done}/${p.tickets_total} tickets`),
      el("span", { class: "tier" }, "T" + p.tier)));
  }
}

const section = (title, sub, body) =>
  el("section", { class: "sec" }, el("div", { class: "sec-h" }, el("h2", {}, title),
    el("span", { class: "sec-sub" }, sub)), body);

function lifecycleBar(stages, stage) {
  const cur = (stage || "").replace("?", "");
  return el("div", { class: "lifecycle" },
    ...stages.map((s) => el("span", { class: "lc" + (s.replace("?", "") === cur ? " cur" : "") }, s)));
}

// ── why the Validate button is/ isn't available ────────────────────────────
function validateState(d) {
  if (d.dispatchable > 0) return { enabled: true, label: `▶ Validate frontier (${d.dispatchable})` };
  const needCode = d.tickets.some((t) => !t.built && t.status !== "validated");
  if (!d.tickets.length) return { enabled: false, label: "▶ Nothing to validate", hint: "No tickets yet. Commit a spec to decompose it:  /app-spec " + d.name };
  if (needCode) return { enabled: false, label: "▶ Nothing to validate", hint: "These tickets need code. Build with AI:  /app-loop " + d.name };
  return { enabled: false, label: "▶ Nothing to validate", hint: "All tickets validated ✓ — hit ↻ Reset to run the demo again." };
}

// ── progress (live) ─────────────────────────────────────────────────────────
function renderProgress(container, run) {
  container.innerHTML = "";
  const steps = liveSteps.length ? liveSteps : (run.steps || []);
  const done = run.result;
  if (run.running || steps.length || done) {
    const strip = el("div", { class: "progress" });
    for (const s of steps.filter((x) => x.phase === "advance")) {
      strip.append(el("div", { class: "pstep " + (s.result === "PASS" ? "ok" : "bad") },
        (s.result === "PASS" ? "✓ " : "✗ ") + (s.cell || s.text)));
    }
    if (run.running) strip.append(el("div", { class: "pstep run" }, "⟳ validating…"));
    else if (done) {
      strip.append(el("div", { class: "terminal " + (done.blocked ? "warn" : "ok") },
        (done.blocked ? "⚠ " : "✓ ") + `Done — ${done.message}`));
    }
    container.append(strip);
  }
}

// ── ticket card ─────────────────────────────────────────────────────────────
function ticketCard(d, t) {
  const badge = t.status === "blocked" ? el("span", { class: "chip bad" }, "blocked")
    : t.built ? el("span", { class: "chip ok" }, "✓ built")
      : el("span", { class: "chip low" }, "needs code");
  const card = el("div", { class: "card" + (t.status === "blocked" ? " blocked" : "") },
    el("div", { class: "card-h" }, el("div", { class: "card-id" }, t.id), badge),
    el("div", { class: "mono small" }, t.target));
  if (t.status === "blocked" && t.reason) {
    card.append(el("div", { class: "reason" }, "⚠ " + t.reason),
      el("div", { class: "reason-fix" }, "fix the code, then Validate again"));
  }
  if (!t.built && t.status !== "validated" && t.status !== "blocked") {
    card.append(el("div", { class: "reason-fix" }, "build with AI:  /app-loop " + d.name));
  }
  if (t.asset && t.built) {
    card.append(el("button", { class: "link", onClick: () => viewFile(d.name, t.asset) }, "view code"));
  }
  return card;
}

// ── results / file viewer ────────────────────────────────────────────────────
async function viewFile(name, path) {
  const { status, body } = await api("/api/project/" + name + "/file?path=" + encodeURIComponent(path));
  const v = $("viewer");
  v.innerHTML = "";
  v.className = "viewer";
  v.append(el("div", { class: "viewer-h" }, el("span", { class: "mono" }, path),
    el("button", { class: "link", onClick: () => (v.className = "viewer hidden") }, "✕ close")));
  v.append(el("pre", { class: "code" }, status === 200 ? body.content : ("error: " + (body && body.error || status))));
}

// ── actions ──────────────────────────────────────────────────────────────────
async function runLoop(name, btn) {
  liveSteps = [];
  if (btn) { btn.disabled = true; btn.textContent = "⟳ validating…"; }
  const { status, body } = await post("/api/project/" + name + "/loop");
  if (status === 409) { toast("A validate run is already in progress.", "warn"); }
  else if (status !== 202) { toast("Couldn't start: " + (body && body.error || status), "bad"); }
  // SSE streams step/done; a change event re-renders. Refresh as a fallback.
  setTimeout(() => current === name && refresh(name), 400);
}
async function resetProject(name) {
  if (!confirm(`Reset "${name}"? Tickets go back to ready-to-validate; your specs and code are kept.`)) return;
  const { status, body } = await post("/api/project/" + name + "/reset");
  toast(status === 200 ? "↻ " + (body.message || "reset") : "Reset failed: " + (body && body.error || status),
    status === 200 ? "" : "bad");
  if (current === name) refresh(name);
}

// ── main render ──────────────────────────────────────────────────────────────
function render(d) {
  const m = $("main");
  m.innerHTML = "";
  const vs = validateState(d);

  const runBtn = el("button", { class: "run-btn" }, d.run.running ? "⟳ validating…" : vs.label);
  runBtn.disabled = d.run.running || !vs.enabled;
  if (vs.enabled && !d.run.running) runBtn.addEventListener("click", () => runLoop(d.name, runBtn));
  const resetBtn = el("button", { class: "reset-btn", onClick: () => resetProject(d.name) }, "↻ Reset");
  resetBtn.disabled = d.run.running;

  m.append(el("div", { class: "head" },
    el("h1", {}, d.name),
    el("span", { class: "tier-badge t" + d.trust.tier }, `Tier ${d.trust.tier} · ${d.trust.label}`),
    el("span", { class: "spacer" }), resetBtn, runBtn));
  m.append(lifecycleBar(d.lifecycle, d.stage));

  // honest scope: what Validate does vs. building with AI
  m.append(el("div", { class: "banner" },
    el("span", {}, "▶ Validate frontier checks the tickets that already have code. To build new code with AI, run "),
    el("code", {}, "/app-loop " + d.name), el("span", {}, " in your Claude Code session."),
    el("button", { class: "link", onClick: () => { navigator.clipboard && navigator.clipboard.writeText("/app-loop " + d.name); toast("copied"); } }, "copy")));
  if (!vs.enabled && vs.hint) m.append(el("div", { class: "hint" }, vs.hint));

  // live progress
  const prog = el("div", { id: "progress" });
  renderProgress(prog, d.run);
  m.append(prog);

  // Specs & Inputs
  const docs = el("div", { class: "cards" },
    ...["idea", "prd", "qa"].map((k) => el("div", { class: "doc" }, el("div", { class: "doc-k" }, k), chip(d.docs[k]))));
  const specs = el("div", { class: "specs" },
    ...(d.specs.length ? d.specs.map((s) => el("div", { class: "spec" },
      el("button", { class: "link mono", onClick: () => viewFile(d.name, "spec/" + s.file) }, "spec/" + s.file), chip(s.maturity)))
      : [el("div", { class: "muted" }, "no specs yet — cultivate idea.md, then  /app-spec " + d.name)]));
  m.append(section("Specs & Inputs", "cultivate these — better specs build more reliably", el("div", {}, docs, specs)));

  // Tickets kanban
  const order = ["defined", "instantiated", "validated", "blocked"];
  const groups = {};
  for (const t of d.tickets) (groups[t.status] = groups[t.status] || []).push(t);
  const kan = el("div", { class: "kanban" });
  for (const st of order) {
    if (!groups[st]) continue;
    kan.append(el("div", { class: "col" }, el("div", { class: "col-h" }, chip(st),
      el("span", { class: "count" }, String(groups[st].length))), ...groups[st].map((t) => ticketCard(d, t))));
  }
  if (!d.tickets.length) kan.append(el("div", { class: "muted" }, "no tickets — commit a spec to decompose it"));
  m.append(section("Tickets", "Validate drives the built ones to validated", kan));

  // Built artifacts (results)
  if (d.builds.length) {
    m.append(section("Built artifacts", "what the loop has produced — click to inspect",
      el("div", { class: "builds" }, ...d.builds.map((b) =>
        el("button", { class: "build link", onClick: () => viewFile(d.name, b.path) },
          el("span", { class: "mono" }, b.path), el("span", { class: "small" }, ` ${b.size}b`))))));
  }

  // Lattice + ledger
  const hist = el("div", { class: "hist" }, ...Object.entries(d.histogram).map(([k, v]) => chip(k, `${k} ${v}`)));
  const feed = el("div", { class: "feed" },
    ...(d.ledger.length ? d.ledger.slice().reverse().map((e) => el("div", { class: "event" },
      el("span", { class: "ev-op" }, e.op), el("span", { class: "mono small" }, e.cell),
      e.result ? chip(e.result === "pass" ? "validated" : "blocked", e.result) : ""))
      : [el("div", { class: "muted" }, "no events yet")]));
  m.append(section("Lattice & ledger", d.trust.reason, el("div", {}, hist, feed)));
}

// ── data + SSE ───────────────────────────────────────────────────────────────
async function refresh(name) {
  try { const { body } = await api("/api/project/" + name); if (current === name && body && !body.error) render(body); } catch { }
  loadDrawer();
}

function subscribe(name) {
  if (es) es.close();
  es = new EventSource("/api/stream?project=" + encodeURIComponent(name));
  es.onopen = () => setConn("live");
  es.onerror = () => setConn(es.readyState === 2 ? "offline" : "reconnecting");
  es.onmessage = (m) => {
    let ev; try { ev = JSON.parse(m.data); } catch { return; }
    if (ev.type === "step") {
      liveSteps.push(ev);
      const p = $("progress"); if (p) renderProgress(p, { running: true, steps: liveSteps });
    } else if (ev.type === "done") {
      liveSteps.push(ev);
      const p = $("progress"); if (p) renderProgress(p, { running: false, steps: liveSteps, result: ev });
      clearTimeout(refreshT); refreshT = setTimeout(() => refresh(name), 150);
    } else if (ev.type === "change") {
      clearTimeout(refreshT); refreshT = setTimeout(() => refresh(name), 150);
    }
  };
}

async function select(name) {
  current = name; liveSteps = [];
  await loadDrawer();
  try { const { body } = await api("/api/project/" + name); if (body && !body.error) render(body); } catch { }
  subscribe(name);
}

loadDrawer();
