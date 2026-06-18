#!/usr/bin/env node
/**
 * render-check.mjs — the kit's RENDER-COHERENCE verifier (the runtime gate above app-shell-check's static floor).
 *
 * app-shell-check proves the shell ASSEMBLES (canvas + module entry + every import resolves). It cannot prove
 * the shell RENDERS: an assembled page can still throw on load, link a program and never draw, or wire a
 * uniform that doesn't exist. This gate EXECUTES the app's real on-load code path headlessly — against a
 * conformant recording mock WebGL2 context + a focused DOM shim — and asserts the render contract is met:
 *
 *   0. the static app-shell checks pass (composed — a shell that doesn't assemble can't render);
 *   1. the module entry executes WITHOUT throwing (mount/auto-run reached steady state);
 *   2. the app actually DRAWS a frame — it useProgram()s a linked program and issues a draw call
 *      (drawArrays/drawElements). "Linked a program but never drew" is the integration bug this catches.
 *   3. (advisory) it sets at least one uniform — the data path from JS into the program is exercised.
 *
 * THE HONEST LIMIT (documented, deliberate): the mock GL reports compile/link SUCCESS, so this gate does NOT
 * catch GLSL-compile errors or verify the actual pixels — that needs a real GPU, i.e. a browser/SwiftShader
 * (Playwright) or headless-gl harness. That adapter is a HEAVY dependency (a browser binary / native build),
 * which would break the marketplace's zero-dependency, copy-alone-install property — so it stays an OPTIONAL
 * escalation, not the always-on CI gate. This harness is node-builtins-only and runs anywhere `node` does. It
 * verifies the render PATH executes and draws against a conformant GL; real-pixel fidelity is its ceiling, not
 * its floor.
 *
 * Usage:  node render-check.mjs <path/to/index.html>     # the kit binds {asset} = the entry
 *         node render-check.mjs --selftest
 */
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';
import { checkShell } from './app-shell-check.mjs';

const MAX_FRAMES = 3;            // drive a few frames so an app that draws only inside rAF still gets traced
let RENDER_SEQ = 0;             // process-global: every inline-module temp gets a UNIQUE import URL (no ESM-cache reuse)

// ── a recording, conformant mock WebGL2 context ──────────────────────────────────────────────────────────
// Every WebGL2 ALL_CAPS constant reads as a number; create*/getUniformLocation hand back live tokens (so the
// app proceeds to set uniforms + draw); compile/link queries report SUCCESS; everything else is a recorded
// no-op. The trace captures the integration-coherence signal: did a linked program get USED and a frame DRAWN?
function recordingGL() {
  const trace = { calls: Object.create(null), drew: false, usedProgram: false, uniforms: 0, programs: 0 };
  const note = (name) => { trace.calls[name] = (trace.calls[name] || 0) + 1; };
  const gl = new Proxy(Object.create(null), {
    get(_t, prop) {
      if (typeof prop !== 'string') return undefined;
      if (/^[A-Z][A-Z0-9_]*$/.test(prop)) return 0x8000 + (prop.length % 256);   // a GL enum constant
      return (...args) => {
        note(prop);
        if (prop === 'getContext') return gl;
        if (prop.startsWith('create')) { if (prop === 'createProgram') trace.programs++; return { __gl: prop }; }
        if (prop === 'getUniformLocation') { trace.uniforms; return { __loc: args[1] }; }   // non-null → app sets it
        if (prop === 'getAttribLocation') return 0;
        if (/^getShaderParameter|getProgramParameter$/.test(prop)) return true;             // compile/link OK
        if (/InfoLog$/.test(prop)) return '';
        if (/^getParameter$/.test(prop)) return 1;
        if (prop === 'useProgram') { if (args[0]) trace.usedProgram = true; return; }
        if (prop.startsWith('uniform')) { trace.uniforms++; return; }
        if (prop === 'drawArrays' || prop === 'drawElements') { trace.drew = true; return; }
        return undefined;
      };
    },
  });
  return { gl, trace };
}

