# Handoff: correctness and claim-verification review

**ID:** HO-cpullm-003  
**Created:** 2026-10-18  
**Review baseline:** `4d4ded6`  
**HEAD when handing off:** `fdb4d78`, with concurrent uncommitted changes.  
**Status:** Nine findings reproduced at the review baseline; current resolution status must be revalidated. This handoff does not implement fixes.

## Assignment for the receiving agent

Resolve the review's five P1 and four P2 findings, verify the text users actually receive, and align public claims with demonstrated behavior. Preserve the existing stage1-v2 frame invariants and explicit delivery rejections. Do not represent passing example tests as a mathematical guarantee against unsupported output.

Start by reading these portable artifacts included in this repository:

- [Full review: findings, locations, suggested fixes, and limitations](reviews/2026-10-18/claim-review-2026-10-18.md).
- [Executable baseline reproduction probes](reviews/2026-10-18/claim-review-2026-10-18-probes.py).
- [Raw baseline observations](reviews/2026-10-18/claim-review-2026-10-18-observations.jsonl).

Also read [the final v1.9 realizer design](cpu-llm-v1.9-realizer.md), [stage1 semantic memory](cpu-llm-v1.8-semantic-memory.md), and [formats/scale](cpu-llm-output-formats-and-scale.md). The final realizer design supersedes its earlier proposals for implementation. The proposed graph/action neural model is not a trained deliverable; do not expand this patch into model training.

## First: reconcile current work

The checkout advanced after the reviewed baseline. At handoff creation, existing changes included README, answering, pipeline, retrieval, word taxonomy, fact-bridge reasoning, and tests, plus new typo/source-deletion files and `docs/handoff-enterprise-gaps.md`. These changes are not part of this handoff and may already address some findings.

1. Read current repository instructions, `git status`, recent commits, and diffs in the affected files.
2. Re-run each relevant probe against the current checkout. The probe script prints observed behavior; it does **not** assert desired correctness. Adapt it if APIs changed, preserving each semantic test case.
3. Classify each finding as open, partially addressed, or fixed with named regression evidence. Do not revert, overwrite, stash, or delete concurrent work to restore the old baseline.
4. Keep this work separate from enterprise roadmap, typo correction, and source deletion unless a dependency requires coordination. An unrelated dirty file is not authorization to change it.

All file/line references in the full review refer to the baseline; locate functions by name on current HEAD.

## Required fixes and acceptance criteria

### F1 · P1 · Gate the actual learned writer candidate

**Functions:** `Writer.write`, `verify` in `src/fact_bridge/writer.py`; `situation_from_chunks`; final reply composition.

**Baseline:** Every nonempty generated candidate was returned without verification. Stubbing only generation to return an ownership claim caused delivery with no rejection. Separately, `verify` accepted changing `over 6 hours` to `under 6 hours`.

**Fix direction:** Enforce an independent meaning/plan check on every delivered candidate. Validate relation/comparison, polarity, modality, subject, quantity, unit, and scope bindings. Reject bad candidates and use only an independently verified fallback. An unchanged lexical allowlist check is insufficient. Make neural extraction/writing explicit and report their actual path; a deterministic request must not silently become neural because model files exist locally.

**Acceptance:** Tests stub malformed, unsupported, role-swapped, comparator-mutated, and empty candidates; none may leak into `reply.text`. Valid candidates still work. A prior Shine/audit/grammar rejection is never overridden. Distinguish the root fact-bridge T5 writer from the untrained v1.9 ranker. Report the scope of each verification flag.

### F2 · P1 · Keep invented statements out of retrieved evidence

**Functions:** `_with_memory`, `_answer`, `ground` in `src/fact_bridge/__init__.py`.

**Baseline:** A premium-economy policy plus a ten-hour London flight produced a positive conclusion citing synthetic policy text and `The flight to London is an international flight.`, neither supplied by retrieval.

