# Stylistic generation: implemented specification v2

This document specifies the current implementation, not every proposed feature in the [design](stylistic-generation-design.md). Its [JSON companion](stylistic-generation-spec.json) records machine-readable controls and construction IDs. The style construction implementation originated in `3b8ab1e`; subsequent parser fixes and strict-mode precedence are noted below. The fresh public-API chat capture uses runtime `271d685`.

## Purpose and execution

Construct alternative sentences and longer related responses from accepted facts or source-bound document claims. The base fact path selects from ten reviewed constructions over color, location, shape, material and explicit weight. The source-checkout document extension adds two technical predicate constructions, using the same lexicon ranking and independent inverse verification. It does not retrieve tone phrases from the knowledge base, infer missing details, change permissions or train a language model.

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

Profiles are explicit and per-request. Use `style=` or an anchored directive such as `in a friendly tone`, `In a friendly tone, ...` or `. Use a friendly tone.` The directive is removed from the evidence query; source documents do not need matching tone vocabulary. API settings override prompt tone. HTTP bodies do not expose `style`, but their prompt text supports these directives. Quoted titles and negated instructions do not activate tone. Repeat the control on a follow-up; it does not persist to later requests.

Strict evidence mode takes precedence and bypasses the style node, even if
`style` is supplied; strict responses do not include a generated stylistic
companion. Finance verdicts and generic medication/clinical attributes remain
outside the current five-relation adapter. See the fresh
[public-API chat demonstration](examples/2026-11-02-tone-chat/TRANSCRIPT.md).

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

On the base single-fact path, canonical reply and judgment fields remain unchanged and the verified text is a companion. On the source-checkout document path, `reply.text` can publish verified derived prose, `judgment.verification` identifies document constructions, and `rendered_response.canonical_text` preserves the quotation view. Original quotes/source evidence and `audit_passed=False` remain. Generated text must not be labeled a verbatim quotation or inherit an audit as proof of real-world truth. The document extension uses `document-style-v1`; the older fact companion remains `style-result-v2`.

## Tested behavior and limits

The [composition evaluation](benchmarks/2026-11-01-stylistic-composition/REPORT.md) records 200 finite-construction cases and the implementation's full live suite: 771 passed, 2 skipped and 3 expected failures. Of the 200 component cases, 120 used an explicitly labeled neutral fallback.

The [fresh scenario audit](benchmarks/2026-11-02-stylistic-scenarios/REPORT.md) records 49/49 stylistic contract checks per real rules/spaCy arm, plus 16/16 live layout/session integration tests. It covers five-fact generation, eight-task composition, budget refusal, missing/conflicting data, relationship restrictions, source scope, historical corrections, clarification, cancellation and no style leakage. These are not overall answer-accuracy percentages or independent human fluency ratings.

The historical audit confirmed an upstream rules issue: “Please give me information about the color of the Virel” returned material information. Styling declined it; spaCy interpreted it correctly. That rules-parser defect was subsequently fixed and covered by `tests/test_domain_gap_fixes_live.py`; the original audit is retained unchanged. The style node itself cannot repair incorrect interpretation by inventing a better answer.

Remaining limits include duplicate corroborating proof sets, unlisted color/shape values, non-ASCII forms, inherited multi-premise facts, arbitrary specialist outputs, general creative prose and automatic tone/audience inference. Long conjunctions can sound repetitive. Broader vocabulary, naturalness improvements and visible publication require further reviewed constructions and tests.

## Verification sources

Runtime: `src/cpu_llm/stylistic/`; public integration: `src/cpu_llm/pipeline.py`; guarded weight-question normalization: `src/cpu_llm/prompt_ingestion.py`.

Tests: `tests/test_stylistic.py`, `tests/test_stylistic_composition.py`, `tests/test_stylistic_live.py`, and `tests/test_stylistic_scenarios_live.py`. The registry consistency test checks the JSON controls, profiles, relationships, relation set and construction IDs against runtime definitions. Immutable audit artifacts preserve original prompts, responses, proof and known findings.

## Trigger checklist

- Enable with `app.ask(message, style="friendly")`, validated `StyleOptions`, or an explicit prompt tone directive. With neither API nor prompt tone, the subgraph is disabled.
- After canonical dispatch, judgment and retrieval repair, execute `stylistic`, then `style_verify`, then layout rendering.
- Require structurally accepted, affirmative, individual, subject-directed facts with matching proof. Supported relations: color, location, shape, material and explicit weight.
- Skip blocked, held, incomplete, unsupported or clarification results. Aggregate batches only when complete supported facts share one subject.
- Respect relationship restrictions and the smaller of the style and response sentence budgets; never discard claims to fit.
- Strict evidence bypasses the node. Built-in social variants are a separate mechanism.
- Anchored tone directives in Python/HTTP prompt text activate it; response length alone does not. Style does not persist between turns.
- Use `stylistic.text` only for `generated` or `unchanged` with verification true. The base fact reply is preserved; document replies can publish verified prose with the quotation view retained. Inspect `executed_nodes`, skip reasons, `tone_alignment`, claim counts and proofs.

The central flag registry includes `request.style`. Public API ordering, explicit activation and strict bypass have regression coverage in `tests/test_style_trigger_order.py`.

## Source-checkout document tone extension

A friendly source phrase is not required. For example, “Write a detailed article
about Helios in a friendly tone” separates the topic Helios from the tone control.
Two additional lexicon entries license friendly/formal document predicate
construction through the existing weighted semantic/intensity/tone/genericness
ranking. New sentences use exact source predicates and additive conjunctions;
friendly contraction is limited to a leading “does not”, and a generated “It”
requires a source-declared nonhuman identity plus the same paragraph subject.
The independent inverse grammar recovers every original predicate in order,
checks source hashes, and refuses omitted/changed claims, unsupported scope or
an insufficient explicit budget. Complex/conditional records remain visibly
attributed quotations. Unsupported expressive preferences report neutral fallback.

This is `document-style-v1`, published as verified derived document prose with
original quotes/proofs and a canonical quotation view retained in JSON. It does
not turn quotations into certified real-world facts, infer an unknown design,
or use a neural decoder. Strict evidence always keeps the quotation-only path.
See `tests/test_document_tone.py` and the saved prompt-tone examples.
