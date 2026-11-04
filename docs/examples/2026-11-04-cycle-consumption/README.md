# Actual cycle-to-sentence and document consumption

November 4, 2026. Unreleased Git-source functionality. Real Appliance construction, ingestion and ask calls on the isolated native PostgreSQL/pgvector database with the cached CPU encoder. These are fictional controlled source records.

## Source fixture

```text
Alpha is a process.
Alpha records audit events.
Alpha causes Beta.
Beta causes Alpha.
Beta causes Gamma.
Gamma causes Alpha.
```

## Show relationship loops for Alpha.

Options: `{}`.

Answer status: `evidence_quote`.

```text
Source-backed lexical cycles; no new inferred facts or resolved word senses.
The source records describe a closed lexical path: Alpha causes Beta; Beta causes Alpha.
Sources: cycle-source-p0003, cycle-source-p0004
The source records describe a closed lexical path: Alpha causes Beta; Beta causes Gamma; Gamma causes Alpha.
Sources: cycle-source-p0003, cycle-source-p0005, cycle-source-p0006
```

Consumed cycles: 2. Each generated path sentence passed the ordered-clause/source-span verifier. The source paths remain lexical candidates; source truth, word sense and a new transitive causal conclusion are not established.

## Write a detailed report about Alpha, including relationship loops through Alpha in a friendly tone.

Options: `{}`.

Answer status: `partial`.

```text
# Alpha — Report

Verified prose constructed from source claims; unrecognized records remain attributed quotations. Missing sections are not stated in the selected evidence.

## Overview

Alpha is a process.

Sources: cycle-source-p0001

> Alpha causes Beta.

Source: cycle-source-p0003

> Beta causes Alpha.

Source: cycle-source-p0004

> Beta causes Gamma.

Source: cycle-source-p0005

> Gamma causes Alpha.

Source: cycle-source-p0006

## Operations

Alpha records audit events.

Sources: cycle-source-p0002

## Limitations

Not stated in the selected evidence.


## Relationship loops

The source records describe a closed lexical path: Alpha causes Beta; Beta causes Alpha.
Sources: cycle-source-p0003, cycle-source-p0004

The source records describe a closed lexical path: Alpha causes Beta; Beta causes Gamma; Gamma causes Alpha.
Sources: cycle-source-p0003, cycle-source-p0005, cycle-source-p0006

Paths use exact labels; word senses and source truth are not independently verified.
```

Consumed cycles: 2. Each generated path sentence passed the ordered-clause/source-span verifier. The source paths remain lexical candidates; source truth, word sense and a new transitive causal conclusion are not established.

## Show relationship loops for Alpha.

Options: `{"strict_evidence": true}`.

Answer status: `unsupported`.

```text
Cycle exploration is disabled in strict evidence mode.
```

## Reproduction

After the usual source/database/encoder setup, ingest the fixture with SourceDocument and use the prompts above. Python/HTTP API cycle_search options remain supported; a strict request or operator floor disables this feature. The report shares one authorized snapshot for ordinary research and cycle exploration.

Maintainer script and raw output: build/show_cycle_consumption.py and build/cycle-consumption-live-examples.json.
