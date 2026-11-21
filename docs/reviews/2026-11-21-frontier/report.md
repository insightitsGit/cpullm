# Frontier node — implementation and AI-bottlenecks evaluation

Date: 2026-11-21. Branch: `feature/frontier-node` (from `main` at `65ce600`). Not merged.

Handoff: [`docs/frontier-node-handoff.md`](../../frontier-node-handoff.md). Design, with the decisions on its
open questions: [`docs/frontier-node-design.md`](../../frontier-node-design.md).

## Summary

- Frontier is implemented as its own pre-graph route in `src/cpu_llm/frontier.py`. It runs from
  `Frontier: <topic>.`, `ask(..., frontier=True)` (or an options object), and `"frontier": true` on `/v1/ask`.
  It is registered in the flag contract, the prompt-flag map (`.md` and `.json`) and `docs/openapi.json`.
- Every requirement in Step 2 is implemented and covered by 38 unit tests (`tests/test_frontier.py`).
- No regressions. The full suite gave 1192 passed and 3 failed on `main`, and 1230 passed and the same 3 failed
  on the branch. The 3 failures are pre-existing and unrelated.
- The end-to-end run uses 64 arXiv papers (1054 chunks) and 9 held-out findings. Frontier is fast (about 3.5 s
  per prompt) and identical from run to run, but **the hypotheses are weak**:
  - **0 of 9** held-out findings were rediscovered fully, and **2 of 9** partially (by hand adjudication).
  - Many top-ranked entries have badly chunked anchors.
  - The main limit is relation extraction. Regex noun-phrase chunking over PDF prose finds about 550 edges in
    6,800 sentences, and few edges are corroborated. The method is sound enough to evaluate, but it needs a
    real parser before its output is useful.

## Step 1: How the existing code works (main at 65ce600)

- **Research route.** `Appliance.ask` sends `Research X` / `Investigate X` and explicit invention prompts to
  `invention.execute_invention`.
  - It takes one authorized snapshot (`invention._snapshot` → `index.strict_source_rows`, capped at 10,000 rows
    and 8 MB).
  - In a two-worker `ThreadPoolExecutor` it runs `research_hypotheses.hypothesis_options` and
    `execute_nammade(..., _source_snapshot=..., _snapshot_only=True, _defer_inference=True)`. Innovation
    (`_innovation_options`) runs on the calling thread because it needs the encoder.
  - After the join, `resolve_hypotheses` runs the abductive bridge over the Nammade evaluations.
  - It then builds the research workspace and appends shared deduction with `inference.attach_inference`.
  - Stages are recorded in `routing.post_stages`: `taxonomy_invention`, `research_hypotheses`,
    `nammade_equilibrium`, `abductive_bridge`, `inference`.
- **Abductive bridge** (`abductive_bridge.py`). This is a deterministic reader of numeric bounds and regime marks
  in Nammade-compared passages, with one active ontology (SIDM: σ/m against relative velocity).
  - `collect` pairs incompatible bounds on one observable that differ on a named regime variable, and emits a
    `RelationalBridge` with `claim_status = "UNVERIFIED_HYPOTHESIS"`.
  - The research methods receipt records `promotion: "blocked"`. Nothing is written back to the index.
- **Relationship-loop search** (`cycle_exploration.py`). `CycleLimits` sets `max_rounds` (1,000; ceiling
  100,000), `max_nodes`, `max_edges`, `max_states`, `max_frontier`, `max_cycles`, `max_bytes` (64 MiB) and
  `max_seconds` (5 s, at most 60).
  - `Budget` is one ledger: `charge(kind)` raises `StopSearch('<kind>_limit')`, and `check()` raises
    `'deadline'`.
  - `explore` is a BFS over source-verified directed edges that carry channel receipts.
- **Deductive and inductive code.**
  - Rule answers live in `inference.py`: `PreparedInference`, `InferenceRequest`, registered binary rules,
    replayed proofs, and the verdicts `ENTAILED_BY_RULES`, `CONTRADICTED_BY_RULES`, `CONFLICT`,
    `INSUFFICIENT_SUPPORT` and `BUDGET_EXHAUSTED`.
  - Constraint Check (`constraint_evaluator.py`) compares sourced numeric intervals, and CrossDomain
    (`cross_domain.py`) joins scoped premises across KBs.
  - Induction is `evidence_analysis._inductive`, which needs explicit Bernoulli records.
  - **There is no pre-thinker logic on main.** PrismThinker (`thinker_pool.py`) scores retrieved evidence inside
    the ordinary graph.
