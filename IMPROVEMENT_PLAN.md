# Defensive integration priorities

Baseline reviewed at `e3ddaa62344616cfe0a53417a25135f99396e7d9`. All 21 tests pass on Python 3.10 and 3.14. The offline workflow uses a fresh CI run ID, fails on incomplete evidence or a regression, and publishes the sanitized report when available.

| Area | Coverage at the baseline commit | Gap identified in the audit |
| --- | --- | --- |
| Retrieval isolation | `retrieval-source` checks the reported source. `tenant-scope` checks recorded actor and visibility labels. | A correct answer and source label can coexist with an extra document in the context delivered to the model. A harness needs an explicit boundary to observe and a way to assert the entire source set. |
| Tool approval | The allowed and denied cases check proposal, decision, effect, and the isolated sink snapshot. A wrong record or value fails. | The contract cannot express which exact action a confirmation authorizes. Multiple actions or intervening edits need observations from the app that binds confirmation to dispatch. |
| v2 export | Strict mode enforces the independently supplied run ID, exact suite hash, unique case rows, and complete evidence. The CI wrapper preserves the gate exit. | The reference collector is tied to the bundled suite. An integrator still has to work out where to read observations, which IDs to use, and how to distinguish a missing observation from an observed empty result. |
| Setup and CI | Strict mode runs on Python 3.10+ with the standard library. The CI recipe supplies a run ID to the reference exporter and gate. | A first custom integration needs a small outside-the-reference example and concrete triage for failed assertions, incomplete evidence, and invalid run or suite binding. |

## Order of work

1. Add an opt-in exact source-set assertion for v2 and a small standalone synthetic exporter. Observe the final context selected by the application before it reaches a model. Verify an allowed source set, an extra source with otherwise correct utility and provenance, and missing or malformed capture. Exercise the CI wrapper and check report redaction. Preserve the bundled 12-case suite and its evidence.
2. Add a synthetic approval-binding case when a consumer can export the action and record IDs seen at approval and dispatch. Check a matched approved action and a denied action with no sink effect. Use mock records and an in-memory sink.
3. Use independent pilot feedback to prioritize v2 setup and diagnostics beyond the example. Likely next fixes are field-specific validation feedback that omits values and a consumer CI example that gates only the relevant test path while reporting a consistent check.

## Optional offline model comparison

A matched base and abliteration-modified checkpoint could test whether a real model adapter preserves task scoring and whether application controls hold across different reply behavior. Run the same benign canaries through both checkpoints, with local weights, a pinned runtime and template, and equivalent decoding settings. Record the exact checkpoints and quantization. Compare task completion separately from the final retrieval context and the mock tool sink, and cover both granted and denied approvals. The canaries may produce identical replies, and the result applies to the exact harness, checkpoints, and fixtures tested. Model refusal can be affected by checkpoint changes. [Arditi et al.](https://arxiv.org/abs/2406.11717)

No matched pair was available in the local model stores checked. Deterministic answer and abstention cases are sufficient to exercise the reporting contract in routine CI. A real model comparison is an optional follow-up. Local tests, hosted CI, and model comparisons are separate from the independent pilot evidence required for stable release.

## Local results

| Item | Verified result |
| --- | --- |
| Approval binding | Four baseline cases pass. Both mock actions can dispatch when granted to the exact target. Changing either identifier after approval leaves the sink empty. A recorded mismatched grant, different dispatch, duplicate, missing dispatch, or dispatch after denial fails with exit 1. Partial capture exits 2. |
| Retrieval isolation | Both baseline variants pass. The exported IDs match the actual context passed to the mock model. An extra or missing source fails even with correct utility and citation. Missing or malformed capture exits 2. |
| v2 export | The bundled 12-case suite passes. Stale run IDs, wrong suite digests, conflicting suite expectations, and malformed exports fail closed. Diagnostics name the affected schema field where available. Report redaction is covered by regression tests. |
| Consumer setup and CI | Both standalone exporters work with Python 3.10 and 3.14. Local Git histories exercise relevant changes, explicit unrelated-change summaries, missing base history, and gate exits 0, 1, and 2. The [CI recipe](EVIDENCE.md#ci-recipe) includes the corresponding consumer workflow. |

Hosted execution of the consumer workflow and behavior in an integrated product remain unverified for this local diff. Stable release requires independent, uncoached retrieval and tool-approval receipts, including at least one complete v2 export from a participant's own synthetic harness.
