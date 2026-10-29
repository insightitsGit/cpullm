# Prompt ingestion and interpretation

Implemented 2026-10-28. The library now has an internal interpretation stage, so
supported conversational questions do not need an application-specific wrapper.
This is bounded interpretation, not unrestricted language understanding or a
claim of bias-free inference. The aim is to make assumptions visible and prevent
them from becoming facts.

## Request flow

See [output layout alignment](output-layouts.md) for the shared format contract
between spaCy, internal planning and post-judgment table/bullet rendering.

1. Keep the original user message. Enforce caller access and raw-prompt guards
   before running the optional NLP backend or retrieving source data.
2. Run the configured interpreter during request planning, then separate explicit
   tasks and field lists. Record their original spans, order
   and derivation. User background supplies reference context, not verified facts.
3. Separate presentation from factual content. A request for detail increases
   existing response/retrieval budgets; it does not license additional claims.
   [Response-depth flags](response-depth.md) connect long/extended wording and
   explicit size requests to retrieval breadth and supported output allowances.
4. Compile declared conversational constructions into direct questions. Preserve
   literal subject words. Keep the rule and input alongside the resulting query.
5. Optionally annotate the input with a local CPU spaCy dependency parser:
   noun phrases, entities, grammatical roles, negation and modal tokens. Parser
   proposals are accepted only for a declared request grammar whose source spans
   account for the complete request. Unconsumed qualifiers prevent rewriting.
6. Run existing clarification/reference resolution, typo handling and the
   six-channel retrieval pipeline. Record the effective engine query separately
   from the initial interpretation.
7. Use the existing bounded dictionary expansion and missing-attribute repair.
   Keep source access/time constraints on every retrieval. Validate each task
   with the shared answer contract and retain all required proof.

The ingestion stage does not use corpus popularity to decide what the user meant,
create hypothetical answers to embed, infer missing demographics or comparison
criteria, or ingest user statements as trusted source facts. Interpretation
records are diagnostics, never citations. spaCy's entity labels are predictions.

## Supported examples

Without installing additional NLP dependencies:

- `Could you tell me what color the Aster is?` → `what color is the Aster?`
- `I'd like to know where the Aster lives.` → `where does the Aster live?`
- `Please tell me who Mary is.` → `who is Mary?`
- `Tell me the material of the Aster.` → `What material is the Aster?`
- `Tell me the color, habitat, and lifespan of the Aster.` → three ordered tasks,
  each with its own retrieval, answerability outcome and evidence.
- `Could you tell me what color the Aster is and where it lives?` → two tasks;
  the existing unique-antecedent rule can bind `it` to Aster.

Explicit field lists recognize color/colour, habitat, lifespan, shape, material,
weight and definition. Unknown fields cause clarification; they are not silently
omitted. Multiple subjects in a field list require separate requests. Existing
limits remain eight tasks, 32,000 total prompt characters and 1,000 characters
per separated task. A single request still has the encoder's own context limits.

With the spaCy backend, `Please give me information about the color of the Aster.`
can compile to `What color is the Aster?`. The parser must identify the attribute
and its `of` subject, and validation must account for the entire wording.
Adding `in Norway` prevents that rewrite: the qualifier cannot be discarded.

Negation, conditions, restrictive quantifiers and modal wording prevent these
surface rewrites. For example, `Can the Aster live without water?` is not rewritten
into a lifespan question. Existing specialized producers may handle guarded text;
otherwise a preserved request may still be unsupported or need clarification.
Preserving constraints does not imply the engine understands every constraint.

`Which lobster is best?` continues to ask for a criterion. Requesting more detail
does not fill missing evidence or turn a class average into an individual fact.
Financial fields, quoted/source text and code are not cleaned into new facts.

## Configuration

The default `prompt_backend=None` (or `"auto"`) selects spaCy when both the library
and `en_core_web_sm` are installed locally. Otherwise it uses rules and records
the missing-assets reason in `fallback_reason`. It never downloads at request
time. Set `prompt_backend="rules"` to disable NLP deliberately, or `"spacy"` to
require it and fail explicitly when setup is incomplete. Install the optional
backend with the same spaCy version range as the reference adapter:

```powershell
python -m pip install -e ".[prompt_nlp]"
python -m spacy download en_core_web_sm
```

```python
from cpu_llm.pipeline import Appliance

def main():
    with Appliance(namespace="guide", prompt_backend="spacy") as app:
        # Ingest authorized source documents before asking.
        result = app.ask("Could you tell me what color the Aster is?")
        print(result["reply"]["text"])
        print(result["prompt_ingestion"])

if __name__ == "__main__":
    main()
```

The HTTP entry point defaults to `--prompt-backend auto` and also accepts `spacy`
and `rules`. Model loading is lazy,
CPU-only, serialized per adapter and reused across requests. It never downloads
at request time. An explicitly selected backend with missing dependencies/model
raises a setup error instead of silently claiming parser coverage. English is the
initial supported language; an installed multilingual tokenizer is not enough.

Applications can also use `PromptInterpreter().interpret(text)` without a database,
or supply an annotation adapter exposing `annotate(text)`. A custom adapter cannot
directly inject a rewritten query: proposals must pass the same span validator.

## Diagnostic contract

