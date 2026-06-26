---
description: The cultivation workflow — author / cultivate a PRD or SPEC as prose, run the spec-council + quality gate, then COMMIT (crystallize): derive its checkable acceptance via a non-executor party, certify entailment, the human seals, and a validated cell is minted that decomposes into draft tickets. Commit is the crystallization gesture — NOT git commit.
argument-hint: "<doc> [commit]   (e.g. prd  ·  spec/cli  ·  spec/storage commit)"
---

Cultivate a document toward commit. **$ARGUMENTS**

A document lives as **freely-editable prose** (`draft → cultivated`) until the human commits it. This command runs the **cultivation** workflow and, on `commit`, the **crystallization** that turns prose into a typed, gated artifact. The first argument is the doc (`prd`, `spec/<name>`); add `commit` to crystallize.

**Cultivate.** Author / refine the doc as prose against the vendored `dev-kernel` spec-format discipline — a PRD carries narrative-acceptance, a SPEC carries checkable-acceptance + non-goals + a decomposition (and `depends_on` its PRD). Mark it `goal: true` to make it an `/app-goal` destination. The **spec-council** + the **spec-quality / prd-quality** gate run **advisorily** while cultivating, so findings land before commit.

**Commit (crystallize) — `/app-spec <doc> commit`** — a server-mediated sealing, **not `git commit`**. The mechanized backbone is two gestures, because the human seal is a real judgement, not a flag the script grants itself:

```
# 1. crystallize: gate → mint spec cell → seal bars by copy → teeth-check → mint rubrics INSTANTIATED
python3 "${CLAUDE_PLUGIN_ROOT}/bin/app-commit.py" projects/<name> spec/<doc>.md

# 2. seal (only AFTER the entailment-critic certifies fidelity AND the human approves):
#    promotes the teeth-checked rubrics instantiated → validated, making them loop-ready
python3 "${CLAUDE_PLUGIN_ROOT}/bin/app-commit.py" projects/<name> spec/<doc>.md --seal
```

The flow fires **quality-gate → derive (`app-factory:acceptance-deriver`) → certify-entailment (`app-factory:entailment-critic`) → human-seal (`--seal`) → mint**, in order; **any failure rejects the commit** (the doc stays `cultivated` with the findings). The spec cell mints to `validated` **through the real signal path**, and each rubric is **teeth-checked** (the sealed bar must FAIL against an empty build — a tautology / presence-check is rejected) and minted **`instantiated`**; it becomes **`validated`** only at `--seal`, the human's act after the entailment-critic certifies the bar faithfully entails the prose. Until then the loop's `dispatchable` refuses it — a teeth-only bar is never auto-trusted. Each spec→ticket edge is stamped with the spec's content hash; `app-commit.py` **refuses any ticket whose sealed bar is absent**.

This is the keystone's predicate-honesty half — **no agent both derives a ticket's acceptance and executes it**; the bar is machine-derived, independently certified, and human-sealed, never authored by the worker graded against it. The full pipeline (the 5-step commit sequence + the runnable backbone) is **`references/cultivation.md`**; the two honesties + the regenerate path + the prose-is-not-a-directive rule are **`references/keystone.md`**.
