---
date: 2026-06-18
coverage: canonical
peers:
  - audit-existing-repo.md
  - adr-introduction.md
  - memory-organization.md
  - self-healing-hooks.md
  - continuous-learning-loop.md
primary_sources:
  - https://code.claude.com/docs/en/best-practices
  - https://github.com/typicode/husky
  - https://pre-commit.com/
  - https://adr.github.io/madr/
  - https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions
  - https://agents.md
status: research-verified
---

# Recipe: greenfield setup (Claude-native; delivers all 5 promises from day one)

> **The premise.** A new repo has no legacy debt — no fat entry file, no orphan docs, no scattered decisions. This is the _only_ moment the repo can ship with all five promises pre-installed. Skip this and you'll be doing `audit-existing-repo.md` in six months.
>
> **Claude-native default.** `CLAUDE.md` is the canonical entry (Claude Code reads it natively); `.claude/` holds config; `docs/ops/` holds the planning/decision docs. `AGENTS.md` + cross-tool pointers are **opt-in** (Step 2b) — add them only if the repo also serves Codex / Cursor / Devin / Copilot.
>
> **Not a new repo?** If your repo is older than ~3 months and has any documentation at all, use `cold-start-harvest.md` instead. That recipe handles the inventory + triage + supersede pattern this one skips.
>
> **Existing `docs/` layout?** If you already have `docs/adrs/`, `docs/postmortems/`, etc., the audit recognizes them; consolidating into `docs/ops/` is one `git mv` documented in `audit-existing-repo.md` § Migration.

## What this recipe delivers

| Promise | Delivered by |
| --- | --- |
| 1. Less-wasteful | One canonical entry file, thin pointers, no duplicated commands |
| 2. Token-and-context-optimized | CLAUDE.md ≤150 lines from day one; layered docs |
| 3. Less-prone-to-staleness | `_Last reviewed:_` lines, frontmatter dates, lychee CI |
| 4. Self-healing | Pre-commit hooks + PR-time CI + scheduled weekly audit |
| 5. Continuously-learning | ADR `0001` bootstrap, PR template architectural-impact checkbox, Memory primitives section |

## Step 1 — `CLAUDE.md` skeleton (Promise 1, 2)

`CLAUDE.md` is THE entry file — Claude Code reads it natively. Drop in the skeleton, customize what's true for the repo, target **80-120 lines**:

```markdown
# CLAUDE.md

Instructions for LLM coding agents working in this repo. Claude Code reads this
file natively; cross-tool agents read it via the pointers in Step 2b.

_Last reviewed: 2026-06-18_

## Project overview          (one paragraph)
## Build / test / run        (commands)
## Conventions               (bullet list)
## Trust boundaries          (DO NOT modify / DO modify)
## Where to find things      (pointers to docs/ops/)
## Memory primitives         (when to read ADRs / postmortems)
```

A `Where to find things` section is **load-bearing for navigation** — without it the agent sees only `CLAUDE.md` and has to guess where everything else lives:

```markdown
## Where to find things
- **Architecture:** `ARCHITECTURE.md`
- **Active plan:** `docs/ops/PLAN.md`   · **Roadmap:** `docs/ops/ROADMAP.md`
- **Decisions (ADRs):** `docs/ops/adrs/` (newest-first)
- **Post-mortems:** `docs/ops/postmortems/`   · **Runbooks:** `docs/ops/runbooks/`
- **Released changes:** `CHANGELOG.md`   · **Contributor guide:** `CONTRIBUTING.md`
```

Verify with `wc -l CLAUDE.md`. The pre-commit hook from Step 5 will fail it past 200.

## Step 2a — `.claude/` config home (Promise 1, 4)

Procedural skills under `.claude/skills/`, hooks under `.claude/hooks/`, settings in `.claude/settings.json`, and (Step 8) the strictness dial in `.claude/repo-ops.toml`. Create the dir so the home exists:

```bash
mkdir -p .claude/skills
```

## Step 2b — (opt-in) `AGENTS.md` + cross-tool pointers (Promise 1)

**Skip unless the repo also serves Codex / Cursor / Devin / Windsurf / Copilot.** When you do want cross-tool support, keep `CLAUDE.md` canonical and add thin pointers to it — never a second fat copy:

```bash
ln -s CLAUDE.md AGENTS.md          # symlink: zero-drift cross-tool pointer
git add AGENTS.md
```

Windows + WSL teams often hit symlink-in-git issues — fall back to the thin-pointer file from `../standards/claude-md-convention.md`. Same shape for `.cursor/rules/instructions.mdc`, `.windsurfrules`, `.github/copilot-instructions.md`. Either is fine; never have two files fat.

