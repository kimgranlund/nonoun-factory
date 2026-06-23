// app-factory productivity shell — buildless, no framework.
const el = (tag, attrs = {}, ...kids) => {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") n.className = v;
    else if (k === "onClick") n.addEventListener("click", v);
    else n.setAttribute(k, v);
  }
  for (const k of kids) if (k != null) n.append(k.nodeType ? k : document.createTextNode(k));
  return n;
};
const MAT = { validated: "ok", operating: "ok", committed: "ok", cultivated: "mid",
  defined: "mid", instantiated: "mid", draft: "low", absent: "low", blocked: "bad" };
const cls = (m) => MAT[m] || "low";
const chip = (m, label) => el("span", { class: "chip " + cls(m) }, label || m);
const api = (p) => fetch(p).then((r) => r.json());

let current = null, es = null, refreshTimer = null;

async function loadDrawer() {
  const ps = await api("/api/projects");
  const nav = document.getElementById("projects");
  nav.innerHTML = "";
  if (!ps.length) nav.append(el("div", { class: "muted pad" }, "No projects yet — run /app-new"));
  for (const p of ps) {
    nav.append(el("button", { class: "proj" + (p.name === current ? " active" : ""), onClick: () => select(p.name) },
      el("span", { class: "proj-name" }, p.name),
      el("span", { class: "proj-sub" }, `${p.stage} · ${p.tickets_done}/${p.tickets_total} tickets`),
      el("span", { class: "tier" }, "T" + p.tier)));
  }
}

const section = (title, sub, body) =>
  el("section", { class: "sec" },
    el("div", { class: "sec-h" }, el("h2", {}, title), el("span", { class: "sec-sub" }, sub)), body);

function lifecycleBar(stages, stage) {
  const cur = (stage || "").replace("?", "");
  return el("div", { class: "lifecycle" },
    ...stages.map((s) => el("span", { class: "lc" + (s.replace("?", "") === cur ? " cur" : "") }, s)));
}

function toast(msg) {
  let t = document.getElementById("toast");
  if (!t) { t = el("div", { id: "toast" }); document.body.append(t); }
  t.textContent = msg;
  t.className = "show";
  clearTimeout(t._timer);
  t._timer = setTimeout(() => (t.className = ""), 7000);
}

async function runLoop(name, btn) {
  btn.disabled = true;
  btn.textContent = "⟳ running…";
  try {
    const res = await fetch("/api/project/" + name + "/loop", { method: "POST" }).then((r) => r.json());
    toast(res.report || "loop finished");
  } catch (e) {
    toast("error: " + e);
  }
  btn.disabled = false;
  btn.textContent = "▶ Run loop";
  render(await api("/api/project/" + name));
  loadDrawer();
}

function render(d) {
  const m = document.getElementById("main");
  m.innerHTML = "";

  const ready = d.tickets.filter((t) => t.status === "defined" || t.status === "instantiated").length;
  const runBtn = el("button", { class: "run-btn" }, ready ? "▶ Run loop" : "▶ Nothing ready");
  runBtn.title = ready ? `${ready} ticket(s) ready to advance` : "commit a spec to decompose tickets, or all tickets are done";
  if (ready) runBtn.addEventListener("click", () => runLoop(d.name, runBtn));
  else runBtn.disabled = true;
  m.append(el("div", { class: "head" },
    el("h1", {}, d.name),
    el("span", { class: "tier-badge t" + d.trust.tier }, `Tier ${d.trust.tier} · ${d.trust.label}`),
    el("span", { class: "spacer" }), runBtn));
  m.append(lifecycleBar(d.lifecycle, d.stage));

  // Specs & Inputs — the cultivation focus
  const docs = el("div", { class: "cards" },
    ...["idea", "prd", "qa"].map((k) => el("div", { class: "doc" },
      el("div", { class: "doc-k" }, k), chip(d.docs[k]))));
  const specs = el("div", { class: "specs" },
    ...(d.specs.length ? d.specs.map((s) => el("div", { class: "spec" },
      el("span", { class: "mono" }, "spec/" + s.file), chip(s.maturity)))
      : [el("div", { class: "muted" }, "no specs yet — cultivate the idea, then /app-spec")]));
  m.append(section("Specs & Inputs", "cultivate these — better specs build more reliably",
    el("div", {}, docs, specs)));

  // Tickets kanban
  const order = ["draft", "defined", "instantiated", "validated", "blocked"];
  const groups = {};
  for (const t of d.tickets) (groups[t.status] = groups[t.status] || []).push(t);
  const kan = el("div", { class: "kanban" });
  for (const st of order) {
    if (!groups[st]) continue;
    kan.append(el("div", { class: "col" },
      el("div", { class: "col-h" }, chip(st), el("span", { class: "count" }, String(groups[st].length))),
      ...groups[st].map((t) => el("div", { class: "card" },
        el("div", { class: "card-id" }, t.id), el("div", { class: "mono small" }, t.target)))));
  }
  if (!d.tickets.length) kan.append(el("div", { class: "muted" }, "no tickets — commit a spec to decompose"));
  m.append(section("Tickets", "the loop drives these to validated — hit Run loop", kan));

  // Lattice + ledger
  const hist = el("div", { class: "hist" },
    ...Object.entries(d.histogram).map(([k, v]) => chip(k, `${k} ${v}`)));
  const feed = el("div", { class: "feed" },
    ...(d.ledger.length ? d.ledger.slice().reverse().map((e) => el("div", { class: "event" },
      el("span", { class: "ev-op" }, e.op),
      el("span", { class: "mono small" }, e.cell),
      e.result ? chip(e.result === "pass" ? "validated" : "blocked", e.result) : ""))
      : [el("div", { class: "muted" }, "no events yet")]));
  m.append(section("Lattice & ledger", d.trust.reason, el("div", {}, hist, feed)));
}

function subscribe(name) {
  if (es) es.close();
  es = new EventSource("/api/stream?project=" + encodeURIComponent(name));
  es.onmessage = () => {
    clearTimeout(refreshTimer);
    refreshTimer = setTimeout(async () => {
      if (current !== name) return;
      render(await api("/api/project/" + name));   // live: kanban updates as each ticket validates
      loadDrawer();
    }, 120);
  };
}

async function select(name) {
  current = name;
  await loadDrawer();
  render(await api("/api/project/" + name));
  subscribe(name);
}

loadDrawer();
