# nonoun-factory

The **builder/operator toolchain** — a Claude Code plugin marketplace for *making and operating* agentic systems and plugins. Its sibling, [`nonoun-plugins`](https://github.com/kimgranlund/nonoun-plugins), holds the domain *products* (brand, product). Every plugin here is a self-contained worked example of the five-primitive component model (skill · agent · command · hook · MCP), authored and adversarially red-teamed with `plugins-factory`.

```
/plugin marketplace add kimgranlund/nonoun-factory
/plugin install plugins-factory@nonoun-factory   # the lifecycle tool (build + judge plugins)
/plugin install harness-forge@nonoun-factory     # the latticed-agentic-workflow kernel
/plugin install agent-ops@nonoun-factory         # author/operate/review agentic systems + repos
```

| Plugin | What it does |
| --- | --- |
| **`plugins-factory`** | Run the plugin lifecycle against one 9-dimension architecture standard, judged by a 9-critic council. Build with `/plugin-author·carve·edit`; judge with `/plugin-score·critique·promote`. The catalog's own validator. |
| **`harness-forge`** | Hydrate a project to run looping, latticed agentic workflows — a typed knowledge-lattice kernel + a bounded autonomous loop whose caps are enforced in code by a consent-wired stop-gate. |
| **`agent-ops`** | Author, operate, and review full-spectrum agentic systems and the repos they live in, with a named-practitioner council + verifiable gates + a repo-memory MCP. |

Nested marketplace: **`dev-factory/`** — the self-hosting "dark factory" built on `harness-forge` (its own `dev-factory/.claude-plugin/marketplace.json` + path-filtered CI).

Split out of `nonoun-plugins` (2026-06-17) so the builder toolchain and the domain products each have their own marketplace + audience. Stdlib Python only; CI is clean-checkout-true.
