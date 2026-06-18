# agent-ops — ROADMAP

_Last reviewed: 2026-06-18 (against CHANGELOG 0.1.19)._

Carve signed off 2026-06-03; **built and shipped — currently at 0.1.18.** This tracks live state + the genuine remaining work. The full delivery history is in [CHANGELOG.md](CHANGELOG.md); this file is the forward view.

## Scope (signed off)

A single, **full-spectrum plugin for authoring, operating, and reviewing agentic systems and the repos they live in.** It knows how to author all sorts of agentic systems and the nuance of context and harness — agent loops & teams, the control plane (termination · verification · context · budget · durability), harness & context engineering, agentic-workflow UX — and how to manage the repo those agents work in (memory/docs, the canonical files, architecture review, house-cleaning). Carved and **de-repo'd** from four mature global skills: `ops-repo`, `arch-repo-review`, `core-agent-loops`, `core-agentic-ux-best-practices`. Self-contained — zero cross-plugin paths (gated by `check-self-contained.py`).

## The five-primitive shape (live)

| Primitive | agent-ops instance |
| --- | --- |
| **Skills (5)** | `agent-ops` (orchestrator) · `repo-ops` · `repo-review` · `agent-loops` · `agentic-ux` |
| **Agents** | the named-practitioner **council (13)** + an `agentic-council` orchestrator, fanned out parallel + isolated |
| **Commands** | thin `/ops-*` entry points — `orient · audit · review · loop · agentic-ux · council` |
| **Hook** | advisory doc-hygiene lint on canonical-file writes (staleness / format / drift) — never blocks |
| **Gates (`bin/`)** | `audit-history.py` (audit ledger: `validate` + `liveness`) · `check_blueprint.py` + `schemas/blueprint.json` (14-field loop-blueprint validator) · `check-sourcing.py` (living-critic provenance) · `check-self-contained.py` (the de-repo invariant) · `doc-hygiene` (advisory) |
| **MCP** | **`repo-memory`** (shipped 0.1.9) — read-only, per-instance retrieval over a repo's agent docs + `docs/ops/audit-history/` (or legacy `.agents/brain/`) ledger |

## Skills

- **`agent-ops`** (orchestrator) — classify the meta-task (author a loop · operate/score a workflow's UX · audit the doc/memory surface · review the code architecture) → route to the owning skill or the council.
- **`repo-ops`** (from ops-repo) — the repo-as-brain memory layer, **Claude-native** (CLAUDE.md canonical + thin pointers · `.claude/` config · `docs/ops/` memory; `AGENTS.md`/`.agents/` opt-in for cross-tool), ~16 audit patterns (stale / orphan / redundant / drift / token-waste), doc-type standards (README · CHANGELOG · ROADMAP · PLAN · ADR · ARCHITECTURE · postmortem), the five promises, the audit ledger, the skill-stewardship loop.
- **`repo-review`** (from arch-repo-review) — the 6-wave Discover → Audit → Synthesize → Adversarial → Polish pipeline → cascade-ranked refactor backlog (3 P0 / 3 P1 / 6 P2 / ∞ P3) + tier-1 patterns doc.
- **`agent-loops`** (from core-agent-loops) — builder-seat loop mechanism design: 11 topologies (Ralph · plan-execute · ReAct/Reflexion · evaluator-optimizer · orchestrator-workers · auto-research · debate · self-improving · spec-driven · async) + the router + the control plane + the 14-field Orchestration Blueprint.
- **`agentic-ux`** (from core-agentic-ux-best-practices) — operator-seat UX evaluation: the 8-dimension agentic-UX rubric + the **7-dimension** agentic-architecture rubric (A1–A7) + lifecycles + techniques.

## Council (13 critics, obscured)

- **UX & Quality:** Amelia W. · Sarah G. · Geoffrey L. · Karri S.
- **Architecture & Utility:** Walden Y. · Harrison C. · Mitchell H. · the MCP / tool-perimeter lens · **Jake V.**
- **Agentic-systems builders:** Boris C. · Garry T. · Andrej K. · Simon W.

Critic display names are obscured to `First L.`; the real practitioner attributions/bios/sources live in a git-ignored `agents/.name-map.md`. Living practitioners: observable-public-only sourcing, verbatim quotes verified, `check-sourcing.py` provenance gate.

## Delivered since the 0.1.0 carve

The build plan (scaffold → de-repo → council → orchestrator/commands/hook → gates → validate → red-team) shipped at **0.1.0** (red-teamed by the plugins-factory council: CONDITIONAL → folded → APPROVED). Since then (0.1.1 → 0.1.18):

- **Council calibration** — the agentic-UX council + `repo-review` calibrated against N=3 fixtures (`evals/council-calibration/`, `evals/repo-review-calibration/`); scoped critic dispatch (`agent-ops:critic-*`) to dodge the same-name-collision drop (I-10).
- **`repo-memory` MCP** (0.1.9) — filled the v0.2 MCP slot: read-only per-instance memory/audit-history retrieval.
- **`repo-ops` made Claude-native** (0.1.19) — `CLAUDE.md` canonical · `.claude/` config + `.claude/skills/` · `docs/ops/` for goals/planning/ADRs/issues/postmortems/runbooks/audit-history; `AGENTS.md` + `.agents/brain/` demoted to an explicit **opt-in cross-tool mode** (used only when prompted). The doc-hygiene hook + `audit-history.py` + `repo-memory` MCP read `docs/ops/` first, legacy `.agents/brain/` still recognized.
- **`.agents/brain/` namespace** + the audit-history ledger (`validate` + `liveness` trip-wire) — the prior layout, now the opt-in mode.
- **repo-ops skill-stewardship loop** (0.1.17) — the four "future evolution" stubs specified as grounded specs (lifecycle states, telemetry utility-detection, description↔body drift, `pairs-with` audit).
- **Jake V. — the 13th critic** (0.1.18) — interpretable context architecture, folder-first organization (skills/tools/resources as navigable files), room-to-think/act, and eval integrity (no self-graded scoreboard); rubric dimension **A7**.

## Now / Next (the live frontier)

The original build plan is fully delivered; these are the genuine open items:

- **Calibrate the `agentic-ux` rubric beyond directional.** The council and `repo-review` were calibrated (N=3 fixtures); the 8-dimension agentic-UX rubric still ships *directional* (calibration-sample-light). Build a fixture set + scored runs to move it directional → recorded, as the others were.
- **Implement the skill-stewardship scripts.** The four loop scripts (`check-skill-frontmatter`, `audit-skills`, `draft-skill`, `iterate-skill`) are specified (0.1.17) but the implementations are user-side; wire executable versions into `bin/` so the procedural-memory audit is gated like the declarative one.
- **Grow the council-calibration corpus.** Add fixtures beyond the current N=3 (especially ones that exercise the newest seats — Jake V.'s folder-organization + scoreboard-independence lens) so the council's verdicts stay measured, not asserted.
- **Score external / third-party agentic workflows.** The council + rubrics have only been run on in-house fixtures; running them on a real outside workflow is the next empirical step.

> **Honesty note (still true):** the `agentic-ux` rubric ships directional, not authoritative, until the calibration above lands. The council is Claude-family models grading agentic systems — a self-graded scoreboard (Jake V.'s own lens); weight its verdicts accordingly and prefer an independent, output-based check where one exists.
