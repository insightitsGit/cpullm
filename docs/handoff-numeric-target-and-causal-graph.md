# Handoff: numeric target and causal graph on a descriptive question

**ID:** HO-cpullm-001  
**Project:** cpu-llm (`c:\code\cpullm`)  
**Date:** 2026-10-12  
**To:** consulting agent  
**Status:** Recommendations 1, 3, and 4 are in cpu-llm. Do not invent a policy, an objective, or a causal edge from prose.

## Question this handoff answers

On “What is Mount Elbert?” PrismThinker still reports a missing numeric target and a missing causal graph. The sentence is still realized. PrismManifest and its CUDA gate were proposed as the fix for the numeric target. This note says what those libraries actually do, and what to change instead.

## What the live turn did

Command shape: `Appliance().ask("What is Mount Elbert?")`.

- `cognition_status`: `deliberated`
- `audit_passed`: true
- PrismShine: `pass`
- Checked sentence starts: “Mount Elbert is visible to the southwest of Leadville, often snow-capped even in the summer.” Further retrieved propositions are realized into the same answer, including the elevation sentence and the “because he brokered a treaty” sentence.
- One run returned `thinker_directive=escalate` with an empty question list. A second run returned `gather` with:
  - `no numeric threshold on hypothesis or objective`
  - `causal_graph is required`
- `numeric_claims` on that gather run:
  - `wikitext2-mount-elbert-p0001`: `amount_min = 4401200000.0`
  - `wikitext2-mount-elbert-p0008`: `amount_min = 4399000000.0`
- No `numeric_qualifiers`. No policy question. Discovery was not suggested.

`escalate` with no questions happens when both misread amounts are in the shortlist and PrismThinker treats them as a conflict. `gather` with the two questions happens when the empirical regime is selected and the conflict does not escalate. Either way the checked sentence is still produced, because `think` always edges to `cognize`.

## Why the numeric target appears

The passage says heights such as `14,440 feet (4,400 m)` and `4,399 m`. It does not state a sum of money.

VectorPrism’s heuristic extractor treats the pattern `number + million` or `number + m` as money and multiplies by 1,000,000:

```179:181:C:\Users\parva\AppData\Local\Programs\Python\Python312\Lib\site-packages\vectorprism\structure_extract.py
    m = re.search(r"\$?\s*([\d,.]+)\s*(million|m\b)", q)
    if m:
        attrs["amount_min"] = float(m.group(1).replace(",", "")) * 1_000_000
```

`4,399 m` matches `m` and becomes `amount_min = 4,399,000,000`. `_structure_metadata` copies that float onto the chunk. `cpu_llm.measurements` knows `m` is metres, but it does not overwrite a key the finance extractor already wrote. Feet are not in that measurement map at all.

A numeric claim flips PrismThinker to the empirical regime. That regime’s evaluators are empirical, causal, and formal. Empirical then asks for a threshold because no hypothesis payload and no `ObjectiveSpec.target` names a goal for `amount_min`. The question is aimed at a fake money figure.

## What PrismManifest and CUDA actually do

Number separation is already on the host, not in the CUDA kernel.

- `prismmanifest.canonicalize.canonicalize_number` strips currency marks and commas.
- `to_micro_units` stores `value * 1_000_000` as an int64.
- `EvidenceSpan` keeps the raw token, character span, `canonical_micro`, and digit fingerprint.
- `cpu_llm.manifest_spans.build_span_grammar` already cuts every numeric token in the retrieved chunks into those spans.
- `answer_numbers_allowed` already rejects a realized sentence whose number is not one of those spans. The `grammar` node runs this on CPU.

`prismmanifest.cuda.kernels_numba.gate_verify_kernel` receives two integer arrays that Python already built: `evidence_micro` and `query_micro`. It passes a field only when the candidate integer occurs in the evidence, the span is grounded, and disagreement stays inside the immaterial band. `verify_gate_host` is the same predicate. `verify_gate_device` uses CUDA only when Numba sees a GPU; otherwise it runs the host function. This engine is CPU-only. The kernel does not parse `m`, does not choose a comparison target, and does not read the passage.

PrismEval (`prism-eval` 0.2.2, source `C:\code\Prism_Eval`) is a pre-deploy test suite for digit drops and prompt injection. PrismShield (`prism-shield` 0.2.0, source `C:\code\Prism_shield`) seals extracted parameters before a tool or DAG runs. Neither supplies an `ObjectiveSpec` target.

## Why the causal graph appears

The causal channel already quotes the passage sentence that says Mount Elbert was named because Samuel Elbert brokered an 1873 treaty. That quote is evidence.

PrismThinker’s causal evaluator does not read “because”. It returns `causal_graph is required` when `ReasoningContext.causal_graph` is missing. A graph is a caller list of edges: source, target, and a sign of `-1`, `0`, or `1`. The evaluator then walks from a treatment to an outcome. This question supplied neither the edge `treaty → naming` nor those two endpoints.

The empirical regime asks for that graph even on a “what is” question, because numeric claims selected the regime. The missing object is the graph, not the sentence.

## Recommendation

