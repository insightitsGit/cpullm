# Strict evidence mode, version 2

Version 1 shipped in `5f68561`. Current policy identifier: `strict-evidence-v2`.
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
nonanswer messages and exact calculation displays are application-owned text,
not model-generated medical claims.
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

Version 2 supports the following bounded request forms:

- `What is the <attribute> of <named entity>?`
- Up to eight such questions separated by question marks, newlines or semicolons.
- `What are the strength and storage of DemoMed?` (explicit attribute lists).
- `List documented attributes of DemoMed.` (up to 32 recognized direct attributes).
- `Calculate 0.1 + 0.2.` (explicit addition, subtraction or multiplication).
- `Calculate the strength of DemoMed times 3.` (unambiguous scalar source fact).
- `Does 3375 mg exceed 3000 mg?` (explicit same-unit numeric comparison).
- `A fictional label states a maximum daily amount of 3000 mg. Does a supplied
  total of 3375 mg exceed that label limit?` (explicit inline numeric context).

Within a batch, `of it` can bind to exactly one previously named entity; multiple
prior entities produce an unsupported task rather than a guessed referent.
The binding is recorded in `task_results[].request.reference_binding`. No
cross-turn session state is read or written. Unknown tasks stay in the result;
one unsupported question never silently removes another requested question.

Recognized whole-chunk source forms are `The <attribute> of/for <entity> is
<value>.`, `<entity>'s <attribute> is <value>.`, and `<entity> has a/an
<attribute> of <value>.` Original numbers, units and wording are quoted without
rewriting. Case-insensitive attribute/entity matching and a leading `the` are
normalized for matching only. Multisentence chunks remain unsupported so a
qualifier in a following sentence cannot be silently discarded.

A one-hop join requires both `<entity> is a/an <type>.` and `Every <type> has
a/an <attribute> of <value>.` Both original premises are returned, not a new
asserted sentence. Class averages, ambiguous memberships and missing premises
do not license an individual fact. Direct and joined values participate in the
same conflict check. This is not unrestricted graph reasoning.

Explicit negations in recognized forms cause a conflict/nonanswer. Recognized
uncertainty or conditions withhold the affected slot, including when another
source has an unconditional value. Unrecognized paraphrases can still be missed;
this is a bounded parser, not exhaustive semantic contradiction detection.

One SQL snapshot scans up to 10,000 authorized, time-valid chunks and eight
million text characters. Authorization
and validity filters precede the limit. An overflow refuses to select an answer.
`as_of` selects historical evidence; otherwise current validity applies. This
scan is independent of vector top-k rankings. It detects differing values only
within the recognized source forms, **not arbitrary semantic contradictions**.
Thus `scan_complete` describes the bounded database scan, not
completeness of medical knowledge or exhaustive semantic conflict detection.

Matching equivalent values retain every source proof. Exact scalar mass
(`mcg`, `mg`, `g`, `kg`), volume (`mL`, `L`) and time (`minute(s)`, `hour(s)`)
values are compared using Decimal and explicit conversion factors. Units are
case-sensitive; compound units, ranges, clinical dose conversions and fuzzy
equivalence are not inferred. Source wording is never converted for display.
Different non-equivalent values
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

Version 2 adds `derived_calculation` for exact deterministic arithmetic,
`partial` when only some requested tasks succeed, and `completed` when every
task succeeds with mixed quotation/calculation types. `task_results` preserves
the status, request interpretation, proofs and optional calculation for each
task. Homogeneous batches retain their common status. Consumers must inspect
individual task statuses and must not interpret a partial result as full success.

Calculations record the operator, input decimal strings, result and unit in
`calculation`; they are labeled arithmetic, not medical advice. Source-based
calculations retain all source proofs and refuse conflicting/uncertain values.
Pure prompt arithmetic does not perform a database scan. Arithmetic is limited
to bounded decimal operands (24 integer and 12 fractional digits), a 100-digit
local Decimal context and the three stated operations; there is no division,
clinical dosing policy or open-ended expression evaluation. As in version 1,
`answer` is null and `audit_passed` is false for every strict result.

The additional `greater_than` calculation form compares two supplied numbers
with identical supported mass/volume unit symbols. It records both operands,
the unit and a `true`/`false` value. It never converts units or declares a dose
safe. Its recognized inline label/policy/rule grammar binds `that limit` to the
explicit preceding numeric limit; arbitrary cross-sentence reference resolution
remains unsupported. Conditions, quotes, mismatched units and unrecognized
wording do not enter that path. The ordinary pipeline routes the same complete
numeric form to the math node while retaining its explicit context.

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

Strict mode is stateless across requests: session IDs do not resolve references or resume
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
enforcement path. The version 1 saved full-suite result is **806 passed, 2 skipped,
3 expected failures**, documented in the
[version 1 validation report](reviews/2026-11-02/strict-evidence-validation.md).
Version 2 coverage is in `tests/test_strict_evidence_v2.py` and the fresh
`tools/benchmarks/evidence_v2.py` synthetic acceptance/local-baseline runner.
See [healthcare acceptance requirements](healthcare-evidence-acceptance.md).
The final version 2 suite passed **854 tests**, with 2 skipped and 3 expected
failures. Its authored evidence evaluation passed 42/42 cases against a simple
local baseline's 25/42; the original domain replay passed 24/24. See the saved
[evidence evaluation](benchmarks/2026-11-02-evidence-v2/REPORT.md) and
[domain replay](benchmarks/2026-11-02-domain-replay-v2/REPORT.md). These scores
do not satisfy the external clinical validation gate.
