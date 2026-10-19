# cpu-llm: features demonstrated on the actual checkout

**Date:** 2026-10-18. **Code baseline:** `5737285`, package metadata 1.8.0. README/consumer-guide edits were present; runtime code was not changed for this exercise.

## How this was checked

Ran a real `Appliance` against the reachable local PostgreSQL service, ingested seven synthetic paragraphs in a fresh namespace, then issued 15 prompts through `app.ask`. The namespace was `feature_demo_5dba7941222e`; existing sources were not changed. Startup took 9.761 seconds in this one run. This is a small demonstration, not a representative accuracy or performance benchmark.

The corpus contained three made-up harbor-kestrel descriptions, the yellow-apple event, one business-class permission rule, and eight-hour/two-hour flight descriptions. The synthetic bird statements are test data, not zoological claims.

Raw prompts, complete displayed outputs, retrieved passages, and component diagnostics are preserved in `feature-demonstration-20261018.json`. The repeatable runner is `feature-demonstration-20261018.py`; it creates a new namespace each run and retains its isolated data. Three finance component calls are saved separately in `feature-components-20261018.json`.

## Real features exercised through ingestion and ask

### 1. Index text and answer a supported definition

The seven paragraphs were stored as `feature-notes-p0001` through `feature-notes-p0007`. Asking `What is the harbor kestrel?` returned:

> The harbor kestrel is a small coastal falcon. it eats small fish.

This demonstrates retrieval plus reconstruction/assembly of supported stored propositions. The wording and lowercase `it` reflect the current realizer. It does not demonstrate unrestricted natural-language understanding.

### 2. Extract and answer event roles

Given `John ate a yellow apple in his house.`:

- `What color was the apple John ate?` → `The apple John ate was yellow.`
- `Where did John eat the apple?` → `John ate the apple in his house.`
- `Who ate the apple?` → `John ate the apple.`

These went through the actual pipeline, with `frame_result.status="answered"`. They demonstrate the supported grammar's role projections, rather than arbitrary graph reasoning or ownership resolution.

### 3. Abstain on a missing event role

`What color was the pear John ate?` returned `No stored sentence states that color in the past.` with frame status `missing`. No query typo rewrite occurred. This is useful bounded abstention; it does not generalize to all unsupported questions, as the France example below shows.

### 4. Produce an extractive summary

`Summarize the harbor kestrel.` appended:

> The harbor kestrel is a small coastal falcon. The harbor kestrel eats small fish.

The summary selected stored sentences. It did not produce a novel explanatory synthesis.

### 5. Expand evidence and list paragraph IDs

`Deep search the harbor kestrel.` returned three possibilities: definition, fish, and nesting paragraphs. `Cite sources for the harbor kestrel.` produced paragraph IDs, but also included two flight-paragraph IDs from the retrieved set. This demonstrates source listing, not a guarantee that every listed source supports the particular displayed claim.

### 6. Reorder stored sentences in creative mode

`Imagine the harbor kestrel.` appended a passage consisting of the fish sentence followed by the definition. This run demonstrates rearrangement/selection of stored sentences; it does not show free story writing or prove run-to-run variation from a single sample.

### 7. Present per-topic comparison sections

`Compare the harbor kestrel and John.` produced a kestrel section and a John section, each containing its stored statements. It did not derive an evaluative comparison or choose a winner.

### 8. Fill a document layout

`Write an email about the harbor kestrel.` produced an Email header, a subject, and three source sentences in its body. To/From/Date were explicitly not stated. The format catalog contains 31 layouts. Only email was exercised live here; the existence of 31 entries is not evidence that all layouts or field bindings are correct.

### 9. Calculate arithmetic

`What is 17 times 24?` returned `17*24 = 408.` through the actual optional math path. This is expression evaluation, separate from retrieved propositions.

### 10. Apply a supported threshold rule

The supplied rule allowed business class for flights over six hours; the Boston–Paris flight was eight hours. `Can I fly business class from Boston to Paris?` returned YES and stated the 8-hour observation and 6-hour threshold. This supports one valid rule case. Previously reproduced implication, modality, conflicting-measurement, and synthesized-evidence issues still limit broader claims about the rule engine.

## Material limits observed live

### An unrelated answer can pass the audit flags

`What is the capital of France?` returned:

> The harbor kestrel is a small coastal falcon. it eats small fish. Business class is allowed for flights over six hours.

Both `audit_passed` and `shine_ok` were true. There was no typo rewrite. Those flags did not establish responsiveness or correctness for this question. This is a direct end-to-end counterexample to treating them as a universal answer-quality test.

Every prompt in this small run reported `thinker_directive="gather"` while still displaying output. That directive is diagnostic advice; a consuming agent must apply its own acceptance policy rather than assume it suppresses delivery.

### The requested neural realizer is not trained

The apple question with `realization="evidence_neural"` returned the same sentence, `mode="deterministic_fallback"`, and `model_checkpoint_id=null`. N0 grammar/planning exists; this did not exercise a trained construction-ranking or graph-decoding model. Separate fact-bridge T5 wording can exist on the machine, but it is not that proposed model.

## Real standalone finance components

Called the actual `validate_message` dispatcher directly, separately from `Appliance.ask`:

- **RefundProof:** 120 tax charged versus 40 correct tax produced 80.0000 USD potential overpayment, **BLOCKED** approval because source/rule bindings were absent, and no actionable total.
- **LedgerCovenant:** 9,000,000 / 2,000,000 produced 4.50x, **COMPLIANT** against a supplied `lte 4.50` threshold.
- **Ledgerlock:** value 84210.00, confidence 0.99, and matching source span `[6:14]` produced **ACCEPT** plus a SHA-256 decision digest.

These are local calculations/validation routines over caller-supplied inputs. They do not establish document authenticity, execute a refund, declare a legal default, or update a loan system. Finance dispatch through the full appliance was not exercised in this run.

## Other implemented surfaces, not demonstrated live here

The repository contains authenticated HTTP entry, tenant/source scopes, deletion, corrections/history, limited aliases/negative frames, typo correction, and local concurrent seats. Code and focused tests exist, but this demonstration did not verify those surfaces end to end. A listing of modules is not a production-readiness claim, and a logical remote-capacity outcome does not prove remote execution.

## What the evidence establishes

The product currently combines a searchable document store, controlled-language answer assembly, role extraction, extractive presentation modes, rule/number utilities, document templates, and integration/service plumbing. The strongest demonstrated common behavior is **retrieving stored text and turning supported pieces into structured replies**. Its general question-answering relevance, rule soundness, and full-reply verification are not consistently established.

No market category, deployment guarantee, or broad accuracy score follows from this small demonstration. The saved examples provide a concrete starting point for choosing what to strengthen next.
