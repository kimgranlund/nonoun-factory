# Changelog — dev-server

The dev-factory runtime (FastAPI/uvicorn over the stdlib ops layer). Not a plugin — it ships in the dev-factory
marketplace and is versioned with the kernel it serves. Format: [Keep a Changelog](https://keepachangelog.com/).

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
