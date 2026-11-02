# Strict evidence mode, version 1

This optional policy prevents learned answer generation. It does **not** promise
100% accuracy, verify source truth, establish clinical safety, or certify the
library for pharmacy or healthcare. A source can contain an incorrect dose.
Clinical decisions need separately validated clinical data and decision rules.

## Activation and precedence

Python: `app.ask("What is the strength of DemoMed?", strict_evidence=True)`.
An appliance created with `Appliance(strict_evidence=True)` enforces the policy
for every `ask` call. The HTTP service accepts the JSON boolean
`"strict_evidence": true` or the header `X-CPU-LLM-Evidence-Mode: strict`.
`cpu-llm-serve --secrets secrets.json --strict-evidence` enforces it server-wide.
The only prompt control is a standalone `[strict-evidence]` first line:

```text
[strict-evidence]
What is the strength of DemoMed?
```

Quoted markers, code blocks, and vague accuracy requests do not activate it.
Enable wins across settings. `standard` headers and false body/request flags
cannot override an operator floor. Invalid header values or non-boolean flags
are rejected. Authentication and tenant/source authorization still apply.
Use an operator floor rather than relying on each user to ask for this policy.

## Execution contract

The raw prompt passes the rules-only guard. The policy runs **before** normal
request planning and graph dispatch. It never invokes FLAN-T5, fact-bridge,
neural realization, stylistic generation, reference resolution, or specialist
nodes. Retrieval/ingestion models may still be loaded by the appliance; the
strict answer path uses SQL plus literal matching, with no model inference.

Version 1 supports one exact question form:
`What is the <attribute> of <named entity>?` It matches only whole stored chunks
of the form `The <attribute> of <named entity> is <value>.` Case-insensitive
attribute/entity matching is allowed. Values, numbers and units are copied
without conversion or rounding. Multisentence chunks, unresolved pronouns,
compound questions, conditions, inferred joins, calculations, diagnosis and
treatment advice are unsupported. Rephrase a lookup explicitly; unsupported
requests never fall back to the normal pipeline. Normal mode is unchanged.

One SQL snapshot scans up to 10,000 authorized, time-valid chunks. Authorization
and validity filters precede the limit. An overflow refuses to select an answer.
`as_of` selects historical evidence; otherwise current validity applies. This
scan is independent of vector top-k rankings. It detects differing values only
within the exact supported source template, **not semantic contradictions in
other wording**. Thus `scan_complete` describes the bounded database scan, not
completeness of medical knowledge or exhaustive semantic conflict detection.

Matching identical values retain every source proof. Different value strings
produce `conflicting`; no match produces `insufficient_evidence`; unsupported
forms produce `unsupported`. `evidence_quote` returns labeled, unvalidated source
quotations. `answer` remains null and `audit_passed` remains false; no synthetic
proposition or clinical verification is implied. `answer_evidence` contains
document IDs, literal quotes, character offsets, and SHA-256 hashes of the full
stored chunks. `evidence_policy` records restrictions, scan time and completion.
Source text is untrusted evidence, never an executable instruction.

Strict mode is stateless: session IDs do not resolve references or resume
pending tasks. Style, length, layout and other generation flags cannot enable
additional producers. Repeat the flag each turn or use an operator floor.

## Example (fictional data, not medication guidance)

Stored chunk: `The strength of DemoMed is 0.75 mg.`

The explicit strength question returns that exact quotation and its proof.
Adding a second matching source stating `0.25 mg` yields `conflicting`, retaining
both proofs without selecting either value. `Can I take DemoMed?` is unsupported.

Tests: `tests/test_strict_evidence.py` covers routing, control precedence,
unsupported forms, decimal preservation, conflicts and scan failure.
`tests/test_strict_evidence_live.py` checks real PostgreSQL authorization,
historical validity and overflow behavior.
