# Strict evidence mode, version 1

Implementation: `5f68561`. Policy identifier: `strict-evidence-v1`.
This document specifies the existing implementation; the “zero hallucination”
description does not introduce a second flag or a broader answering contract.

This optional policy prevents learned answer generation. It does **not** promise
100% accuracy, verify source truth, establish clinical safety, or certify the
library for pharmacy or healthcare. A source can contain an incorrect dose.
Clinical decisions need separately validated clinical data and decision rules.

## Meaning of “zero hallucination”

The term describes an execution restriction: strict mode MUST NOT generate
factual answer wording with a learned model. Delivered evidence MUST be a
literal substring of an authorized stored chunk. Source labels and fixed
nonanswer messages are application-owned text, not generated medical claims.
If evidence cannot satisfy the supported lookup contract, the mode MUST return
a nonanswer or fail the request; it MUST NOT retry through ordinary generation.

This restriction does not prove that a quotation is true, current in the real
world, complete, or suitable for a patient. Database validity timestamps describe
stored versions, not external medical approval. “Zero hallucination” MUST NOT
be presented as 100% factual accuracy, universal contradiction detection,
clinical validation, or regulatory certification.

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

## Consumer and accountability contract

Consumers MUST branch on `answer_status`; a nonempty `reply.text` alone does
not mean the request was answered. Supported terminal statuses are
`evidence_quote`, `conflicting`, `insufficient_evidence`, `unsupported`, and
`blocked`. Source evidence can accompany a conflict without authorizing the
application to choose either value.

For all strict responses, `evidence_policy.enabled` is true,
`learned_generation`, `clinical_validation` and `source_truth_verified` are
false, and `stateless` is true. The policy records the permitted source scope
and disabled producers. Successful database scans additionally record `as_of`
and `scanned_chunks`; unsupported and blocked requests do not perform the scan.
`scan_complete` is false if no scan completed or the scan overflowed. An empty
authorized scope can complete a scan with zero chunks and no answer.

Each proof's `start` and `end` are Python string character offsets into the full
stored chunk, with an exclusive end. `chunk_sha256` is the SHA-256 digest of
the full chunk's UTF-8 bytes, including whitespace; it is not a digital signature
or an assertion about publisher identity. The response includes `tenant_id`,
the original message, and the caller's request ID when supplied by authenticated
context. These are response receipts, not a durable audit-log service. Applications
requiring audit retention must retain the response and corresponding source
version under their own access and retention policy.

Strict responses bypass the ordinary graph's judgment and output rendering.
Consumers MUST NOT require ordinary graph-specific fields to interpret this
envelope or treat `audit_passed=False` as permission to retry with generation.

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
`tests/test_strict_evidence_http.py` checks the actual HTTP header and server
enforcement path. The saved full-suite result is **806 passed, 2 skipped,
3 expected failures**, documented in the
[validation report](reviews/2026-11-02/strict-evidence-validation.md).
