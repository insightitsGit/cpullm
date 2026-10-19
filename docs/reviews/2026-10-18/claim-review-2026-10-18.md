# Code review: do current claims match delivery?

**Date:** October 18, 2026  
**Reviewed root:** `C:\code\cpullm`  
**Baseline:** `4d4ded6`  
**Verdict:** The current implementation does not substantiate the README's broad claims of mathematically verified answers without hallucination. There are reproducible correctness defects in the newly added rule/writer paths. The constrained frame improvements are present, but their invariants do not automatically extend to other reply producers.

Production code was not changed. This review covers the tracked root package, current claims, relevant designs, new rule/writer, N0 realizer, formatting, and scale paths. The untracked `cpullm-factbridge/` tree and unrelated dirty `.pytest-basetemp` files were left untouched and were not reviewed as another product. The root package's ability to auto-discover models in that directory was considered because it affects root-package behavior. This is not an exhaustive proof of correctness or a security audit.

**Concurrent working-tree change:** Near completion, README and pyproject edits appeared from outside this review. The revised README removes the headline mathematical/no-hallucination claim and qualifies old latency figures, but retains `no decoder` and broad spoken-output auditing language. Claim quotations here identify the reviewed committed baseline unless explicitly stated otherwise. Those documentation edits were preserved; they do not repair the reproduced implementation defects.

## Findings, by impact

### F1 · P1 · The live learned writer delivers arbitrary nonempty output without verification

**Location:** `src/fact_bridge/writer.py:533`–`542`; reachable from `src/cpu_llm/answering.py:39`–`47` and reply composition.

`Writer.write` calls `generate`, then immediately returns any nonempty candidate as `path="model"`. It never calls the module's `verify` function. This occurs after the main pipeline's checked `answer`; those earlier checks do not cover the replacement text. `situation_from_chunks` automatically requests the learned path when a rule-cued question is missed by the pattern extractor and local models are present, even with the default `realization="deterministic"`.

**Reproduction:** Use a genuine supported YES plan and stub only `Writer.generate` to return `Yes. John owns the house and business class is forbidden.` Calling the real `Writer.write` returns that text as model output with an empty rejection list. This demonstrates a missing delivery gate, not a claim that the actual model generated this particular string.

**Additional defect:** Simply calling the current `verify` is insufficient. Changing a valid candidate's policy from `over 6 hours` to `under 6 hours` still returns `(True, [])`. It checks vocabulary, verdict prefix, and numeric presence without validating the comparison relation.

**Fix:** Route every candidate through an actual plan/meaning verifier; use a verified fallback on candidate rejection. Bind comparator, modality, entity, quantities, and units to their specific roles, or restrict the writer to approved constructions. Make learned extraction/writing explicit opt-ins and disclose the actual path. Until corrected, do not claim the delivered rule answer is audited because `answer` was audited.

### F2 · P1 · Rule reasoning invents evidence and cites it as retrieved

**Location:** `src/fact_bridge/__init__.py:626`–`644`.

`_with_memory` silently appends hardcoded definitions and synthesizes policy/category statements before `ground` constructs its trusted source set. Grounding then accepts these additions as though they came from retrieval.

**Reproduction:** Supply only:

```text
Employees traveling internationally for more than 8 hours are eligible to book premium economy.
Our flight to London takes roughly 10 hours.
```

Ask `Can I book premium economy on our flight to London?`. The result is YES and its sources include two unsupplied sentences:

```text
Premium economy is allowed for international flights over 8 hours.
The flight to London is an international flight.
```

The latter is not established by the destination: a flight could originate in the UK. The reply-composition probe also delivers this unsupported international classification.

**Fix:** Keep immutable retrieved evidence separate from explicitly supplied knowledge and derived claims. Remove destination-specific inference. Any normalization must carry a validated derivation and preserve subject/scope; cite original passages, not generated sentences relabeled as sources. Optional background knowledge must be explicit, versioned, and distinguishable from retrieval.

### F3 · P1 · Sufficient conditions are silently converted into necessary conditions

**Location:** `src/fact_bridge/__init__.py:403`–`416`; `src/fact_bridge/writer.py:298`.

For both allowed and required rules, `_opinion` returns NO whenever a condition is false. That concludes the inverse of the retrieved implication. The writer adds `only`, which the source never stated.

**Reproduction:** `Business class is allowed for flights over 6 hours.` plus `The flight to Paris takes 2 hours.` produces `No. ... business class is allowed only for flights over 6 hours.` The rule establishes a sufficient permission for long flights; it says nothing about permission for short flights. A policy with another short-flight exception is compatible with that source.