// ── a focused, permissive DOM/host shim (node-builtins only; no jsdom) ───────────────────────────────────
// Covers the surface an integrator shell touches on load (the mount(root) convention + an inline render loop):
// element create/append/query, attributes/events (no-op), a canvas whose getContext returns the recording GL,
// sane dimensions, and a requestAnimationFrame that drives exactly MAX_FRAMES then stops (no runaway loop).
function makeHost() {
  const { gl, trace } = recordingGL();
  const swallow = new Proxy(() => swallow, { get: () => swallow, set: () => true, apply: () => swallow });
  const mkEl = () => {
    const el = {
      width: 300, height: 150, clientWidth: 300, clientHeight: 150, offsetWidth: 300, offsetHeight: 150,
      value: '', textContent: '', innerHTML: '', id: '', className: '',
      style: swallow, dataset: {}, children: [], childNodes: [],
      classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
      getContext: (t) => (String(t).includes('webgl') ? gl : null),
      appendChild: (c) => c, append: () => {}, prepend: () => {}, removeChild: (c) => c, insertBefore: (c) => c,
      replaceChildren: () => {}, replaceWith: () => {}, before: () => {}, after: () => {},
      cloneNode: () => mkEl(), insertAdjacentElement: (_p, c) => c, insertAdjacentHTML: () => {},
      remove() {}, setAttribute() {}, removeAttribute() {}, getAttribute: () => null, hasAttribute: () => false,
      addEventListener() {}, removeEventListener() {}, focus() {}, blur() {}, click() {},
      querySelector: () => mkEl(), querySelectorAll: () => [], closest: () => null,
      getBoundingClientRect: () => ({ width: 300, height: 150, top: 0, left: 0, right: 300, bottom: 150 }),
    };
    return el;
  };
  const rafCbs = [];
  let rafN = 0;
  // a working in-memory Web Storage (a faithful browser has it; an app that round-trips save→load runs cleanly)
  const memStore = () => { const m = new Map(); return {
    getItem: (k) => (m.has(String(k)) ? m.get(String(k)) : null), setItem: (k, v) => { m.set(String(k), String(v)); },
    removeItem: (k) => { m.delete(String(k)); }, clear: () => m.clear(), key: (i) => [...m.keys()][i] ?? null,
    get length() { return m.size; } }; };
  const localStorage = memStore(), sessionStorage = memStore();
  const host = {
    document: {
      createElement: () => mkEl(), createElementNS: () => mkEl(),
      getElementById: () => mkEl(), querySelector: () => mkEl(), querySelectorAll: () => [],
      body: mkEl(), head: mkEl(), documentElement: mkEl(), addEventListener() {}, removeEventListener() {},
    },
    window: { addEventListener() {}, removeEventListener() {}, devicePixelRatio: 1, innerWidth: 1280, innerHeight: 720,
              localStorage, sessionStorage, matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }) },
    localStorage, sessionStorage,
    requestAnimationFrame: (cb) => { if (rafN < MAX_FRAMES) { rafN++; rafCbs.push(cb); } return rafN; },
    cancelAnimationFrame: () => {},
    drainFrames(now) { let n = 0; while (rafCbs.length && n < MAX_FRAMES) { rafCbs.shift()(now + n * 16); n++; } },
    trace,
  };
  return host;
}

