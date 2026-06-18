---
date: 2026-04-27
coverage: canonical
peers:
  - agents-md-spec.md
  - claude-md-convention.md
primary_sources:
  - https://agents.md — canonical adopters list
  - https://github.com/anthropics/claude-code/issues/31005 — Claude Code AGENTS.md request
  - https://docs.devin.ai/onboard-devin/agents-md
  - https://github.blog/changelog/2025-08-28-copilot-coding-agent-now-supports-agents-md-custom-instructions/
  - https://cursor.com/docs/rules
  - https://aider.chat/docs/usage/conventions.html
  - https://docs.continue.dev/customize/deep-dives/rules
  - https://docs.github.com/copilot/customizing-copilot/adding-custom-instructions-for-github-copilot
  - https://cognition.ai/blog/windsurf — Windsurf acquisition
status: research-verified
---

# Cross-tool compatibility matrix

> **The single load-bearing fact:** Claude Code reads `CLAUDE.md` natively but **not** `AGENTS.md`; almost every *other* major agent reads `AGENTS.md`. This skill is Claude-native — `CLAUDE.md` is canonical (the fat one) — and to serve the other tools you add a thin `AGENTS.md` (plus the tool rule files) that points back to `CLAUDE.md`. One source of truth, pointers everywhere else, minimal drift. (A Codex/Devin-first repo with no Claude Code inverts this — `AGENTS.md` canonical; see `agents-md-spec.md`.)

## The matrix (April 2026)

| Tool | Native instruction file(s) | Reads AGENTS.md natively? | Notes |
| --- | --- | --- | --- |
| **Claude Code** (Anthropic) | `CLAUDE.md` (+ `~/.claude/CLAUDE.md`, `CLAUDE.local.md`, `.claude/rules/`, `@import`) | **No** | Issue [#31005](https://github.com/anthropics/claude-code/issues/31005) open with no Anthropic response. **Canonical here** — for cross-tool add `AGENTS.md` → `CLAUDE.md` (`ln -s CLAUDE.md AGENTS.md`). |
| **OpenAI Codex** | `AGENTS.md` (+ `~/.codex/AGENTS.md`, `AGENTS.override.md`) | **Yes** — primary | Founding member of the agents.md working group. |
| **Cognition Devin** | `AGENTS.md` | **Yes** — primary | [docs.devin.ai/onboard-devin/agents-md](https://docs.devin.ai/onboard-devin/agents-md). |
| **Cognition Windsurf** | `.windsurfrules`, `.windsurf/rules/` | **Yes** | Cognition acquired Windsurf Dec 2025 (~$250M). |
| **Cursor** | `.cursor/rules/*.mdc` (newer); `.cursorrules` (deprecated, still works) | **Yes** | Founding member of the agents.md working group. |
| **GitHub Copilot** (coding agent + CLI) | `.github/copilot-instructions.md`, `.github/instructions/**/*.instructions.md` | **Yes** (added 2025-08-28) | Also reads `CLAUDE.md` and `GEMINI.md`. |
| **VS Code agent mode** | `AGENTS.md` (+ Copilot's instructions) | **Yes** |  |
| **Google Jules / Gemini CLI** | `AGENTS.md` | **Yes** | Founding member of the working group. |
| **JetBrains Junie** | `AGENTS.md` | **Yes** |  |
| **Sourcegraph Amp** | `AGENTS.md` | **Yes** | Founding member. (Sourcegraph Cody, distinct, has no documented file convention; relies on indexed context.) |
| **Aider** | `CONVENTIONS.md` (loaded via `--read`), `.aider.conf.yml` | **Configurable** — not auto by default | Set `read: ["AGENTS.md"]` in config to opt-in. |
| **Continue.dev** | `config.yaml` rules; Markdown rule files in `.continue/rules/` | **Not yet native** | Issue #6716 open. |
| **goose, Factory, Kilo, Antigravity, OpenClaw** | `AGENTS.md` | **Yes** | All listed on agents.md adopters page. |

## What this means for the audit

When auditing a repo (Claude-native default):

1. **CLAUDE.md** is the canonical entry — it should exist and be the fat one (Claude Code reads it natively).
2. **For each _other_ file the listed tools read natively** (incl. `AGENTS.md`), check whether it exists. If it does, it should be a thin pointer or symlink to `CLAUDE.md`, not a fat duplicate.
3. **AGENTS.md is the cross-tool pointer.** When the repo serves Codex/Cursor/Devin/Copilot, add a thin `AGENTS.md` → `CLAUDE.md` (`ln -s CLAUDE.md AGENTS.md`). (Inverted for an AGENTS.md-first repo with no Claude Code.)
4. **Continue.dev is the holdout.** If the project uses Continue, maintain `.continue/rules/main.md` as a pointer. Watch the issue tracker for native AGENTS.md support.
5. **Copilot triple-reads** — it reads its own instructions file PLUS CLAUDE.md PLUS AGENTS.md. Drift between any of those will be visible to Copilot users; the audit should flag any inconsistency.

## "Gas Town" — what it is, why it's not on this matrix

Gas Town ([gastownhall.ai](https://gastownhall.ai)) is **Steve Yegge's open-source multi-agent orchestrator** (released Jan 1, 2026), described as "Kubernetes for AI coding agents." It coordinates Claude Code, Codex, Gemini, etc., persisting work state in git-backed hooks.

It does **not** define a repo-doc format of its own — it dispatches to the underlying agents, each reading whatever file convention they support. Any AGENTS.md / CLAUDE.md set up correctly per this matrix will already work under Gas Town orchestration.

## "Hermes" — what it is, why it's not on this matrix

[NousResearch's Hermes Agent](https://hermes-agent.nousresearch.com) is a self-improving agent that uses **Skills stored in `~/.hermes/skills/`** with a `SKILL.md` + YAML frontmatter pattern (essentially the same shape as Anthropic's Agent Skills). It does **not** define a project-instruction file convention. There is no `HERMES.md`.

Note: "Hermes" is not Cognition Labs' product. Cognition's coding agent is **Devin** — see the row above. Confusion is common.

## Recipe: the minimal pointer set for full compatibility

If you want to support every major agent without drift, the minimum file set is:

```text
/repo
├── CLAUDE.md                            # ← the fat one (canonical, Claude-native)
├── AGENTS.md                            # ← symlink → CLAUDE.md  OR  3-line pointer (the cross-tool standard)
├── .cursor/rules/main.mdc               # ← 3-line pointer (optional; reads AGENTS.md too)
├── .windsurfrules                       # ← 3-line pointer (optional; reads AGENTS.md too)
├── .github/copilot-instructions.md      # ← 3-line pointer (optional; reads AGENTS.md/CLAUDE.md too)
├── .continue/rules/main.md              # ← 3-line pointer (Continue doesn't read AGENTS.md natively)
└── CONVENTIONS.md                       # ← only if Aider is in use
```

If you do not use Cursor/Windsurf/Copilot/Continue, drop those files. The two that always matter: CLAUDE.md (canonical, Claude Code) and AGENTS.md (the cross-tool standard everyone else reads).

## Cross-references

- CLAUDE.md convention (canonical): `claude-md-convention.md`
- AGENTS.md cross-tool standard (opt-in): `agents-md-spec.md`
- Audit checks: `../audit-patterns/entry-file-coverage.md`
