# CPU-LLM 1.12.1 capability and reliability benchmark

Evaluate the installed release wheel against a disposable PostgreSQL database with pgvector. Record the wheel hash, Git revision, Python and dependency versions, hardware, encoder assets, and test switches. Freeze prompts and expected outcomes before scoring. Keep live release tests separate from capability scores.

## Tracks and scoring

- **Installation and ingestion** covers a fresh install, dependency checks, CLI entry points, supported document formats, source replacement, and ingestion time.
- **Retrieval and strict evidence** covers direct and joined facts, aliases, missing and conflicting evidence, citation integrity, and caller or tenant isolation. Compare with a local retrieval baseline where available.
- **Prompts and conversation** covers short and long prompts, multiple tasks, clarification, correction, and batch continuation. Score each task and the conversation outcome separately.
- **Reports and presentation** covers short and detailed responses, articles, tables, lists, and tone. Score evidence coverage, output format, response budgets, and retention of citations.
- **Deterministic checks** covers exact finance decisions, rounding and missing fields. Compare with independently calculated values.
- **Research and invention** covers research routing, relationship loops, cited hypotheses, and follow-up depth. Credit a follow-up for additional cited evidence, a computed result, or a specific missing dependency.
- **CrossDomain and Constraint Check** covers two, three, and seven KBs, missing premises, model versus bound, measurements after unit conversion, and incompatible conventions.
- **Numerical scans and scale** covers a synthetic intersection with known answers, the illustrative leptogenesis scan, and retrieval under larger corpora. Record accepted points, boundary brackets, timings and peak memory when measured.

Gold records specify required status, citations, forbidden claims, and output fields. Report pass counts, wrong answers and abstentions by track and arm. Keep dense and identity projection evidence distinct from symbolic and disabled channels. Use blind human scoring for research usefulness where reviewers are available. Report missing tracks as unrun. Unauthorized evidence, false strict citations, and wrong deterministic decisions block release sign-off.

## Execution plan

Use the fresh request-pipeline development and frozen holdout cases with dense and resonance configurations. Run the local strict evidence benchmark with its canonical lookup and Decimal baseline. Add a live baryon asymmetry walkthrough for the invention, CrossDomain, Constraint Check, and numerical scan paths. Replay the release tests for additional functional coverage. Scale runs use the same probes against a larger corpus and report the corpus size and measured latency. Keep exact replies and raw receipts alongside summaries. Hosted comparison and independent human review are separate arms.

Install the 1.12.1 wheel in a dedicated environment and use that environment's
Python for the following commands. Set `VECTORPRISM_PG_DSN` to the disposable
database `cpullm_bench_271027` with the vector extension enabled. Prepare the
encoder assets before starting offline runs. Use fresh output directories.

```shell
python tools/benchmarks/request_pipeline/run_eval.py --phase selftest
python tools/benchmarks/request_pipeline/run_eval.py --phase prepare --corpus fresh --out build/capability/request
python tools/benchmarks/request_pipeline/run_eval.py --phase dev --arm both --out build/capability/request
python tools/benchmarks/request_pipeline/run_eval.py --phase holdout --arm both --out build/capability/request
python tools/benchmarks/evidence_v2.py --out build/capability/evidence
python tools/benchmarks/capability_1121.py --out build/capability/features
```

The feature runner's scale smoke uses ten strict lookups before and after
ingesting 1,000 distractor chunks. Its nearest-rank p95 is the largest of the
ten samples. Use the request-pipeline runner's separate scale phase for larger
corpora, mixed prompts, and additional order seeds.

## Run record

The November 10, 2026 run used the installed 1.12.1 wheel from revision
`f04dd25f147d0f61ce5f919085ad802a216b68c3` on Windows x64 and CPython 3.12.10.
Wheel SHA-256 was `386551c04ca75ed9376c285e99d74e587de2ec2798038d040136317a89b64e02`.
Raw replies, scorer receipts, and environment snapshots are under
`build/capability-1.12.1-2026-11-10`.

- The scorer passed all 27 self-tests. Fresh request cases scored 390/460 across both arms, including conversation turns. Dense scored 201/230 and resonance 189/230. The full contract passed on 211/278 gold-expected answer rows, below the 95% gate. Authorization cases passed 48/48. The scorer flagged zero false assertions and zero silent task losses on this run.
- Strict evidence scored 42/42 and the local lookup plus Decimal baseline scored 25/42. These are fictional evidence-handling cases.
- Feature and scale probes passed 31/31 on the completed retry. The seven-KB join cited all seven sources, Constraint Check handled unit conversion, source replacement and incompatible conventions, and the automatic scan reproduced 30/4,000 accepted samples and 140 brackets.
- Adding 1,000 distractor chunks took 10.82 seconds. All 20 strict lookup probes passed. Median latency was 0.55 ms before and 6.39 ms after ingestion. The ten-sample p95s were 7.57 ms and 6.62 ms, respectively. These are smoke measurements from a single host.

The installed release test run is separate and recorded 1,110 passes, two skips,
and three expected failures. Independent human review, hosted comparison,
peak memory, and the larger mixed-query scale run were outside this execution.

The saved 1.13.1 request scores show 229/278 answer-like responses (82.4% coverage) and 211/229 full contract passes among delivered answers (92.1%). On gold-expected answer rows, 30 insufficient-evidence replies and 17 clarification replies had no flagged false assertion, and two replies were budget refusals. Across the suite, 84 gold-expected abstentions passed and the scorer flagged zero false assertions. These figures describe the synthetic suite and its configured checks. Whether a missed row was truly answerable requires review of the prompt and source evidence.
