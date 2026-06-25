# Cultivation → commit (crystallization) — the full sequence

The deep mechanics behind `/app-spec`, lifted out so the command stays a thin router. The two honesties + the earned-autonomy model are in [`keystone.md`](./keystone.md); this doc is the cultivation/commit pipeline.

## Cultivate (author / refine)

A document lives as **freely-editable prose** (`draft → cultivated`) until the human commits it. Invoke the cultivation skill in the doc's mode:

- A **PRD** carries **narrative-acceptance** — a usage narrative, *never* an `/app-goal` predicate.
- A **SPEC** carries **checkable-acceptance** (an executable check or a validated rubric cell) + non-goals + a decomposition, authored as prose first against the vendored `dev-kernel` spec-format discipline. When a PRD exists the SPEC `depends_on` it (never "spec atop air"). Mark it `goal: true` to make it an `/app-goal` destination.

Run the **spec-council** + the mechanical **spec-quality / prd-quality** gate **advisorily** while cultivating, so findings land *before* commit, not after.

## Commit (crystallize) — the order, any failure rejects

`/app-spec <doc> commit` is a server-mediated sealing, **not `git commit`**. It runs in order; **any failure rejects the commit** — the doc stays `cultivated` with the findings, never a committed-on-red limbo:

1. **Quality gate fires** (prd-quality / spec-quality). Red → rejected.
2. **Acceptance is derived by a non-executor party** — the `app-factory:acceptance-deriver` agent, drawn from a family **disjoint from any executor under the same goal** (enforced at dispatch, never requested in prose), producing the typed checkable-acceptance from the prose.
3. **Independent entailment check** — `app-factory:entailment-critic` certifies the derived predicate **faithfully entails the prose intent** (the fidelity check the deriver cannot reach) and is **deterministic** (calibration record). Fail → rejected.
4. **The human seals** — reviews and *seals* the certified acceptance. An authorship act, not a rubber-stamp; a bare confirm does not satisfy it.
5. **Cell minted + decomposition proposed** — a `validated` spine cell is minted, the spec→ticket edge is stamped with the spec's content hash (the ticket's `validated_against`), and commit proposes **draft** tickets — live work only via triage (`ticket-ready`).

## The runnable backbone

Steps 1 and 5 are mechanized:

```
python3 "${CLAUDE_PLUGIN_ROOT}/bin/app-commit.py" projects/<name> spec/<doc>.md
```

It runs the gate (`app-spec-gate.py`), mints the spec cell to `validated` **through the real signal path** (the gate is the cell's verifier — doneness is a signal, not an assertion), decomposes the contract into draft ticket files + ready `capability`/`rubric` cells, and stamps each spec→ticket edge with the spec's content hash. Steps 2–4 (derive · entail · seal) are the agents + the human producing the sealed acceptance scripts under `.factory/acceptance/` that the crystallizer consumes — `app-commit.py` **refuses any ticket whose sealed bar is absent**, so a bar that was never derived + certified + sealed cannot crystallize.

After commit, edits flow through the **regenerate** path: a flip back to `cultivated` cascades `stale` to decomposed tickets and invalidates their signals; the bar a failing loop missed may be **raised**, never **lowered** by the party that failed it.
