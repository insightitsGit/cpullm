# CPU-LLM benchmark validity review

The 1.13.1 request benchmark measures end-to-end behavior under synthetic request fixtures. It already tests citation, access, clarification, abstention, and request budgets. Its aggregate also mixes open-ended response depth and adversarial input handling with precise evidence lookup. Use the aggregate as a request-pipeline regression metric. Use the separate strict-evidence suite for the narrower evidence contract.

## Checks against the saved corpus

- `direct-har-05` asks how much the Kestrel weighs. Authorized gold passage `har-public-p0015` explicitly says 18 pounds. The insufficient-evidence reply earns credit for avoiding an unsupported assertion and remains a missed answer.
- `depth-har-05` asks “Tell me about the Kestrel.” The gold requires “survey skiff” from `har-public-p0001`. This fact is grounded, but the prompt does not uniquely require it. Score the supported facts independently and test completeness with explicit requests, such as “What kind of vessel is the Kestrel?” or “Give its type and color.” Score duplicate sentences separately as presentation defects.
- `separation-har-10` appends long repeated-character padding to a color question. Keep the case under input robustness and specify whether the contract requires recovery or a structured refusal at the stated input limit. Report this stratum separately from ordinary evidence lookup.

## Evidence-first acceptance suite

1. Freeze prompts, source versions, access scopes, gold, and scorer before execution. Review source support independently of the engine reply. Label each case as answerable, partially answerable, missing, ambiguous, conflicting, or blocked for that caller.
2. Validate the relationship between entity, attribute, and value, including units and negation. Accept equivalent verified representations where the contract allows them. For exact quotation, check span offsets and text. Allow alternative proof sets when they establish the same fact, and check the cited source is authorized.
3. Credit abstention or clarification when justified by the source and policy. For gold-answerable cases, report a missed answer separately from unsupported assertions. Separate budget refusals, missing retrieval, and evidence dropped after retrieval. Treat automated evidence-loss labels as diagnostic until checked against the source.
4. Exercise paired cases that differ by one fact or permission. Examples include the same question with the evidence present, removed, contradicted, or inaccessible. Include exact arithmetic and rounding cases in their own stratum. Keep research hypotheses and numerical scans in a separate contract with reproducible inputs and observable checks.
5. Report counts and denominators for claim support, valid proof, answer coverage, justified abstentions and clarifications, avoidable refusals, access failures, and exact calculations. Measure determinism separately by replaying fixed cases and comparing normalized outcomes, facts, and proof IDs. Publish unverified cases and scorer disagreements alongside the results.

Retain the current score for historical comparison. Before rescoring, adjudicate the 67 misses and a sample of passes, record each source-backed reason for any changed expectation, and freeze the revised rubric. Use a fresh holdout for the revised benchmark.

## Knowledge-base coverage and evidence growth

For each expected fact, record whether sufficient evidence is absent from the source corpus, present but missing from the index, indexed but unauthorized for the caller, indexed and authorized but not retrieved, or retrieved but lost before the final reply. Also record ambiguity and conflicting sources. A retrieved fragment only counts as sufficient evidence if it supports the requested fact or completes the required proof set.

- If the authorized knowledge base lacks evidence, credit a justified abstention or targeted request for the missing document. Report the coverage gap separately from engine errors.
- If source evidence exists but failed to ingest, record an ingestion defect. If it was indexed and authorized, trace retrieval, ranking, and final evidence retention before recommending more data.
- Run paired tests on the same question and caller. Begin with missing evidence, then add a relevant authorized passage and require a cited answer. In separate variants, add irrelevant volume, duplicates, contradictory or superseded material, and restricted evidence. Require stable supported answers under noise, appropriate handling of conflicts, and no disclosure of restricted material.
- Report the change in grounded answer coverage after adding relevant evidence, along with any new unsupported claims, regressions on previously supported questions, and ingestion or retrieval costs. Keep fixture changes separate from pipeline changes so improvements can be attributed correctly.