## Step 3 — `docs/ops/` directory tree + `.gitignore` (Promise 2, 5)

```bash
mkdir -p docs/ops/{adrs,postmortems,runbooks,archive,architecture}
touch docs/ops/{adrs,postmortems,runbooks,archive,architecture}/.gitkeep
```

Add an index `README.md` in each memory home (~10-20 lines each, `_Last reviewed:_` stamped). See `memory-organization.md` for the rationale on which folders go where and what each index file contains.

Then add transient-state homes to `.gitignore`. `docs/ops/cache/` is the WebFetch cache populated by external-reference verification. `docs/ops/cold-start/working/` is the harvest-session scratch space. The persistent state (`adrs/`, `postmortems/`, `runbooks/`, `archive/`, `architecture/`, `audit-history/`, `changesets/`) gets committed; config lives in `.claude/repo-ops.toml`.

```bash
cat >> .gitignore << 'EOF'

# repo-ops transient state
docs/ops/cache/
docs/ops/cold-start/working/
EOF
```

> **Want `docs/ops/` entirely local?** Set `mode = "local-only"` in `.claude/repo-ops.toml` and gitignore the whole `docs/ops/` directory (instead of just the cache/cold-start subdirs). See `../guidance/reliability-dial.md` § Git sync. Promise 5 then applies to your local clone only — multi-contributor recipes and the auto-archive PR workflow become moot.

## Step 4 — Bootstrap ADR `0001` (Promise 5)

The first ADR records the decision to use ADRs. Without it, the practice itself isn't decided. Use the Nygard format ([cognitect.com 2011](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)); template in `../doc-types/adr-pattern.md`:

```markdown
# 1. Record architecture decisions

Date: 2026-06-18

## Status
Accepted

## Context
We need to record architectural decisions made on this project so future
contributors (human and LLM agent) can understand why the codebase looks
the way it does.

## Decision
We will use Architecture Decision Records as described by Michael Nygard.
ADRs live in `docs/ops/adrs/` as `NNNN-kebab-case-title.md` with a `Status:`
field. The collection is the decision log.

## Consequences
- Architectural decisions are captured at decision time, not retroactively.
- New contributors read `docs/ops/adrs/` newest-first to understand commitments.
- Decisions become harder to silently override — supersession requires a new ADR.
```

Save as `docs/ops/adrs/0001-record-architecture-decisions.md`. Update `docs/ops/adrs/README.md`.

## Step 5 — Pre-commit hooks + CI (Promise 3, 4)

Install the full stack from `self-healing-hooks.md`:

```bash
cp ~/.repo-brain-templates/.pre-commit-config.yaml .
mkdir -p scripts && cp ~/.repo-brain-templates/scripts/*.sh scripts/
chmod +x scripts/*.sh

pip install pre-commit && pre-commit install

mkdir -p .github/workflows
cp ~/.repo-brain-templates/.github/workflows/*.yml .github/workflows/
```

Five files land: `.pre-commit-config.yaml`, `scripts/check-entry-pointer-drift.sh`, `scripts/check-doc-dates.sh`, `.github/workflows/repo-brain-pr.yml`, `.github/workflows/repo-brain-weekly.yml`. The verbatim contents are in `self-healing-hooks.md`.

