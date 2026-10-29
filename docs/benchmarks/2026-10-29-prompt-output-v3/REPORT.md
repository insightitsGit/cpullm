# Prompt/output v3: provisional public run

Executed October 29, 2026 against fixed runtime **`24150c640de97505ef049ea2232619414c0aa156`**. The documentation/evaluator commit containing this report is later than the tested runtime. No runtime code was changed for this run.

**This is a completed public-case execution, not a completed v3 acceptance benchmark.** Scorer/gold limitations and missing protocol gates below prevent a release-readiness claim.

## Recorded scores

Using corrected independent scorer `prompt-output-v3-scorer-2` on the original saved responses:

- Rules: **215/240 core cases, 89.58%**; **28/32 public routing cases, 87.50%**; **68/68 scripted turns, 100%**.
- Real spaCy: **219/240 core cases, 91.25%**; **28/32 public routing cases, 87.50%**; **68/68 scripted turns, 100%**.
- Total: **680 executed requests**, including 32 scripts / 68 turns per arm. Script scores count turns, not independent standalone cases or whole-script successes.
- On the narrower positive-answer core subset, rules pass **135/156 (86.54%)**, spaCy **139/160 (86.88%)**. Rules excludes four explicitly spaCy-only positive tasks. Neither reaches the proposed 90% supported-answer threshold under this provisional oracle; the overall core percentages include successful nonanswers.
- Required/forbidden node, order and post-stage checks pass on all 64 public routing requests. Their eight remaining failures are answer-outcome expectations for unsupported comparison requests, not observed node-order failures. Routing evidence is distinct from answer quality.
- No execution exceptions or private-canary disclosures were detected. This finite canary check does not establish complete confidentiality or absence of semantic errors.

The full fixed-source suite ran in the clean wheel environment: **709 passed, 2 skipped, 3 expected failures, 0 unexpected failures**. The initial standard invocation skipped 22 opt-in live tests; all 22 were then executed successfully with `CPU_LLM_LIVE_TESTS=1`. These counts combine those two invocations without counting the skipped live tests twice. The remaining skips need absent extractor checkpoints. Six NumPy overflow warnings remain recorded. See `test-summary.json`, `suite.xml`, and `live-suite.xml`.

## What improved, and what failed

The paired difference is four conversational attribute requests: the real spaCy backend interprets the supported “Please give me information about the color of …” wording. In the rules arm, some of these requests return a retrieved sentence about a different entity rather than a safe nonanswer. That is a substantive intent/evidence-binding gap, even though the sentence exists in the corpus.

Per arm, the corrected core scorer reports:

- Access/history, attribute slots, field lists/task coverage, instruction/data distinction, output layouts, missing/unsupported questions and response-depth cases: **20/20 each**. Passing this narrow synthetic coverage does not establish all variants of those features.
- Conversational normalization: **16/20 rules, 20/20 spaCy**.
- Join/retrieval repair: **17/20**. Three possession requests return a directly supported handle but omit the additional universally inherited component required by the authored expectation. These are completeness failures; the observed direct handle claim is supported.
- Meaning/reference: **18/20**. Two failures have an alternative source sentence that directly establishes the expected type using an alias construction. The gold specifies only the separate type sentence. These are likely overly restrictive proof expectations and require explicit gold adjudication before an acceptance score. They remain failures in the frozen reported scores.
- Existing specialists/templates: **16/20**. Four Markdown-report overview requests abstain despite stored facts. Trace the overview producer/hold/composition path before changing the renderer.
- Proof/display fidelity: **8/20**. Twelve requests ask for an attribute value containing a literal pipe, tag-like text and Jinja-looking braces. Retrieval/answerability returns insufficient evidence rather than the expected value; the rendered nonanswer is not evidence of template execution. A separate controlled renderer fixture is still needed to establish literal preservation independently of factual extraction.

Long summaries can include nearby entities' facts. The current overview gold checks minimum supported facts and budgets, not exhaustive relevance to the requested subject. Do not interpret 20/20 depth scores as proof that every summary sentence is relevant. No runtime fixes were made from these observations.

## Evaluator correction and limits

The original scorer reported core **191/240 rules** and **195/240 spaCy**, routing **24/32 per arm**, and scripts **66/68 per arm**. Those results remain in `summary.json` and the compressed raw result records.

Two independently identifiable evaluator defects were corrected in a separately versioned file, without new model calls or edits to frozen gold:

