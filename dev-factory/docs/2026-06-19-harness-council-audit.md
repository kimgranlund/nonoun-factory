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

## The bigger items — now CLOSED (rounds 3–6)

The backlog the first two rounds deferred has been worked through:

1. **H6 · live refuter producer (round 3, #25).** `dispatch.produce_refuter`/`produce_refuters` arm an independent
   `fresh_refute` oracle when a code cell validates; the heartbeat sweeps it; `run_refuter` measures it. Tier 2 is
   now EARNABLE on a real build (`evals/earned-autonomy` proves it, no `agreed=True` fake). The "cold-start persists
   the verify-spec" claim is now backed by code.
2. **H5-C1/C3 + no-progress · budget realism (round 4).** Failure-path `activity-fail` now carries `cost_usd`/`tokens`
   (the ceiling sees failed-run spend); a window `DEV_FACTORY_DOLLAR_CEILING` + an always-on per-dispatch
   `--max-budget-usd` (`DEV_FACTORY_DISPATCH_USD`, default $10); and the kernel's `ledger.no_progress` was fixed
   (it compares failure events, not all events) and WIRED (`n=2`) so a stuck cell blocks early.
3. **H1 · the cycle detector (round 5).** `compass.detect_cycle`/`surface_cycle` — a deterministic DFS that NAMES a
   `depends_on` cycle once in the ledger; the heartbeat calls it whenever non-terminal work exists. The detector
   lives in `compass.py` exactly as the `dependency-arbiter`/`decomposition` contracts always claimed.
4. **H4 · naming drift (round 6).** `docs/specs/` → `docs/spec/` (the repo now matches its own "spec/, never specs/"
   rule); the off-vocab `spec-decomposer` design agent consolidated into `spec-architect` (the actor the build
   already uses); and `naming.schema.json`'s `_block_note` corrected — it claimed gate-naming computes the `block`
   vocab, which it does not (the gate computes only `actor`/`gateverb`/singular-`layer`-dir).

## Remaining (accepted, low threat)

- **Verifier-author residual `Bash` surface** — the rubric-architect keeps `Bash` (it calibrates) + can write
  `verify.mjs`; signals stay gate-protected but the inline-interpreter forge is not caught by the heuristic. Lower
  threat (authors the gate, not the product; runs before the module exists; denied the `index.mjs` barrel since
  round 2) — accepted, noted here.
