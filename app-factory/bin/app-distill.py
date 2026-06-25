#!/usr/bin/env python3
"""app-distill.py — the outer loop's distillation: ledger windows → reusable pattern docs, with provenance.

The corpus only compounds if precedent is captured. This reads a window of the ledger and compresses
RECURRING precedent into pattern docs under `knowledge/patterns/`: a failure signature seen ≥ N times is an
anti-pattern; a recurring solution shape is a pattern. Each doc carries the exact ledger entries it was
distilled from (provenance, not opinion) and the window marker. On each run it also AGES OUT superseded
patterns — a pre-existing pattern more than a full window of events stale and not re-confirmed this run is
marked `maturity: stale`, so app-context's freshness filter is live (the marker is read, not just written)
and frozen knowledge stops feeding build context. Distilled, not authored: it writes `draft` proposals —
the `app-distiller` agent and a human decide what becomes canon. Stdlib, Python 3.8+.

  app-distill.py <project> [--window N] [--min-occur N]   # defaults: window=50, min-occur=2
  app-distill.py selftest
"""
import datetime
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "kernel"))
import ledger as _led  # noqa: E402


def _signature(rationale):
    """Stable signature: strip the variable bits (cell ids, paths, hashes, timestamps) so the same failure
    mode across different tickets groups together."""
    s = re.sub(r"[a-z]+\.[a-z0-9-]+\.[a-z0-9-]+", "<cell>", rationale or "")
    s = re.sub(r"sha256:[0-9a-f]+", "<hash>", s)
    s = re.sub(r"\bbuild/\S+|\.factory/\S+|spec/\S+", "<path>", s)
    s = re.sub(r"\d{4}-\d\d-\d\dT\S+", "<ts>", s)
    return re.sub(r"\s+", " ", s).strip()


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:48] or "pattern"


def distill(project, window=50, min_occur=2):
    project = os.path.abspath(project)
    state = os.path.join(project, ".factory", "state")
    kb = os.path.join(project, "knowledge", "patterns")
    evs = _led.read(state)
    win = evs[-window:]
    win_id = f"ledger[-{len(win)}]@{len(evs)}"
    groups = {}
    for e in win:
        if e.get("operation") == "validate" and e.get("rationale") and e.get("cell_id"):
            groups.setdefault((e["result"], _signature(e["rationale"])), []).append(e)

    os.makedirs(kb, exist_ok=True)
    ts = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    written = []
    for (result, sig), events in sorted(groups.items()):
        if len(events) < min_occur:
            continue
        kind = "anti-pattern" if result == "fail" else "solution"
        slug = _slug(f"{kind}-{sig}")
        prov = "\n".join(f"- `{e.get('cell_id')}` @ {e.get('ts', '?')} — {e.get('rationale', '')[:120]}" for e in events)
        with open(os.path.join(kb, f"{slug}.md"), "w", encoding="utf-8") as f:
            f.write(f"---\nkind: knowledge\nname: {slug}\nmaturity: draft\npattern: {kind}\n"
                    f"occurrences: {len(events)}\ndistilled_window: {win_id}\ndistilled_ts: {ts}\n---\n\n"
                    f"# {kind}: {sig}\n\nA recurring {kind} distilled from {len(events)} ledger event(s) "
                    f"(**proposed — review before relying on it**; the distiller distills, it does not author canon).\n\n"
                    f"**Signature.** {sig}\n\n**Provenance.**\n{prov}\n")
        written.append(slug)

    # FRESHNESS: age out superseded patterns. A pre-existing pattern whose distillation window is more than a
    # full `window` of events stale AND was NOT re-confirmed this run is marked `maturity: stale`. This makes
    # app-context's freshness filter LIVE — something actually SETS stale, so the `distilled_window` marker is
    # read, not merely written, and frozen knowledge stops feeding build context. (Re-distilling a still-
    # recurring pattern overwrites it above with a fresh window, resetting its clock.)
    total = len(evs)
    aged = []
    for fn in sorted(os.listdir(kb)):
        if not fn.endswith(".md") or fn[:-3] in written:
            continue
        path = os.path.join(kb, fn)
        txt = open(path, encoding="utf-8").read()
        if "maturity: stale" in txt:
            continue
        m = re.search(r"distilled_window:\s*ledger\[-\d+\]@(\d+)", txt)
        if m and total - int(m.group(1)) > window:
            open(path, "w", encoding="utf-8").write(txt.replace("maturity: draft", "maturity: stale", 1))
            aged.append(fn[:-3])
    return written, aged


