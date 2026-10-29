# Change record: installation, prompt interpretation and response rendering

Recorded 2026-10-29. This document accompanies the implementation, tests and
benchmark specification in the same commit. It covers work after base revision
`a9c45918f373879ffddeed63549aeceec7c819ee`, performed on October 28–29.
To identify the exact committed implementation, use the commit containing this
document and its associated benchmark specification, not the base revision.

## Why this work was done

A consumer reported installation/build difficulty and said an external wrapper
was needed to convert human prompts into forms the library understood. We also
needed prompt-controlled longer responses and consistent tables, bullets,
numbering and report templates. The work connects those concerns through the
existing evidence-backed pipeline rather than adding a free-form answer decoder.

The shared factual answer contract, final judging and earlier identity/possession/
causal improvements were already committed in the base revision. Their scope is
documented in [the semantic implementation report](semantic-implementation-report.md).
This record describes the subsequent integration, not a replacement of those rules.

## 1. Reproduced and corrected a clean-install failure

A source build, fresh editable installation, wheel installation and module imports
succeeded on Windows x64 / Python 3.12.10. First ingestion then failed with
`No module named 'community'`, followed by PrismRAG's message that NetworkX and
python-louvain were required. The development environment already had the missing
package, hiding the problem from its live tests.

The dependency is now `prismrag-patch[graph]==0.2.1`, requesting the graph packages
that normal taxonomy ingestion needs. Rebuilding and installing the corrected
wheel pulled python-louvain automatically. Ingestion, a color question and a
two-premise possession join passed in the isolated environment. The reporting
user's exact error/platform was unavailable, so this is a confirmed independent
failure, not proof of what happened on their machine.

The audit also distinguished database connection refusal from package building.
PostgreSQL/pgvector and encoder assets remain explicit runtime prerequisites.
PyPI and Git both use version 1.9.1 while containing different code; this work did
not publish a release or change that version. See the complete
[clean-install audit](reviews/2026-10-28/clean-install-audit.md).

## 2. Added internal prompt interpretation and adopted spaCy

