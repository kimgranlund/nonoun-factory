# Harness-council VERIFICATION re-audit — verdict & remediation

_Date: 2026-06-20. Reviewer: `harness-forge:harness-council` (7 structural critics), run as a verification pass over
the [first audit](2026-06-19-harness-council-audit.md)'s remediation. Theme: do not self-attest the fixes — send
them back through the same independent council._

## What the re-audit found

**The round-3 H6 "fix" was hollow, and the council was right.** The live producer armed `verify_gen.fresh_refute`'s
generic invariants (`typeof e === 'function'`, `JSON.stringify(e) === JSON.stringify(e)`) as the refuter — but those
are **tautologies**: no module that passed its gate can fail them. So `false_pass` was structurally pinned at `0.0`
and Tier 2 auto-granted again — *the prior `record_refuter_check(agreed=True)` fake wearing a `node` subprocess*. The
`earned-autonomy` eval only "proved" the disagree case by **hand-overwriting** the sidecar. Six of seven critics
converged on `verify_gen.py:67-88` as the keystone. The re-audit also surfaced four supporting findings (H1/H3/H5).

The re-derived verdict was **Tier 1 (Gated), Tier 2 NOT honestly earned** — `unmeasured` is not earned, and a `0.0`
pinned by a vacuous oracle is not measured.

## Findings → fixes (all landed, each verified by selftest + a node-gated eval)

| # | Finding | Fix |
| --- | --- | --- |
| **Keystone (H6/H2/H7)** | the refuter was a tautology → Tier 2 auto-granted | A refuter MEASURES only if it EXERCISES behavior (`verify_gen.is_behavioral` — invokes an export on an input the gate didn't use). `produce_refuter` arms a MEASURING refuter only from a behavioral refute set; else the generic floor as a NON-measuring liveness check. `ledger.refuter_checks` counts only measuring checks. `earned-autonomy` rewritten: the generic floor stays `unmeasured`/Tier 1; a behavioral refuter earns Tier 2 and CATCHES an overfit that genuinely passes its gate — no hand-overwrite. (dev-kernel 0.2.17) |
| **H3** | the refuter ran in the worker's dir and trusted exit status (a module could `process.exit(0)` on import and "agree") | `run_refuter` runs in a temp dir, imports the module by `file://` URL, and requires the harness's `pass:` sentinel in stdout. `earned-autonomy` H4 proves an exit-on-import module fools the exit-code gate but not the refuter |
| **H5** | `arm()` defaulted all four ceilings to `None` (unbounded window); `no_progress` compared raw strings | `arm()` stamps a safety wall-clock deadline when no ceiling is set; `ledger.no_progress` normalizes path/exit/timestamp variance (dev-kernel 0.2.18) |
| **H1** | `gate_dispatch` read the ticket's `cells_ready` while the cycle detector/`ready()` read the cell's `depends_on` — two graphs | `gate_dispatch` enforces the cell's `depends_on` on a validating transition, so all three traverse the SAME graph (dev-kernel 0.2.19) |

## The honest standing consequence

Closing the keystone means **Tier 2 is no longer auto-granted by a tautology — it requires a real independent oracle
(a behavioral refute set the gate's author did not write).** The dev-server consumes that set when present; absent it,
the family sits honestly at **Tier 1 (Gated)** — a perfectly good operating tier (the human signs off at `in-review`).

**The one open enhancement (deferred, not a correctness gap): a headless refuter-author** — a rubric-architect, blind
to the gate, that authors domain refute cases from the spec into the verify-spec (via a worker→server hand-off, since
the verify-spec is server-only). That would make Tier 2 **autonomously** earnable on a real build. A mock cannot author
real domain cases without re-introducing a weak-but-passing oracle, so the mock path is an honest no-op (stays Tier 1).
The system is honest and safe without it; this is the path to lights-out, not a hole.

## Residuals noted (not closed this pass)

- The **gate** itself (run by the vendored `validate.py`) still trusts exit status, so a `process.exit(0)`-on-import
  module can pass its gate; the hardened refuter is now the backstop that catches it. A full gate fix needs a
  kit-level verifier wrapper (the runner is vendored).
- True in-process refuter isolation (a module can still monkey-patch globals) would need a `vm`/sandbox — a heavier
  dependency, deliberately not taken; the temp-dir + `file://` + sentinel closes the realistic (worker-authored)
  surface.

## Round 2 — a SECOND council verification caught the first round short (and it was right)

The fixes above were sent back through the council a second time rather than self-attested. It found the keystone
**still not closed** — the producer path was honest, but the *measurement* was forgeable three more ways. All fixed:

| # | Finding (council, round 2) | Fix |
| --- | --- | --- |
| **CRITICAL** | the **counting-default hole**: `ledger.refuter_checks` counted `measuring is not False`, so a check with NO `measuring` key (`record_refuter_check`, reachable from the `autonomy refuter` CLI) minted a measured 0.0 with no oracle — the exact `agreed=True` fake, alive. I had *blessed* this in a comment. | `refuter_checks` counts ONLY `measuring is True` (fail-closed; absence = non-counting). `record_refuter_check` defaults `measuring=False` (it ran no oracle). The autonomy selftest now PROVES an asserted check stays unmeasured/Tier 1; the simulation callers (tests/demo) opt into `measuring=True` explicitly; the heartbeat dispatch test uses an explicit `tier=2` override, not a minted check. |
| **CRITICAL** | the **forgeable `pass:` sentinel**: a module that prints `pass` + `process.exit(0)` on import forges agreement. | `run_refuter` injects a per-run **NONCE** printed only at the harness's own success exit; AGREE requires the nonce, which the module cannot know. `earned-autonomy` H4 now uses the exact `print('pass')+exit` forge. |
| **CRITICAL** | **`gate_dispatch ⊊ ready()`**: it checked `depends_on` but not the verifier RUBRIC, so a cell could validate against a non-validated (incident-staled) rubric — "verified against air." | `gate_dispatch` re-checks, at dispatch, that the rubric the cell validates against (its `verifier` field AND the ticket's `acceptance.rubric_cell`) is `validated`, and enforces `depends_on` on `validated → operating` too. (The full LAYER_DEPS half of `ready()` is the frontier scan's job over a complete lattice — enforcing it per-ticket wrongly blocks single-cell advances.) Selftest covers verified-against-air. |
| **MAJOR** | `is_behavioral` accepted **value-free invocations** (`compute(1)===compute(1)`, `typeof compute(0)`) as measuring. | It now rejects identical-operand tautologies and `typeof` shape-probes; over-rejection is fail-safe (toward unmeasured). |
| **MAJOR** | `arm()` guarded on `is None`, so `arm(deadline_s=0)` minted an unbounded window. | Guards on FALSY; `arm(deadline_s=0)` gets the safety deadline. |
| **MAJOR** | `propagate_staleness` was **one-hop**, not transitive — a grandchild integrator survived stale-but-trusted; the SKILL.md "transitive" claim was false. | `self_heal_cell` drives `propagate_staleness` to a FIXPOINT (transitive un-ship); the SKILL.md claim is corrected (one-hop per call, caller-driven to a fixpoint, lattice-health backstops). `self-heal` H4b proves the grandchild is un-shipped. |

dev-kernel 0.2.20. The deferred item is unchanged: a headless refuter-author for autonomous Tier 2. The self-heal
**declaw** the council noted (a self-healed cell re-arms only the generic floor, so its measurement capacity is spent
until a behavioral oracle is re-authored) is honest (reads `unmeasured`) and is closed by that same refuter-author.