// ── execute the app's module entry against the shim, then assert the render contract ─────────────────────
async function renderTrace(entry) {
  const errs = [];
  const root = path.dirname(path.resolve(entry));
  const html = fs.readFileSync(entry, 'utf8');
  const host = makeHost();

  // inject host globals BEFORE importing the app module (top-level + mount() read these)
  const saved = {};
  for (const k of ['document', 'window', 'requestAnimationFrame', 'cancelAnimationFrame', 'localStorage', 'sessionStorage']) {
    saved[k] = globalThis[k];
    globalThis[k] = host[k] ?? host.window;
  }
  if (typeof globalThis.performance?.now !== 'function') globalThis.performance = { now: () => 0 };

  const temps = [];
  try {
    // (a) linked module entries: <script type="module" src="./main.mjs"> — import; call mount(root) if exported
    const linked = [...html.matchAll(/<script\b[^>]*\btype\s*=\s*["']module["'][^>]*\bsrc\s*=\s*["'](\.[^'"]+)["']/gi)].map((m) => m[1]);
    // (b) inline module scripts — write beside the entry (so relative imports resolve) and import to auto-run
    const inline = [...html.matchAll(/<script\b[^>]*\btype\s*=\s*["']module["'][^>]*>([\s\S]*?)<\/script>/gi)]
      .map((m) => m[1]).filter((s) => s.trim());

    let executed = 0;
    for (const spec of linked) {
      const file = path.resolve(root, spec);
      const cands = [file, file + '.mjs', file + '.js', path.join(file, 'index.mjs')];
      const hit = cands.find((c) => fs.existsSync(c));
      if (!hit) continue;
      const mod = await import(url.pathToFileURL(hit).href);
      executed++;
      const mount = mod.mount || mod.default?.mount || (typeof mod.default === 'function' ? mod.default : null);
      if (typeof mount === 'function') mount(host.document.getElementById('app'));
    }
    for (const code of inline) {
      const seq = ++RENDER_SEQ;
      const tmp = path.join(root, `.render-check-${process.pid}-${seq}.mjs`);
      fs.writeFileSync(tmp, code);
      temps.push(tmp);
      await import(url.pathToFileURL(tmp).href + `?seq=${seq}`);   // unique URL → auto-runs THIS shell's on-load path
      executed++;
    }
    if (!executed) errs.push('no executable module entry — nothing to drive a render (need an inline or src= module script)');

    host.drainFrames(16);   // pump a few frames for apps that only draw inside requestAnimationFrame
  } catch (e) {
    errs.push(`render path THREW on load: ${e && e.message ? e.message : e} — the assembled shell does not run`);
  } finally {
    for (const k of Object.keys(saved)) { if (saved[k] === undefined) delete globalThis[k]; else globalThis[k] = saved[k]; }
    for (const t of temps) { try { fs.unlinkSync(t); } catch { /* best-effort */ } }
  }

  const { trace } = host;
  if (!errs.length) {
    if (!trace.usedProgram) errs.push('no program was used (gl.useProgram never called) — the shell links nothing into the pipeline');
    if (!trace.drew) errs.push('the render path issued NO draw call (drawArrays/drawElements) — the app assembles but never draws a frame');
  }
  return { errs, trace };
}

async function check(entry) {
  const stat = checkShell(entry);                                  // compose the static floor first
  if (stat.length) return { errs: stat.map((e) => `[static] ${e}`), trace: null };
  return renderTrace(entry);
}

// ── selftest ─────────────────────────────────────────────────────────────────────────────────────────────
async function selftest() {
  const os = fs.mkdtempSync(path.join(process.env.TMPDIR || '/tmp', 'render-check-'));
  const fails = [];
  const ck = (cond, label) => { console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}`); if (!cond) fails.push(label); };
  const write = (p, s) => { fs.mkdirSync(path.dirname(path.join(os, p)), { recursive: true }); fs.writeFileSync(path.join(os, p), s); };

  // a REAL renderer module (mirrors the core compiler + render loop shape) used by the coherent cases
  write('core/index.mjs', `
    export function compileShader(gl, src) {
      const s = gl.createShader(gl.FRAGMENT_SHADER); gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) return { program: null, errors: [{ message: gl.getShaderInfoLog(s) }] };
      const p = gl.createProgram(); gl.attachShader(p, s); gl.linkProgram(p);
      return gl.getProgramParameter(p, gl.LINK_STATUS) ? { program: p, errors: [] } : { program: null, errors: [] };
    }`);
  // 1. coherent: inline shell that compiles + draws a frame
  write('ok.html', `<!doctype html><canvas id=gl></canvas><script type="module">
    import { compileShader } from './core/index.mjs';
    const gl = document.getElementById('gl').getContext('webgl2');
    const { program } = compileShader(gl, 'void main(){}');
    function frame(){ gl.useProgram(program); gl.uniform1f(gl.getUniformLocation(program,'iTime'), 0); gl.drawArrays(gl.TRIANGLES,0,3); requestAnimationFrame(frame); }
    frame();
  </script>`);
  ck((await check(path.join(os, 'ok.html'))).errs.length === 0, 'a shell that compiles + USES a program + DRAWS a frame PASSES');

  // 2. assembles but never draws (links a program, no draw call)
  write('nodraw.html', `<!doctype html><canvas id=gl></canvas><script type="module">
    import { compileShader } from './core/index.mjs';
    const gl = document.getElementById('gl').getContext('webgl2');
    compileShader(gl, 'void main(){}');   // links but never useProgram/drawArrays
  </script>`);
  ck((await check(path.join(os, 'nodraw.html'))).errs.some((e) => /draw/.test(e)), 'a shell that assembles but never DRAWS fails (the "links but never renders" bug)');

  // 3. render path throws on load (imports a product module so it clears the static floor, then throws)
  write('throws.html', `<!doctype html><canvas id=gl></canvas><script type="module">
    import { compileShader } from './core/index.mjs';
    const gl = document.getElementById('gl').getContext('webgl2');
    compileShader(gl, 'void main(){}');
    null.boom();   // runtime error during the on-load render path
  </script>`);
  ck((await check(path.join(os, 'throws.html'))).errs.some((e) => /THREW/.test(e)), 'a shell whose render path throws on load FAILS');

  // 3b. the shim covers standard DOM (replaceChildren) + a working localStorage round-trip — common app surface
  write('hostapi.html', `<!doctype html><canvas id=gl></canvas><script type="module">
    import { compileShader } from './core/index.mjs';
    const gl = document.getElementById('gl').getContext('webgl2');
    localStorage.setItem('k', 'v'); if (localStorage.getItem('k') !== 'v') throw new Error('storage round-trip');
    document.getElementById('panel').replaceChildren(document.createElement('div'));
    const { program } = compileShader(gl, 'void main(){}');
    gl.useProgram(program); gl.drawArrays(gl.TRIANGLES, 0, 3);
  </script>`);
  ck((await check(path.join(os, 'hostapi.html'))).errs.length === 0, 'the shim covers replaceChildren + a working localStorage round-trip (a shell using them PASSES)');

  // 4. src= main.mjs exporting mount(root) — the integrator convention — is driven
  write('main.mjs', `
    import { compileShader } from './core/index.mjs';
    export function mount(root){ const c = document.createElement('canvas'); root.appendChild(c);
      const gl = c.getContext('webgl2'); const { program } = compileShader(gl, 'void main(){}');
      gl.useProgram(program); gl.drawArrays(gl.TRIANGLES, 0, 3); }`);
  write('mounted.html', `<!doctype html><canvas></canvas><script type="module" src="./main.mjs"></script>`);
  ck((await check(path.join(os, 'mounted.html'))).errs.length === 0, 'a src= main.mjs exporting mount(root) is driven and PASSES');

  // 5. static failure short-circuits (dangling import never reaches the runtime trace)
  write('dangling.html', `<!doctype html><canvas></canvas><script type="module">import './core/missing.mjs';</script>`);
  ck((await check(path.join(os, 'dangling.html'))).errs.some((e) => /\[static\]/.test(e)), 'a static-incoherent shell fails at the static floor (before the render trace)');

  fs.rmSync(os, { recursive: true, force: true });
  console.log(fails.length ? `render-check selftest: FAIL (${fails.length})` : 'render-check selftest: OK');
  return fails.length ? 1 : 0;
}

// ── CLI ──────────────────────────────────────────────────────────────────────────────────────────────────
const arg = process.argv[2];
if (arg === '--selftest') process.exit(await selftest());
if (!arg) { console.error('usage: render-check.mjs <index.html> | --selftest'); process.exit(2); }
const { errs, trace } = await check(arg);
if (errs.length) { console.error('render INCOHERENT:\n' + errs.map((p) => '  - ' + p).join('\n')); process.exit(1); }
console.log(`render coherent: ${arg} — executes, useProgram + ${trace.uniforms} uniform call(s) + a draw (${Object.keys(trace.calls).length} distinct GL ops); real-GPU pixels are the optional escalation`);
process.exit(0);
