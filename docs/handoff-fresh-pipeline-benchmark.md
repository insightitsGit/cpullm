# Handoff: fresh-data full request-pipeline benchmark

Prepared 2026-10-27. **Design only; benchmark not executed.**
Implement and execute [this specification](benchmark-design-request-pipeline.md).
The goal is to measure the new separator together with retrieval, bounded joins,
response depth, clarification, and final delivery judgment on fresh fictional data.

## Read first

- [Current implementation contract](current-design.md).
- [Separator](request-separation.md) and [depth classifier](response-depth.md).
- [Prior benchmark integrity findings](reviews/2026-10-26/benchmark-followup-review.md).
- Historical harness: `docs/benchmarks/2026-10-25-baseline/run_eval.py`. Reuse useful
  environment/snapshot helpers after review; do not reuse its scorer blindly.
- Live examples: `tests/test_request_planner_live.py`, `tests/test_join_pipeline.py`,
  `tests/test_evidence_judge.py`, and `tests/test_response_policy_live.py`.

At preparation HEAD was `cab025efe2524a40d8dbe1e72d61fc10d27859f6` and the tree
was clean before these two documents were added. Re-snapshot the actual checkout
when you run; do not assume this revision is still latest. Earlier 545-pass suite
evidence is historical, not a result for the new corpus or a new checkout.

Include the subsequent combined-response-budget fix in the evaluated snapshot.
Record its actual commit or exploratory patch; its 90-pass focused validation is
development evidence, not a result for this benchmark.

## Required budget checks

The design's combined-budget section is mandatory. Verify shared allocation
before generation, brief/default/detailed totals, local instruction ceilings,
global counts below task count, long-background invariance, and clarification
resume. Capture parent allocation metadata and actual child producer ceilings.
Check that aggregate rendering removes repeated question headings while retaining
every task outcome and all proof/citations. Include scorer fixtures for a valid
proof exceeding budget, optional material exceeding its child ceiling, and a
short response that silently omits a task. Never treat required-proof overflow
as a hard word-limit failure. Report length alongside coverage and correctness.

## Work sequence

1. Inventory installed Python, CPU models, PostgreSQL/pgvector and constructor/API
   settings. Use an isolated disposable database and working directory, never a
   user's current database. Keep model downloads disabled for primary arms.
   Store credentials outside artifacts. Record fresh-extension bootstrap behavior.
2. Build a new runner under `tools/benchmarks/` (create directory if needed), with
   explicit corpus/gold/run paths, seed, dense/resonance arm, and scale options.
   Require a new `--out` directory and refuse overwrite before database mutation.
   Document the actual CLI you implement; no runnable CLI exists for this design
   yet. Add read-only instrumentation for retrieval stages and call counts.
3. Author and audit the 120+ factual/300 distractor paragraphs, 180 standalone
   cases and 24 conversation scripts specified in the design. Make a machine
   coverage manifest that enforces family counts and split assignments. Validate
   all referenced paragraph IDs and independent proof sets before asking the app.
4. Test the scorer using the deliberately good/bad response fixtures in the design.
   Keep false assertions, omissions, abstentions, clarification, conflict, and
   contract inconsistencies separate. Freeze and hash the holdout before its run.
5. Run the development set first, with a fresh namespace per arm. Report observed
   failures without changing the library or gold to fit the answers. Repair a
   demonstrable harness defect with a new scorer version and retain old outputs.
6. Once infrastructure is valid, run the frozen holdout on both arms and paired
   atomic-query references. Run all scripts with original parent session IDs;
   assert child pending/resume states and caller/history isolation at every turn.
7. Run the complete test suite with live database tests enabled. Record failures,
   skips, expected failures and warnings; do not silently deselect tests. An
   unavailable optional model is an explicit untested arm, not a passing result.
8. Run the 1k/10k scale and timing phases after correctness. Set an explicit timeout
   and record it. Keep incomplete scale data clearly labeled. Stop only resources
   created for this run, and preserve all artifacts before cleanup.
9. Produce the report, failure catalog, and next implementation handoff. No runtime
   fixes, commit, push, or benchmark result replacement are part of this handoff.
   A later fix should be a separately reviewed change and a new run ID.

Example existing suite invocation in PowerShell, after provisioning an isolated
database and setting its DSN through your local environment:

```powershell
$env:CPU_LLM_LIVE_TESTS = '1'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -u -m pytest tests -ra --tb=line -p no:cacheprovider
```

Set `VECTORPRISM_PG_DSN` to that disposable database before running. Check the
process exit code and verify live tests actually ran; the environment flags alone
do not prove this. Capture actual environment/version/setup commands in the report.

## Deliverables and completion

Return clickable paths to the immutable run report, corpus and gold manifests,
raw per-turn/per-child responses, retrieval traces, scorer source/fixtures,
metrics, suite output, timings and a prioritized failures file. Each failure must
contain case/turn/task ID, prompt/options, gold proof, actual public response,
retrieved IDs, expected versus actual semantic outcome, reproduction command,
and suspected stage: planning, reference, intent, extraction, retrieval, join,
selection, judge, rendering, session, scope/history, or scorer.

The report must answer: which families work; what the separator changed; whether
required proof was retrieved but lost later; what clarifications completed;
whether dense or resonance is better by family; what failed safely versus made a
false assertion; whether larger corpora changed results; and which readiness
gates passed. Include exact denominators and excluded contract disagreements.

Completion means fresh corpus and frozen gold exist, both primary arms and
conversation scripts have raw results, scorer review is documented, suite results
are recorded, and scale phases are completed or explicitly reported as blocked/
timed out. Missing phases prevent calling this a full completed benchmark.
Do not claim the library is production-ready solely from this synthetic run.