- **Trigger map.** `flag_contract.FLAG_BINDINGS` is authoritative. `docs/prompt-flag-map.json` is generated from
  it and checked for exact equality by `test_flag_contract.py`, and `validate_graph_consumers` lists the
  consumers that run outside the graph.
  - `routing.executed_nodes` is appended by the graph's `register` wrapper (`pipeline._compile`) only for graph
    nodes.
  - Pre-graph routes record `routing.post_stages` instead.

### Where the code differs from the design (and what I did)

| Design (1.14.0) | Code on main | Frontier decision |
|---|---|---|
| "Reuse relationship-loop search" for the relation graph | `explore()` needs edges with channel receipts and symbolic support, from `extract_facts`, whose patterns cover mostly taxonomy and animal facts | Reused `Budget`/`StopSearch` and the limits pattern. Built a separate relation graph from `extract_facts` plus a causal and constraint cue lexicon. |
| Abductive check | The bridge is specific to the SIDM ontology and numeric bounds | Frontier's abductive check is a general relation-composition check. It reuses the bridge's bound parser (`_first_bound`) to mark quantitative premises. |
| Deductive check | Rule engine with a fixed set of relations | Kept the non-contradiction and span checks. A `constrains` conclusion is also sent to `PreparedInference` as `requires`, and a contradiction or conflict rejects it. |
| Pre-thinker layer | Does not exist | Implemented as a deterministic validator inside Frontier (see below). |
| Execution record | Pre-graph routes use `post_stages` | Frontier uses `post_stages` `frontier_snapshot` → `frontier_rank` and registers them as external consumers. |

## Step 2: Implementation

- **Triggers.**
  - `frontier_seed` reads `Frontier: <topic>.`.
  - `frontier=True` treats the message as the topic, and `frontier={"topic":…, "limits":{…}}` is also accepted.
  - HTTP accepts a boolean or an object.
  - Combining Frontier with another specialist raises `Submit Frontier and other specialist requests
    separately.` An empty topic asks for clarification.
- **Snapshot.** One authorized snapshot via `invention._snapshot`, the same scoped and time-valid read the
  research routes use.
- **Generation.** `generate()` is a generator over the topic-scoped edges. Edges meet where two terms share a
  head noun, and it yields every combination of these patterns:
  - two-edge chains (three-edge chains with `max_path_edges=3`);
  - shared-target pairs;
  - shared-source pairs.

  No preference ordering is applied. `batches()` streams candidates in rounds of `batch_size`.
- **Filters, in order.**
  1. `abductive_check`: the relations compose into a defined reading (sign algebra; constrain ∘ constrain;
     taxonomy inheritance) through a related bridge term.
  2. `deductive_check`: every premise is an exact span in its hashed chunk; no source negates or reverses a
     premise or the conclusion; no rule contradiction; it also computes `deductive_relevance`.
  3. `pre_thinker_check`: rejects malformed, circular, single-source and restated candidates.

  Rejections are counted by reason.
- **Scores and ranking.** The formulas are in the design doc's decisions section. Each score lies in [0, 1].
  Ranking is lexicographic: source support, then relevance, then novelty.
- **Output.** At most 50 entries (the hard cap). If fewer than `min_results` (10) survive, the run reports
  `status: shortage` with a `shortage` record and does not pad. Each entry carries:
  - the text, pattern and relation;
  - `source_ids` and `citations` (quote, offsets, chunk SHA-256);
  - the three scores;
  - a falsification test and its assumptions.
- **Contract.** `claim_status: UNVERIFIED_HYPOTHESIS`, `promotion: blocked`, `index_write: false`. The route only
  reads, and the unit tests use an index stub that has no write methods. The standard invention note is
  appended once. Strict evidence returns `unsupported` before any snapshot is taken.