Citations: [pre-commit.com](https://pre-commit.com/), [Husky](https://github.com/typicode/husky) (Node monocultures), [Lychee](https://github.com/lycheeverse/lychee-action).

## Step 6 — PR template (Promise 5)

The architectural-impact checkbox closes the continuous-learning loop. Drop in `.github/pull_request_template.md`:

```markdown
## What
[summary]

## Why
[motivation]

## Architectural impact
- [ ] No architectural change (no ADR needed)
- [ ] Architectural change — ADR added at: `docs/ops/adrs/NNNN-*.md`
- [ ] Architectural change — ADR exemption granted by: [name]
      Reason: [why no ADR]

## Docs touched
- [ ] CLAUDE.md updated if conventions / commands changed
- [ ] ADR added if architectural commitment made
- [ ] Runbook added if new ops procedure introduced
```

See `continuous-learning-loop.md` for the auto-detection workflow that warns when architectural files change without an accompanying ADR.

## Step 7 — `_Last reviewed:_` lines (Promise 3)

Every doc gets a date — YAML frontmatter `date:` or inline `_Last reviewed: YYYY-MM-DD_`. The greenfield seed:

```bash
TODAY=$(date +%F)
for f in CLAUDE.md README.md CONTRIBUTING.md SECURITY.md docs/ops/**/*.md; do
    [ -f "$f" ] || continue
    grep -q "_Last reviewed:" "$f" || \
        printf "\n_Last reviewed: %s_\n" "$TODAY" >> "$f"
done
```

The pre-commit hook from Step 5 enforces this on future edits.

## Step 8 — `.claude/repo-ops.toml` (optional: tune the strictness dial)

The hooks installed in Step 5 default to `strictness = "normal"`. To tune up or down, drop a `.claude/repo-ops.toml`:

```toml
[repo-ops]
strictness = "normal"  # lax | normal | strict
version = "1.1"
```

- **`lax`** — side projects, prototypes (warnings, no blocking)
- **`normal`** — most production repos (default)
- **`strict`** — regulated codebases, monorepos (every trip-wire blocks; multi-agent review for apply-mode fixes)

See `../guidance/reliability-dial.md` for what each position changes per trip-wire. Skip this step entirely to use `normal` defaults — `.claude/repo-ops.toml` is an override, not a requirement.

## Step 9 — Verification checklist

- [ ] `CLAUDE.md` exists, ≤150 lines, has all 6 sections incl. `Where to find things`
- [ ] (opt-in) `AGENTS.md` / tool pointers, if present, are symlinks to `CLAUDE.md` OR ≤15-line pointers
- [ ] `docs/ops/{adrs,postmortems,runbooks,archive,architecture}/` exist with README index files
- [ ] `docs/ops/adrs/0001-record-architecture-decisions.md` is `Accepted`
- [ ] `.gitignore` excludes `docs/ops/cache/` and `docs/ops/cold-start/working/`
- [ ] `.pre-commit-config.yaml` present; `pre-commit install` ran
- [ ] `scripts/check-*.sh` present and executable
- [ ] `.github/workflows/repo-brain-{pr,weekly}.yml` present
- [ ] `.github/pull_request_template.md` has architectural-impact checkbox
- [ ] Every `.md` has `_Last reviewed:_` or YAML `date:`
- [ ] `README.md` references `CLAUDE.md` once (no duplicated build commands; see `../standards/readme-conventions.md`)
- [ ] (Optional) `.claude/repo-ops.toml` present if non-default strictness desired
- [ ] `pre-commit run --all-files` passes

12 boxes ticked → all 5 promises ship from day one.

## First commit message

```text
chore: bootstrap repo-brain-compliant doc surface

- CLAUDE.md (canonical, Claude-native), AGENTS.md → symlink (opt-in, if cross-tool)
- docs/ops/{adrs,postmortems,runbooks,archive,architecture}/
- .gitignore for docs/ops/cache/, docs/ops/cold-start/working/
- ADR 0001 — Record architecture decisions
- pre-commit hooks (drift, length, doc-date)
- CI (PR-time link-check + weekly audit)
- PR template with architectural-impact checkbox

Delivers all 5 repo-ops promises from day one.
```

## Common greenfield mistakes

- **Indirecting through `AGENTS.md` for a Claude-Code repo.** Claude Code reads `CLAUDE.md` natively — make it canonical and stop. Add `AGENTS.md` only as an opt-in pointer when other agents (Codex, Cursor, Devin, Copilot) actually use the repo.
- **Skipping ADR 0001.** Without the bootstrap, the next contributor wonders if ADRs are required.
- **Pre-commit installed but not run.** `pre-commit install` writes `.git/hooks/pre-commit`; clones don't pick it up. Document the install in `CONTRIBUTING.md`.
- **Lychee with `fail: false` on PR.** Defeats the gate. `fail: true` on PR; `fail: false` only in scheduled audits.
- **Stamping `_Last reviewed:_` programmatically and never touching it again.** The date should be re-stamped on real edits, not just the seed.
- **Committing `docs/ops/cache/` or `docs/ops/cold-start/working/`.** Transient state belongs in `.gitignore`.

## Cross-references

- CLAUDE.md convention (canonical entry): `../standards/claude-md-convention.md`
- AGENTS.md cross-tool standard (opt-in pointers): `../standards/agents-md-spec.md`
- README/CONTRIBUTING/SECURITY conventions: `../standards/readme-conventions.md`
- ADR pattern: `../doc-types/adr-pattern.md`
- Self-healing hooks (Step 5 detail): `self-healing-hooks.md`
- Continuous-learning loop (Step 6 detail): `continuous-learning-loop.md`
- Memory organization (folder layout rationale): `memory-organization.md`
- Token-budget rationale for length caps: `../guidance/context-budget.md`
- Migration recipe for existing `docs/` layouts: `audit-existing-repo.md` § Migration
```
