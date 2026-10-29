# Agent handoff: execute prompt/output benchmark v3

Prepared 2026-10-29. **This is a handoff, not a completed benchmark.** No other
agent has been started or messaged. The evaluator described below must be built;
the existing v2 runner is not a ready-made v3 runner.

The implementation and specification are now being versioned together. Select
the commit containing this handoff and [the change record](change-record-2026-10-29.md)
when the checkout is clean. References to uncommitted changes at handoff creation
describe the design-time state, not a requirement to use the historical base HEAD.

Read [the design](benchmark-v3-design.md) and
[the protocol JSON](benchmark-v3-spec.json) first. Use this prompt for the agent:

> Run the prompt/output benchmark v3 specified in these two files. First freeze
> the actual current implementation, including uncommitted and untracked source,
> and build/install its wheel in an isolated environment. Implement the v3
> evaluator and independently authored fresh gold, validate its adversarial
> fixtures, then execute paired rules/spaCy arms, the complete live suite, known
> regression replay, and the fresh development/holdout cases and conversation
> scripts. Exercise long responses, Tabulate/Jinja2 formats, visible output and
> complete proof. Produce reproducible artifacts, a failure catalog, independent
> adjudication where available, and ranked architectural improvements. Do not
> modify library runtime code or tune against holdout during the run. Preserve
> every failure and previous artifact. Do not publish, push or create another
> agent/chat unless the user separately requests it.

## Ordered execution

1. Inspect status, current source and project instructions. At handoff creation,
   base HEAD `a9c4591` does not include the new features. Record the actual state;
   use a new commit supplied by the user or an immutable working-tree source bundle.
   Execute the extracted snapshot, with import-path assertions and file hashes.
2. Create a new timestamped output root, e.g.
   `build/benchmark-v3-2026-10-29-<snapshot-id>-<run-id>/`. Refuse reuse. Use isolated
   runtime directories, virtual environments and databases, not existing tenant data.
3. Pass clean-install gates, including ingestion, real model loading and built
   distribution metadata. Install optional spaCy assets explicitly during setup;
   disable downloads for actual requests. Confirm automatic fallback configurations
   separately from the two forced-backend quality arms.
4. Build evaluator code under `tools/benchmarks/prompt_output_v3/` in the evaluation
   workspace. This path is **proposed and does not exist yet**. Reuse existing
   transport/snapshot helpers only after checking their assumptions. Version the
   evaluator separately from the frozen runtime and record both hashes. Implement
   commands for prepare, scorer-selftest, setup, regressions, suite, development,
   holdout, timing, optional scale/resonance, and report. Document actual CLI usage.
5. Author new corpus, 240 standalone cases and 24 scripts with the fixed family/
   split counts. Freeze expected capability classes, gold, scorer and hashes before
   official calls. Keep old test subjects/examples only in regression replay.
6. Run scorer adversarial fixtures. The existing command below is useful for
   legacy checks, but does not certify new HTML/table/depth/workflow scoring:

   ```powershell
   python -m tools.benchmarks.request_pipeline.run_eval --phase selftest
   ```

7. Run the complete live test suite on the frozen runtime and retain logs. Set
   `CPU_LLM_LIVE_TESTS=1`, `VECTORPRISM_PG_DSN` to a disposable database and the
   offline model environment variables only after assets are verified. Make
   pytest collect the snapshot's tests. On Windows, use a guarded `main()` runner;
   do not let spawned workers re-enter database setup or pytest.
8. Run paired core arms and scripts through public `ask()` on original prompts.
   Do not repair prompts in an external wrapper. Use fresh state per split/arm and
   bounded timeouts. Freeze runtime and scorer throughout holdout execution.
9. Complete mandatory quality/reporting before optional scale. A failed or timed
   optional arm remains separately labeled; it cannot block delivery indefinitely.
10. Audit all failures/uncertain scores and the fixed passing sample. Publish raw
    and reviewed counts, review limitations, representative actual outputs and
    root-cause improvements. Do not silently apply fixes and replace the run.

## Environment notes from this checkout

- Windows/PowerShell, development Python 3.12.10. Previous smoke environments and
  model assets exist under `build/`, but they are not clean-install evidence for
  this new run. Create fresh environments and record intentional cache reuse.
- The earlier disposable native PostgreSQL cluster was
  `build/join-audit-pgdata`, port 55433, with PostgreSQL 18 binaries under
  `C:/Program Files/PostgreSQL/18/bin`. It was stopped at the end of prior work.
  Verify current status and availability before use; do not assume it is stopped
  or reuse its application databases. Docker/another disposable service is fine.
- In this sandbox, loopback/network operations may need ordinary tool escalation.
  If using a managed native server, start, run and stop it in one approved process
  with `try/finally`; interrupting a wrapper can otherwise leave a stale PID marker.
  Verify server/process/listener status before altering any stale marker. Do not
  disable host safeguards or change a production service.
- Set writable workspace-local `TEMP`, `TMP` and pytest `--basetemp` if the
  restricted runner's default Temp directory is inaccessible. Do not classify
  sandbox Temp/network failures as product defects without reproduction outside
  those restrictions.
- Prior source snapshots/results include `build/template-flags-validation/`,
  `build/template-flags-suite.log`, `build/template-flags-dist/` and
  `build/clean-install-audit/`. They are known development artifacts. Preserve them;
  they do not replace the new source freeze, clean install or unseen holdout.

## Required artifact layout

Use equivalent names only if documented in the manifest:

```text
manifest.json
snapshot/                    # source archive, file hashes, base HEAD/status/diff
environment/                 # lock, platform, model/checkpoint hashes, import paths
install/                     # wheel/sdist, metadata, setup matrix and smoke logs
gold/                        # corpus, corrections, cases, scripts, frozen hashes
scorer/                      # evaluator source/version and adversarial selftests
suite/                       # complete live pytest output, exit and actual counts
regressions/                 # separate known-case replay
raw/rules/ raw/spacy/         # original prompts, complete results and stage traces
metrics/                     # per-dimension/family/split/arm, paired deltas
timing/ optional/            # cold/warm stage timings; explicitly optional experiments
review/                      # failure catalog, pass sample, adjudications
REPORT.md
NEXT-IMPROVEMENTS.md
```

The report must answer: Does spaCy improve supported human wording? Which requests
still need clarification or remain unsupported? Do length flags retrieve and use
more eligible facts without padding? Do Markdown/HTML layouts preserve the actual
visible claims and citations? Do joins retain both authorized premises? What are
the latency and installation costs? Which next improvements address entire
failure categories rather than the benchmark's particular words?
