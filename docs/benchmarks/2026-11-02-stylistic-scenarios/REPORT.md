# Fresh live stylistic scenario audit

November 2, 2026. Tested fixed runtime **`3b8ab1eba15ead26d8a73793730cb64bda6bfc80`**, without changing library code. Scenario expectations and corpus were frozen before runtime calls. This extends the earlier finite-construction evaluation with actual ingestion, retrieval, canonical judgment, style generation and rendering.

**All 98 stylistic contract scenarios passed: 49/49 rules and 49/49 real spaCy. This is not 98 correct end-to-end answers.** Review found a known upstream wrong-relation response in the rules arm, detailed below.

## Setup and checks

Both arms ingested the same 24 fictional source paragraphs, with private, conflicting, conditional, negative, duplicate and historical records. Each arm used its own fresh PostgreSQL/pgvector database, namespace and local working directory. One correction was applied with explicit historical validity so old/current proofs could be tested. The real spaCy model was installed in the existing dependency environment; no mocked parser or runtime decision was substituted. Resonance and optional reference adapters were disabled. Cached pretrained encoder assets were reused offline; this is not a cold-install or performance benchmark. PostgreSQL was stopped after completion.

Each scenario made a canonical baseline `ask` and a separate styled `ask`: **196 live requests** in total. A further 98 direct applications to baseline results checked recursive canonical immutability without new retrieval. The audit compared visible canonical replies, answer/outcome, judgment and evidence; checked generated values and selected gold proof sets; enforced expected style status, tone fallback, claim/sentence budgets, private-source exclusions and source-scope bounds. It did not perform an independent general semantic judgment of every canonical answer.

## Results by arm

- Rules: **49/49 contract checks passed**; 18 generated, 2 unchanged, 26 skipped, 3 child-only aggregate results.
- spaCy: **49/49 contract checks passed**; 19 generated, 2 unchanged, 25 skipped, 3 child-only aggregate results.
- Across both arms: **37 generated**, **4 unchanged**, **51 skipped** and **6 child-only aggregates**. These are top-level outcomes; child generation is not added to this denominator.
- No execution exceptions, unexpected canonical-field changes, private-value disclosures in the checked visible replies, or out-of-scope stylistic proof IDs were detected.

Expected skips count as passing contract tests, not successful generation. In particular, a canonical answer can be correct while the current stylistic adapter declines it.

An additional **16/16 live integration tests passed** against both parser backends (`layout-session.xml` / `layout-session.log`). These separately tested Markdown/HTML tables and reports with identical canonical output, clarification followed by successful batch completion with full proof, cancellation, no style leakage through pending session state, and no implicit style persistence after a successful request. Test cases and live scenarios use different counting units and are not combined into a single accuracy percentage. No runtime fixes were needed.

## Scenarios exercised

- Formal color and material; friendly location; oval article grammar; decimal weight and units; hyphenated names.
- Five related independently retrieved facts, all five proofs, and three composed sentences.
- Eight explicit tasks composed into two sentences; nine tasks refused by the existing request limit.
- Mixtures of tone affinities; extreme valid intensity settings; poetic/emotional/playful/melancholic/empathetic neutral fallbacks.
- Unknown intimate context; explicit romantic context with neutral fallback; familial, familial-plus-romantic, formal/playful and colleague/emotional restrictions.
- Style-level and prompt-level one-sentence budgets that cannot retain five facts; aggregation declined without truncating claims.
- Different subjects, partially missing data, unknown fields, conflicting values, negative/conditional sources and conditional prompts.
- Empty and restricted caller source scopes, a private alternative color, and a historical correction with both old and current source proofs.
- Unsupported multi-premise lifespan realization, duplicate corroborating documents, non-ASCII names, unlisted color/shape values, math/overview specialist outputs, ambiguous references/senses and quoted instruction-like text.
- Parser-backed conversational attribute wording, with different declared capabilities for rules and spaCy.

