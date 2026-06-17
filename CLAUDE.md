# CLAUDE.md

Guidance for Claude Code working in **nonoun-factory** — the builder/operator toolchain marketplace, split out of `nonoun-plugins` on 2026-06-17 so the *tools that build/operate agentic systems* and the *domain products* (brand, product, in the sibling `nonoun-plugins` repo) each have their own marketplace + audience.

## What this repo is

A Claude Code plugin marketplace (`name: nonoun-factory` in `.claude-plugin/marketplace.json`; install ids end `@nonoun-factory`). Catalog plugins:

- **`plugins-factory/`** — the plugin-lifecycle tool: author & red-team plugins against one 9-dimension standard, judged by a 9-critic council; the gate suite in `plugins-factory/bin/` validates every plugin in this repo (and is vendored into nonoun-plugins to gate the products there). This repo auto-enables it via `.claude/settings.json`.
- **`harness-forge/`** — the latticed-agentic-workflow kernel (typed lattice + a code-bounded autonomous loop).
- **`agent-ops/`** — author/operate/review agentic systems + the repos they live in.
- **`dev-factory/`** — the self-hosting dark factory built on `harness-forge` (its own nested marketplace + path-filtered `dev-factory.yml`).

No build system; plugins are markdown + stdlib Python (3.8+). "Testing" = the gates in CI (`.github/workflows/ci.yml`), all clean-checkout-true.

## Conventions (carried from nonoun-plugins)

- **Self-contained plugins, zero cross-plugin dependencies.** CI orchestrates cross-plugin checks; plugins never import each other.
- **Keep the four descriptions in sync** — `marketplace.json` entry · `plugin.json` · `README.md` · `CHANGELOG.md` (gated by `check-manifest-sync.py`).
- **Critic personas are obscured (D-4): never commit real names** to `agents/critic-*.md`, reviews, or rosters; real-name bios live in gitignored `agents/.name-map.md`. Reuse is allow-listed in `KNOWN_AGENT_REUSE`; dispatch critics by plugin-scoped name (`<plugin>:critic-<name>`).
- **Project STATE under `.agents/`** (harness-forge → `.agents/harness/`, agent-ops → `.agents/brain/`); config/wiring under `.claude/`.
- **gen-index** bakes versions + enumerates `git ls-files`: regenerate `index.html` after any version bump OR new tracked file (`gen-index.py --check` in CI).
- **Gates clean-checkout-true** (R-1/D-6): green locally must imply green on a fresh clone; replay against `git clone . /tmp/ci-repro` before pushing.

## Relationship to nonoun-plugins

`nonoun-plugins` (brand-forge, product-forge) is the product marketplace. It **vendors this repo's `plugins-factory/bin` gate suite** (synced + drift-checked) so its CI validates the products without an in-repo plugins-factory. The brand/product council-calibration **recall corpora + judge records** live in nonoun-plugins (their checkers are there); this repo carries only the factory-plugin judge artifacts.

## Commands

Smoke-test bins, then validate with the gates (Python 3.8+):

```bash
PF=plugins-factory
python3 "$PF/bin/validate_plugin.py" marketplace .          # validate the manifest + cross-plugin collision check
python3 "$PF/bin/check-manifest-sync.py" harness-forge      # four-descriptions sync
python3 harness-forge/bin/lattice.py selftest               # the kernel proves itself
python3 tools/sync-dev-kernel.py --check                    # harness-forge kernel vendored into dev-factory, in sync
```
