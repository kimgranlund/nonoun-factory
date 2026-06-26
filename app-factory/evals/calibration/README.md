# Entailment-critic calibration

The deterministic teeth floor (`app-commit.py bar_has_teeth`) proves a sealed bar is **not a no-op** —
it rejects `exit 0`. It CANNOT prove the bar **faithfully entails the spec**: an import-only bar
(`import storage; sys.exit(0)`) passes the teeth floor yet asserts nothing. That judgement is the
**entailment-critic's** job, and `--seal` trusts it. This corpus answers: *does the entailment-critic
actually refuse the hollow bars the teeth floor misses — and still certify a genuinely faithful one?*

A fidelity gate has one safe failure mode and one fatal one:
- **fatal — a FALSE CERTIFY:** a hollow bar waved through ⇒ silent false passes for the life of the ticket.
- **safe — a false refuse:** a faithful bar bounced back to the deriver to strengthen.

So `score-calibration.py` fails calibration on **any** false certify, independent of agreement.

## Files
- `exemplars.json` — the corpus: (spec, proposed bar) pairs with a known-correct verdict and rationale.
  Seven REFUSE failure modes (import-only · presence-attribute · contradicts-spec · partial-coverage ·
  nondeterministic · single-key-memorizable · multikey-hardcoded-literals) + two CERTIFY shapes
  (seeded-multikey · seeded-overwrite).
- `score-calibration.py` — grades a verdicts file; selftested (headless, runs in CI). CALIBRATED iff
  zero false certifies AND agreement ≥ `pass_threshold`.
- `runs/<date>.json` — a recorded run's verdicts (provenance; re-score with `--verdicts`).

## Run protocol (agent-dispatched, not headless)
The judge is an agent, so a run is orchestrated from a Claude Code session, not a subprocess:
1. For each exemplar, dispatch the **entailment-critic** in an **isolated context**, giving it only the
   shared spec + that exemplar's `bar` + `deriver_map` (never the `expected`/`why` — that would bias it).
   Ask it to end with exactly `VERDICT: CERTIFY` or `VERDICT: REFUSE`.
2. Collect the verdicts into `runs/<date>.json` (`{exemplar_id: "CERTIFY"|"REFUSE"}`).
3. `python3 score-calibration.py --verdicts runs/<date>.json` → CALIBRATED / NOT CALIBRATED.

A NOT-CALIBRATED result is actionable, not a failure of the harness: a false **certify** means the
critic (its `entailment-critic.md` contract) needs sharpening; a false **refuse** usually means an
exemplar's `expected` was too lenient — which is exactly how this corpus was hardened (see below).

## Latest run — 2026-06-26 (`runs/2026-06-26.json`): **CALIBRATED, 9/9, 0 false-certify**
Judge: the `entailment-critic.md` contract, run via isolated general agents (the `app-factory:entailment-critic`
subagent type was not registered in that session, so the contract was supplied inline — a faithful exercise
of the same judge; re-run with the registered agent when available).

What the run established and changed:
- **The dangerous direction is clean.** The critic refused all five hollow bars — crucially the
  `import-only` bar (`E2`), the exact shape the teeth floor passes. The judgement layer catches what the
  deterministic floor cannot. Zero false certifies.
- **It is not refuse-everything.** It CERTIFIED both robust bars (`R1`, `R2`) — so `--seal` can still be
  earned; the gate is discriminating, not decorative.
- **It is stricter than the corpus first assumed — correctly.** Two bars first labelled CERTIFY
  (single-key `'k'/'v'`, and multi-key but hardcoded `'a'->'1'`) were REFUSED: a memorizing stub
  (`load(k): return 'v' if k=='k' else None`) passes them without ever storing. The corpus was
  recalibrated to that standard (E1/E6 are now REFUSE), and the lesson was baked into the
  acceptance-deriver: **a faithful bar exercises multiple distinct keys with non-literal (seeded-
  deterministic) values, all stores before all loads, `is None` for absent-key** — see `R1`/`R2`.
