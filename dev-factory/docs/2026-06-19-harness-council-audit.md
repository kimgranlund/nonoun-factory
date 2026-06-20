# Harness-council audit of dev-factory — verdict & remediation ledger

_Date: 2026-06-19. Reviewer: `harness-forge:harness-council` (7 structural critics, parallel isolated contexts).
Scope: the app-build campaign's changes — the factory-authored verifier loop (#2), the `--allow-verify` permit,
single-file shell authoring + the render gate, the autonomy/budget model._

## Why this exists

The largest body of recent work (the #2 verifier loop, the shell authoring, the gates) was authored **and
self-verified in one session by the same agent**. An independent adversarial review was run before building
further, to catch the blind spots a one-session self-verify structurally cannot. It did.

## Verdict

**Earned autonomy: Tier 1 (Gated).** Three caps fired — **H3 reward-hacking ≤2 · H2 verifier-integrity =1 ·
H6 autonomy-trajectory ≤2.** The architecture is **mature** — H1 (partial-order), H4 (naming), H7 (staleness)
*pass* their caps. The caps fire on one thing: **the verification floor on the live `headless` path is mock-deep,
because CI only ever exercises the `MockAdapter`.** Green CI proved the *mock* loop closes on itself and nothing
about the real-verifier path. The session's "closed loop, proven" framing was **operator-attested (attended),
not refuter-attested** — the correction the audit delivered.

## Convergent findings (≥2 critics, independently)

| Finding | Critics | Status |
| --- | --- | --- |
| `run_refuter` resolved the cell dir as `.factory/{layer}/{slug}/`, ignoring the app kit's `output_root:".."` → the false-pass oracle silently no-op'd for every app cell (so the autonomy trajectory could never *measure* its way to Tier 2) | H2·H6·H7·(RH) — **4-way** | **FIXED** (r1, #23) — now mirrors `self_heal_cell` |
| Live `headless` module worker carried `Bash`; the gate's forge floor deliberately ignores inline interpreters → a worker could forge a signal past the gate the gate assumed it couldn't | H3 (C1) — highest severity | **FIXED** (r2) — role-aware tool-scope, no Bash for the module worker |
| Verifier-author permit left `index.mjs` writable → one dispatch could author both the gate and the module that passes it | H3 (C2) | **FIXED** (r2) — `VERIFIER_AUTHOR` denies `*/index.mjs` (dev-kernel 0.2.14) |
| CI only exercises the mock path; `_is_mock_verifier` is an evadable line-count heuristic | H2 (M1·M2) + H5 | **FIXED** (r2) — `evals/real-verifier-teeth` runs a real gate; detector is now behavioral |
| Verifier-author pass uncounted / spend discarded | H5 (C2) + H3 | **FIXED** (r1) — attaches metrics to the run ceiling |

## Remediation rounds (done)

- **Round 1 (#23):** `run_refuter` output_root path; verifier-author spend counted against the token ceiling.
- **Round 2 (#24):** module worker loses `Bash` (role-aware `_allowed_tools`); `VERIFIER_AUTHOR` denies the
  product barrel; `_is_mock_verifier` is marker+behavioral (not line count); `evals/real-verifier-teeth` proves a
  real gate has teeth, is satisfiable, and that the stub it replaces is blind to the same deviation — wired into CI.

## Remaining backlog (prioritized, NOT yet done)

These are the bigger / trade-off items the rounds above did not close — surfaced here so they are not lost:

1. **H5-C1/C3 · budget realism** — the token ceiling reads success-path telemetry only (failure runs carry no
   tokens); headless is dollar-uncapped by default (`--max-budget-usd` only when `budget.dollars` is set). Add
   tokens to `activity-fail`; default a window `$` ceiling.
2. **H6 · live refuter producer in `dev-server`** — the cold-start verify-spec/refuter producer exists in `debug/`
   ralph but NOT the server path; `dev-server/CHANGELOG.md` (the older "cold-start planner persists the verify-spec"
   claim) has no `dev-server/` code behind it. Wire it, and stop the demos/heartbeat reaching Tier 2 via hardcoded
   `agreed=True`.
3. **H1-M1 · the cycle detector** — asserted by the dependency-arbiter/decomposition agent contracts, but no code
   detects a `depends_on` cycle (it silently starves the frontier). Implement it (dev-server side; `lattice.py` is
   vendored).
4. **H4 · template drift** — `docs/specs/` (a pluralized layer-like dir in the spec template) and a `decomposer`
   off-vocab actor. *Verify first* — `docs/specs/` is a docs folder, not a lattice instance layer dir, so the gate
   may be over-flagging; confirm before renaming (it would move spec links).
5. **Verifier-author residual `Bash` surface** — the rubric-architect keeps `Bash` (it calibrates) + can write
   `verify.mjs`; signals stay gate-protected but the inline-interpreter forge is not caught by the heuristic. Lower
   threat (authors the gate, not the product; runs before the module exists) — accepted for now, noted here.