**Fix:** Track implication versus biconditional/only-if semantics. A nonfiring permission/obligation is silent or unknown unless an explicit prohibition or exhaustive policy establishes NO. Do not insert `only`. Update existing tests that currently enshrine this assumption; passing them is not evidence that the logic is valid.

### F4 · P1 · Contradictory measurements produce retrieval-order-dependent answers

**Location:** `src/fact_bridge/__init__.py:503`.

`next(...)` selects the first fact with the rule's metric. Contradiction logic later compares rules, not multiple incompatible facts for the same entity/metric.

**Reproduction:** One business-class rule and both `The flight to Paris takes 7 hours.` and `The flight to Paris takes 2 hours.` produce YES when 7 hours comes first and NO when 2 hours comes first. The other measurement disappears from the reported supporting sources.

**Fix:** Group all applicable entity/metric observations; reconcile compatible units and explicit temporal scope. If conflicting values cannot be resolved from evidence, return contested/ambiguous and retain both sources. Require invariant results under source permutation and duplicate evidence.

### F5 · P1 · YES/NO verdicts ignore what modality the question asks about

**Location:** `src/fact_bridge/__init__.py:485`–`516`.

Rule selection matches object words but does not represent the question's requested modality or polarity. A positive permission is treated as YES to a prohibition question.

**Reproduction:** Ask `Is business class forbidden on the flight to Paris?` with the permission rule and a 7-hour Paris flight. Actual: `verdict="YES"`, `Yes. Business class is allowed ...`. That is a contradictory direct answer and a wrong machine-readable verdict.

**Fix:** Parse the proposition being queried, including permission, obligation, prohibition, and negation. Compare the derived claim to that proposition. Return unsupported/unknown for question forms outside the accepted query grammar instead of a generic YES.

### F6 · P2 · N0's independent checker trusts a derivation's own grammar claims

**Location:** `src/cpu_llm/realizer/derivation_check.py:19`–`61`.

`EMIT_GRAMMAR.surface` is accepted without checking it against an approved construction or grammar position. Required/allowed roles are read from the supplied derivation rather than independently established by the plan/construction. Inflection membership also does not establish authorized tense. The checker cannot enforce the advertised boundary on a mutated derivation.

**Reproduction:** Start with the actual legal apple color derivation. Insert `Action("EMIT_GRAMMAR", construction_id, surface=" John owns the house.")` immediately before STOP. `check_derivation` returns `[]`; replay says `The apple John ate was yellow. John owns the house.`

**Impact boundary:** This is a checker-contract failure, not evidence that the current deterministic derivation builder emits the forged action. There is no trained N0 ranker producing novel actions today. Correct it before relying on this verifier as the independent barrier for a learned component or claiming N0 rejects such mutations.

**Fix:** Load the canonical construction by ID, independently derive legal action types/order/symbols/role obligations from plan and construction, and reject all extra or altered actions. Validate action/derivation construction IDs, scope, and exact renderer output. Add mutation tests beyond stolen COPY spans.

### F7 · P2 · A draft borrows recipient/date/sender roles from unrelated topics

**Location:** `src/cpu_llm/formats.py:339`–`375`.

The body filters topic-related sentences, but `_values` invokes `_stated` on every retrieved row. Header roles are not bound to the requested topic or a matching document.

**Reproduction:** Request an email about the late shipment with `The shipment is late.` and `The picnic recipient is Mary.`. Actual output includes `To: Mary`; returned sources list only the shipment row. The email acquired a recipient from a different event, with no trace of its source in that source list.

**Fix:** Extract fields from a coherent topic/document record, retaining per-field provenance. A nearby topic word alone is not sufficient attachment. Ambiguous field ownership should remain missing. Include field evidence in sources and test mixed-topic retrieval.

### F8 · P2 · Memory-pressure scaling adds local engines to solve a shared physical-memory shortage

**Location:** `src/cpu_llm/scale.py:331`–`346`; callers `performance_matrix` and `scale_order`.

Required engines are calculated by dividing stored bytes by the entire available physical memory, treating that capacity as independent for every engine. Placement then uses CPU count alone, allowing multiple such shares on the same host. Multiple engines do not multiply the host's available memory.

**Reproduction:** `scale_order(stored_bytes=2000, available_bytes=1000, cpu_count=24, engines=1, busy=False, waiting=0)` returns `add_engine`, two engines, `this_server`, although the data alone is twice the host's free memory.

**Fix:** Budget total host memory across all seats, model/worker overhead, index/storage overhead, and reserve. A host-level memory shortage needs actual remote capacity or out-of-core storage, not another local seat. Describe this module as capacity planning/control-plane bookkeeping until provisioning, replication/sharding, and routing are implemented and tested.

