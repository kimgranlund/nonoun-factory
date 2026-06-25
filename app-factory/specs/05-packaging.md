---
name: app-factory-packaging
stage: packaging
status: phase-C hardened (post red-team) — walking-skeleton thin slice
depends_on: 00-charter, 03-loop-and-goal
---

# Packaging — the plugin surface in nonoun-factory

**Intent.** Define app-factory's operator surface (commands/skills/agents/MCP), what
it vendors and from *where*, and how it sits in the marketplace. The operator surface
is deliberately small; the *vendored rigor* is not (red-team fix — the rigor lives in
two repos, and `05` now names both honestly).

## The operator surface (thin — `app-{verb}` namespaced)

All commands are `app-{verb}` (red-team fix: resolves the `/loop` collision with the
built-in recurring-task skill, and matches every sibling plugin's grammar).

| Command | Purpose |
|---------|---------|
| `/app-new <name>` | Scaffold a project corpus (`idea.md` + folders + `.factory/`) |
| `/app-goal <doc>` | Set a committed PRD/SPEC as destination; run the bounded loop until met (attended) |
| `/app-loop` | Advance the frontier of ready tickets under caps (attended) |
| `/app-spec <doc>` | Author / cultivate / **commit** a PRD or SPEC (the cultivation workflow; `commit` is the crystallization gesture, not `git commit`) |
| `/app-qa <project>` | Emit / run the QA plan; replay acceptance |
| `/app-status <project>` | Cheap dashboard — stage map, frontier, budget, ledger tail, **trust tier**, **stale knowledge/patterns** (no agent) |

Skills back these: a **cultivation** skill (idea→PRD→spec authoring), a **decompose**
skill (committed spec → draft tickets), an **execute** skill (the loop), a **distill**
skill (corpus growth). Agents include the **non-executor acceptance-deriver**, the
**entailment critic**, the **independent refuter**, and the reused **spec-council**.

> Conceptual core unchanged: the two verbs are still *goal* and *loop*; only the
> command tokens are namespaced. (Resolves OD-00-B / OD-05-A.)

## What it vendors — and from where (the split that the red-team forced)

The earlier draft claimed everything came from `harness-forge`. **Half of it does
not.** The authoring discipline, the gates, the refuter, and calibration live in
`dev-kernel`/`dev-kit-corpus`. app-factory vendors from **both**, drift-checked, and
the lattice machinery is present-but-hidden beneath the prose surface.

**From `harness-forge` (the loop spine):**

| Primitive | File |
|-----------|------|
| Bounded loop + goal | `harness-forge/bin/goal.py`, `harness-forge/agents/harness-builder.md` |
| Budget / caps (fail-closed arm) | `harness-forge/bin/run-budget.py`, `gate-budget` |
| Ledger (append-only) | `harness-forge/bin/ledger.py` |
| Signal minting + generator/critic gate | `harness-forge/bin/validate.py`, `gate-signal` |
| Frontier ranking | `harness-forge/bin/lattice.py` (`rank`) |
| Trust-tier **gauge** | `harness-forge/bin/ledger.py` (`false_pass_rate`, `trust_tier`) |
| Staleness cascade | `harness-forge/bin/propagate-staleness` |
| Read-only query surface | `harness-forge/bin/lattice-mcp.py` pattern |

**From `dev-kernel` / `dev-kit-corpus` (the authoring + verification rigor) —
*this is the half the earlier draft wrongly attributed to harness-forge*:**

| Primitive | File |
|-----------|------|
| Spec authoring discipline + format | `dev-kernel/skills/spec-author/` |
| Spec review council + lens critics | `dev-kernel` `spec-council`, `critic-spec-*` |
| Ticket contract + lifecycle gates | `dev-kernel/schemas/ticket.schema.json`, `dev-kernel/bin/lifecycle.py` (`gate-ticket-ready`) |
| Mechanical spec/PRD gates | `dev-kit-corpus/rubric/{spec-quality,prd-quality}.rubric.json` |
| Rubric **calibration** (entailment + determinism) | `harness-forge/evals/calibration/` discipline applied to derived acceptance |
| Independent **refuter** (the trust sensor) | `dev-kernel` refute-author dispatch + `--allow-refute`; `dev-server/dispatch.py` |
| Autonomy actuator (tier consumer + incident→demotion) | `dev-kernel/bin/autonomy.py` |

**Protected perimeter** — the spine's deny-on-write set is extended to app-factory's
new load-bearing assets: committed `spec/*.md`, `tickets/*.md` `acceptance`, `qa.md`,
and the app-factory ledger (`02`).

**Regenerate budget** — the outer loop carries a regenerate-count cap so
spec↔cultivated oscillation is bounded (`01`, `03`).

## Marketplace placement

- New entry in `.claude-plugin/marketplace.json` (`name: nonoun-factory`), install id
  `app-factory@nonoun-factory`.
- Four-descriptions sync (marketplace.json · plugin.json · README · CHANGELOG),
  gated by `check-manifest-sync.py`.
- Self-contained, zero cross-plugin imports; the `harness-forge` **and** `dev-kernel`
  primitives are *vendored*, not imported, and drift-checked in CI (the
  `tools/sync-dev-kernel.py --check` pattern, extended to both sources).

## Acceptance criteria

- AC-05-1: The operator surface is ≤ ~6 commands, all `app-{verb}`, each mapping to a
  lifecycle stage in `01`.
- AC-05-2: Every vendored primitive cites a real source file and the **correct
  repo** (`harness-forge` vs `dev-kernel`/`dev-kit-corpus`); the authoring/refuter/
  calibration half is attributed to dev-kernel, not harness-forge.
- AC-05-3: The vendor set includes the trust **sensor** (refuter) and **actuator**
  (autonomy.py), not only the gauge; and `propagate-staleness`.
- AC-05-4: The marketplace entry obeys the four-descriptions sync + zero
  cross-plugin import conventions.

## Non-goals

- Not the web UI / productivity shell (deferred — it mounts over this same corpus +
  ledger substrate, like `dev-server/ui/`).
- Not re-deriving any spine primitive.

## Open decisions

- OD-05-B: Vendor the two kernels wholesale, or fork a slimmed `kernel/` carrying
  only the named primitives? (Trades sync simplicity vs. surface area; ties to
  OD-00-C, the escalation-capacity question.)
- OD-05-C: Is the acceptance-deriver a dedicated agent or a constrained reuse of
  `spec-author`/`ticket-triager` (OD-02-D)?
