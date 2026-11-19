# Inference source guide

These additions apply to the repository source; they do not describe a new PyPI
release. Ingest evidence before requesting deductions or analyses.

## Deductive inputs and triggers

Use `ask(..., inference={"subject": "Kestrel", "relation": "requires",
"object": "radio"})` or a complete supported question. Examples:

- `Is elephant bigger than cat?`
- `Is Kestrel a member of vessel?`
- `Is cutter a subclass of vessel?`
- `Is pump a physical part of engine?`
- `Is pump located in dock?`
- `Does engine physically contain pump?`
- `Does Kestrel require radio?`

`Infer whether ...` also accepts the corresponding declarative form. Rules use
explicit canonical names; plural/singular equivalence is not assumed. Supported
source clauses include `Every cutter is a vessel`, `Every vessel has a radio`,
`Every vessel requires a radio`, `The pump is a physical part of the engine`, and
`The ship is located in the dock`. Negated premises remain distinct. Part-of is
a strict physical-component relationship, not generic membership or association.
Containment is derived from part-of; containment alone does not establish part-of.

Class requirements are the implemented conditional deduction form. Arbitrary
`if ... then ...` prose cannot install rules. Location itself is not declared
transitive; class averages never become individual properties.

Natural questions keep ordinary answering and can attach an `inference` receipt
only when their retrieved subset establishes or contradicts the relationship
(or detects a conflict). `inference_evidence_scope` labels this as
`retrieved_subset`; no full-snapshot inference fetch is added and the normal
answer is not replaced. Strict-mode natural questions keep the strict quotation route. An unparseable
explicit command asks for clarification; malformed API options raise validation
errors. Explicit negative evidence yields `CONTRADICTED_BY_RULES`, distinct from
missing support and from mutually conflicting premises.

Subjects and objects must be atomic names. Coordinators and trailing
prepositional clauses are refused symmetrically in requests and source facts.
For example, `radio and a crew of five` is not interpreted as a radio fact,
and `donkey in Kenya` is not treated as an entity named donkey. This conservative
subset can reject legitimate complex names; use unambiguous canonical names.

Innovation, research, Nammade and CrossDomain invoke applicable deduction
automatically. CrossDomain restricts this to its selected prefixes. Returned
`research_inference.receipts` and `research_methods.inference` describe the
checks. One coordinator owns deduction in combined research. A proof establishes
entailment from those sources and registered rules, not real-world source truth.

## Structured analysis records

Store one complete JSON object per chunk using `catalog_chunks`. Explicit chunk
IDs make selection reproducible. For example, inside an initialized Appliance:

```python
import json

app.catalog_chunks([
    ("dates-p0000", json.dumps({
        "schema": "inference-record-v1", "kind": "interval",
        "start": "2026-01-01", "end": "2026-01-31",
    })),
    ("dates-p0001", json.dumps({
        "schema": "inference-record-v1", "kind": "interval",
        "start": "2026-01-31", "end": "2026-02-28",
    })),
])
result = app.ask("Compare intervals", inference={
    "mode": "temporal", "source_ids": ["dates-p0000", "dates-p0001"],
})
assert result["inference"]["intersection"] == ["2026-01-31", "2026-01-31"]
```

Temporal records use closed intervals and exact `YYYY-MM-DD` dates. Exactly two
records are required. The engine does not infer timezone, current validity or
causation from dates.

For `inductive`, select chunks containing records of this form:

```json
{"schema":"inference-record-v1","kind":"bernoulli","observation_id":"sample-1","population":"batch-a","success":true}
```

All selected observations need unique IDs, one population label and boolean
outcomes. Results include `sample_size`, `successes`, `proportion`, and
`interval_95`. The Wilson interval assumes independent Bernoulli sampling;
selection bias and independence are not verified. This is not a population-wide
guarantee, universal rule, causal conclusion or medical recommendation.

For `abductive`, select observations and at least two explanation alternatives:

```json
{"schema":"inference-record-v1","kind":"observation","id":"O1","description":"A spectrum peak was observed."}
```

```json
{"schema":"inference-record-v1","kind":"explanation","id":"H1","description":"Candidate material effect.","explains":["O1"],"contradicts":[],"test":"Repeat with another material."}
```

A second explanation must have a distinct ID and a distinguishing test. Coverage
references must name selected observation IDs. The existing AbductiveBridge
orders alternatives by declared contradiction count, then declared coverage,
then ID. It does not establish that the declared coverage is physically correct
or assign probabilities. Every candidate remains `UNVERIFIED_HYPOTHESIS`.
The existing Nammade-driven domain bridge continues to work separately.

Explicit prompt equivalents are `Temporal: sources: dates-p0000, dates-p0001`,
`Induction: sources: trial-p0000, trial-p0001`, and
`Abduction: sources: research-p0000, research-p0001, research-p0002`.
Python and HTTP accept the same `inference` request object.

## Boundaries and receipts

Structured modes select 1–256 distinct authorized chunk IDs, each at most 65536
characters. Missing, inaccessible or malformed records do not yield conclusions.
Guard, strict mode and historical snapshots apply before analysis. Receipts bind
source spans, versions, scope, snapshot, policies and audit hashes. Use
`cpu_llm.inference.verify_receipt(receipt, original_snapshot_rows)` for replay.
No new runtime dependencies or general-purpose scientific solver are introduced.

Standalone inference cannot be combined with conflicting specialist API flags;
research automatically coordinates the applicable methods instead. Ordinary
lookups do not activate structured statistics or explanation comparisons.

Inference runs as a shared service, not a registered core graph stage. Explicit
commands/API options read the authorized snapshot; research uses its own snapshot;
ordinary augmentation consumes retrieved rows only. The core graph has 27 stages.
