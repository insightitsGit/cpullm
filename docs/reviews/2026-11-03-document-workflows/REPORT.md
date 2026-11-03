# Report, article and design-document workflow investigation

Date: November 3, 2026. Runtime baseline `5766172`, with the working-tree style flag-registry addition recorded in this checkout. Exploratory full-pipeline run, not a scored benchmark. Ten requests completed against PostgreSQL 18/pgvector, cached CPU encoder assets, the rules prompt backend and a fresh namespace. Twelve fictional Helios backup-service facts and two unrelated Aster facts were ingested. Raw inputs, outputs and the exact runner/hash receipt are saved here. Runtime behavior was not changed for these cases.

## What the engine did

1. **Write a detailed report about Helios.** Produced a report with five stored findings and citations. Plan: standard depth, three optional sentences, retrieval budget five, no deep stage. The draft path bypasses the overview budget and uses matching retrieved sentences. The planned three-sentence number is not an enforced limit on this document path.
2. **Write a detailed article about Helios.** Produced an article with five stored sentences and citations. It correctly marked the byline as not stated. The same unrecognized detailed-document cue left retrieval at five.
3. **Write a detailed design document about Helios.** Produced a generic numbered Document with five facts. It did not produce architecture, requirements, decisions, interfaces, risks or validation sections. No dedicated design-document schema was selected.
4. **Give me a detailed overview of Helios as a Markdown report.** Selected detailed/overview mode, eight-sentence ceiling and twelve-passage retrieval. All twelve Helios paragraphs reached the child pipeline; final content contained only two factual sentences. The Jinja report supplied a heading, request section and sources, rather than a sectioned research report.
5. **The same overview with deep=True.** The routing receipt confirms `deep` ran and reached/retained twelve candidates. It still delivered only two factual sentences. Retrieval expansion alone does not solve this case.
6. **Explain Helios in twelve sentences as bullet points.** Planned twelve sentences and sixteen retrieval candidates; returned two bullets. Counts are ceilings, not promises. The list item budget remained eight even though the sentence budget was twelve; these distinct units need explicit handling in a unified plan.
7. **HTML report.** Returned actual HTML with report sections and source IDs, but the same two-sentence body. Layout works independently of information coverage.
8. **Three questions as a Markdown table.** Preserved three rows and their statuses. Identity and stored objects were quoted; the database question returned insufficient evidence despite the stored sentence “Helios uses PostgreSQL for metadata.” The aggregate was partial, not complete.
9. **Detailed report with style=friendly.** The tone companion stayed at `children`, reason `incomplete_or_unsupported_children`. It did not turn general technical summary content into prose; the tone node currently supports a narrower fact subset.
10. **Strict detailed report.** Returned unsupported with instructions to use named attribute questions. This was an intentional boundary, not a successful strict report-generation path.

## Why the body stayed short

The response classifier recognizes detailed answers, summaries, overviews and explanations, but not detailed reports/articles/design documents. Direct `parse_order` returned None for all three detailed-document commands; the downstream format-sense fallback nevertheless selected Report, Article or generic Document. Consequently document selection and response planning disagree.

The overview branch converts source paragraphs into supported internal propositions before cognition ranking and verified realization. Direct inspection of `proposition_from_chunk` accepted only three of the twelve Helios paragraphs: the service identity, stored encrypted backups and the negative failover statement. Nine other technical statements were not parsed. Only the first two appeared in the actual summary. This isolates an extraction/realization coverage bottleneck; the exact handling of the negative proposition still needs its own trace. It must not be described as missing knowledge or fixed by increasing top-k alone.

The draft renderer instead copies topic-matching sentences from its passage pool. It can show richer technical sentences than the overview branch, but lacks one shared coverage/budget contract. Report selection and report layout are separate paths with different behavior. The tone companion is separately verified and is not automatically used as the report body.

## Recommended design before implementation

1. **One document request plan.** Separate genre (report/article/design), topic, requested audience/tone, section outline, media/layout and length. Recognize ordinary detailed-document phrasing. Preserve explicit constraints and ask about genuinely ambiguous scope. Do not equate a report with unrestricted deep search.
2. **Section-aware evidence acquisition.** Create bounded section queries for topic overview, requirements, components, interfaces, operational behavior, limits and tests when appropriate to the requested genre. Apply caller/source/time scope to every query and graph hop. Deduplicate results and stop at explicit retrieval/coverage limits. Enable wider retrieval for substantial document requests; use graph expansion only when the plan needs it or the caller explicitly requests it.
3. **A provenance-preserving document representation.** Represent each section as supported claims, exact quotations, derived results or explicit missing information, with source spans. Retain useful technical sentences as labeled source quotations when no supported proposition parser exists, rather than silently discarding them. Do not convert those quotations into inferred design decisions or pretend they passed semantic reasoning.
4. **Coverage and conflict checks before writing.** Track requested sections, retrieved evidence, accepted/rejected claims and uncovered requirements. Contradictions, negation, numbers, permissions and uncertainty must survive. Report incomplete coverage explicitly; an `answered` wrapper alone is not evidence of a complete report.
5. **One length contract.** Share document/section budgets across draft, overview and batch paths. Distinguish word, sentence and list-item counts. Treat insufficient evidence as a coverage gap instead of padding prose. Preserve necessary premises/citations and explain unavoidable budget overruns. Very long outputs need bounded continuation rather than an undocumented hard truncation.
6. **Compose, then render.** Apply the tone node only to eligible accepted claims and keep its verification/proofs. Broader report prose requires additional reviewed constructions or attributed source extracts; do not expand tone vocabulary by silently changing facts. Render the same document representation into Markdown/HTML/table/bullets, rather than producing different facts for each format.
7. **Keep strict mode explicit.** A strict report path would need a specified quotation/derived-result-only document contract, unsupported-section policy and validation. Do not silently relax strict evidence to make a report look complete.
8. **Evaluate new corpora and varied wording.** Cover section completeness, technical verbs, negation, conflicting sources, multiple subjects, denied sources, temporal corrections, clarification/continuation, numeric precision, budget handling, format equivalence and tone fallback. Score supported coverage and proper missing-section handling, not word count alone.

## Practical conclusion

The engine can produce source-backed document layouts today. It does not yet provide a reliable comprehensive-report/article/design workflow across ordinary wording. The primary work is connecting document intent, section planning, evidence coverage and composition. More retrieval or a larger tone sentence budget alone is insufficient.

## Implementation references

- `src/cpu_llm/response_policy.py`: genre/depth recognition and budgets.
- `src/cpu_llm/formats.py`: output catalog, parse_order, topic sentence selection and draft bodies.
- `src/cpu_llm/pipeline.py`: `_deep`, `_brief`, `_brief_rows`, graph selection and finalization.
- `src/cpu_llm/clauses.py`: proposition extraction coverage.
- `src/cpu_llm/request_planner.py`: task and combined optional-response budgets.
- `src/cpu_llm/output_rendering.py`: Jinja/Tabulate rendering of judged responses.
- `src/cpu_llm/stylistic/node.py`: bounded companion generation and verification.

To replay the captured runner, copy `runner.py` into the repository's `build/` directory, configure `VECTORPRISM_PG_DSN` for an available disposable database with vector enabled, and set offline encoder environment flags if assets are cached. The runner uses a fresh namespace but the fixed output directory `build/document-workflow-20261103`; choose a new directory for a separate run. The results here are observations on fictional fixtures, not general accuracy rates or a competitive benchmark.
