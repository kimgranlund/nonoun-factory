---
date: 2026-04-27
coverage: canonical
peers:
  - claude-md-convention.md
  - cross-tool-matrix.md
primary_sources:
  - https://agents.md — canonical home of the spec
  - https://openai.com/index/agentic-ai-foundation/ — Agentic AI Foundation announcement (Dec 2025)
  - https://techcrunch.com/2025/12/09/openai-anthropic-and-block-join-new-linux-foundation-effort-to-standardize-the-ai-agent-era/
  - https://developers.openai.com/codex/guides/agents-md
  - https://docs.devin.ai/onboard-devin/agents-md
  - https://github.blog/changelog/2025-08-28-copilot-coding-agent-now-supports-agents-md-custom-instructions/
  - https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/
status: research-verified
---

# AGENTS.md — the cross-tool entry-file standard (opt-in)

> **Opt-in in this skill.** repo-ops is **Claude-native by default**: `CLAUDE.md` is the canonical entry (Claude Code reads it natively). `AGENTS.md` is the **cross-tool standard** you adopt when the repo also serves Codex / Devin / Cursor / Windsurf / Copilot — *only when prompted*. Two ways to adopt it: **(a) Claude-native + cross-tool** — keep `CLAUDE.md` canonical and add a thin `AGENTS.md` that points to it (`ln -s CLAUDE.md AGENTS.md`), the recommended path when Claude Code is in the mix (see `claude-md-convention.md`); or **(b) AGENTS.md-canonical** — a Codex/Devin-first repo with no Claude Code, where `AGENTS.md` itself carries the instructions (the fat structure below). This page documents the standard for both.

## What AGENTS.md is

`AGENTS.md` is a Markdown file at the repo root that instructs an LLM coding agent on how to work in the repo. The format **emerged August 2025** out of a working group of OpenAI Codex, Amp (Sourcegraph), Jules (Google), Cursor, and Factory. As of **December 2025 it is stewarded by the Agentic AI Foundation (AAIF) under the Linux Foundation**, alongside Anthropic, OpenAI, Block, Google, Microsoft, AWS, Bloomberg, and Cloudflare. Adoption (as of April 2026) is **60,000+ open-source projects**.

