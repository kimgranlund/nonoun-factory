# real-verifier-teeth — answer key

`replay.py` closes the blind spot the harness-council named (H2-M1): in CI the adapter is always `MockAdapter`, so every `verify.mjs` is the lenient presence stub — green CI proved the *mock loop closes on itself* and **nothing** about whether a real spec-conformance gate works. The #2 fix's whole value (factory-authored verifiers that mean "implements the spec") was therefore untested.

This eval drives a **real** spec-conformance `verify.mjs` through the kernel's actual signal-minter (`validate.run_validation` — the exact path `dispatch` uses; verdict = the verifier's exit status) over a `compute(a,b)` contract, and proves the gate both bites and is satisfiable — and that the stub it replaces is blind to the same deviation.

| # | Asserts |
| --- | --- |
| **H1** | a REAL `verify.mjs` (asserts the contract's VALUES — `compute(2,3)===5`, `compute(10,0)===10`, `compute(4,4)===8`) REFUSES a deviating module (`compute = a*b`): a `fail` signal is minted from the nonzero exit and the cell is NOT advanced (stays `instantiated`) |
| **H2** | the SAME `verify.mjs` PASSES a conformant module (`compute = a+b`): the cell advances `instantiated → validated` and a real `pass` signal lands on disk (minted by the validation path, worker-deny). A gate that never passes anything is useless — a real gate must be *satisfiable* |
| **H3** | the CONTRAST that motivates the #2 fix: the seeded MOCK smoke stub (only `typeof m.compute === 'function'`) PASSES the SAME deviating module H1 caught — a presence predicate is structurally blind to a value/behavior deviation. This is the rubber stamp green-under-the-mock was hiding |

Both modules export `ready = true` and a `compute` function, so they are indistinguishable to a presence stub; only a behavioral gate separates them. That separation — refuse the wrong answer, accept the right one — is the property the verifier-author DEFAULT exists to install, now regression-guarded in CI.

Needs `node` (the verifier is a real ES-module harness); skips with exit 0 if node is absent. Complements the unit coverage in `dispatch.py selftest` (`_is_mock_verifier` discriminates seed-stub vs. real harness by behavior, not line count) and `validate.py selftest` (exit-status → signal).