- **Budgets.** `FrontierLimits` covers rounds, candidates, edges, bytes and seconds, plus `batch_size`,
  `max_path_edges` and the result counts, all on the shared `Budget` ledger. A budget stop sets
  `incomplete: true` and `stop_reason`, and the reply says "Search incomplete".
- **API field.** `frontier` contains `status`, `hypotheses`, `candidates_generated`, `candidates_passed`
  (`abductive`, `deductive`, `pre_thinker`), `candidates_rejected`, `budget_used`, `incomplete` and
  `stop_reason`. It also carries `limits`, focus terms, edge counts and the snapshot.
- **Tests (38).** They cover triggers and options, relation extraction, each filter, the scoring formulas,
  ranking order, the cap, the shortage report, each budget stop (candidates, rounds, edges, bytes and deadline),
  streaming, optional three-edge chains, focus fallback, strict-mode bypass, specialist conflicts, the guard,
  and HTTP pass-through and validation.

Existing files touched:
- `pipeline.py`: a `frontier` parameter and one route block before the invention routes.
- `serve.py`: the field and its validation.
- `flag_contract.py`: one binding and the external consumers.
- `docs/openapi.json`, `docs/prompt-flag-map.json` and `docs/prompt-flag-map.md`.

**No existing node's behaviour changed.** Prompts that do not match `Frontier:` and calls without `frontier`
take the same path as before.

## Step 3: Regression check

Both runs used a disposable PostgreSQL 16 database with pgvector 0.8.7, and the cached `all-mpnet-base-v2`
encoder in offline mode. The baseline ran in a clean worktree of `main`.

| Run | Passed | Failed | Skipped | xfailed |
|---|---|---|---|---|
| `main` (65ce600) | 1192 | 3 | 56 | 3 |
| `feature/frontier-node` | 1230 | 3 | 56 | 3 |

The extra 38 passes are the new Frontier tests. The same three tests fail on both:

- `test_cycle_composition.py::test_document_consumes_cycles_after_style_from_one_snapshot` and
  `::test_document_api_and_prompt_override_and_scope` expect the snapshot mock to be called once, but it is
  called twice.
- `test_request_pipeline_benchmark.py::test_fresh_corpus_keeps_the_counts_and_drops_known_names` expects
  `gold-v2-fresh` but finds `gold-v3-fresh`.

I did not change them.

Environment notes:
- Ubuntu's pgvector 0.6 lacks `subvector`, which 25 tests need, so I installed 0.8.7 from apt.postgresql.org.
- The encoder needed Hugging Face hosts.
- Both were added to a personal `cpullm` cloud environment.

## Step 4: AI-bottlenecks end-to-end test

### Corpus

`tests/fixtures/ai_bottlenecks/`: 64 arXiv papers. `SOURCES.md` lists the title, URL, date, licence and content
used for each.

| Subtopic | Papers |
|---|---|
| Compute and chips | 9 |
| Energy and power | 13 |
| Memory bandwidth | 12 |
| Training data | 9 |
| Algorithmic efficiency | 10 |
| Cost | 3 |
| Talent and access | 2 |
| Regulation and governance | 6 |

Talent and cost are thin: arXiv has little primary material on them, and the arXiv search API returned
503/429 throughout the session, so the papers were chosen by ID.

- **Licences.**
  - 32 CC BY / CC BY-SA papers contribute body text: pypdf extraction, before the references, capped at about
    40,000 characters, with NFKC normalization.
  - The other 32 contribute only the abstract, which arXiv publishes as CC0 metadata.
  - No CC BY-NC or ND body text is used.
- **Holdout.** `holdout.md` and `holdout.json` define 9 findings (H1–H9), each with match groups.
  - The stated passages were cut.
  - Then every corpus sentence containing a term from each "full" group of any finding was dropped: 767
    sentences in total (for example, H1: 106 memory-with-inference sentences).
  - This is strict, so no ingested sentence states a finding in the terms used to score it. It also removes much
    of the surrounding evidence, which matters for the results below.

### Run