Canonical home: [agents.md](https://agents.md).

## What the spec actually requires

**Almost nothing.** The spec is deliberately format-light — _"just standard Markdown, no required fields."_ Authority is governance (AAIF/Linux Foundation steward), not schema. Any sectioning convention (e.g., "Where to find things") is **opinionated overlay**, not spec compliance.

This skill recommends the structure below — but it is _our_ recommendation, layered on top of a deliberately permissive spec.

## Recommended structure (this skill's overlay)

````markdown
# AGENTS.md

This file gives instructions to LLM coding agents (Codex, Devin, Cursor,
Windsurf, Copilot, Aider, Continue, Jules, Junie — and Claude Code via
symlink/pointer) working in this repo.

_Last reviewed: 2026-04-27_

## Project overview

One paragraph: what this repo does, who uses it.

## Build / test / run

```bash
pnpm install
pnpm test
pnpm build
```

## Conventions

- TypeScript strict mode; ESM only
- Vitest for tests; Playwright for E2E
- Conventional Commits

## Trust boundaries

- DO NOT modify: `db/migrations/`, `legal/`, `LICENSE`
- DO modify: `src/`, `tests/`, `docs/ops/` (with care for ADRs)

## Where to find things

- **Architecture:** `ARCHITECTURE.md`
- **Active plan:** `docs/ops/PLAN.md`
- **Roadmap:** `docs/ops/ROADMAP.md`
- **Architecture Decision Records:** `docs/ops/adrs/` (see also `docs/ops/adrs/README.md` for the index)
- **Post-mortems:** `docs/ops/postmortems/`
- **Runbooks:** `docs/ops/runbooks/`
- **Released changes:** `CHANGELOG.md`
- **Contributor guide:** `CONTRIBUTING.md`

## Memory primitives

- **Before making architectural decisions**, read `docs/ops/adrs/` newest-first.
- **When debugging a production issue**, search `docs/ops/postmortems/`.

````

The "Where to find things" section is **load-bearing for navigation** even if not strictly required by the spec. Without it, the agent sees only `AGENTS.md` and has to guess where everything else lives.

## Adoption matrix (April 2026)

| Tool | Reads AGENTS.md natively? | Notes |
| --- | --- | --- |
| **OpenAI Codex** | **Yes** — primary | Plus `~/.codex/AGENTS.md`, `AGENTS.override.md` |
| **Cognition Devin** | **Yes** — primary | docs.devin.ai/onboard-devin/agents-md |
| **Cursor** | **Yes** | Plus `.cursor/rules/*.mdc` (newer) and `.cursorrules` (deprecated, still works) |
| **Windsurf** (Cognition-owned since Dec 2025) | **Yes** | Plus `.windsurfrules`, `.windsurf/rules/` |
| **GitHub Copilot** (coding agent + CLI) | **Yes** (added 2025-08-28) | Also reads `CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md` |
| **VS Code agent mode** | **Yes** |  |
| **Google Jules / Gemini CLI** | **Yes** |  |
| **JetBrains Junie** | **Yes** |  |
| **Sourcegraph Amp** | **Yes** | Founding member of the agents.md working group |
| **goose, Factory, Kilo, Antigravity, OpenClaw** | **Yes** | All listed on agents.md adopters page |
| **Aider** | Configurable via `--read CONVENTIONS.md` | Default is `CONVENTIONS.md`, AGENTS.md only via config |
| **Continue.dev** | **Not yet** | Issue #6716 open |
| **Claude Code** (Anthropic) | **NOT natively as of April 2026** | Issue [#31005](https://github.com/anthropics/claude-code/issues/31005). Claude-native: keep `CLAUDE.md` canonical and point `AGENTS.md` at it (`ln -s CLAUDE.md AGENTS.md`); AGENTS.md-first repo: the reverse |

## One source of truth + thin pointers (whichever file is canonical)

The invariant is **one canonical entry file, every other agent-rules file a thin pointer/symlink to it** — never N divergent copies. Which file is canonical depends on the repo:

| Approach | Problem |
| --- | --- |
| `CLAUDE.md` only (no pointers) | Codex / Devin / Cursor / Windsurf / Copilot don't read it natively. Cross-tool repos drift. |
| `.cursorrules` only | Other tools don't read it. Same problem inverted. |
| One fat file per tool | N copies of the same content, guaranteed to drift over time. |
| **Claude-native (default): `CLAUDE.md` canonical + thin `AGENTS.md`/tool pointers** | One source of truth; Claude Code reads it natively; cross-tool files are 3-line redirects (or `ln -s CLAUDE.md AGENTS.md`). |
| **AGENTS.md-canonical (no Claude Code): `AGENTS.md` + thin pointers** | One source of truth for a Codex/Devin-first repo; tool-specific files redirect to `AGENTS.md`. |

## Audit checks for AGENTS.md

When auditing a repo:

1. **Existence** — does `AGENTS.md` exist at the repo root?
2. **Recommended sections present** — project overview, build/test/run, conventions, trust boundaries, where-to-find-things, memory primitives. (None are spec-mandated; all are recommended for navigability.)
3. **Pointer integrity** — does each `docs/ops/...` reference point to a real path?
4. **Freshness** — `_Last reviewed:_` line or YAML frontmatter `date:` present?
5. **One canonical entry; all others thin pointers/symlinks** — never two fat copies. **Claude-native default:** `CLAUDE.md` is canonical and `AGENTS.md` / `.cursorrules` / `.windsurfrules` redirect to it. **AGENTS.md-canonical repo (no Claude Code):** the reverse. Either way, a divergent second fat copy is drift. See `claude-md-convention.md`.
6. **Length** — under ~200 lines is the ergonomic target (per Anthropic's own CLAUDE.md guidance, which ports cleanly to AGENTS.md). Long instructions degrade adherence; push detail into `docs/ops/` subfolders.

## Common anti-patterns

- **Naked AGENTS.md** — just a project overview, no `Where to find things` section. Agent has nothing to navigate to.
- **Duplicate content** — AGENTS.md and CLAUDE.md both contain full instructions, drifted apart. Pick one canonical, make the others pointers/symlinks.
- **Stale build commands** — `npm install` listed but project moved to pnpm a year ago. Audit catches this by comparing to `package.json` / lockfiles.
- **No trust boundaries** — agent edits files it shouldn't (migrations, legal, generated code). Trust-boundary section prevents this.
- **No memory primitives section** — agent doesn't know to read ADRs before architectural decisions.
- **Bloated AGENTS.md** — 800-line instruction dump that nobody (human or agent) reads. Compress, link out.

## Cross-references

- CLAUDE.md as thin pointer / symlink: `claude-md-convention.md`
- Cross-tool compatibility matrix (full): `cross-tool-matrix.md`
- Audit checks: `../audit-patterns/entry-file-coverage.md`
- Greenfield setup recipe: `../recipes/greenfield-setup.md`
- LLM-doc-writing guidance: `../guidance/llm-doc-writing.md`