New `src/cpu_llm/prompt_ingestion.py` supplies `PromptInterpreter`, bounded request
normalization and a lazy CPU `SpacyPromptBackend`. Research considered spaCy,
Stanza, Microsoft Recognizers-Text and KeyBERT. spaCy was selected for local
dependency/phrase annotations and compatibility with the existing optional
reference stack; [research and selection](prompt-ingestion.md#open-source-research-and-selection)
remain in the detailed specification.

Supported inquiry shells and indirect constructions become direct questions.
Explicit field lists become ordered retrieval tasks. For example, development
wording such as `Could you tell me what color the Aster is?` can become
`what color is the Aster?`; a color/habitat/lifespan request becomes three tasks.
These examples are known regressions, not fresh benchmark data.

The parser proposes source spans, entities and attribute structures. Internal code
checks declared grammar, original span coverage and preservation of qualifiers
before accepting a proposal. Parser predictions do not become stored facts or
citations. Unknown fields ask for clarification instead of disappearing. Conditions,
negation, restrictive quantifiers and modality are not paraphrased away. This does
not establish that every preserved condition is understood, or that any parser
is bias-free.

Configuration is `Appliance(prompt_backend=...)` and the HTTP
`--prompt-backend` option. Default `None`/`"auto"` selects a locally installed
spaCy model when available and otherwise records a rules fallback and reason.
`"rules"` disables NLP; `"spacy"` requires setup and fails explicitly if assets
are absent. `cpu-llm[prompt_nlp]` declares the optional spaCy dependency. Model
installation is explicit; request handling never downloads it implicitly.

## 3. Connected planning, retrieval and the parser

`request_planner.py` now uses the configured interpreter while planning tasks,
including parser-backed compound information requests. Caller scope and raw
guards precede planning-time model invocation. The existing eight-task and prompt
size bounds remain; original text, task spans and derivations are retained.

`attribute_search.py` now supports bounded repair for shape, material and weight
in addition to the previously supported relations. It uses the shared request and
assessment contracts, source allowlists and historical time filters. It does not
grant new permission to infer an individual's attributes from arbitrary class
attributes. Existing joins still require licensed membership/universal premises.

`pipeline.py` exposes `prompt_ingestion`, its initial interpretation and the
effective engine query/contract after reference and typo handling. Initial rule
channel cues are distinct from the engine's actual trained/enabled head metadata.
The six-channel retrieval design and existing proof rules remain in place.

## 4. Connected prompt-derived response-length flags

`response_policy.py` recognizes long/extended/detailed requests, elaboration,
additional-detail directives and explicit sentence/item/word requests. The policy
separates presentation from factual intent and returns `response_plan.flags`,
including `long_response`, `expand_retrieval` and `extended_overview`.

Ordinary retrieval starts with five candidates; a normal detailed prose overview
uses twelve. Larger optional output budgets scale retrieval, currently up to 24
candidates after the 20-unit output clamp. Existing search-call/repair limits,
source authorization and temporal filters remain. Composition consumes the
optional sentence/item budget before final judgment.

Word counts inform an estimated allocation of one unit per 25 words, rounded up
and clamped, with explicit sentence/item counts taking precedence. Exact word
count enforcement is not implemented. Mandatory proof is not trimmed to meet a
presentation ceiling, and a small corpus is not padded to reach a requested length.
A longer color answer must still answer the color question; length alone does not
authorize unrelated facts. See [response-depth specification](response-depth.md).

## 5. Added Tabulate, Jinja2 and output-format flags

New `src/cpu_llm/output_rendering.py` supplies a shared layout recognizer and
post-judgment rendering. It separates explicit format directives before spaCy
parses factual content, preventing `as a table` from becoming part of an entity.
The existing fixed email/letter/report/checklist/FAQ catalog remains available.

Direct dependencies now include `tabulate>=0.9,<1` and `Jinja2>=3.1.6,<4`.
Tabulate renders Markdown/escaped HTML tables with numeric parsing disabled.
Jinja2 renders built-in Markdown and HTML templates from judged response records.
Template-like source strings are data, never executable template source; HTML
templates autoescape their values. No user-authored template execution was added.

Prompt flags include `table`, `bullets`, `numbered`, `report`, `html`, `markdown`
and `template_requested`. They are reflected in `response_plan.format` and
`output_media`, the interpreter's output-format record, and rendered media metadata.
Examples include `as a Markdown table`, `as an HTML report`, `as bullet points`
and `as a numbered list`. Format/depth instructions can apply to a whole batch.

Integration testing found and corrected a propagation gap: global list style
was reaching the aggregate renderer but not the child overview producer. The
child now receives the layout needed to produce verified list units. A direct
factual question's content query is not changed just to add numbering or bullets.

Rendering arranges existing judgments rather than selecting new facts. Initial
tables have Request/Response/Sources columns, one row per judged task response.
Pending tasks remain pending and nonanswers stay nonanswers. This is not arbitrary
entity/attribute spreadsheet generation. Every source ID comes from accepted
evidence, not simply from a retrieval neighbor.

`rendered_response` retains canonical text, structured rows/evidence, template ID,
renderer, media type and display text. `reply.text` contains the requested layout;
`reply.body` and factual judgments retain their canonical contracts. HTML output
is a returned payload, not a published website. See [output-layout specification](output-layouts.md).

## 6. Validation history and evidence

The work progressed through independent install reproduction, focused negative
tests, full live suites and real spaCy integration probes. Full-suite milestones
were 635, 658, 664, 676, 686 and finally **695 passing tests**, with two skipped
trained-extractor cases, three existing expected resonance sense-grouping failures
and six existing NumPy overflow warnings. Milestones are successive regression
snapshots, not independent quality measurements or additive test counts.

Latest complete live suite: **695 passed, 2 skipped, 3 expected failures in 78.66
seconds**. It covers prompt flags, scoped HTML reports, joins, clarification,
budgets and rendered proof. The actual spaCy 3.8.18 / English model 3.8.0 adapter
was exercised in a separate Python 3.12 environment, including a two-row cited
table, unknown-field clarification and empty-scope rejection before model loading.
Encoder loading deliberately reused cached assets; fresh model downloading and
all operating systems/Python versions were not established by these checks.

Fresh wheel/sdist builds succeeded, metadata contains both rendering dependencies,
and install checks used environments without system packages. Tests verify exact
leading-zero values, literal Jinja-like source text, escaped HTML/table markup,
source boundaries and no padding. No broad accuracy claim follows from them.

Local evidence is ignored under `build/`: `clean-install-audit/`,
`template-flags-validation/`, `template-flags-suite.log`,
`template-flags-build.log` and `template-flags-dist/`. Validation snapshots include
source bundles and hashes; these local artifacts are not a published release.

## 7. Preserved benchmark specification and handoff

The following three files are versioned with this change:

- [Benchmark v3 design](benchmark-v3-design.md).
- [Machine-readable protocol](benchmark-v3-spec.json).
- [Execution handoff](handoff-benchmark-v3.md), including the next agent's assignment.

V3 specifies 240 fresh standalone cases across 12 families, split 144 development /
96 holdout, plus 24 conversation scripts split 12/12. The paired primary arms are
forced rules and real spaCy with resonance tags off. It separately checks automatic
backend selection, clean installation, known regressions, source/holdout freezing,
visible Markdown/HTML output, proof, scope/time, continuation and performance.

**The v3 benchmark has not been run.** Its evaluator needs to be implemented by
the executing agent. The existing v2 runner is not a complete v3 scorer. A new
run must select the commit containing the implementation/specification, or freeze
an explicitly recorded working tree, rather than evaluating historical base HEAD.

## Remaining work and limits

Run v3 before claiming general improvements on fresh prompts. Preserve all
failures and adjudicate uncertain scoring independently. The broader typed
semantic compiler, complete relation registry, unrestricted grammar/multilingual
coverage, strict word limits, arbitrary user templates and Word/Excel output
exports remain outside this implementation. Resonance grouping failures and
existing numeric warnings are still visible. Reingestion may be necessary when
adopting extractor/graph changes; a code update alone does not rewrite stored facts.

This commit records implementation and specifications. Publishing a new package
version, deploying a service or pushing the commit are separate actions.