The scripts are in `scripts/` in this folder: `fetch.sh` and `parse.py` (arXiv pages), `pdftext.py`, `build.py` (fixtures and holdout), `e2e.py` (ingest and run) and `evaluate.py`. The run:
- ingests into the namespace `ai_bottlenecks_frontier`: 64 files, 1054 chunks, 852 s of CPU encoding;
- runs five prompts three times each: `Frontier: AI bottlenecks.`, `Frontier: AI energy bottlenecks.`,
  `Frontier: memory bandwidth bottlenecks.`, `Frontier: training data supply.`, `Frontier: AI compute cost.`

Raw receipts are in `raw-<prompt>-run<n>.json`, the run log in `runs.json`, and the aggregates in
`evaluation.json`.

| Prompt | Status | Returned | Generated | Passed abductive | Passed deductive | Passed pre-thinker | Time per run (s) |
|---|---|---|---|---|---|---|---|
| AI bottlenecks | hypotheses | 19 | 143 | 69 | 69 | 19 | 3.8 / 3.6 / 3.5 |
| AI energy bottlenecks | hypotheses | 23 | 196 | 94 | 86 | 23 | 3.4 / 3.7 / 3.7 |
| Memory bandwidth bottlenecks | insufficient_evidence | 0 | 42 | 32 | 32 | 0 | 4.1 / 3.5 / 3.5 |
| Training data supply | hypotheses | 50 (capped; 62 survived) | 611 | 230 | 230 | 62 | 3.7 / 3.6 / 3.8 |
| AI compute cost | hypotheses | 50 (capped; 63 survived) | 393 | 206 | 206 | 63 | 3.5 / 3.7 / 3.6 |

Rejection reasons are in `evaluation.json`:
- The largest abductive causes are `no_explanatory_relation` (taxonomy-only pairs) and `unrelated_bridge`.
- The largest pre-thinker cause is `malformed`.
- Energy is the only prompt where the deductive check rejected anything: 8 `premise_contradicted`, where
  sources disagree on direction.

Resources:
- **Run-to-run variation: none.** The three runs of each prompt returned the same IDs in the same order.
- **Time.** About 3.5 s per prompt. The pure Frontier work took 3.3–4.0 s, most of it building the relation
  graph over 6,800 sentences. No budget was hit: at most 3 rounds and 611 candidates, against defaults of 1,000
  and 200,000.
- **Memory.** Python peak traced allocation was about 26 MB per run, and budget-accounted bytes were about
  0.3 MB. The process maximum RSS was 2.98 GB, dominated by the encoder and the PrismThinker worker pool.

### Top hypotheses

The top 10 for every prompt, with scores, citations, falsification tests and assumptions, are in
`evaluation.json → prompts.<prompt>.top10`. The first five for the broad prompt:

| # | Hypothesis | Support | Relevance | Novelty | Sources |
|---|---|---|---|---|---|
| 1 | far more compute may constrain AI model's capabilities through single training run (read as final training run). | 0.80 | 0.65 | 0.51 | 2402.08797 p23, 2405.21015 p9 |
| 2 | large investments and tens of thousands of GPUs may jointly constrain training advanced AI models, so relieving one may shift the bottleneck to the other. | 0.80 | 0.61 | 0.65 | 2311.15377 p2, 2405.10799 p21 |
| 3 | compute used to train a model and final training run may jointly constrain capabilities, so relieving one may shift the bottleneck to the other. | 0.80 | 0.51 | 0.61 | 2405.10799 p7, p20; 2405.21015 p9 |
| 4 | Projects for civilian use may affect training advanced AI models through Japan's consistent investment (read as large investments). | 0.80 | 0.49 | 0.60 | 2402.08797 p30, 2311.15377 p2 |
| 5 | data and tens of thousands of GPUs may interact in their effect on training increasingly large models. | 0.80 | 0.43 | 0.55 | 2112.06905 p8, 2405.10799 p21 |

For compute cost, the next entries after the shared ones are:
- "matrix-vector products may constrain single training run through compute"
- "investment may constrain single training run through increased compute"

For training data, the top entry is "Global deduplication upsamples may reduce training increasingly large
models through quality data".

### Holdout rediscovery

The automatic matcher (`evaluation.json → holdout`) reports 3 full and 7 partial matches. Most of these are
spurious substring hits, so every match was adjudicated by hand:

| ID | Finding | Verdict | Why |
|---|---|---|---|
| H1 | Memory bandwidth bottlenecks serving | Not found | The memory prompt returned nothing after the holdout removal. |
| H2 | Compute-optimal scaling: data and model size scale together | **Partial** | "data and tens of thousands of GPUs may interact in their effect on training increasingly large models" pairs data with compute for training, but has no direction or ratio. |
| H3 | Human text stock runs out around 2026–32 | Not found | |
| H4 | Algorithmic efficiency cuts compute faster than hardware | Not found | The two matches are about int8 quantization; they are spurious. |
| H5 | Hardware and location choices cut carbon 100–1000× | Not found | |
| H6 | Repeated data is nearly as good up to about 4 epochs | Not found | |
| H7 | Progress is strongly reliant on compute | **Partial** | "far more compute may constrain AI model's capabilities" states the dependency but not the unsustainability. |
| H8 | Chips and staff dominate training cost | Not found | The automatic "full" match (quantization → cost improvement) is spurious. |
| H9 | Training on generated data causes collapse | Not found | |

**Result: 0 full and 2 partial out of 9.**

Two caveats:
- The strict removal deleted most sentences that could anchor H1, H4 and H8, which makes this a hard test.
- H7's partial is close to text that remains in a governance paper, so it is weak evidence of discovery.

### Hypotheses that look wrong, trivial or unsupported

- **Bridge misreadings.**
  - "Projects for civilian use may affect training advanced AI models through Japan's consistent investment
    (read as large investments)". The head-noun bridge treats a country's investment in civilian projects as the
    "large investments" needed to train models. The stated same-quantity assumption is false.
  - "matrix-vector products may constrain single training run through compute". The GPTQ inference-kernel
    sentence is joined to a training-compute sentence.
- **Broken anchors that passed the filter.** "GLaM MoE models and central ingredient our model may move
  together because both depend on less data", "estimate may affect …", "how an AI system interacts and Large
  compute investors should help may jointly constrain Risks". Clause fragments survive the malformed check.
- **Trivial or near-circular.**
  - "compute used to train a model and final training run may jointly constrain capabilities". A final training
    run's compute *is* the compute used, so this is one constraint stated twice.
  - "far more compute may constrain capabilities" is close to common knowledge.
- **Weakly supported.** Almost every edge rests on one sentence, so source support is 0.80 (or 0.55 when hedged)
  for nearly all entries. The first ranking key therefore barely discriminates, and relevance decides most of
  the order.

### Known limits

1. **Relation extraction is the bottleneck.** Regex cues with noun-phrase cut points recover about 550 edges from
   6,800 sentences. Subjects and objects are often clause fragments, and corroboration (the same edge stated in
   two documents) is rare. Most `malformed` rejections, and most of the bad survivors, come from this.
2. **Head-noun relatedness** is what makes the graph connected, and also what produces the false bridges. It is
   down-weighted (×0.8) and stated as an assumption, but it is not checked semantically.
3. **The topic focus is lexical.** Stems that appear in more than half the chunks count as background, with a
   fallback when too few edges are anchored. "AI" is effectively ignored.
4. **The restatement check is conservative but lexical.** A paraphrase in different words will not be caught.
5. **Holdout scoring is substring-based** and needs hand adjudication, as above.
6. **Determinism.** The result is deterministic for a given snapshot. The variability note is still appended, as
   required, because a different snapshot or an early budget stop changes the result.

### Suggested next steps

1. Replace the regex noun-phrase chunker with the optional spaCy dependency (`prompt_nlp`), using
   dependency-parsed subject/verb/object triples. Of all the options, this would probably improve quality the
   most.
2. Check bridge terms with the encoder: accept a head-noun bridge only above a cosine threshold, reusing
   `pipeline.encode_texts` as the invention node does.
3. Score corroboration over paraphrased edges, not only exact keys, so that source support discriminates.
4. Add an encoder-based restatement check (sentence similarity to the hypothesis) next to the lexical one.
5. Run a looser holdout variant that removes only the stated passages, to separate "cannot find" from "evidence
   was removed".

## Step 5: Delivery

- The code, tests, fixtures, docs and this review are committed on `feature/frontier-node`. Not merged; nothing
  was published to PyPI.
- The design doc's open questions are answered in `docs/frontier-node-design.md` under "Decisions on the open
  questions".