**Fix direction:** Remove silent destination-specific and hardcoded background inferences. Keep retrieved evidence immutable. Any optional supplied knowledge must be explicit, versioned, and labeled; any legitimate normalization/derivation must cite its real premises and preserve subject and scope.

**Acceptance:** London destination alone does not establish international travel. No reported retrieved source is fabricated. Adding an explicit supported international classification can enable a valid conclusion if the rest of the policy is correctly bound. Recheck hardcoded purchase/expense and laptop definitions as well.

### F3 · P1 · Do not infer the inverse of an implication

**Functions:** `_opinion`, `_reason`, and negative `wordings`.

**Baseline:** `Business class is allowed for flights over 6 hours.` and a two-hour flight produced NO and inserted `only` into the policy.

**Fix direction:** Represent sufficient versus necessary conditions explicitly. A nonfiring permission or obligation does not prove prohibition or absence of obligation. Return no supported conclusion/unknown unless a genuinely restrictive or exhaustive rule establishes one.

**Acceptance:** Test sufficient-only, explicit only-if, explicit prohibition, boundary values, and exceptions. Do not remove valid explicit NO behavior. Update tests that currently encode the incorrect closed-world assumption instead of preserving them as supposed invariants.

### F4 · P1 · Detect incompatible observations before choosing one

**Function:** `_reason`, currently the first matching metric selection.

**Baseline:** A seven-hour and two-hour measurement for the same Paris flight produce YES/NO depending on source order.

**Fix direction:** Group applicable entity/metric observations; compare compatible units and explicit temporal scope. Preserve incompatible sources and return contested/ambiguous when the evidence cannot resolve them.

**Acceptance:** All permutations produce the same noncommittal verdict with both incompatible sources. Duplicate equivalent values do not create false conflicts. Unit-equivalent values agree. Distinct explicitly scoped events/times must not be silently merged.

### F5 · P1 · Bind the verdict to the proposition asked

**Function:** `_reason` rule selection and query interpretation.

**Baseline:** `Is business class forbidden on the flight to Paris?` receives YES followed by `Business class is allowed ...`.

**Fix direction:** Parse query modality and polarity; answer the queried claim rather than generically affirming that some rule fires. Unsupported query forms should explicitly abstain.

**Acceptance:** Cover allowed, required, forbidden, and negated questions against the same evidence. Machine-readable verdict and delivered text must agree. Do not silently equate permission with obligation.

### F6 · P2 · Make N0 checking independent of the producer

**Function:** `check_derivation` in `src/cpu_llm/realizer/derivation_check.py`.

**Baseline:** Inserting `EMIT_GRAMMAR` with ` John owns the house.` into the actual apple derivation passes checking.

**Fix direction:** Resolve canonical construction rules from a trusted registry. Check action types, order, exact grammar symbols, binding IDs, obligations, tense transformations, and construction closure against that registry and the plan. Do not trust `required_roles`/`allowed_roles` supplied by the candidate itself.

**Acceptance:** Mutations of grammar text, IDs, roles, required-role declarations, order, inflection/tense, STOP placement, and extra actions are rejected. Canonical candidates still replay exactly. This baseline probe demonstrates a checker weakness, not that the existing deterministic builder emits forged traces.

### F7 · P2 · Bind formatted document fields to the right topic

**Functions:** `_values`, `_stated`, `_sentences_about` in `src/cpu_llm/formats.py`.

**Baseline:** A shipment email receives `To: Mary` from `The picnic recipient is Mary.`; its source list includes only the shipment row.

**Fix direction:** Require explicit coherent topic/document attachment for header fields. Keep per-field provenance and expose those sources. A shared keyword by itself does not prove attachment.

**Acceptance:** Unrelated recipient/sender/date/attendees/byline stay missing. Correctly attached fields populate. Ambiguous competing records abstain visibly. Header-source provenance survives rendering.

### F8 · P2 · Budget memory per host, not per logical engine

**Functions:** `_engines_for`, `_place`, `scale_order`, `performance_matrix` in `src/cpu_llm/scale.py`.