The complete original prompts and expected statuses are in `cases.json`. Unsupported cases were deliberately included to test conservative behavior rather than make the generation rate look larger.

## Actual generated examples

Five-fact response, identical in both parser arms:

> The Virel is blue, and you can find the Virel in Harbor Reach. The Virel has an oval shape, and the Virel is made of brass. The Virel weighs 0.75 kilograms.

The historical query generated **“The color of the Revora is blue.”** at the earlier validity time, and **“The color of the Revora is teal.”** at the current time, retaining the corresponding original/corrected source IDs.

The eight-task example retained all requested facts, including repetitions, and all five unique source proofs. It is mechanically faithful but repetitive: four clauses joined with repeated `and` are not evidence of polished long-form prose. Naturalness was not independently rated.

## Important upstream finding

For **“Please give me information about the color of the Virel.”**:

- Rules returned **“The material of the Virel is brass.”** The stylistic node skipped the response because there was no supported immutable factual frame. It did not turn the wrong-relation response into a verified companion.
- spaCy normalized the question to **“What color is the Virel?”**, retrieved the blue fact, and generated **“The color of the Virel is blue.”**

This confirms the previously identified conversational interpretation/answer-binding gap in the rules path. The style test correctly passes its abstention requirement, but the rules canonical response is still wrong for that question. See `review-findings.json`. No runtime fix or new overall answer-accuracy claim is made in this audit.

For this tested form, the direct question “What color is the Virel?” worked in both arms. The installed spaCy backend also handled the conversational wording. A future rules-path fix should preserve the explicit attribute request or ask for clarification rather than return a nearby unrelated attribute.

## Remaining practical limits

Duplicate identical corroborating documents still cause a styling skip because the adapter requires one proof per direct frame. Unsupported palette values, shape values and non-ASCII names also decline styling. Inherited lifespan facts keep their canonical answer/proof but cannot yet become stylistic constructions. General summaries and unresolved references are not silently converted into facts.

Potential next work is to support equivalent corroborating proof sets, broaden reviewed vocabulary/language coverage, reduce repetition while retaining task coverage, and repair the rules path's unsupported-request fallback. Those changes require separate design/tests; passing this audit does not establish unrestricted generation or production readiness.

## Evidence and reproduction

- `freeze.json`: tested revision, runtime source hashes, evaluator hash and pre-run case hash.
- `cases.json` / `corpus.json`: frozen expectations and fresh fictional sources.
- `rules-raw.jsonl.gz` / `spacy-raw.jsonl.gz`: original baseline/styled result dictionaries, checks and timings. Non-JSON values use string representations.
- `*-scores.json`, `summary.json`, `review-findings.json`: automated contract results plus the separately recorded canonical wrong-relation finding.
- `*-setup.json`, `environment.json`, `execution.log`: parser/asset environment, correction receipts and execution evidence. The rules setup has no optional backend object; spaCy has an actual `SpacyPromptBackend` instance. These are not inferred from source prose.
- `artifact-hashes.json`: byte hashes of saved audit files, protected from Git newline conversion by a scoped attributes rule.

The harness is `tools/benchmarks/stylistic_scenarios.py`. It requires a new output directory and a disposable local PostgreSQL cluster on port 55433 with a role permitted to create databases and the `vector` extension. Its fixed database names refuse reuse rather than delete prior results. Run it using an environment with this revision and real spaCy assets:

```powershell
python tools/benchmarks/stylistic_scenarios.py --out <new-output-directory>
```

The caller manages PostgreSQL startup/shutdown. This audit did not rerun or replace the full suite or the October 29 benchmark; the preceding implementation's full-suite counts remain separate evidence.

Repeat the layout/session checks with `CPU_LLM_LIVE_TESTS=1` and a disposable database using `python -m pytest tests/test_stylistic_scenarios_live.py`. The real spaCy branch requires its optional model; absence skips that branch rather than pretending the rules parser is spaCy. Both branches actually ran in this audit.
