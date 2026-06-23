# Changelog — dev-server

The dev-factory runtime (FastAPI/uvicorn over the stdlib ops layer). Not a plugin — it ships in the dev-factory
marketplace and is versioned with the kernel it serves. Format: [Keep a Changelog](https://keepachangelog.com/).

## 2026-06-22 — prompt → autonomous loop: auto-triage + persistent posture + the overwrite guard

The factory was *designed* for "write a prompt, walk away, get working software" — prompt → untriaged intake →
**triage** (bind cell + transition + validated rubric) → active → compass ranks → heartbeat dispatches → cell
advances — but two wires were never connected and one footgun made full autonomy on `mock` destructive. Closed all
three (headless-only for the judgment step; `mock` stays a free, safe no-op for triage):

- **Auto-triage producer (`dispatch.triage_intake` + `triage_frontier` + `_apply_triage_proposal`, wired into
  `heartbeat.on_tick`).** Each headless tick, the oldest untriaged prompt/issue is dispatched to a **gate-blind
  ticket-triager** (`HeadlessClaudeAdapter._triage_prompt`, wired `--allow-triage`) that writes ONE file — a
  proposal under `coordination/triage/<tid>.json` — which the single-writer server reads and applies via
  `api.triage_issue`, then attempts draft→active (`gate-ticket-ready` decides legality). A prompt now moves the loop
  with **no human at the triage form**. A prompt the triager cannot bind to one cell, or an illegal binding, parks
  (a `triage-attempt` is ledgered; `triage_frontier` skips it after two tries).
- **Persistent autonomous posture + auto-resume on switch (`app.py`).** `run/posture.json` (`{heartbeat, tier}`,
  server-only write, under the worker-protected `run/*` perimeter) replaces the ephemeral global, so "this project is
  autonomous" survives navigation: the heartbeat loop is now **always-on** (idles when disabled, ticks when enabled,
  no restart needed), pause/resume persist the posture, and switching INTO a project **restores** its armed posture +
  re-arms its bounded window (a never-armed project still lands paused — the safe default). "No steering" now survives
  navigation, while spend stays bounded by each project's own armed `run/heartbeat.json`.
- **Overwrite guard (`dispatch_unit`).** An adapter-independent refusal (fires before any worker runs) to re-author a
  **settled** cell (maturity ∈ `validated`/`operating`) unless the transition is a deliberate un-ship
  (→`regenerating`) or the operating promotion. So pointing the autonomous loop at a real product can never stub a
  hand-authored `index.html` over the shipped one (and the lease-reaper re-activation of a validated ticket is no
  longer a re-clobber path); the ticket blocks and surfaces to the operator.

**Council fixes (harness-council red-team — reward-hacking · autonomy-trajectory · budget-cost):**

- **Autonomy (CRITICAL):** the live loop now dispatches at `app._dispatch_tier()` = `min(posture_tier,
  autonomy.tier_for(d))` — posture is a **CEILING, never a floor**. An operator (or a stale posture) can run BELOW the
  ledger-earned tier but never above it, so an *unmeasured* family can't be driven lights-out by setting posture
  tier 2, and a mechanical demotion re-clamps the very next tick. The earned-autonomy ladder stays load-bearing on the
  live server, not only in the evals.
- **Budget (CRITICAL):** the triage dispatch's `cost_usd`/`tokens` are now ledgered on a metrics-bearing event so the
  window's token/dollar ceiling sees them (the H5-C1 uncounted-spend leak). Same fix applied to the `author_refuters`
  per-tick dispatch (same class).