def _flag(argv, name, default):
    return argv[argv.index(name) + 1] if name in argv else default


def main(argv):
    if argv and argv[0] == "selftest":
        return selftest()
    pos = [a for a in argv if not a.startswith("--")]
    if not pos:
        print("usage: app-distill.py <project> [--window N] [--min-occur N]", file=sys.stderr)
        return 2
    written, aged = distill(pos[0], int(_flag(argv, "--window", "50")), int(_flag(argv, "--min-occur", "2")))
    print(f"distilled {len(written)} pattern draft(s) → knowledge/patterns/: {', '.join(written) or 'none'}"
          + (f"\naged {len(aged)} superseded pattern(s) → stale: {', '.join(aged)}" if aged else ""))
    return 0


def selftest():
    import json
    import tempfile
    fails = []
    def expect(c, m):
        if not c:
            fails.append(m)
    with tempfile.TemporaryDirectory() as proj:
        state = os.path.join(proj, ".factory", "state")
        os.makedirs(os.path.join(state, "ledger"))
        evs = [
            {"operation": "validate", "actor": "v", "cell_id": "capability.task.a", "result": "fail",
             "rationale": "sealed acceptance failed — FAIL capability.task.a not advanced", "ts": "t1"},
            {"operation": "validate", "actor": "v", "cell_id": "capability.task.b", "result": "fail",
             "rationale": "sealed acceptance failed — FAIL capability.task.b not advanced", "ts": "t2"},
            {"operation": "validate", "actor": "v", "cell_id": "capability.task.c", "result": "pass",
             "rationale": "sealed acceptance passed", "ts": "t3"},
        ]
        for e in evs:
            _led.append(state, e)
        written, aged = distill(proj, min_occur=2)
        kb = os.path.join(proj, "knowledge", "patterns")
        anti = [w for w in written if w.startswith("anti-pattern")]
        expect(anti, f"a recurring failure (2x) must distill to an anti-pattern: {written}")
        expect(not any(w.startswith("solution") for w in written), "a single pass (1x) must NOT distill (below min-occur)")
        doc = open(os.path.join(kb, anti[0] + ".md")).read()
        expect("capability.task.a" in doc and "capability.task.b" in doc, "the pattern must carry its provenance (both cells)")
        expect("occurrences: 2" in doc and "draft" in doc, "the pattern must record occurrences + be a draft proposal")
        # normalization: the two fails differ only by cell id → one grouped pattern, not two
        expect(len([w for w in written if w.startswith("anti-pattern")]) == 1, "cell-specific bits must normalize to ONE signature")
        # FRESHNESS: a pre-existing pattern from a superseded window gets AGED to stale on a later run
        with open(os.path.join(kb, "old-shape.md"), "w") as f:
            f.write("---\nkind: knowledge\nname: old-shape\nmaturity: draft\ndistilled_window: ledger[-1]@1\n---\n# old\n")
        for i in range(8):   # grow the ledger well past the old pattern's window-end (@1) + the window size
            _led.append(state, {"operation": "validate", "actor": "v", "cell_id": "capability.task.z",
                                "result": "pass", "rationale": f"distinct run {i}", "ts": f"u{i}"})
        _w2, aged2 = distill(proj, window=2, min_occur=2)
        expect("old-shape" in aged2, f"a superseded pattern (window-end far behind) must be aged to stale: {aged2}")
        expect("maturity: stale" in open(os.path.join(kb, "old-shape.md")).read(),
               "the aged pattern's frontmatter must be flipped to maturity: stale (so app-context excludes it)")
    if fails:
        sys.stderr.write("app-distill selftest: FAIL\n")
        for f in fails:
            sys.stderr.write(f"  - {f}\n")
        return 1
    print("app-distill selftest: OK (a failure mode recurring across tickets distills to ONE anti-pattern draft "
          "carrying its ledger provenance; a one-off stays below threshold; signatures normalize cell ids/paths/"
          "hashes; a superseded pattern is aged to stale so the freshness filter is live, not decorative)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
