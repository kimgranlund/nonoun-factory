---
date: 2026-06-18
coverage: canonical
peers:
  - agents-md-spec.md
  - cross-tool-matrix.md
primary_sources:
  - https://code.claude.com/docs/en/best-practices — Anthropic Claude Code best practices
  - https://github.com/anthropics/claude-code/issues/31005 — request to support AGENTS.md (Apr 2026: still open, no Anthropic response)
  - https://github.com/anthropics/claude-code/issues/6235 — parent issue (3,020 upvotes, 224 comments, 7 months open)
  - https://www.humanlayer.dev/blog/writing-a-good-claude-md
status: research-verified
---

# CLAUDE.md — the canonical entry file (Claude-native)

> **The canonical pattern (Claude-native default).** `CLAUDE.md` at the repo root is **THE** entry file for LLM coding agents — Claude Code reads it natively, so it carries the real instructions, not a redirect. Other tools' rule files (`.cursor/rules/*.mdc`, `.windsurfrules`, `.github/copilot-instructions.md`) and the **opt-in** `AGENTS.md` are thin pointers (or symlinks) **to** `CLAUDE.md` — never divergent second copies. Add them only when the repo serves those tools (see `agents-md-spec.md`).

## How Claude Code actually reads CLAUDE.md

Claude Code loads CLAUDE.md with this **precedence** (highest → lowest):

1. **Managed enterprise policy** (org-level)
2. **`~/.claude/CLAUDE.md`** (user global)
3. **`CLAUDE.md`** (project root)
4. **`CLAUDE.local.md`** (personal overrides, gitignored)

It also walks parent directories, supports `@import` syntax, and reads `.claude/rules/` for path-scoped rules.

## Why CLAUDE.md is canonical here — Claude Code does NOT read AGENTS.md natively

As of April 2026, **Claude Code does not natively read `AGENTS.md`**. The community has been requesting this since at least September 2025; [issue #31005](https://github.com/anthropics/claude-code/issues/31005) and the parent issue #6235 (3,020 upvotes, 224 comments, 7 months open) both have **zero Anthropic response**. So for a Claude-Code-first repo there is no reason to indirect through `AGENTS.md`: put the instructions in `CLAUDE.md` and stop. `AGENTS.md` becomes worthwhile only when you also serve Cursor / Codex / Devin / Windsurf and want the cross-tool standard — and then it points back at `CLAUDE.md`.

## Opt-in: adding cross-tool pointers to CLAUDE.md

When the repo serves other agents, add thin pointers — each 3-5 lines, all redirecting to `CLAUDE.md`:

**Pointer A — `AGENTS.md`** (the cross-tool standard; opt-in):

```markdown
# AGENTS.md

This repo's canonical instructions for LLM coding agents live in [`CLAUDE.md`](./CLAUDE.md).
Please read that file. The contents apply identically across tools.

_Last reviewed: 2026-06-18_
```

Or a symlink (minimal footprint): `ln -s CLAUDE.md AGENTS.md`.

**Caveat:** symlinks have known compatibility quirks on Windows + WSL and across some tool sandboxes — verify on the platforms you target; the thin-pointer file is the safe default.

**Pointer B — other tools' rule files** (same shape):

```text
# .cursor/rules/instructions.mdc
This repo's instructions live in CLAUDE.md at the root. Please read it.
```

```text
# .windsurfrules
This repo's instructions live in CLAUDE.md at the root. Please read it.
```

```text
# .github/copilot-instructions.md
This repo's instructions live in CLAUDE.md at the root. Please read it.
```

(Note: GitHub Copilot reads `AGENTS.md`/`CLAUDE.md` natively, but a thin pointer here is harmless and helps consistency.)

## Anthropic's own guidance for CLAUDE.md

Per [Anthropic's Claude Code best practices](https://code.claude.com/docs/en/best-practices) and the widely-cited [HumanLayer post](https://www.humanlayer.dev/blog/writing-a-good-claude-md):

- **Keep CLAUDE.md under ~200 lines.** Instruction quality decreases as count increases.
- **Only universally-applicable instructions.** Path-specific rules belong in `.claude/rules/<path>/CLAUDE.md`.
- **Prefer hooks over advisory text** for deterministic behavior — hooks always execute; CLAUDE.md text is advisory.
- **Iterate by telling Claude to add corrections to CLAUDE.md itself.** Treat it as live, not frozen.

These same ergonomics port to any cross-tool pointer — but the content lives once, in `CLAUDE.md`.

## Anti-pattern: divergent CLAUDE.md and AGENTS.md

The most common stale-docs failure: `CLAUDE.md` and `AGENTS.md` both carry real content and have drifted. Different build commands. Different conventions. Different trust boundaries.

Audit signal:

- Both files exist
- Both are non-trivial in size (>15 lines each)
- A diff shows substantive content differences

Fix: keep `CLAUDE.md` canonical, demote `AGENTS.md` to a pointer or symlink (`rm AGENTS.md && ln -s CLAUDE.md AGENTS.md`).

## Migration recipe — consolidating onto a canonical CLAUDE.md

If you have a fat `AGENTS.md` (e.g. an AGENTS.md-standard repo) and want Claude-native:

1. **Make `CLAUDE.md` canonical.** If `CLAUDE.md` is missing or thin, `cp AGENTS.md CLAUDE.md` and edit from there; if both are fat, diff and merge into `CLAUDE.md`.
2. **Keep wording tool-neutral** where the repo is cross-tool ("LLM coding agents (Claude Code, Codex, Devin, Cursor, Windsurf, …)").
3. **Add a `Where to find things` section** if missing — pointing at `docs/ops/`.
4. **Trim `CLAUDE.md` to under ~200 lines.** Push detail into `docs/ops/`.
5. **Replace `AGENTS.md`** with either a symlink (`rm AGENTS.md && ln -s CLAUDE.md AGENTS.md`) or a thin pointer file — only if cross-tool support is wanted; otherwise drop it.
6. **Add `.cursor/rules/instructions.mdc`, `.windsurfrules`, `.github/copilot-instructions.md`** as thin pointers if those tools are used.
7. **Commit clearly:** `docs: consolidate agent instructions onto canonical CLAUDE.md`.

## Audit checks for CLAUDE.md

1. **`CLAUDE.md` exists at the repo root** — it is the canonical entry. Absent → recommend creating it.
2. **If `AGENTS.md` (or another tool's rule file) exists**, it should be a symlink to `CLAUDE.md` OR a thin pointer (≤15 lines). Anything else is drift.
3. **If both `CLAUDE.md` and `AGENTS.md` exist as fat files**, flag as drift risk — diff them and recommend consolidation onto `CLAUDE.md`.
4. **If `CLAUDE.md` references files that don't exist**, flag broken pointers.
5. **`CLAUDE.md` > 200 lines** — flag as a length smell. Anthropic's own guidance recommends shorter.

## Cross-references

- AGENTS.md cross-tool standard (opt-in): `agents-md-spec.md`
- Full cross-tool compatibility matrix: `cross-tool-matrix.md`
- LLM-doc-writing guidance (length, content quality): `../guidance/llm-doc-writing.md`
- Audit checks: `../audit-patterns/entry-file-coverage.md`
- Migration recipe in detail: `../recipes/audit-existing-repo.md`
