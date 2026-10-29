# Prompt-to-output layout alignment

The prompt interpreter, response policy and request planner now share the layout
recognizer in `output_rendering.py`. A format instruction is separated from the
factual question before spaCy parses it. This prevents `as a table` from becoming
part of an entity name or invalidating an otherwise complete attribute parse.

Supported explicit forms include:

- `Show the color and habitat of the Aster as a table.`
- `Please give me information about the color and habitat of the Aster as a table.`
- `What color is the Aster? Please use a table.`
- `Explain the Aster in a table.`
- `What color is the Aster as bullet points?`
- `Tell me about the Aster as a numbered list.`
- `Show the color and habitat of the Aster as an HTML table.`
- `Show the color and habitat of the Aster as an HTML report.`
- `Tell me about the Aster as a Markdown report.`

The second form uses the configured spaCy parser to identify attribute proposals;
internal code validates complete source coverage, expands the explicit fields,
and assigns one factual contract to each child. The layout does not supply facts.
Quoted text, `What is a table?`, and negated layout requests are not format flags.
The ambiguous phrase `in a table` requires a recognized command position; it is
not stripped from a question such as `Where is data stored in a table?`.

## Rendering contract

The public `ask()` boundary renders after the existing single-task final judgment
or aggregate per-task judgment. It does not reretrieve, select different facts,
infer comparisons, or invent missing values. Access/guard refusals retain their
existing refusal path.

Table rendering uses the declared `tabulate>=0.9,<1` dependency with GitHub Markdown
or escaped HTML output and numeric parsing disabled. Jinja2 (`>=3.1.6,<4`) is a
direct dependency and renders the application-owned templates. The initial table
schema has three columns:
`Request`, `Response`, and `Sources`. Each row contains one already-judged child
response; a single-task result produces one row. This is a table of verified
responses, not an arbitrary spreadsheet whose cells have independently inferred
meanings. New entity/attribute matrix templates require additional typed binding
and proof rules before support can be claimed.

`rendered_response` (`rendered-response-v1`) preserves:

- `rows`: original request/response text, status, accepted evidence and source IDs.
- `canonical_text`: the original response that passed the factual judgment.
- `text`, `format`, `media_type`: the display representation.
- `template_id`, `renderer`, `table_renderer`: the built-in template and rendering
  libraries actually used. Markdown layouts use `content.md.j2` or
  `report.md.j2`; HTML uses format-specific `.html.j2` templates.
- `verification`: a statement that this is layout of judged content, not new claims.

`reply.text` receives the requested display layout. `reply.body`, `answer_status`,
the answer judgment, and evidence remain available in their original contracts.
Shine and the factual judge check the canonical claims before layout; the table
renderer does not claim a second grounding verdict. Source HTML is escaped, table
pipes are escaped, and source newlines become display line breaks. Raw strings,
including leading-zero values, remain in structured row data.

Pending tasks remain pending. Clarification text stays a question. An insufficient
answer is displayed as its existing nonanswer. No renderer completes these cells.
Source IDs come only from accepted answer/supporting evidence, not neighboring
retrieval candidates. Existing source-scope, historical filtering, length budgets
and proof retention continue to apply.

Existing bullet/numbered document templates remain in `formats.py`. Existing list
and batch producers keep their own item boundaries. A single factual response
requested as bullets/numbering can be wrapped as one intact unit, preserving
multi-premise proof rather than splitting it into unsupported fragments.

## Configuration and compatibility

No new rendering argument is required in Python. Format directives produce
`response_plan.format` values `table`, `bullets`, `numbered`, or `report`; ordinary
output remains `prose`. `response_plan.output_media` is `text/markdown` or
`text/html`. The prompt-derived flags are `table`, `bullets`, `numbered`, `report`,
`html`, `markdown`, and `template_requested`; they coexist with the response-depth
flags rather than replacing them. Applications can inspect these fields without
trying to infer layout from the returned text. For HTML, `reply.media_type` and
`rendered_response.media_type` identify the payload explicitly.
`PromptInterpreter.interpret()` also returns `output_format`, `output_media` and
`original_input`, with linguistic span offsets relative to its layout-free
`input_text`. Batch task offsets still refer to the original user message.

The existing letter/report/checklist/FAQ catalog is unchanged. The new report
layout groups judged task responses with citations; it is separate from the
existing document drafting catalog. Jinja2 uses a fixed in-code template loader,
strict missing-field handling and HTML autoescaping. Prompt/source strings are
values, never executable template source. Only Tabulate's already-escaped HTML
table markup is trusted as markup; unsafe HTML table mode is not exposed.

This change does not implement arbitrary user-authored Jinja templates,
Word/Excel export files, or every spelling of a table-creation command. Use the
documented layout forms. HTML reports are returned as payload strings, not
published pages. Source selection and the existing document templates stay in
the library.

## Verification

`tests/test_output_rendering.py` covers layout recognition, source offsets, parser
alignment, literal values, evidence retention, escaped markup, and pending tasks.
The new request-planner live case requests a two-row table under an explicit source
scope and verifies that a private color does not enter the table.

The real spaCy pipeline is also exercised through a compound information request
and table rendering in a separate dependency environment and disposable database.
Results are kept locally under `build/clean-install-audit/format-alignment-live.*`;
the full suite log is `build/format-alignment-suite.log`.

Final validation on 2026-10-28: **686 passed, 2 skipped, 3 expected failures**
in 77.95 seconds. The skips require unavailable trained extractor checkpoints;
the expected failures are the existing resonance sense-grouping cases. Six
existing NumPy overflow warnings remain. Real spaCy 3.8.18 / English model 3.8.0
plus Tabulate 0.10.0 produced the two-row cited table successfully. The live suite
also checks multi-item bullet and numbered overviews, including propagation of
the parent layout to the child producer. Both package distributions build with
the renderer module and its declared Tabulate dependency. No release is implied.

After Jinja2 and the Markdown/HTML/report prompt flags were added, the full live
suite returned **695 passed, 2 skipped, 3 expected failures** in 78.66 seconds
(same six existing warnings). HTML report integration verifies caller scope,
both requested fields and evidence retention. Unit tests verify HTML escaping,
literal template-like source text, leading-zero values and agreement between
spaCy's presentation record and response-policy flags. Both distributions build
with direct dependencies on Tabulate and Jinja2. Latest evidence is in
`build/template-flags-suite.log` and `build/template-flags-build.log`.