1. Stop the false money claim before consulting a target. `m` as metres must not become `amount_min`. Keep the existing finance behavior for a real “N million” or “exceeds N million” phrase, including `amount_min = 10_000_000` from “exceeds 10 million”. Do not let the physical extractor treat “10 million” as metres. After the false claim is gone, re-ask “What is Mount Elbert?” and record whether `gather_questions` is empty.
2. Treat PrismManifest spans as the observation list. A number in the answer must remain a span cut from a retrieved passage. Do not add a CUDA requirement. The host span check is the same decision.
3. Leave the numeric target caller-owned. An observation is “the passage says 14,440 feet / 4,400 m”. A target is a second number the caller puts on a hypothesis payload or an `ObjectiveSpec` term when they ask for a comparison. Do not invent that number from the article. A descriptive question should not demand a threshold merely because a height was written.
4. Leave the causal graph caller-owned. Keep quoting the “because” sentence from the causal channel. Do not promote that sentence into an edge. If step 1 removes the empirical regime from this question, the causal evaluator should drop out with it. That is the desired result for this prompt.
5. Do not add a policy rule for this question. Policy is for a may or must decision. This turn did not ask for one.

## Out of scope for this consult

- Training the relational, disentangled, hyperbolic, or causal VectorPrism heads. Dense is the only trained retrieval channel. Identity’s anchor is still zero.
- Parsing the 407 validation chunks that have no round-tripping proposition.
- Gating `cognize` on `thinker_directive == answer`. Today `think` always continues to `cognize`, so a gather or escalate result still realizes the sentence. That is a separate behavior from these two questions.
- Discovery stage 5.

## Files

- `src/cpu_llm/pipeline.py` — `_structure_metadata` copies finance attrs, then literal measurements; graph order is channels, detail, spans, think, cognize, grammar, shine, reply.
- `src/cpu_llm/measurements.py` — physical units include metres and feet, including a hyphen (`14,440-foot`). `stated_million_amount` keeps a span when a currency marker, a currency word, or a bare `million` is money, and rejects bare `m`, a following count noun, and `noun of N million`.
- `src/cpu_llm/manifest_spans.py` — PrismManifest span grammar already wired.
- `src/cpu_llm/channels.py` — causal channel quotes a because-sentence and does not build an edge.
- VectorPrism `structure_extract.py` — `amount_min` regex above. Do not edit the installed package in place; fix the claim on the cpu-llm side or by a deliberate VectorPrism change.
- PrismThinker `evaluators/empirical.py` — `no numeric threshold on hypothesis or objective`.
- PrismThinker `evaluators/causal.py` — `causal_graph is required`.
- PrismManifest `cuda/verify_core.py` and `cuda/kernels_numba.py` — integer evidence match, not a target.

## Re-run after the span fix (2026-10-12)

`Appliance().ask("What is Mount Elbert?")` after dropping metre-as-million claims:

- `thinker_directive`: `gather`
- `thinker_regime`: `empirical` (`REASON_AST_REJECTED` only; the score came from numeric claims)
- `gather_questions`: `no numeric threshold on hypothesis or objective`, `causal_graph is required`
- `cognition_status`: `deliberated`
- `audit_passed`: true
- `numeric_claims` for `wikitext2-mount-elbert-p0008`: `height_ft = 14433.0`, `height_m = 4399.0`
- no `amount_min`, no invented policy, objective, or causal edge

The false billions are gone. The two questions remained on that re-run because the real height was still a numeric claim, and PrismThinker selected the empirical regime for any numeric claim.

## Re-run after descriptive routing (2026-10-12)

A measurement with no caller target and no caller causal graph is now a formal check. The empirical and causal heads are not selected. `Appliance().ask("What is Mount Elbert?")`:

- `thinker_directive`: `answer`
- `thinker_regime`: `closed_formal`
- `thinker_evaluators`: `formal` only
- `gather_questions`: `[]`
- `cognition_status`: `deliberated`
- `audit_passed`: true
- PrismShine: `pass`
- `wikitext2-mount-elbert-p0008` still has `height_ft = 14433.0` and `height_m = 4399.0`
- no invented policy, objective, or causal edge

A turn that already has a causal graph, such as the policy/incident pair, still runs the empirical and causal heads. A caller-supplied objective target does too.

## Later lexical layer (2026-10-12)

Word relations, sleep, and identity lookup are specified in section 7 of `docs/cpu-llm-v1.6.1-architecture-spec.md`. They do not change the Mount Elbert routing above.

- Ingestion tags content words with the article slug and a PrismResonance key. Sleep writes `TAXONOMIC_LINK` between chunks that share a category and pass the relational cosine and PrismCognition ruin checks.
- A stored copula that cognition accepts becomes `INSTANCE_OF` on concept nodes `word:{term}`. `SUBCLASS_OF` is added only when a second copula chains and the child tensor sits in the parent Poincaré cone.
- Training and `Appliance.sleep()` write a length-0.05 signature of the second and third hand into the last 32 values of the relational channel. The dense core is unchanged. The category integer is not written into `relational[0]`.
- “What is …” / “Who is …” can realize an accepted copula from those word nodes when the retrieved paragraph has no proposition. A why-question does not.
- No numeric target, `ObjectiveSpec`, or causal edge is invented from a passage. PrismThinker is not used to mint word links.