- **Reward-hacking (hardening):** a stale/planted `coordination/triage/<tid>.json` is cleared before each triage
  dispatch (only THIS dispatch's write is ever applied — closes the cross-ticket laundering vector); `TRIAGE_AUTHOR`
  denies the product barrel `*/index.mjs` like its sibling producers.

Requires `dev-kernel` 0.2.26 (the `TRIAGE_AUTHOR` gate boundary + the `triage-attempt` ledger event). New selftest
coverage in `dispatch`/`heartbeat`/`app`/`_gates`; the earned-autonomy + walk-milestone replays stay green.

## 2026-06-21 — the bootable-shell invariant: a drained app with no shell reads INCOMPLETE, not done

Follow-on to the mock-shell fix, after the same demo showed a deeper gap: a decomposition can silently OMIT the
bootable shell, and the factory still called the app "drained" (done) even though nothing boots. New
`api.app_completeness(d, kit_dir)` mechanizes the invariant — KIT-AWARE (only an instance whose kit declares a
single-file shell authoring needs one): a shell-declaring instance that built capability modules but has no validated
`capability.system.shell` (and no `index.html` at the product root) is `bootable: false`, and `factory_state` reads
**`incomplete`** instead of `drained`. So the missing entry is a tracked, surfaced gap, not a buried Preview-tab note.
Paired with the `lattice-management` skill mandate (dev-kernel 0.2.25). Selftested in `api.selftest`.

## 2026-06-21 — fix: the mock shell imports a REAL built sibling, not a hardcoded `./core/`

Surfaced building a demo app whose modules weren't named `core`: the MockAdapter's single-file (shell) author
hardcoded `import './core/index.mjs'`, so a mock shell build over any other decomposition (e.g.
`osc-303`/`viz-renderer`/…) emitted an import that doesn't resolve — which the static app-shell + render-coherence
gates correctly REFUSE, leaving a "built" instance with no bootable entry. The mock shell now scans the product
root for the first built sibling module (a dir with an `index.mjs`) and imports THAT; it falls back to a
self-contained mount only when no module is built yet. Regression-guarded in the dispatch selftest (a shell over an
`engine` module must import `./engine/`, never `./core/`). dev-server only — no kernel change, no version bump.

## 2026-06-21 — FULL autonomous Tier 2: the gate-agnostic independence proof (harness-council round 7)

The refute-author's provenance gate (round 6) let an autonomous oracle MEASURE but not self-promote — full autonomy
waited on a way to TRUST an auto-authored oracle without a human. `_mutation_independent` is that proof, and it is
gate-AGNOSTIC: an autonomous oracle is `mutation_verified` → TRUSTED (earns unattended Tier 2 hands-off) iff it catches
a gate-PASSING defect the gate misses — there exists a server-generated text-mutant `M'` of the real module where the
gate `G(M')` PASSES but the refuter `R(M')` FAILS. It RUNS the real gate (never parses it), so it works on the opaque
data-driven/negative-form gates the static `independent_of_gate` arm cannot inspect (eval H9 vs H7). `produce_refuter`
stamps `mutation_verified`; `run_refuter` propagates it; `ledger.trusted_refuter_checks` counts it.

The council (reward-hacking · verifier-integrity) red-teamed it:

- **Forge-resistant** — `G` and `R` run STDIN-piped, so the worker's module can't read the harness source to tell them
  apart and selectively fake a witness; it can only suppress one (fail-safe).
- **The DECOY forge, closed** (round-7 CRITICAL): a worker planted a non-spec export `_k=()=>7` the gate ignores + a
  refute `_k()===7`; a `7`→`8` mutant faked a witness off the dead export. `_gate_scoped_refute` confines the proof to
  the gate's CONTRACT surface (refute assertions calling only gate-declared exports / JS globals). Proven by eval H10.
- **Honest bar + double-bound trust**: a witness proves INDEPENDENCE (not a gate-copy) — stronger than the bare human
  path, but NOT exhaustive adversarial competence (no static check can, for an opaque gate). It is double-bound by the
  live `run_refuter` re-check: a weak/false oracle that fails the REAL module self-incidents → demotion. The
  "full autonomy proven" language was toned to "independence-proven."

This completes task #23 — `/loop`-driven lights-out is now reachable hands-off for an oracle that proves its
independence, with the human glance still required for the unprovable (tight-arithmetic) case. dev-kernel 0.2.23 → 0.2.24.

## 2026-06-20 — the REFUTE-AUTHOR (autonomous Tier-2 producer) + the human-glance gate (harness-council round 6)

The missing PRODUCER for earned autonomy: until now the behavioral refute set (the false-pass oracle) was
hand-authored, so a cell stayed honestly `unmeasured` (Tier 1) until a human wrote one — Tier 2 was earnable but not
*autonomously*. This adds a gate-blind **refute-author** (`author_refuter` / `author_refuters`, a rubric-architect
role wired `--allow-refute`) that authors a cell's `refute` set from the spec; the server's three-proof calibration
(`is_behavioral` · `_refuter_discriminates` · `independent_of_gate`) decides `measuring`; `produce_refuter` UPGRADES a
liveness floor to measuring (the producer's landing point) and stamps PROVENANCE. Wired into the heartbeat
(headless-only, one per tick, budget-bounded). `verify_gen.independent_of_gate` closes the gate-COPY hole using the
**server-read gate source**, not the worker-writable `acceptance` field.

The harness-council (reward-hacking · autonomy-trajectory · verifier-integrity · scoreboard-independence) red-teamed
it and found the autonomous-Tier-2-for-lights-out claim unsafe: the calibration is partial for opaque
data-driven/negative-form gates, and the loop could self-promote on a fake measurement. **Fixes (round 6):**

- **The human-glance gate, in code (not prose).** An autonomously-authored oracle is stamped `autonomous: true` (a
  server-owned, worker-protected registry `run/autonomous-oracles.json` + the refuter sidecar); `tier_for` grants
  unattended Tier 2 only with a TRUSTED (non-autonomous) check. The autonomous oracle MEASURES (builds the visible
  rate + a track record) but cannot SELF-PROMOTE; a human-vetted oracle is the trusted check that lifts the family.
- **The cross-cell LAUNDERING close.** Provenance follows the WRITE, not the nominal target: `author_refuters` diffs
  the verify-spec dir before/after each dispatch and registers every cell the worker actually authored — so a
  dispatch targeting X cannot launder a machine-authored oracle onto a sibling Y to dodge the gate.
- The mock refute-author is an honest no-op; full *autonomous* Tier 2 awaits a gate-agnostic independence proof
  (deferred — see `docs/2026-06-20-refuter-author-autonomous-tier2.md` + `…-council.md`). Eval `earned-autonomy`
  H6/H7/H8 prove the gate-copy rejection, the human-glance gate, and the laundering close. dev-kernel 0.2.22 → 0.2.23.

## 2026-06-20 — harness-council RE-AUDIT round 5 (round 14): the in-process forge is CLOSED; fix the fail-open default

The fifth verification CONFIRMED the keystone goal: a worker who authors `index.mjs` cannot forge the measurement —
every in-process nonce channel (fd0, /proc/self/fd/0, import.meta, Error().stack, execArgv, ps) and every emission
trick (exit-override, uncaughtException, process.on('exit'), prototype-pollution) is closed, and the two-poison
discriminator is un-tautology-able over strict `===`. The four prior rounds of module-facing hardening are complete.

The one remaining hole was OUTSIDE the module: `run_refuter` read `sdata.get("measuring", True)` — a keyless sidecar
defaulted to MEASURING, so a trivially-passing sidecar minted a measured 0.0 → auto-Tier-2, guarded only by the
worker-deny glob *when the gate is wired*. Fixed:

- **The `measuring` default is now `False` (fail-safe, wiring-independent).** A check earns the false-pass denominator
  ONLY if its sidecar EXPLICITLY declares `measuring: true` — which the server's `produce_refuter`/`self_heal_cell`
  set ONLY after the two-poison calibration passes. A keyless sidecar is liveness-only by construction.
  `evals/earned-autonomy` H5 proves a keyless trivially-passing sidecar agrees yet is recorded `measuring=False`.
- `evals/debug-coldstart` stamps its (real, behavioral) hand-seeded refute `measuring: true` explicitly; the H4 forge
  sweep gained the four un-executed classes (stack-scrape, exit-handler, prototype-pollution vs. the acceptance loop).

After five independent council verifications the keystone false-pass measurement is unforgeable by a worker-authored
module AND fail-safe by default. (Residual, accepted: on a fully-unwired instance with no per-dispatch gating an
explicit `measuring: true` sidecar could be dropped — the per-dispatch worktree gate is the protection.)

## 2026-06-20 — harness-council RE-AUDIT round 4 (round 13): the nonce leaves the process entirely

The round-3 `node -e` nonce was readable in-process via `process.execArgv[2]` / `/proc/self/cmdline` / `ps` — the
secret had only moved from a file to the command line. The structural close (the secret is never where the imported
module can reach it):

- **`run_refuter` pipes the harness over STDIN (`node -`), not argv/`-e`,** so the nonce-bearing program is in NONE of
  `process.argv`, `process.execArgv`, `/proc/self/cmdline`, or `ps` — the worker-authored module cannot READ it.
- **Failures THROW (not `process.exit(1)`),** so a module that overrides `process.exit` or handles
  `uncaughtException` cannot fall through to the success line that emits the nonce — a thrown failure never reaches it.
  `earned-autonomy` H4 now sweeps EVERY channel (execArgv · argv · /proc · ps · exit-override · uncaughtException ·
  print-`pass`) and proves all are caught.
- **`_refuter_discriminates` calibrates against TWO typed poisons (a number AND a string),** closing the type-coercion
  annihilator class (`compute(1)*0===0` held over numbers but `NaN`s a string, so a single string poison leaked it).
- The self-heal re-arm now AND-gates `_refuter_discriminates` (matching the live producer); `record_incident`
  un-ships verifier-bound dependents too (dev-kernel 0.2.22).

The keystone measurement — the `measuring: True` refuter agreement the autonomy ladder consumes — is now unforgeable
by a worker-authored `index.mjs`: it can neither read the nonce (not in-process) nor make the harness emit it without
the discriminating checks genuinely passing (throw-on-failure), and a vacuous refute set fails the typed calibration.

## 2026-06-20 — harness-council RE-AUDIT round 3 (round 12): the nonce was readable off disk; is_behavioral leaked

A THIRD council verification caught two more measurement forges (and three structural majors). The keystone fixes:

- **`run_refuter` runs the harness via `node -e`, not a temp FILE.** The round-2 nonce was injected into a harness
  FILE, so the graded module (which runs in-process at import, before the checks) could `readFileSync(process.argv[1])`
  and grep the cleartext nonce. With `-e` there is no harness file: `process.argv[1]` is undefined, the source is not
  on disk, and the nonce is not in env — the module cannot obtain it. `earned-autonomy` H4 now uses the exact
  read-off-disk forge.
- **`produce_refuter` CALIBRATES a refute set (a positive can-disagree proof), not just `is_behavioral`.** A 2-form
  syntactic denylist leaked 5/5 vacuous-but-invoking refuters (`compute(1)===compute(1)`, `[compute(1)].length===1`,
  `compute(1),true`, …). `dispatch._refuter_discriminates` runs the refute harness against a deterministic POISON
  stub; only a refute set that DISAGREES with the deliberately-wrong module earns `measuring`. Fail-safe (a vacuous
  set, or any error, → non-measuring → the cell stays `unmeasured`/Tier 1).
- Paired with the kernel's N1 (scope-keyed LAYER_DEPS at dispatch) + N2 (transitive un-ship on an incident), dev-kernel
  0.2.21. Noted residuals (deeper/vendored): the base gate (`validate.py`) still trusts exit status — the hardened
  refuter is the backstop; true in-process module isolation would need a `vm`/sandbox; the operator `lattice stale`
  CLI is one-hop (vendored), with `lattice-health` as the backstop.

## 2026-06-20 — harness-council RE-AUDIT round 2 (round 11): the measurement was forgeable three more ways

A SECOND council verification caught the first re-audit short — the producer path was honest but the measurement
was still forgeable. All fixed (see `docs/2026-06-20-harness-council-reaudit.md` § Round 2; kernel side in dev-kernel
0.2.20):

- **`run_refuter` agree now requires an unforgeable per-run NONCE**, not a `pass:` substring. A module that prints
  `pass` and `process.exit(0)`s on import forged the old sentinel; the nonce is printed only at the harness's own
  success exit, which an import-time short-circuit never reaches, and the module cannot know it. `earned-autonomy` H4
  uses the exact `print('pass')+exit` forge.
- **`verify_gen.is_behavioral` rejects value-free invocations** (`compute(1)===compute(1)` determinism tautologies,
  `typeof compute(0)` shape-probes) — invoking an export is necessary but not sufficient to MEASURE; the assertion
  must be able to disagree. Over-rejection is fail-safe (toward `unmeasured`).
- **`heartbeat.arm()` guards on FALSY, not `is None`** — `arm(deadline_s=0)` (a zero ceiling) no longer mints an
  unbounded window; it gets the safety deadline.
- **`dispatch.self_heal_cell` un-ships TRANSITIVELY** — it drives the kernel's one-hop `propagate_staleness` to a
  fixpoint, so a grandchild integrator (`core ← ui ← shell`) can't survive stale-but-trusted. `self-heal` H4b proves it.
- The simulation callers of `record_refuter_check` (tests/demo/evals) opt into `measuring=True` explicitly; the
  heartbeat tier-2 dispatch test uses an explicit `tier=2` override instead of minting a check (counting-default hole).

## 2026-06-20 — harness-council RE-AUDIT (round 10): the refuter is isolated from the module it grades (H3)

- **`run_refuter` no longer runs in the worker's own dir, and exit 0 alone is no longer agreement.** It used to write
  `.refute.mjs` INTO the cell's product dir and `node`-run it there — so the graded module could shadow the refuter's
  node environment, and a module that `process.exit(0)`s on import would make the refuter exit 0 (the checks never
  run) and "agree." Now the refuter runs in a TEMP dir the worker can't control, imports the module by an absolute
  `file://` URL (the module's own relative deps still resolve from its real dir), and AGREE requires the
  `gen_cap_verify` harness's `pass:` sentinel in stdout — so an import-time short-circuit reads as a non-agreement.
  `evals/earned-autonomy` H4 proves a `process.exit(0)`-on-import module fools the exit-code gate but is caught by the
  refuter. (Residual: the gate itself — run by the vendored `validate.py` — still trusts exit status; the refuter is
  now the backstop that catches a gate-gaming import-time exit.)

## 2026-06-20 — harness-council RE-AUDIT (round 9): an armed window is never unbounded (H5)

- **`arm()` stamps a safety wall-clock deadline (`DEFAULT_WINDOW_DEADLINE_S`, 2h) when the operator sets NONE of the
  four ceilings.** The re-audit found `app.py` defaulted all of deadline / max-dispatches / token / dollar to `None`,
  so an armed run was bounded only by the per-dispatch `$10` cap × an unbounded number of cells and retries. Now an
  armed-but-uncapped window can't exist — an explicit ceiling overrides the safety deadline. (Paired with the kernel's
  `ledger.no_progress` signature normalization, dev-kernel 0.2.18, so a stuck cell can't burn retries on path/exit
  variance either.)

## 2026-06-20 — harness-council RE-AUDIT (round 8): the Tier-2 measurement was hollow — now it isn't (keystone)

A verification re-audit caught the round-3 H6 "fix" as hollow, and it was right. The live producer armed
`verify_gen.fresh_refute`'s generic invariants as the refuter — but they are TAUTOLOGIES (`typeof e === 'function'`,
`x === x`), so no gate-passing module can fail them: `false_pass` was pinned at `0.0` and Tier 2 auto-granted again,
the `agreed=True` fake wearing a `node` subprocess. The `earned-autonomy` eval only "proved" the catch by
hand-overwriting the sidecar. Corrected:

- **A refuter only MEASURES if it exercises behavior.** `verify_gen.is_behavioral` distinguishes an assertion that
  INVOKES an export (`compute(7,8)===15`) from a presence/self-stability probe. `produce_refuter` now arms a
  MEASURING refuter only from a BEHAVIORAL refute set (planner/operator-authored, in the verify-spec); absent one it
  arms `fresh_refute`'s generic floor as a NON-measuring **liveness** check (it still catches a module that throws on
  load, but it cannot disagree, so it must not mint a measurement). `run_refuter` records `metrics.measuring`;
  `ledger.refuter_checks` counts only measuring checks (dev-kernel 0.2.17); `self_heal_cell`'s generic re-arm is
  marked non-measuring too.
