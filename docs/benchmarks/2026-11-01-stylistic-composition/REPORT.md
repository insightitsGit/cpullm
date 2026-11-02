# Related-sentence composition and tone controls

Started November 1 and completed November 2, 2026. Stage 1 is checkpoint `dc8878b`; this evaluation records stage-2 working-tree runtime hashes in `composition-evaluation.json`. The October 29 answer-quality benchmark remains unchanged.

## Delivered behavior

The stylistic output subgraph now selects among ten curated constructions over color, location, shape, material and explicit weight. Complete same-subject child tasks can become longer related sentences while every source proof is retained. For five independently accepted facts, the friendly output is:

> The Aster is blue, and you can find the Aster in coastal waters. The Aster has a round shape, and the Aster is made of steel. The Aster weighs 12.5 pounds.

That three-sentence text is assembled at request time; it does not need to exist verbatim in the source database. It appears in `result["stylistic"]["text"]`. Existing canonical replies, judgments, statuses and proof fields remain intact. This is controlled construction generation and composition, not a general language model or new factual reasoning.

## Design gaps addressed

- Added normalized ten-channel tone controls, intensity validation and combined relationship flags. Exclusions override permissions; familial plus romantic still forbids intimate tone.
- Added a read-only struct-of-arrays construction lexicon. Exact relation eligibility, POS intersection and register-risk masks precede scoring. Tone suitability is separate from inherent romantic/emotional/colloquial risk. Score components and selected construction IDs are exposed per claim.
- Weighted ranking is deterministic and cannot trade away semantic eligibility. Valence distance is normalized by two; tone affinity mass is normalized; tie-breaking uses stable entry IDs.
- Added complete-coverage composition with only additive `and`. Independent inverse grammars check each clause, source proof and complete surface. Missing/pending children, conflicting values, different subjects or an inadequate budget prevent aggregation.
- Added shape article handling (`an oval shape`), material and explicit weight constructions. Names, values and decimal units remain copied; no new intensifiers or feelings are invented.
- Preserved default behavior and existing contracts. Style remains an explicitly requested companion; neutral outcomes, retrieval, frame models and vector schemas are not globally rewritten to permit arbitrary paraphrases.

The live test exposed an existing weight-route gap: the field compiler emitted “How much does X weigh?”, which could be owned by an unsupported event producer. Weight fields now compile to the already supported “What is the weight of X?” factual form. Simple direct weight questions receive the same auditable normalization; guarded/qualified questions are left intact. Initial failing runs are retained in `targeted.log`, `targeted.xml` and `live-debug.log`. The final full suite includes the corrected live test.

## Results

**Full live suite: 771 passed, 2 skipped, 3 expected failures, zero unexpected failures.** All 776 collected cases ran with live tests enabled against a new disposable PostgreSQL database. Both live stylistic tests passed: ordinary single-fact generation and five independently retrieved attributes composed into three sentences with all five source IDs. Six existing NumPy overflow warnings remain. See `suite.xml`, `suite.log` and `verification.json`. The two skips require absent extractor checkpoints; the three expected failures remain existing resonance grouping limits. The cluster was stopped after execution.

The component evaluator authored 20 synthetic subjects with five facts each, then evaluated ten tone settings: **200 cases**, each checking five claims and their exact proof union. All finite grammar/coverage assertions passed, along with canonical-result immutability checks. **80 cases used matching tone-affinity entries; 120 explicitly reported `neutral_fallback`.** Those labels are construction-affinity diagnostics, not independent human ratings of naturalness or emotional quality. The current vocabulary contains no licensed romantic, poetic or emotional factual embellishments.

The evaluator also replayed the preserved 680 canonical October 29 responses under friendly and formal styles: **1,360 top-level invocations**. Results were **256 generated, 120 unchanged, 848 skipped and 136 child-only aggregates**. Canonical fields were compared recursively and remained unchanged. These are generation coverage outcomes, not a new answer-quality score. They must not be compared directly with stage 1's 264 count, which included child outputs in its denominator. No retrieval was rerun in this replay.

The evaluator initially wrote a hardcoded `fresh_cases: 400` despite emitting 200 records; the corrected count is derived from recorded outcomes. The original metadata is retained in `composition-evaluation-original-metadata.json`; raw results and expectations were not changed. `composition-evaluation.json` records the correction. This finite evaluation is a component test, not an independently adjudicated broad language benchmark.

## Remaining limits

Ten tone controls do not imply ten kinds of expressive prose. The small lexicon currently supports factual friendly/formal/serious/analytical variants. Unsupported expressive intent receives an honest neutral fallback or a relationship-policy skip. There is no automatic tone/audience inference, broad word-sense embedding lexicon, learned stylistic model, unrestricted synonym substitution or HTTP style parameter.

Negation, modality, conditions, tense changes, multi-premise inherited facts, unresolved senses and arbitrary producer contracts remain outside the supported adapter set. The node declines unsupported inputs. It cannot fix an upstream fact/retrieval error or establish source truth. Visible-answer promotion remains separate future work; a derived companion must not be labeled a verbatim quote. Related sentences require related accepted facts; requesting more words does not create them.

## Reproduction and saved artifacts

```powershell
python tools/benchmarks/stylistic_composition_smoke.py --out <new-output-directory>
python -m pytest tests/test_stylistic.py tests/test_stylistic_composition.py
# With a disposable PostgreSQL/pgvector database and cached encoder:
$env:CPU_LLM_LIVE_TESTS="1"
python -m pytest tests/test_stylistic_live.py
```

`fresh.jsonl` contains all 200 component results. `canonical-replay.jsonl` contains the 1,360 top-level companion results; original canonical responses remain in the October 29 archive. `composition-evaluation.json` records counts, examples and runtime source hashes. `verification.json` records suite counts and source-hash agreement. `runtime-source.zip` preserves the exact changed runtime bytes; the base commit supplies unchanged modules. Artifact hashes are preserved across Git checkouts by a narrowly scoped attributes rule. Wheel packaging evidence is stored separately in `build.log` / `wheel.json`. The clean dependency environment and cached encoder from the earlier audit were reused; no training ran. See the [design](../../stylistic-generation-design.md), [spec](../../stylistic-generation-spec.json) and [consumer guide](../../library-consumer-guide.md).