The JSON sizing routine also serializes a synthetic embedding and empty attributes; its byte count is not an exact measurement of each actual stored node. Document the estimate or measure real serialized records.

### F9 · P2 · Publishing an existing chunk double-counts capacity

**Location:** `src/cpu_llm/scale.py:252`–`262`.

`publish_chunk` always increments chunk and byte counters even when its catalog already maps that ID. The dictionary entry is overwritten, leaving one logical chunk with multiple counted copies. Republishing to another seat can also leave stale counts on the original seat.

**Reproduction:** Publish ID `same-id`, text `hello`, twice. Reported stored bytes increase from 12,465 to 24,930; chunk count becomes 2 while catalog size remains 1.

**Fix:** Maintain the previous footprint and owner for each ID. Treat publish as an idempotent upsert, apply byte deltas for replacement, and decrement the old seat on relocation. Test identical retries, updates, moves, and remote replay. Avoid triggering false add-engine orders from delivery retries.

## Claim assessment

**Not substantiated:** README's broad descriptions `without ... hallucination`, `mathematically verified assertion`, and whole-spoken-output auditing. The counterexamples above are within reachable package code, including default rule answering. Extraction, construction, and lexical checks cannot establish source truth or universal entailment.

**Misleading in current default behavior:** README's `no decoder`. The root reply path can automatically load a local FLAN-T5 extractor/writer when a pattern misses. This is a separate code path from the opt-in v1.9 realizer; its existence does not mean the N0 ranker is trained. Default behavior also varies with model directories on the machine. Make the policy explicit and report each output's actual verification scope.

**Correctly disclosed:** The v1.9 realizer has N0 objects/constructions/checker, no trained ranker checkpoint, and deterministic fallback. There is no evidence to describe the proposed learned graph/action model as delivered. The later entity-resolution, durable role-index, and tenant-lifecycle stages remain intentionally unimplemented, not regressions by themselves.

**Implemented but narrowly demonstrated:** Closed stage1-v2 frame extraction, visible frame non-answers and delivery holds; stored document-format layouts; basic unit conversions and rule matching; CPU paths. Passing example tests support these specific behaviors, not general correctness of all generated conclusions.

**Not validated here:** End-to-end PostgreSQL ingestion/retrieval behavior, current whole-appliance latency, remote engine execution, production capacity limits, universal absence of unsupported output, and corpus-wide contradiction completeness.

## Verification performed

1. Ran the tracked root tests excluding `tests/test_pipeline.py` and `tests/test_upload.py`, using `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, and a fresh writable `--basetemp`. **178 passed**, with two reported dependency deprecation warnings. The excluded files include both PostgreSQL and non-PostgreSQL tests; 178 is the precise count for this command, not a claim to reproduce the historical 180-pass record.
2. Ran actual package functions for the counterexamples. Saved the repeatable probes in `claim-review-2026-10-18-probes.py` and raw observed outputs in `claim-review-2026-10-18-observations.jsonl` beside this report. All ten probe observations reproduced (F1 has both missing-gate and comparator-mutation observations).
3. Retried `tests/test_pipeline.py -x` with local-service access. It stalled without a test outcome and was interrupted. A separate read-only PostgreSQL probe with `connect_timeout=3` timed out for both localhost addresses. **No integration pass is claimed.** No database/container configuration was changed.
4. Did not retrain models, change source code, alter the existing dirty files, or inspect the separate untracked project as a complete codebase.

Focused-suite command:

```powershell
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
python -m pytest --ignore=tests/test_pipeline.py --ignore=tests/test_upload.py --basetemp=<fresh-writable-directory> --tb=short
```

Probe command from the installed checkout:

```powershell
python <artifact-directory>\claim-review-2026-10-18-probes.py
```

## Recommended order before release

1. Close the learned-writer delivery gap and make neural usage explicit; hold unsupported rule answers until the semantic checks are correct.
2. Remove manufactured evidence, fix implication semantics and query modality, and detect conflicting observations before selecting a verdict.
3. Make the construction checker independent of producer-supplied assertions. Bind formatting fields to their topic/source.
4. Correct capacity accounting and host-level budgets. Avoid presenting logical seats as demonstrated deployed engines.
5. Revise the README to describe bounded, evidence-traceable behavior and verification scope; preserve explicit limitations.
6. Add the probe cases as desired-behavior regressions, then run real ingest -> retrieve -> answer -> verify -> reply tests with PostgreSQL available. Report per-component verification and historical latency separately from fresh results.

This review is complete as a review; fixing the findings and verifying deployment remain separate work.