Flag-to-node ownership and execution precedence are governed by the
[mapping contract](flag-routing-review.md), rather than inferred from spaCy
annotations. The [mapping table](prompt-flag-map.md) lists actual consumers.
Graph-backed child results expose observed routing; source/guard/clarification
early returns may have no graph execution. See benchmark v3 revision 2 for
required activation, hold, API-boundary and trace tests.

Single-task results after interpretation contain `prompt_ingestion` with schema
`prompt-interpretation-v1`:

- `input_text`, `query`, `transformations`, `status`: what was interpreted and how.
- `request`: the initial shared factual contract, or `None` for unsupported forms.
- `channels`: initial rule cues, not measured/trained projection-head availability.
  The engine's `prompt_intent` remains authoritative for its actual channel state.
- `constraints`: literal numeric/guard cue spans. Dates/amounts in spaCy entities
  are annotations, not automatically applied database/history filters.
- `annotations`: backend/model, exact spans relative to `input_text`, and a label
  explicitly stating that they are unverified linguistic annotations.
- `backend_policy` and `fallback_reason`: whether automatic selection was requested
  and why a local model could not be selected. The actual backend is never hidden.
- `search_plan`: primary question and at most one existing dictionary equivalent;
  the existing missing-attribute mechanism allows at most three repair searches.
- `engine_query`, `effective_request`: the query/contract after reference and
  typo processing, when execution reaches encoding.

Diagnostics cap annotations and constraint cues at 64 and report omitted counts;
the original query itself is not truncated by that cap. Early scope/guard blocks
do not run this stage. Other early clarifications may return its partial record.

Batch results retain `request_plan.original_message`, each task's original
`text`/source offsets and its `interpretation`. Field-list expansions deliberately
share the original clause span and mark their derivation `explicit_fields`.
Every executed child carries its own `prompt_ingestion` record. Existing batch
continuation, proof and optional-material budgets remain in force.

An information request such as `Please give me information about the color and
habitat of the Aster.` is interpreted during planning, before independent child
retrieval. Previously parser-backed interpretation only ran inside a single
child. Known fields paired with an unknown field ask for clarification rather
than executing only the known part. Raw access/guard checks now precede this
planning-time parser invocation as well as child execution.

Shape, material and weight slots now participate in bounded missing-attribute
retrieval. They use the shared assessment contract, caller source scope and as-of
time, and stop on a supported answer. These slots do not acquire a new rule for
inheriting class attributes: a retrieved class fact must still prove the requested
individual fact under an existing licensed inference.

## Open-source research and selection

- [spaCy](https://github.com/explosion/spaCy), MIT licensed, provides local
  [dependency parsing](https://spacy.io/api/dependencyparser) and
  [rules over tokens/dependencies](https://spacy.io/usage/rule-based-matching).
  Its [versioned model packages](https://spacy.io/usage/models) support explicit
  offline setup. Selected for this adapter and compatibility with the existing
  optional reference stack. Parsed noun/attribute edges supply proposals; source
  coverage checks decide whether a proposal may become a query.
- [Stanza](https://github.com/stanfordnlp/stanza) also supplies tokenization,
  named entities and parsing through configurable
  [processors](https://stanfordnlp.github.io/stanza/pipeline.html). It is a possible
  future annotation adapter; this change does not add a second NLP model stack.
- [Microsoft Recognizers-Text](https://github.com/microsoft/Recognizers-Text)
  handles numbers, units and temporal expressions. The project labels its Python
  distribution alpha. It is a candidate for a separately tested typed-value
  adapter; calendar/timezone resolution must not become an implicit assumption.
- [KeyBERT](https://github.com/MaartenGr/KeyBERT) extracts keywords with embeddings.
  Keywords alone do not express which argument, condition or polarity the user
  requested, so it is not the request-contract authority in this design.

## Validation

`tests/test_prompt_ingestion.py` covers supported normalization, literal subjects,
guarded wording, field coverage, reference binding and rejected parser proposals
with unconsumed qualifiers. `tests/test_request_planner_live.py` exercises human
wording and field-list coverage through actual `ask()` and authorized retrieval.
The real spaCy model is additionally smoke-tested in an isolated dependency
environment; results and full-suite output are retained locally under `build/`.

Latest validation on 2026-10-28 after automatic adoption and planning integration:
**664 passed, 2 skipped, 3 expected failures** in the full live suite (78.10 seconds).
The skips require unavailable trained extractor
checkpoints; expected failures remain the existing resonance sense-grouping
cases. Six existing NumPy overflow warnings remain. A separate Python 3.12
environment ran spaCy 3.8.18 with `en_core_web_sm` 3.8.0 against a disposable
PostgreSQL/pgvector database: automatic backend selection, dependency-backed
attribute interpretation, compound color/habitat retrieval, unknown-field
clarification, cited color output, two-premise possession output and
scope-before-parser checks passed. Scoped/as-of repair regressions cover shape,
material and both supported weight question forms. Encoder assets came from the
existing cache. See `build/prompt-adoption-suite.log` and
`build/clean-install-audit/prompt-adoption-live.json` for the latest local evidence.

General conversation, implicit intentions, arbitrary coordinated clauses and
unrestricted multilingual paraphrases remain outside these declared grammars.
Measure new wording on a frozen independent holdout before claiming general
intent accuracy or an increase in factual coverage.
