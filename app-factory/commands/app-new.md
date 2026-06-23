---
description: Scaffold a project corpus — the prose the human cultivates (idea → PRD → specs → knowledge) plus the hidden `.factory/` spine beneath it (lattice, ledger, signals, the deny-on-write perimeter). The one deterministic gesture; then the human cultivates `idea.md`.
argument-hint: "<name> [--into DIR]   (default DIR=./projects)"
---

Scaffold a new project. **$ARGUMENTS**

A project is a **corpus of prose documents** a bounded loop compiles into software. This command lays that corpus and the hidden spine — it is the one deterministic action a human types; everything after is cultivation.

Run `python3 "${CLAUDE_PLUGIN_ROOT}/bin/app-new.py" <name> [--into DIR]` (default `DIR=./projects`). It shells the proven scaffolder — the lattice itself is minted by the *vendored* kernel (`lattice.py init`), never re-implemented here — and writes:

- the **prose corpus** at `projects/<name>/`: `idea.md prd.md qa.md` (all at `draft` maturity) + `research/ prototype/ spec/ tickets/ knowledge/`;
- the **hidden spine** at `projects/<name>/.factory/`: `lattice.json`, `ledger/`, `signals/`, `run/`, `project.json` (stage · doc maturities · `autonomy_tier: 0`), and `protected.json` — the **deny-on-write perimeter** that registers the committed bars (`spec/**`, `tickets/**`, `qa.md`, the ledger) so a coding agent can never edit the bar it is graded against.

`app-new` refuses to scaffold into a non-empty directory (no silent clobber). The new project is **Tier 0 (attended)**: no autonomy is earned until the ledger shows a measured false-pass track record.

Then **point the human at cultivating `idea.md`** — one paragraph of intent (what is this, who is it for, what does "good" look like). The human edits prose; they never hand-build a typed grid. When the idea is ready, move it toward a committed PRD/SPEC with `/app-spec`, and watch with `/app-status <name>`. The corpus is the asset; cultivating it is the highest-leverage work — not steering execution.