1. Successful specialists can expose their delivery outcome in `judgment.outcome` without `answer_status`. The original adapter incorrectly scored those as an empty outcome. V2 reads that field as a fallback and normalizes `clarification` to the benchmark outcome name. Visible claims and proof are still checked separately.
2. HTML table header cells may contain whitespace padding. V2 strips header padding before comparing column names. It does not remove or rewrite answer content.

Original scorer fixtures: **14 passed**. Corrected fixtures: **17 passed**, including the outcome fallback, padded HTML headers, and rejection of a wrong visible answer despite an accepted judgment field. The original scorer source remains `tools/benchmarks/prompt_output_v3/scorer.py`; V2 is `scorer_v2.py`. `rescored-v2/summary.json` lists every changed pass/fail decision.

The synthetic corpus has **630 paragraphs**: 330 factual/private/history paragraphs plus 300 distractors, with 30 corrections applied separately in each arm/split database. There are 12 core families of 20 cases, 144 development / 96 holdout cases, 32 public routing cases, and 32 scripts. Names and values are fresh, but many templates repeat across names/domains. This measures those authored contracts, not broad language ability. The literal-assertion checker is conservative and incomplete; it is not an independent general semantic judge.

## Protocol gates still incomplete

The design's 16 controlled routing fixtures were **not executed**; the gold manifest's `controlled_fixtures: 16` is a planned count, not an execution result. Also incomplete: real optional-installation setup matrix, separately scored known-failure replay, five warm timing repetitions on the prescribed 30 cases, real process-restart lifecycle, complete positive/negative flag-witness coverage, and independent gold/scorer review. Finance, explicit conflicts, causal-answer positives and deletion/reopen scenarios are not comprehensively represented in this authored core. Existing tests cover some of these but do not substitute for the benchmark protocol.

Failure patterns were inspected by the executing agent; this was not an independent review, and exhaustive failure/passing-sample adjudication remains pending. The two alternative-proof failures and unsupported comparison targets need adjudication. Do not silently relax their expectations or merge their scores into a new official denominator. Optional scale and resonance arms were not run.

## Setup and observed waiting times

A new virtual environment with `include-system-site-packages=false` installed a wheel built from the archived revision, the `prompt_nlp` extra, pytest, and the real `en_core_web_sm` model. `pip check` passed. Cached pretrained encoder assets were reused offline; this does not test a cold internet download. PostgreSQL 18/pgvector used disposable databases on loopback, with separate local working directories and namespace state for each arm/split. Rules and spaCy both ran with resonance disabled and no optional reference backend. The PostgreSQL cluster was stopped after execution.

First appliance construction took **58.64 seconds**; later constructions in the same process took **1.15–1.50 seconds**. Corpus ingestion plus 30 corrections took **22.90–25.38 seconds** for 630 paragraphs per arm/split. These are single-machine observations under concurrent suite load, not repeatable latency benchmarks or training estimates. No model training ran. The trained retrieval checkpoint is shipped; document ingestion is required, and Model01's `train()` is a survey without an optimizer.

## Saved evidence and reproduction

- `results/*.jsonl.gz`: complete captured result dictionaries, original prompts/contracts, search traces, timings and original scores. Non-JSON runtime values use their string representation; these files are not model tensor dumps.
- `gold/`: frozen corpus, cases, scripts, typed facts, seeds embodied by the generator, and content hashes.
- `rescored-v2/`: corrected per-request scores, selftests, changed decisions and summaries; raw runtime responses were not regenerated.
- `ingest/`, `environment/`, `snapshot/`: receipts/correction IDs, runtime import path, dependency lock, revision and wheel/source-archive hashes.
- `artifact-hashes.json`: hashes of the execution evidence exported before this report was added. Git records this report and evaluator source as well.

To reproduce, archive the recorded revision, build/install its wheel into a new environment with the same lock/model, start a disposable PostgreSQL instance with a role permitted to create databases and the `vector` extension, then run:

```powershell
# From the repository containing the evaluator; use a NEW output directory.
<snapshot-venv-python> tools/benchmarks/prompt_output_v3/run.py --out <prepared-output>
<python> tools/benchmarks/prompt_output_v3/rescore.py --out <prepared-output>
<python> tools/benchmarks/prompt_output_v3/publish.py --out <prepared-output> --dest <new-archive>
```

`run.py` requires `<prepared-output>/snapshot/HEAD.txt` and an installed wheel; it uses the documented local port 55433 and fixed disposable database names, refusing an existing results directory. For a repeat on the same server, use a new disposable cluster; it never drops prior benchmark databases. Model downloads and PostgreSQL startup/shutdown are external setup steps. See the [full design](../../benchmark-v3-design.md) and [handoff](../../handoff-benchmark-v3.md) for gates beyond this provisional runner.
