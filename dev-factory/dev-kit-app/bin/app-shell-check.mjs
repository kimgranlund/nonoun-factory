#!/usr/bin/env node
/**
 * app-shell-check.mjs — the kit's APP-SHELL coherence verifier.
 *
 * The kit grades capabilities as pure ES modules imported headlessly by their sibling verify.mjs. That
 * model can prove the LOGIC but not that the modules ASSEMBLE into a runnable app — so a build can validate
 * every capability and still ship no browser entry (the "app" cell degenerates to a re-export barrel), or
 * ship a shell with imports that don't resolve. This verifier gates that integration layer: given the app
 * entry (index.html), it statically checks the shell is a coherent, runnable assembly OVER the built modules.
 *
 * WHAT IT CHECKS (static, headless — exit 0 = coherent, 1 = not):
 *   1. the entry exists and is HTML with a <canvas> and a <script type="module">;
 *   2. every relative import in the module graph reachable from the entry RESOLVES to a real product file
 *      (no dangling `./core/index.mjs` the assembly references but the build never produced);
 *   3. the entry actually USES the product (imports at least one product module), not an empty page.
 *
 * WHAT IT DOES NOT CHECK (the honest limit): that the app RENDERS. Runtime/semantic coherence — e.g. a
 * fragment shader written for a different GLSL version than the compiler links, a uniform name mismatch —
 * needs the page actually executed. That is a BROWSER/RENDER harness adapter (headless-gl / puppeteer +
 * screenshot-diff), the next adapter on the kit's roadmap; this static gate is its floor, not its ceiling.
 *
 * Usage:  node app-shell-check.mjs <path/to/index.html>     # the kit binds {asset} = the entry
 *         node app-shell-check.mjs --selftest
 */
import fs from 'node:fs';
import path from 'node:path';
import url from 'node:url';

export function checkShell(entry) {
  const errs = [];
  if (!fs.existsSync(entry) || !fs.statSync(entry).isFile()) {
    return [`app entry not found: ${entry} — the build produced no runnable shell (a re-export barrel is not an app)`];
  }
  const html = fs.readFileSync(entry, 'utf8');
  // a runnable app needs a render surface: a <canvas> (WebGL/2D app) OR a DOM mount root (a DOM/SVG app —
  // <main>, id="app"/"root", or [data-app/-root/-mount]). <body> alone doesn't count (it's always present).
  const hasSurface = /<canvas[\s>]/i.test(html) || /<main[\s>]/i.test(html) ||
    /\bid\s*=\s*["'](app|root|app-root|main|mount)["']/i.test(html) || /\bdata-(app|root|mount)\b/i.test(html);
  if (!hasSurface) errs.push('no render surface — needs a <canvas> or a DOM mount root (<main>, id="app"/"root", or [data-app])');
  if (!/<script\b[^>]*\btype\s*=\s*["']module["']/i.test(html)) errs.push('no <script type="module"> — nothing wires the modules into a running page');

  // collect the module-graph: every relative import reachable from the entry's inline + linked module scripts
  const root = path.dirname(path.resolve(entry));
  const importRe = /\bimport\b[^'"]*?from\s*['"](\.[^'"]+)['"]|\bimport\s*['"](\.[^'"]+)['"]/g;
  const seen = new Set();
  const queue = [];
  let usesProduct = false;

  // inline module scripts in the entry
  for (const m of html.matchAll(/<script\b[^>]*\btype\s*=\s*["']module["'][^>]*>([\s\S]*?)<\/script>/gi)) {
    for (const im of m[1].matchAll(importRe)) {
      const spec = im[1] || im[2];
      usesProduct = true;
      queue.push({ from: entry, spec });
    }
    // linked module entry: <script type="module" src="./x.mjs">
  }
  for (const m of html.matchAll(/<script\b[^>]*\btype\s*=\s*["']module["'][^>]*\bsrc\s*=\s*["'](\.[^'"]+)["']/gi)) {
    usesProduct = true;
    queue.push({ from: entry, spec: m[1] });
  }
  if (!usesProduct) errs.push('the module script imports no product module (./…) — the shell does not actually use the built code');

  // walk the import graph, resolving each relative specifier against a real file
  while (queue.length) {
    const { from, spec } = queue.shift();
    const resolved = path.resolve(path.dirname(from), spec);
    const cands = [resolved, resolved + '.mjs', resolved + '.js', path.join(resolved, 'index.mjs'), path.join(resolved, 'index.js')];
    const hit = cands.find((c) => fs.existsSync(c) && fs.statSync(c).isFile());
    if (!hit) { errs.push(`dangling import ${spec} (from ${path.relative(root, from) || 'index.html'}) — references a module the build never produced`); continue; }
    if (seen.has(hit)) continue;
    seen.add(hit);
    const src = fs.readFileSync(hit, 'utf8');
    for (const im of src.matchAll(importRe)) queue.push({ from: hit, spec: im[1] || im[2] });
  }
  return errs;
}

function selftest() {
  const os = fs.mkdtempSync(path.join(process.env.TMPDIR || '/tmp', 'shell-check-'));
  const fails = [];
  const ck = (cond, label) => { console.log(`  ${cond ? 'PASS' : 'FAIL'}  ${label}`); if (!cond) fails.push(label); };
  // a coherent shell over a real module
  fs.mkdirSync(path.join(os, 'core'), { recursive: true });
  fs.writeFileSync(path.join(os, 'core', 'index.mjs'), 'export const compileShader = () => ({program:{},errors:[]});\n');
  fs.writeFileSync(path.join(os, 'index.html'),
    '<!doctype html><canvas id=gl></canvas><script type="module">import { compileShader } from "./core/index.mjs"; compileShader();</script>');
  ck(checkShell(path.join(os, 'index.html')).length === 0, 'a coherent shell (canvas + module script + resolving product import) PASSES');
  // missing entry
  ck(checkShell(path.join(os, 'nope.html')).length > 0, 'a missing entry FAILS (no runnable shell)');
  // dangling import
  fs.writeFileSync(path.join(os, 'bad.html'),
    '<!doctype html><canvas></canvas><script type="module">import "./ui/missing.mjs";</script>');
  ck(checkShell(path.join(os, 'bad.html')).some((e) => /dangling/.test(e)), 'a shell with a dangling import FAILS (references a module the build never produced)');
  // barrel-only / no canvas
  fs.writeFileSync(path.join(os, 'barrel.html'), '<!doctype html><script type="module">export * from "./core/index.mjs";</script>');
  ck(checkShell(path.join(os, 'barrel.html')).some((e) => /canvas/.test(e)), 'a no-canvas page FAILS (not a runnable render surface)');
  fs.rmSync(os, { recursive: true, force: true });
  console.log(fails.length ? `app-shell-check selftest: FAIL (${fails.length})` : 'app-shell-check selftest: OK');
  return fails.length ? 1 : 0;
}

// CLI — only when run directly (not when imported by render-check.mjs, which composes checkShell)
if (process.argv[1] && import.meta.url === url.pathToFileURL(process.argv[1]).href) {
  const arg = process.argv[2];
  if (arg === '--selftest') process.exit(selftest());
  if (!arg) { console.error('usage: app-shell-check.mjs <index.html> | --selftest'); process.exit(2); }
  const problems = checkShell(arg);
  if (problems.length) { console.error('app-shell INCOHERENT:\n' + problems.map((p) => '  - ' + p).join('\n')); process.exit(1); }
  console.log(`app-shell coherent: ${arg} — canvas + module entry + every product import resolves`);
  process.exit(0);
}
