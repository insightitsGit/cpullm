# Actual research and cycle examples

Historical before-fix run. The observed email/length problems below were
subsequently corrected; see the [after-fix examples](../2026-11-04-long-document-fix/README.md).

Date: November 4, 2026. Implementation: source branch `codex/research-cycle-nodes`, commit `fb3b60a`. Not in published 1.11.2.

Executed through real Appliance construction, SourceDocument ingestion and Appliance.ask, using an isolated native PostgreSQL/pgvector test database, cached CPU encoder and rules prompt backend. These are fictional controlled fixtures, not clinical, financial or general accuracy benchmarks.

## Ingested source records

### helios-demo

```text
Helios is a backup service.
Helios stores encrypted backups.
Helios uses PostgreSQL for metadata.
Helios does not support automatic regional failover.
PostgreSQL is a relational database.
PostgreSQL supports transactions.
```

### cycle-demo

```text
Alpha causes Beta.
Beta causes Alpha.
Beta causes Gamma.
Gamma causes Alpha.
```

### acyclic-demo

```text
Lobster is a crustacean.
Crustacean is an animal.
```

## Article

Prompt: Write a detailed article about Helios and PostgreSQL.

Options: `{}`

Answer status: `evidence_quote`.

### Actual reply

```text
# Helios and PostgreSQL — Article

Source quotations; design decisions are not inferred. Missing sections are not stated in the selected evidence.

## Overview

> Helios is a backup service.

Source: helios-demo-p0001

> PostgreSQL is a relational database.

Source: helios-demo-p0005

## Details

> Helios stores encrypted backups.

Source: helios-demo-p0002

> Helios uses PostgreSQL for metadata.

Source: helios-demo-p0003

> PostgreSQL supports transactions.

Source: helios-demo-p0006

## Limitations

> Helios does not support automatic regional failover.

Source: helios-demo-p0004

```

### Expanded research instruction

```text
Prepare a detailed article about Helios and PostgreSQL. Preserve the original scope and constraints. Investigate these questions without assuming their premises are true:
What is documented about Helios and PostgreSQL?
What properties and capabilities of Helios and PostgreSQL are documented?
Which relationships involving Helios and PostgreSQL are explicitly documented?
How does the documented process involving Helios and PostgreSQL work?
What conditions, exceptions or limitations apply to Helios and PostgreSQL?
Use only supported evidence; retain conflicts and missing information. Do not infer causes or new transitive facts. Do not send a draft.
```

Research coverage: `{"selected_chunks": 6, "question_answers_verified": false, "missing_facets": ["mechanism"]}`. Candidate evidence availability is not verified question-answer coverage.

## Email

Prompt: Draft a concise email to Alex about Helios.

Options: `{}`

Answer status: `partial`.

### Actual reply

```text
# Helios — Email

Source quotations; design decisions are not inferred. Missing sections are not stated in the selected evidence.

## Overview

> Helios is a backup service.

Source: helios-demo-p0001

> Helios stores encrypted backups.

Source: helios-demo-p0002

## Details

Not stated in the selected evidence.

## Limitations

> Helios does not support automatic regional failover.

Source: helios-demo-p0004


More evidence available. Continue: Write a email about Helios in 3 items, including Overview, Details, Limitations, page 2, as of 1793783201 as a Markdown report.
```

### Expanded research instruction

```text
Prepare a brief email about Helios. Preserve the original scope and constraints. Investigate these questions without assuming their premises are true:
What is documented about Helios?
What properties and capabilities of Helios are documented?
Which relationships involving Helios are explicitly documented?
How does the documented process involving Helios work?
What conditions, exceptions or limitations apply to Helios?
Use only supported evidence; retain conflicts and missing information. Do not infer causes or new transitive facts. Do not send a draft.
```

Research coverage: `{"selected_chunks": 4, "question_answers_verified": false, "missing_facets": ["mechanism"]}`. Candidate evidence availability is not verified question-answer coverage.

## Cycles

Prompt: Explore the documented loops through Alpha.

Options: `{"cycle_search": {"seed": "Alpha"}}`

Answer status: `evidence_quote`.

### Actual reply

```text
Source-backed lexical cycles; no new inferred facts or resolved word senses.
[cycle-demo-p0001] Alpha causes Beta.
[cycle-demo-p0002] Beta causes Alpha.
[cycle-demo-p0003] Beta causes Gamma.
[cycle-demo-p0004] Gamma causes Alpha.
```

### Search outcome

Cycles: 2; rounds: 3; complete: True; stop: `frontier_exhausted`.

```text
Alpha --causes--> Beta
Beta --causes--> Alpha
```

```text
Alpha --causes--> Beta
Beta --causes--> Gamma
Gamma --causes--> Alpha
```

First edge channel activity: `{"dense": null, "relational": true, "disentangled": null, "hyperbolic": null, "identity": null, "causal": true}`. Null means unavailable/unknown, not a positive vote. All six symbolic evaluators ran; this path does not compute calibrated vector matches.

## No Cycle

Prompt: Explore the documented loops through Lobster.

Options: `{"cycle_search": {"seed": "Lobster"}}`

Answer status: `insufficient_evidence`.

### Actual reply

```text
Source-backed lexical cycles; no new inferred facts or resolved word senses.
No qualifying cycle found within the authorized snapshot and search limits.
```

### Search outcome

Cycles: 0; rounds: 3; complete: True; stop: `frontier_exhausted`.

## Round Limit

Prompt: Explore the documented loops through Alpha.

Options: `{"cycle_search": {"seed": "Alpha", "limits": {"max_rounds": 1}}}`

Answer status: `insufficient_evidence`.

### Actual reply

```text
Source-backed lexical cycles; no new inferred facts or resolved word senses.
No qualifying cycle found within the authorized snapshot and search limits.
Search incomplete: max_rounds.
```

### Search outcome

Cycles: 0; rounds: 1; complete: False; stop: `max_rounds`.

## Observed gaps

- Email output is still a sectioned evidence document. Recipient is retained in plan metadata but is not rendered as a normal email greeting/body/sign-off.
- The brief email budget omits a relevant source record and emits continuation. Its empty Details section does not establish that the KB lacks details.
- Article section coverage can be complete while a planned mechanism question has no evidence. Research question coverage remains separately exposed.
- Cycles use exact labels and carry lexical-candidate status. Closed paths are not new facts, resolved senses or validated causal explanations.
- No-cycle and budget-exhausted outcomes differ; ordinary direct facts remain usable without cycles.

Full structured output is retained in `build/research-cycle-live-examples.json`; execution script/log are `build/show_research_cycles.py` and `build/research-cycle-live-examples.log`.
