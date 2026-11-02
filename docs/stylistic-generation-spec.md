# Stylistic generation: implemented specification v2

This document specifies the current implementation, not every proposed feature in the [design](stylistic-generation-design.md). Its [JSON companion](stylistic-generation-spec.json) records machine-readable controls and construction IDs. The tested runtime is `3b8ab1e`; later documentation/test commits do not change that implementation.

## Purpose and execution

Construct alternative sentences and longer related responses from already accepted factual decisions. The node selects from ten reviewed constructions over five relations: color, location, shape, material and explicit weight. It does not retrieve new facts, change source permissions, infer missing details or train a language model.

`stylistic -> style_verify` is a ChorusGraph output subgraph invoked after canonical request dispatch, final judgment and retrieval repair, before existing layout rendering. Batch children are processed separately; complete same-subject children can also receive an aggregate companion. The verifier checks each licensed clause, complete claim coverage and the proof union. Only additive `and` is available for composition; causal or comparative implications cannot be added.

## Python API

`Appliance.ask(message, *, style=None)` accepts a tone string or `cpu_llm.stylistic.StyleOptions`. Omitting style retains the existing path without loading the style subgraph. No new required constructor argument or database schema is introduced. Invalid controls raise `ValueError` before retrieval.

```python
from cpu_llm.stylistic import StyleOptions, Relationship

# Run inside an existing appliance context, after ingesting the relevant facts.
result = app.ask(
    "Tell me the color, habitat, shape, material, and weight of the Aster.",
    style=StyleOptions(
        tone="friendly",
        relationship=Relationship.COLLEAGUE,
        max_sentences=3,
        clauses_per_sentence=2,
    ),
)
sidecar = result.get("stylistic", {})
if sidecar.get("status") in {"generated", "unchanged"}:
    print(sidecar["text"])
    print(sidecar["proof"])
```

Profiles are explicit and request-local. Repeat the argument on a follow-up if wanted; it does not enter pending session state or persist to later requests. Existing HTTP request models do not expose this parameter. Prompt wording alone does not enable tone selection.

## Controls and constraints

- Tone order: friendly, poetic, formal, emotional, serious, playful, melancholic, empathetic, analytical, intimate. `tone_weights`, when supplied, is an immutable ten-value tuple of finite nonnegative weights summing to one within tolerance. It replaces the one-hot preference; the tone label remains diagnostic.
- Intensity: `magnitude` and `arousal` are finite values in `[0, 1]`; `valence` is in `[-1, 1]`. Defaults are `0.4`, `0.3` and `0.0` respectively. These rank eligible constructions; they do not authorize stronger factual claims.
- Relationships: UNKNOWN, FAMILIAL, ROMANTIC, COLLEAGUE, FORMAL and CASUAL flags. Combine flags with `|`. Restrictions accumulate and override permissions; FAMILIAL plus ROMANTIC still forbids intimate tone. Unknown context does not authorize intimate diction. Conflicting tone/context requests skip styling.
- Budget: `max_sentences` defaults to 3, range 1–20. `clauses_per_sentence` defaults to 2, range 1–4. The sentence allowance is intersected with the existing response plan. At most eight complete task frames can be aggregated. If every claim cannot fit, composition is declined rather than truncated.

Construction eligibility uses exact relation licenses, POS-mask intersections and register-risk exclusions before scoring. Read-only arrays hold curated tone/intensity/genericness features. Ranking weights are semantic license `0.40`, intensity `0.25`, tone affinity `0.25`, minus genericness penalty `0.15`. Valence distance is normalized by two; ties use rounded scores and stable IDs. This is not a trained word-embedding dictionary or permission for arbitrary synonym substitution.

## Eligibility and output

The current adapter accepts structurally judged affirmative individual decisions with a matching subject, a supported canonical construction, and one exact accepted source proof per frame. Names, values and decimal units are copied. Canonical text is bounded to 240 characters and supported slots to 80; vocabulary/forms are deliberately limited. Unsupported negation, conditions, quantifiers, tense changes or multi-premise derivations do not receive a rewritten frame.

`result["stylistic"]` uses schema `style-result-v2`:

- `generated`: new verified companion text is present.
- `unchanged`: a verified construction prints canonical wording; text is present.
- `skipped`: unsupported input, policy conflict or inadequate budget; no companion text.
- `rejected`: a style execution/verification failure; no companion text.
- `children`: child sidecars exist, but no safe aggregate companion is available.

Successful results expose `text`, original source `proof`, per-claim subject/relation/value, selected construction IDs, score components, sentence count, `tone_alignment`, actual style-node execution and a `style-verification-v2` record. `neutral_fallback` means the requested expressive tone has no matching factual diction; it is not evidence of successful emotional/poetic style. A skipped result can be the correct behavior even when its canonical answer is valid.

Canonical `reply`, `answer`, answer/outcome, `judgment`, audit and source-evidence fields retain their existing meanings. The generated text is a **derived paraphrase**; it must not be labeled a verbatim source quotation or inherit a canonical audit as proof of world truth. Existing Markdown/HTML rendering uses canonical content. An application can explicitly consume the verified companion, but automatic visible-answer replacement is not implemented.

## Tested behavior and limits

The [composition evaluation](benchmarks/2026-11-01-stylistic-composition/REPORT.md) records 200 finite-construction cases and the implementation's full live suite: 771 passed, 2 skipped and 3 expected failures. Of the 200 component cases, 120 used an explicitly labeled neutral fallback.

The [fresh scenario audit](benchmarks/2026-11-02-stylistic-scenarios/REPORT.md) records 49/49 stylistic contract checks per real rules/spaCy arm, plus 16/16 live layout/session integration tests. It covers five-fact generation, eight-task composition, budget refusal, missing/conflicting data, relationship restrictions, source scope, historical corrections, clarification, cancellation and no style leakage. These are not overall answer-accuracy percentages or independent human fluency ratings.

The audit also confirms an upstream rules issue: “Please give me information about the color of the Virel” returned material information. Styling declined it; spaCy interpreted it correctly. Direct supported questions such as “What color is the Virel?” worked in both arms. The style node cannot repair incorrect interpretation by inventing a better answer.

Remaining limits include duplicate corroborating proof sets, unlisted color/shape values, non-ASCII forms, inherited multi-premise facts, arbitrary specialist outputs, general creative prose and automatic tone/audience inference. Long conjunctions can sound repetitive. Broader vocabulary, naturalness improvements and visible publication require further reviewed constructions and tests.

## Verification sources

Runtime: `src/cpu_llm/stylistic/`; public integration: `src/cpu_llm/pipeline.py`; guarded weight-question normalization: `src/cpu_llm/prompt_ingestion.py`.

Tests: `tests/test_stylistic.py`, `tests/test_stylistic_composition.py`, `tests/test_stylistic_live.py`, and `tests/test_stylistic_scenarios_live.py`. The registry consistency test checks the JSON controls, profiles, relationships, relation set and construction IDs against runtime definitions. Immutable audit artifacts preserve original prompts, responses, proof and known findings.