**Baseline:** 2,000 stored bytes, 1,000 available host bytes, and 24 CPUs result in two engines on the same host as the proposed memory solution.

**Fix direction:** Track total host budgets, reserve, and relevant engine/model/index overhead. A host shortage needs remote capacity or out-of-core behavior, not multiplication of the same free-memory figure. Synthetic node JSON size is an estimate unless actual records are measured. Clearly separate planning/bookkeeping from provisioned remote execution.

**Acceptance:** Multiple local seats cannot claim independent copies of host memory. Capacity-order tests cover memory pressure separately from CPU/queue pressure, and estimates are accurately labeled. Do not claim measured deployment or throughput from a capacity formula.

### F9 · P2 · Make chunk accounting idempotent

**Function:** `EngineManager.publish_chunk`, and corresponding receive/update accounting.

**Baseline:** Publishing one ID/text twice doubles counters while the catalog retains one entry.

**Fix direction:** Maintain per-ID footprint and ownership; apply deltas on update, no increment on identical retry, and remove the old owner's counts on relocation.

**Acceptance:** Test identical publish retries, shorter/longer replacements, moves, and remote replay. Aggregate seat counts/bytes must match the catalog's actual logical contents.

## Proposed implementation sequence

1. Close F1's candidate-delivery gap and establish explicit verification scope.
2. Correct evidence provenance and policy/query semantics: F2–F5. Add desired-behavior tests before modifying logic.
3. Harden N0's checker and draft field binding: F6–F7.
4. Repair scale budgeting and upsert accounting: F8–F9.
5. Reconcile README/design claims with final implemented behavior, then run end-to-end tests with the real database.

Use small logical patches. If concurrent work has already fixed a finding, validate it and avoid duplicate rewrites. No new decoder, trained model, entity-resolution framework, or general parser is required to safely abstain on unsupported inputs.

## Validation record and required reruns

At `4d4ded6`, **178 tests passed** using:

```powershell
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
python -m pytest --ignore=tests/test_pipeline.py --ignore=tests/test_upload.py --basetemp=<fresh-writable-directory> --tb=short
```

The two excluded files include some non-PostgreSQL tests too. Do not compare 178 directly with the historical 180-pass record without matching the selected tests.

The saved probe script produced ten observations across the nine findings (F1 has two probes):

```powershell
python docs/reviews/2026-10-18/claim-review-2026-10-18-probes.py
```

It is a baseline observation tool, not a suite whose undesirable outputs should be preserved. Convert each case into an assertion of the **correct** desired behavior. Writer generation was stubbed for its gate test; no claim is made that a real model generated the adversarial string.

The pipeline retry stalled and was interrupted. A separate read-only PostgreSQL connection with `connect_timeout=3` timed out on localhost port 5433. **No end-to-end pass is claimed.** Follow existing local setup documentation and run real ingestion/retrieval/reply tests once PostgreSQL is available. Do not label mocks as an end-to-end pass or treat a database timeout as a product assertion failure.

## Definition of done

- Every finding has a current disposition and named regression tests; partially addressed findings remain clearly open.
- Verdict, evidence, actual delivered text, and component verification flags agree.
- No fabricated evidence, lost condition direction, arbitrary conflict winner, modality mismatch, forged construction, cross-topic header borrowing, or erroneous capacity accounting remains in the supported cases.
- Prior rejection stays authoritative across normal, neural, formatted, and mixed optional-agent output.
- Existing supported frame and deterministic behavior pass appropriate tests; tests that encoded invalid logic are corrected with an explanation.
- End-to-end results are reported with exact commands and environment limitations. No new latency claim without measurement.
- Public claims describe bounded evidence faithfulness and source/verification scope, not universal truth or universal absence of hallucination.
- Final report lists changed files, fixed/remaining findings, test results, compatibility decisions, and outstanding risks. Preserve concurrent work and do not mark a finding fixed merely because its wording was removed from documentation.
