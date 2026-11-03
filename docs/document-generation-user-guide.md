# User guide: reports, articles, design documents and tone

These features are included in the published cpu-llm 1.11.0 release.
The PyPI 1.10.0 wheel and release whitepaper have not been replaced. Install `cpu-llm==1.11.0` from PyPI or use a checkout. From a
checkout containing these changes, install with `python -m pip install -e .`.
Configure PostgreSQL/pgvector and the encoder assets as described in the
[installation guide](../README.md). Ingestion supplies knowledge; it is not
training. The bundled projection needs no retraining for this demonstration.

## A complete working example

Run from the checkout after database/model setup:

```shell
python examples/document_workflows/demo.py --out build/document-demo-new-run
```

The script uses a fresh namespace, ingests seven fictional Helios statements,
and saves a friendly article and strict report with their JSON evidence.
No record contains the word “friendly”. Use a new output directory each run.
The [captured friendly output](examples/2026-11-03-manual-demo/friendly-article.md)
and [strict output](examples/2026-11-03-manual-demo/strict-report.md) were produced
by this exact command against the configured demonstration database.
The existing twelve-fact [generated article](examples/2026-11-03-prompt-tone/article.md)
and [report](examples/2026-11-03-prompt-tone/report.md) show actual captured output.

Inside an existing appliance, ask:

```python
result = app.ask("Write a detailed article about Helios in a friendly tone.")
print(result["reply"]["text"])
print(result.get("stylistic", {}).get("verification"))
```

Tone is a presentation instruction, not a word that must occur in the KB.
For example, stored predicates can produce this new sentence:

> Helios stores encrypted backups and uses PostgreSQL for metadata.

That sentence is a verified derivation, not a verbatim quotation or a guarantee
that the source itself is true. Claims outside the supported grammar remain
clearly attributed source quotations; they are not silently simplified.

## Useful prompt recipes

- Article: `Write a detailed article about Helios in a friendly tone.`
- Report: `Write a detailed report about Helios. Use a formal tone.`
- Design: `Write a detailed design document about Helios, including Architecture, Interfaces and Costs.` Missing sections remain explicitly missing.
- HTML: `Write a detailed article about Helios in a friendly tone as an HTML report.`
- Table: `Write a detailed report about Helios in a friendly tone as a Markdown table.`
- Bullets: `Write a brief report about Helios as bullet points.`
- Broader topic scan: `Use deep search to write a detailed report about Helios in a friendly tone.` Documents use the bounded authorized snapshot strategy, not an unrestricted web/graph search.

Prefer an explicit topic. General aliases, omitted subjects and indirect
class joins are not universally understood. A detailed request includes more
supported evidence; it cannot manufacture missing facts or design decisions.

## Python control and precedence

```python
from cpu_llm.stylistic import StyleOptions, Relationship

result = app.ask(
    "Write a detailed report about Helios in a friendly tone.",
    style=StyleOptions(tone="formal", relationship=Relationship.COLLEAGUE,
                       max_sentences=12, clauses_per_sentence=2),
)
```

The explicit API tone wins: this request uses formal construction. String
profiles use the document's budget; an explicit StyleOptions budget is honored.
If it cannot retain every claim, generation is rejected and the quotation view
remains. Tone never persists automatically to another request.

Ten tone controls do not mean unrestricted expressive prose. Friendly/formal
technical constructions are reviewed; unsupported poetic/emotional preferences
can return `tone_alignment="neutral_fallback"`. Relationship exclusions still
apply. The tone node does not infer a relationship or emotional state.

## Read the results correctly

For a document, `reply.text` is the selected rendered output. With successful
tone generation it contains verified prose and any literal fallbacks.
`stylistic.status` is `generated`, `unchanged`, `skipped` or `rejected`; inspect
its reason, verification and tone alignment before presenting a “styled” badge.
`executed_nodes` confirms actual node execution, not merely a requested flag.

Original source proofs remain in `answer_evidence` and `document.sections[].quotes`.
Derived sentences and their source IDs are in `document.sections[].prose`.
The original quotation view remains in `rendered_response.canonical_text`.
For the older single-fact path, style is a companion in `stylistic.text` and
does not replace the canonical reply. These two publication behaviors differ.

Check `document.coverage` for missing sections, recognized conflicts, included
records and additional pages. `partial` is not a complete answer. An
`evidence_quote` document can include verified derived wording when tone is
enabled; consult `judgment.verification` and `document.presentation` rather
than assuming every displayed sentence is a direct quote. `audit_passed=False`
is intentional and never confers clinical approval.

## Strict reports and HTTP

```python
result = app.ask(
    "Write a detailed report about Helios in a friendly tone.",
    strict_evidence=True,
)
```

Strict evidence wins over tone: the result contains quotations without generated
style. An appliance/service strict floor cannot be weakened by the request.

After configuring the authenticated service, send `POST /v1/ask` with the
existing bearer credential and this JSON body:

```json
{"message": "Write a detailed article about Helios in a friendly tone as an HTML report."}
```

No HTTP `style` field is added. Explicit tone directives work through prompt
text. Use `X-CPU-LLM-Evidence-Mode: strict` or the existing strict body setting
to request quotation-only output. See the [HTTP contract](library-consumer-guide.md#authenticated-http-service).

## Length, continuation and troubleshooting

Standard, detailed and brief documents allow eight, sixteen and three atomic
quote units respectively, capped at twenty for explicit numeric requests.
Generated prose combines supported claims within its sentence budget; it does
not add padding. Exact word/sentence limits are not guaranteed because evidence,
qualifiers and citations cannot be clipped. Coverage reports budget overruns.

When `has_more` is true, use the returned `continuation_prompt`. It retains
the topic, section outline, page size and historical timestamp. Permissions
are checked again. Bare “continue” is not a document-state protocol.

If a result stays short, inspect coverage and literal fallbacks before increasing
the budget. If a section is missing, ingest appropriate source records. If tone
is skipped/rejected, inspect its reason and use the quotation output rather than
claiming prose was generated. If nothing is found, verify topic wording, caller
permissions, historical time and DB/encoder setup. Do not disable strict mode
merely to hide insufficient evidence.

The [findings specification](document-generation-findings-spec.md) records why
these rules exist and which capabilities remain outside the current contract.