- **The honest consequence:** a cell with no behavioral refute set stays `unmeasured` → Tier 1. Tier 2 now requires a
  real independent oracle (a behavioral refute set), not a tautology. Auto-producing that oracle on a headless build
  (a refuter-author) is the tracked next step; until then Tier 2 is earnable only with an operator-authored refute set.
- **`evals/earned-autonomy` rewritten** to prove it the honest way: the generic floor stays unmeasured (Tier 1); a
  behavioral refuter earns Tier 2 on a conformant module; and the SAME producer-armed refuter CATCHES an overfit that
  genuinely passes its gate (`run_validation` advances it) — disagreeing with NO hand-overwrite.

## 2026-06-20 — harness-council audit fixes (round 7): the signal-forge floor is now absolute (H3-C1 residual)

- **NO headless worker carries `Bash` anymore.** Round 2 dropped it from the module worker but kept it for the
  verifier-author (rubric-architect) to self-calibrate the harness it writes. That was the last inline-interpreter
  forge surface (`python3 -c open('…/signals/…','w')` past the gate's redirect heuristic). It is now gone: the
  verifier-author authors `verify.mjs` Write-only and its calibration is the downstream loop — the module is built
  against the gate and a broken gate fails validation → re-author (`_verifier_prompt` already authored blind, "the
  module may not exist yet"). Every headless worker is now Write-only over a deny-list that blocks signals, the
  ledger, the lattice, and the product barrel — zero forge surface. A `team` plan still adds `Task` (the one
  capability that can't forge state). Selftest asserts the no-Bash invariant across module · verifier · team units.

## 2026-06-20 — harness-council audit fixes (round 5): the frontier never silently starves (H1)

- **The heartbeat now NAMES a dependency cycle (H1).** A `depends_on` cycle leaves its cells un-advanceable forever
  (each waits on another around the loop, so every dispatch is refused by the partial-order gate) — and the loop
  used to just spin with no event saying why. `on_tick` now calls `compass.surface_cycle` whenever non-terminal
  work exists: a cycle is detected (`compass.detect_cycle`, dev-kernel 0.2.16) and ledgered ONCE so the operator /
  `dependency-arbiter` sees the loop to break. The tick summary carries `cycle`. (The detector lives in `compass.py`
  exactly as the `dependency-arbiter`/`decomposition` contracts always claimed — now true.)

## 2026-06-20 — harness-council audit fixes (round 4): budget realism (H5)

The token ceiling read success-path telemetry only, headless was dollar-uncapped by default, and the shipped
signature-based no-progress detector was never wired — so the run budget was softer than it looked on a real build.

- **Failure-path spend now counts (H5-C1).** A worker run that produced no artifact still spent tokens/dollars, but
  its `activity-fail` recorded no metrics — so a failure-then-retry burned spend the ceiling never saw. The
  worker-failure `activity-fail` now carries the adapter's `cost_usd`/`tokens`, which `_tokens_since`/`_cost_since`
  sum. (The verifier-author spend was already fixed in round 1.)
- **A window DOLLAR ceiling + a per-dispatch default cap (H5-C3).** `arm` gains `dollar_ceiling`
  (`DEV_FACTORY_DOLLAR_CEILING`); `budget_exhausted` halts the window when `_cost_since` crosses it (alongside the
  deadline / max-dispatches / token ceiling). And every headless dispatch now ALWAYS passes `--max-budget-usd` —
  the ticket's `dollars` if set, else `DEV_FACTORY_DISPATCH_USD` (default $10) — so a single run is never unbounded
  (previously the cap was appended only when a ticket set `dollars`, which the default budget never did).
- **The no-progress signature detector is WIRED (H5-major).** `dispatch_unit` now calls the (now-fixed)
  `ledger.no_progress` (`n=2`): two identical failure signatures block a deterministically-stuck cell early, while
  distinct failures still retry to the attempt cap. A new selftest distinguishes the two backstops.

## 2026-06-20 — harness-council audit fixes (round 3): the LIVE refuter producer (H6 — earned autonomy)

The H6 cap's root: nothing in the dev-server validation path PRODUCED the refuter sidecars the false-pass oracle
(`refute_frontier` → `run_refuter`) consumes — only `self_heal_cell` re-armed one post-incident, and eval fixtures
hand-seeded them. So `false_pass` stayed `unmeasured` forever, the app family could never legitimately reach Tier 2
(`autonomy.tier_for`), and the only in-tree paths to Tier 2 asserted `record_refuter_check(agreed=True)`.

- **`dispatch.produce_refuter` / `produce_refuters` — the live producer.** When a CODE cell reaches `validated`, the
  server recovers its exports from its `verify.mjs` (`_exports_from_verify`) and arms an INDEPENDENT refuter — a
  `verify_gen.fresh_refute` oracle (generic invariants: export stability + determinism) distinct from the gate the
  worker coded to — plus the verify-spec. The heartbeat runs `produce_refuters` each tick (a sweep) BEFORE the
  refuter frontier, so a cell validated this epoch (Tier 1 human-accepted OR Tier 2 auto) is measurable next tick.
  Idempotent + non-clobbering (a self-heal-re-armed or planner oracle is never overwritten); only multi-file code
  cells with a real `verify.mjs` get one — a presence-stub-validated cell stays honestly unmeasured. **This makes
  the verify-spec genuinely persist in `dev-server` (not just `debug/` ralph) — the prior CHANGELOG claim is now
  backed by code.**
- **`evals/earned-autonomy` — the affirmative proof.** A validated code cell is UNMEASURED (Tier 1 even with a
  budget); the producer arms a real oracle; `run_refuter` MEASURES it → `false_pass` 0.0 → **Tier 2 EARNED**, with no
  `record_refuter_check` fake; a disagreeing oracle mechanically REVOKES it. Wired into `dev-factory.yml`.
- The remaining `record_refuter_check(agreed=True)` calls (heartbeat selftest, `demo.py`) are now clearly labeled
  as **node-free unit/doc-domain simulations** of what the live code path earns for real — not production shortcuts.

## 2026-06-19 — harness-council audit fixes (round 2): the integrity floor on the LIVE path

Round 1 fixed the two unambiguous bugs; round 2 hardens the verification floor the audit found "mock-deep" on the
headless path (the caps fired on H2 verifier-integrity · H3 reward-hacking).

- **The live module worker no longer carries `Bash` (H3-C1, the highest-severity finding).** The headless adapter
  granted `Read,Edit,Write,Bash,Glob,Grep` to EVERY role — but the gate's signal-forge floor explicitly rests on
  the forging worker having no Bash (`_gates._BASH_WRITE_VERBS` deliberately ignores inline interpreters like
  `python3 -c open(…,'w')` to avoid false-denying the validator's reads). So the live worker could forge a signal
  past the gate the gate's own comment assumed it couldn't. `_allowed_tools` is now ROLE-AWARE: the product-authoring
  worker (cell-advancer) gets NO Bash (matching the canonical actor); Bash is granted back ONLY to the verifier-author
  (rubric-architect, which must calibrate the harness it writes, authors the GATE not the product, and runs before the
  module exists). A `team` plan still adds Task.
- **`_is_mock_verifier` discriminates by BEHAVIOR, not line count (H2-M2).** The old `import { ready }` + `<6 lines`
  heuristic missed the MockAdapter's own `import * as m` smoke stub (so a mock build's gate posed as 'real' on the next
  headless run) and waved through any long-but-vacuous harness. Now: an explicit `dev-factory:mock-verifier` sentinel
  (stamped on every seed/mock-authored stub) OR a behavioral test — a real harness CALLS a module export
  (`m.compute(…)`); a presence stub only READS `m.ready`, so it never matches. Length-independent.
- **A CI eval that runs a REAL verifier (H2-M1) — `evals/real-verifier-teeth`.** CI's adapter is always the
  MockAdapter, so green only ever proved the mock loop closes on itself. The new eval drives a real spec-conformance
  `verify.mjs` through the kernel's actual validation path and proves it REFUSES a deviating module, PASSES a
  conformant one, and that the presence stub it replaces is blind to the same deviation. Green now means "a gate with
  teeth caught a real deviation," not "the mock loop closed." (Wired into `dev-factory.yml`.)
- See `dev-kernel` 0.2.14 for the paired permit-barrel fix (`VERIFIER_AUTHOR` now also denies `*/index.mjs`, H3-C2).

## 2026-06-19 — harness-council audit fixes (round 1): the false-pass oracle path + verifier-author spend

An independent harness-council review of the app-build campaign's changes surfaced these (top of a larger backlog):

- **`run_refuter` now resolves the cell dir by `asset_ref`/`output_root`, not the naive `.factory/{layer}/{slug}/`** — the single most-corroborated finding (H2 · H6 · H7 convergence). The independent false-pass oracle ran in `.factory/capability/{slug}/` (no `index.mjs`) for any app-kit cell whose code is rooted OUT to the product tree (`src/{project}/{slug}/`) — so it silently no-op'd or manufactured a spurious incident, and since `false_pass_rate` is what the autonomy trajectory consumes, **the app family could never legitimately measure its way to Tier 2.** Now mirrors `self_heal_cell` (the sibling that already did it right). self-heal/demotion/fly evals stay green.
- **The auto verifier-author pass now attaches its spend metrics**, so it counts against the run's token ceiling (`_tokens_since` sums `metrics.tokens` from any event) — previously the rubric-architect dispatch burned tokens the budget never saw (budget-cost C2).

## 2026-06-19 — the verifier-author pass is the DEFAULT for real builds (no operator pre-step)

- **`dispatch_unit` now authors a cell's real verifier automatically, before the module builds — on real (headless) builds only.** When the adapter is headless, the target is a capability MODULE (multi-file), the transition is signal-bearing, and the per-cell `verify.mjs` is still a mock `ready` stub (`_is_mock_verifier`), the rubric-architect authors the real, spec-derived harness FIRST (in a gate-permitted worktree), then the module worker builds against it. So every real build grades its modules against a real contract with zero operator action — closing #2's last gap (it was a deliberate `author_app_verifiers` pre-step; now it's the default). **Mock builds (CI/Crawl) skip it** (the adapter isn't headless), so the eval suite is unaffected; the run's token ceiling bounds the extra spend; a non-stub/hand-authored verifier is left untouched. `dispatch.selftest` (incl. `_is_mock_verifier`) + integration/crawl/walk/tier1/render/server-smoke evals green.

## 2026-06-19 — the verifier-author handles DOM cells (it was punting on them)

- **`_verifier_prompt` now guides DOM-cell verifier authoring.** Extending real verifiers from pure-logic cells (`core`, `persistence`) to `ui` exposed a gap: pointed at a DOM module (`renderGallery`/`renderControls`/`renderPreview`, which take a root element), the rubric-architect **punted — it left the mock `ready` check** (Node has no DOM, and the prompt didn't say how to test one). The prompt now instructs: if the module renders to the DOM, author a minimal shim at the top of `verify.mjs` (`globalThis.document` with a `createElement` that returns a RECORDING element tracking `appendChild`/`textContent`/`innerHTML`/`addEventListener`, plus `getElementById`/`querySelector`), then CALL each render function with a mock root + its callbacks and assert it actually mounted content and wired its handlers — explicitly NOT a bare `ready` check. Surfaced by the breadth frontier; `dispatch.selftest` green.

## 2026-06-18 — the verifier-author PASS: `author_app_verifiers` (run before the modules build)

- **`author_app_verifiers(d, slugs, adapter)` runs the rubric-architect over every listed capability cell's `verify.mjs` BEFORE the modules build** — each in its own provisioned, gate-permitted worktree. After the pass, every cell is graded against a real, spec-derived gate, so a module deviating from its spec'd contract is REFUSED, not rubber-stamped. This is the build-orchestration step that wires factory-authored verifiers into a build (`#2`). `dispatch.selftest` covers it (the pass authors a harness for each listed cell).

## 2026-06-18 — the verifier-author worktree permit (closing the #2 loop)

- **A `kind == "verifier"` dispatch wires `gate-verifier --allow-verify`, so a headless rubric-architect can author the cell's `verify.mjs`.** `wire_gates` gains `allow_verify`; the headless adapter passes `allow_verify=(unit.kind == "verifier")`. The verifier-author may write the harness it authors (it IS the gate), while signals/lattice/ledger/rubric stay denied — the module worker is still wired without the flag, so the generator/critic split holds. Proven end-to-end: a real `claude -p` verifier-author writes a spec-conformance `verify.mjs` under the permit. Pairs with dev-kernel 0.2.13 (`gate-verifier --allow-verify`).

## 2026-06-18 — factory-authored verifiers (#2) + prompt refactor (remove the obsolete integrator branch)

- **The factory can author a cell's REAL critic harness, closing the presence-predicate-verifier weakness.** Per-cell `verify.mjs` were mock (`ready === true`) — so `validated` meant "exports `ready`," not "implements the spec"; the build campaign showed modules were good only because the *worker* followed the spec, never because the *critic* checked. New: a **verifier-authoring** dispatch (`unit.kind == "verifier"`) — `HeadlessClaudeAdapter._verifier_prompt` tasks the **rubric-architect** with a real spec-conformance `verify.mjs` *from the spec* (`import * as m from './index.mjs'`; assert the named exports exist + produce correct results; explicitly NOT a `ready` check); the MockAdapter writes a deterministic smoke check; `author_verifier(d, cell, adapter)` runs it before the module builds, so the worker is graded against a real gate the worker stays gate-denied from writing. (The autonomous-loop integration + the headless verifier-author worktree gate-permit are the remaining wiring; the mechanism + prompt land here.)
- **Prompt refactor — removed the obsolete `is_integrator` branch (a campaign-learned cleanup).** After the shell-authoring fix, integration is the single-file SHELL cell — but the multi-file capability prompt still told *any* module depending on another capability (e.g. `ui → core`) to author `index.html` + `main.mjs` + `mount(root)`, the whole assembly, conflicting with the modular lattice. Removed: a capability MODULE is just a module; the shell assembles. `dispatch.selftest` gains verifier-prompt, integrator-removal, and `author_verifier` cases; integration/tier1/render/server-smoke/crawl/walk evals stay green.

## 2026-06-18 — dispatch authors the integration shell at the product root (single-file authoring)

- **`dispatch` supports single-file-at-root authoring, so the factory can author the integration shell.** A live design-tokens-lab build reproduced the shell-authoring gap: capability authoring routes every cell to `../{slug}/`, but a shell's `index.html` belongs at the product root — the worker had no path and the ticket blocked. `_authoring_for` gains slug-specificity (a `{slug: "shell"}` entry wins over the layer-default); `_asset_rel` resolves `mode: "single-file"` to `<output_root>/<entry>` (`../index.html`); the headless `_prompt` gives the shell a **bootstrap prompt** — "the modules are ALREADY BUILT as sibling cells; import + mount them at the root" — instead of the legacy `is_integrator` whole-assembly prompt that conflicted with the modular lattice; MockAdapter authors a minimal valid bootstrap; the asset-recording checks the entry FILE. Pairs with dev-kit-app 0.5.1 (the kit's shell authoring entry). New `dispatch.selftest` single-file-shell case; multi-file path unchanged.

- **Picking another project in the header selector now re-points the running server at that instance** — `POST /api/project {project}` reassigns the active `DIR` to `src/<name>/.factory`, re-projects the store, and the board reloads against it. Everything (api · store · heartbeat) already read `DIR` dynamically and open the index per call, so a re-projection is all it takes — the previously-promised "drop-in switcher" is now wired. Replaces the old "Switching isn't wired yet — point `DEV_FACTORY_DIR` and restart" toast.
- **Guarded**: the switch refuses while a worker is running (`409` — switching mid-build would orphan the lease), rejects a name that escapes `src/` (path-traversal `404`), and **lands the new project PAUSED** so a switched-to instance never auto-dispatches — each project carries its own run budget under its `.factory/run/`, armed/resumed deliberately. UI cache-bust v17→v18; `app.py selftest` + `server-smoke` green.

- **`reconcile_leases` no longer reaps a completed, critic-validated `in-review` ticket back to `active`.** The Tier-1 success path parks a cell at `in-review` for the operator's sign-off, but it left the worker's `lease_expiry` set — so 15 min later (`LEASE_TTL_S`) the lease reaper declared the (long-finished) worker "presumed dead" and bounced the validated work to `active`, destroying the sign-off-pending state and, at Tier 2+, inviting a re-author + re-spend. Fix: **clear the lease at the clean in-review hand-off** in `dispatch_unit` — a stale lease must never outlive the worker that held it. The reaper already keys off a still-present `lease_expiry` (`if not exp: continue`), so this makes the lease the discriminator: a cleanly-validated `in-review` ticket (lease cleared) is skipped — a pending human approval is not a dead worker — while a genuinely crashed-mid-dispatch ticket (lease still set) is still re-queued. Surfaced by the live shader-sliders build, whose Tier-1 gate parked `capability.system.ui` at `in-review`; the reaper returned it to `active` 14 min after it was built + validated.
- **Regression in `dispatch.selftest`** — a Tier-1 gated dispatch (`auto_validate=False`) reaches `in-review` with its claim cleared, and `reconcile_leases` then leaves it in `in-review` instead of reaping it (the prior expired-lease-reclaims-a-`claimed`-ticket case stays green, proving genuine crash recovery is unaffected).

## 2026-06-18 — create/triage modal: cell fields become lattice-populated menus

- **The `Target cell` and `Acceptance rubric cell` fields are now `<select>` menus, not free text.** A user can't be expected to type a legal `layer.scope.slug` from memory, so the two cell-addressed fields are populated from the live lattice (`store.lattice.peek()` — snapshotted on open, so a lattice poll can't wipe a half-filled form). **Target cell** is grouped by layer (`<optgroup>`) with each cell's current maturity shown as a suffix; **Acceptance rubric cell** is filtered to `rubric`-layer cells that are `validated`/`operating` — the same constraint `gate_ticket_ready` enforces, surfaced at *selection* time instead of as a post-submit rejection. When no rubric qualifies, the menu shows a disabled option that says *why* (validate a rubric first) rather than going silently blank.
- **Picking a target cell auto-fills `From maturity`** to that cell's current state (the gate requires `from == the cell's maturity`); still overridable. `name="target_cell"`/`name="rubric"` are preserved, so `#submit` and `#whyNotReady` are unchanged. DOM-shim load + `cellOptions` logic selftests green; cache-bust v16→v17.

## 2026-06-18 — per-card Triage: bind an untriaged intake from the board

- **A `Triage →` button on untriaged intake cards (prompt/issue).** The dashboard let you create a Prompt but gave no way to advance it — a prompt is *untriaged intake* (it parks for the cold-start planner), can't be dragged to Active, and had no triage affordance, so a hand-made prompt was a dead end. Now a draft prompt/issue card shows **Triage →**, which opens the binding form (target cell + from/to + a validated rubric, with the same inline readiness check as create), calls `POST /api/issues/{id}/triage`, and the card becomes a structured ticket draggable to Active.
- **`triage_issue` broadened to accept any untriaged intake** (`issue` / `prompt` / `instruction`), not just `issue` — so an operator can hand-bind a prompt (the cold-start planner stays the automated path). api/app/server-smoke selftests + the headless UI load green; cache-bust v14→v15.
- **Intake-card layout (review-driven).** The card now reads in two beats: one muted meta row (chip · cell · **id demoted to the right**) and a **divided action slot** for the button. Most importantly, **untriaged cards are non-draggable** (`draggable=false`, no keyboard move, no move-hint, a Triage-pointing aria-label) — removing the dead-end "drag me" gesture so the Triage button is the *only* forward path (affordance honesty). cache-bust v15→v16.

## 2026-06-18 — UX: inline readiness check on the create-ticket modal (no stuck draft + late 409)

- **The structured create form pre-validates against `gate_ticket_ready` and shows the reason inline.** A structured ticket dropped on a non-draft column requests `→ active`, which the readiness gate rejects when a binding is incomplete — most often a `rubric_cell` that isn't `validated` yet (the form makes every binding optional). That used to surface as a *stuck draft + a late 409 toast*. The modal now mirrors the gate (`#whyNotReady`): the target cell exists in the lattice, both maturities are set, and the acceptance rubric cell is `validated` — failing with a specific inline message and creating nothing. (Also: UI cache-bust v12→v13; fixed a stale `.agents/dev-factory` path in the file:// nudge.)

## 2026-06-18 — `_kit_verifier` gains slug-specificity (binds the app-shell coherence gate)

- **A kit validation adapter can now target `{layer, slug}`, not just `{layer}`.** In `dispatch._kit_verifier`, a slug-specific adapter wins over the layer-default, regardless of list order — backward-compatible (the generic `capability-harness` still grades every other capability; `integration-milestone` stays green). This lets the app family bind a `capability.*.shell` cell to its **app-shell coherence gate** (dev-kit-app 0.3.2) — the integration check the headless `verify.mjs` model lacked, which distinguishes an assembled runnable app from built-but-unassembled modules (a re-export barrel). New `evals/app-shell-gate/` (A1–A4); CI-wired; full suite (11) green.

## 2026-06-18 — opt-in: Tier-1 STRICT acceptance gating (downstream waits for your sign-off)

- **`DEV_FACTORY_TIER1_STRICT=1` makes Tier 1 wait for human ACCEPTANCE cell-by-cell.** By default Tier 1 flows on critic-validation (the build advances; tickets park at `in-review` for async acceptance). With the flag set, a dependent is held until its dependency cells are *accepted* (their tickets `done`), not merely *validated* — so the build advances behind the operator's sign-off. Implemented as a SERVER policy (`heartbeat.strict_accept_filter`, applied in `on_tick` when the flag is set and `tier < 2`) layered on the kernel's partial order — the kernel still only requires deps `validated`; moot at Tier 2+ (auto-accept). Default behavior unchanged. Proven by `evals/tier1-strict-gate/` (S1–S4, both modes). Threaded `app.py` → `on_tick(strict_accept=…)`.

## 2026-06-18 — observability: `in-review` is not a running worker (the "busy-but-stuck" fix)

- **`agents_running` now counts only ACTUALLY-EXECUTING workers (`claimed`/`in-progress`), not `in-review`.** An in-review ticket is the cell critic-validated and PARKED at the human-acceptance gate (Tier 1) — not a worker. Counting it in the live-workers slice made a finished, fully-validated build read as N frozen agents with future lease times, and drove `factory_state` to report `running` when nothing was executing. (`count_running`, the concurrency/backpressure counter, already excluded in-review — so the loop was always correct; this was purely a display defect, surfaced by the live shader-playground build whose Tier-1 gate parks every validated cell.)
- **New `factory_state` `awaiting-review` state + `awaiting_review` count.** When the autonomous work is done and tickets are parked at the human gate (no running workers, nothing dispatchable), the headline now reads `AWAITING-REVIEW · N awaiting your sign-off` instead of a misleading `RUNNING` / `DRAINED` — the dashboard distinguishes "the build is working" from "the build is done and waiting for you." Full eval suite stays green.

## 2026-06-18 — the critic runs at every tier; only acceptance is tier-gated (lattice-guided iteration under human oversight)

- **`dispatch_unit` at Tier 1 now runs the critic (`lifecycle.run_critic`) before parking at in-review.** The autonomy tier gates only ACCEPTANCE — auto-close at Tier 2+, the human sign-off gate at Tier 1 — never *whether* the work was verified. A signal-bearing cell is critic-validated at Tier 1 (so the operator's later **plain `done` approval** passes `gate-signal` with no verifier to hand-supply), and a critic refusal re-authors against the feedback (bounded), exactly as the unattended path does. Fixes the **Tier-1 livelock** where a produced-but-unvalidated cell blocked the whole partial order and the heartbeat idled to its deadline. The produce→validate→iterate loop, guided by the lattice model, now runs at **every** tier — general-purpose output iteration under human oversight, not only unattended (pairs with dev-kernel 0.2.12's `run_critic`).
- **`evals/tier1-acceptance-gate/` (new)** — proves it (T1–T5): at Tier 1 a structured spec is critic-validated (cell `validated`, critic-minted signal, actor `cell-validator`) and parks for the operator's plain sign-off, which succeeds; a prose spec is refused and re-authored (the reward-hack teeth bite at Tier 1). The full suite stays green (`crawl` · `walk` · `server-smoke` · `integration` · `run` · `demotion` · `self-heal` · `fly`).

## 2026-06-16 — a caught false pass SELF-HEALS (decision #123: "full self-heal + new oracle")

- **`verify_gen.py` (new)** — ONE home for the per-cell critic-harness generator (`gen_cap_verify`, moved out of the cold-start planner so the runtime can regenerate the exact gate) plus the pure self-heal transform `fold(spec)`: merge the refuter's checks INTO the gate (acceptance ∪ refute) and re-arm a FRESH independent refuter (the "new oracle"); on oracle exhaustion it returns no harness, so the caller escalates rather than churns. Selftested.
- **`dispatch.self_heal_cell` + the `run_refuter` hook** — when the refuter catches a false pass, after the existing incident+demote the cell is now REPAIRED in code: the gate is folded (server-side write — the worker is gate-denied from `verify.mjs`), a fresh refuter is re-armed, the cell drops `validated → regenerating`, and staleness propagates to **un-ship** every dependent validated against it (the app integrator). The bounded `no-progress → block` breaker still backstops a cell that can't converge.
- **`refute_frontier` re-admits a re-validated cell** — it now keys off the LAST relevant ledger event per cell (robust to second-precision ts ties), so a cell self-healed → re-authored → re-validated re-enters the frontier and the fresh oracle re-measures the new validation epoch (the loop closes; it is not a one-shot).
- The cold-start planner persists the per-cell **verify-spec** (`coordination/verify-spec/*` = exports + acceptance + refute) as the fold substrate; `_gates.VERIFIER` protects it (dev-kernel 0.2.6). Proven end to end by `evals/self-heal/` (catch → fold → re-arm → stale + un-ship → re-author → re-measure, no model, no human).

## 2026-06-15 — the PRD milestone (outside-in) on the dashboard

- **`api.milestones` splits the spec layer into PRD + SPEC.** A spec cell whose slug ends `-prd` is the **PRD**
  (outside-in) stage; the rest is the **SPEC** (inside-out) stage. The header strip now reads
  `PRD 1/1 › SPEC 1/1 › CAPABILITY 2/3 › SHIP`, and the spec-iteration timeline shows revisions routed to either
  the PRD or the SPEC. No UI change needed — the strip + timeline render the stages the API reports.

## 2026-06-15 — env-selectable headless adapter + dashboard depth

- **The `HeadlessClaudeAdapter` is now wired into the server, env-selectable.** `dispatch.resolve_adapter()` reads
  `DEV_FACTORY_ADAPTER` (`mock` | `headless`); the heartbeat uses it, defaulting to **mock (free, no tokens)** so a
  Walk loop never spends tokens unless the operator opts in with `DEV_FACTORY_ADAPTER=headless`. `/api/status`
  carries the adapter name; the header shows a **mock / ● LIVE** badge (LIVE pulses in alert colour) so it's
  obvious whether a run spends real tokens. `run.sh`'s heartbeat warning is now adapter-accurate (it only flags
  token spend for `headless`). This is the last gap between "proven pipeline" and a real token-spending build.
- **Live team visibility.** `api.agents_running` is implemented from the ledger: each running worker carries its
  dispatch's **orchestration shape · delegation (team) · depth · parallelism · model tier**, plus the claim for
  the elapsed timer + a probe-cost ETA. The Agents view renders the orchestration line with a team dot.
- **Spec-iteration timeline.** The Roadmap view gains a first-class bi-directional timeline — `regenerate`
  (upstream spec revisions) + `stale-propagated` (the downstream cascade), derived from the ledger.
- **Per-cell verify status.** The Lattice grid marks a validated cell with a passing harness signal with a
  ✓ (and keeps the ⚠ stale flag). `app.js?v=8`.
- dispatch/api/app/store selftests + the `debug-coldstart` replay cover the adapter default + `agents_running`.

## 2026-06-15 — orchestration + observability: real teams, token-burn graph, roadmap, elapsed/effort

- **The planned sub-agent team now EXECUTES, not just records.** `HeadlessClaudeAdapter`: a `team` delegation
  plan makes the worker an ORCHESTRATOR — the prompt instructs decompose + delegate to sub-agents via the Task
  tool to the planned `max_depth` at `parallelism`, and `_allowed_tools` adds `Task` so it can spawn them. The
  activity ledger records the REAL `depth` (the plan's, not `0`) + `parallelism` + `model_tier` + `reasoning_effort`
  (dev-kit-app plans `orchestrator-workers` / depth 2 / parallelism 2 for capabilities). Cross-cell parallelism was
  already real (the heartbeat's concurrency); now the within-cell team is wired.
- **Token-burn graph.** Dispatch stamps `model_tier` + `reasoning_effort` onto the spend metrics; a **15s poll**
  (`_wire_token_poll`) snapshots cumulative tokens (+ USD) to `run/token-snapshots.jsonl`, attributed **per model
  tier + per reasoning effort**, and streams a `tokens` SSE. `GET /api/tokens` serves the series; a new **Tokens**
  view draws a realtime SVG area chart (cumulative total + per-model lines) with per-model / per-effort breakdown bars.
- **The roadmap is hydrated.** The cold-start planner now creates one **epic per milestone** (SPEC · CAPABILITY ·
  SHIP) with its tickets nested, so the Roadmap view fills in.
- **Elapsed time + estimated effort.** The claim stamps `claimed_at` (materialized); the Agents view shows a **live
  per-worker elapsed timer** (a 1s clock, no round-trip) + a **probe-cost token ETA** on each worker. `app.js?v=7`.
- api/app/store/dispatch selftests + the `debug-coldstart` replay assert the team ledger, the token attribution,
  the roadmap epics, and `claimed_at`; server-smoke covers `/api/tokens`.

## 2026-06-15 — dashboard richness: a milestone/ship progress strip

- **`api.milestones(d)` + `/api/status.milestones`** — a build-progress rollup the dashboard renders: the
  SPEC · CAPABILITY · SHIP stages (each `done/total`), whether the `capability.system.app` integrator has
  validated (`shipped`), and `spec_revisions` — the count of ledgered spec regenerations (the visible trace of
  the bi-directional loop). Generic over any lattice (a per-layer rollup), surfacing the app-building milestones
  when present. The UI header gains a colour-coded strip beside the work-state chip — `SPEC 1/1 › CAPABILITY
  2/3 › SHIP` with a `⟲ n` spec-revision badge — so the cockpit answers "where is the build, and has it shipped?"
  at a glance. `app.js?v=5`. api/app selftests + server-smoke cover the new field.

## 2026-06-15 — the code-authoring adapter (shippable software, DF-9)

- **`dispatch.py` authors real multi-file source.** `_authoring_for(cell)` reads the bound kit's `authoring`
  declaration; for a multi-file layer (dev-kit-app `capability`) the `MockAdapter` + `HeadlessClaudeAdapter._prompt`
  author source files into the cell's **directory** (industrial module boundaries, pure-logic ES modules + a thin
  shell) graded by the cell's per-cell `verify.mjs` — the worker is gate-denied from writing that harness
  (dev-kernel 0.2.4). Doc cells (dev-kit-corpus) stay single-`.md` (back-compat). This is the DF-9 fix that turns
  a "markdown lattice" into shippable software; the `/debug/` harness drives it through milestone rubrics to a
  shipped integrator. dispatch selftest covers the multi-file routing + the worker-protected harness.

## 2026-06-15 — two operator surfaces (the ralph-loop debugging system)

Two shipped features that make the autonomous loop watchable and steerable in real time, exercised by the new
`/debug/` ralph-loop harness (repo-root `debug/`).

### Added

- **5-second operator-input channel, folded into the loop's reasoning.** `POST /api/input` enqueues a steering
  message to `run/input.jsonl` (append-only intake); a **separate 5s asyncio poll** (`_wire_input_poll`,
  independent of the 30s dispatch heartbeat and of `HEARTBEAT_ENABLED`, so steering works even in Crawl) drains
  new intake into `run/guidance.json` and streams a `guidance` SSE event. `HeadlessClaudeAdapter._prompt` folds
  the latest guidance into each **newly dispatched** worker's prompt. **Security:** both files sit under `run/`,
  which `_gates.VERIFIER` already denies to gate-wired workers — so guidance is operator→loop only, by
  construction (a worker cannot forge it; proven in the `debug-coldstart` replay). **Honest limit:** a running
  one-shot `claude -p` worker can't be steered mid-flight — guidance reaches the *next* dispatch + the
  orchestrator. UI: a persistent **Steer dock** (`df-steer`) with a streaming guidance feed; its input survives
  the 5s updates (static template + a separate feed effect + direct-DOM toggle).
- **Two-mode ticket creator (tabs: Structured · Prompt · Instruction).** The create-ticket modal (`df-modal`)
  gains an intake-mode tab control. **Prompt** = a free-form brief that parks for the cold-start planner to
  triage into structured tickets; **Instruction** = literal steps that the server also folds into the guidance
  buffer (so the next worker sees it) and shows on the board. Backed by the dev-kernel `prompt`/`instruction`
  ticket kinds (schema + `gate_ticket_ready`, dev-kernel 0.2.3). `app.js?v=4`.

### Notes

- The `/debug/` harness (`debug/bin/{scaffold,coldstart,ralph,verdict}.py`) drives the whole arc — brief → spec
  → hydrated lattice → built app — bounded by construction. `debug-coldstart/replay.py` proves it CI-safe with
  the MockAdapter (no model, no server, no tokens); a live run (`DEBUG_RALPH_LIVE=1`) dispatches real workers.
