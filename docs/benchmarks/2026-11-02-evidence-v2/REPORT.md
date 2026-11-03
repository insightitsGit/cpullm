# Strict evidence v2: authored acceptance and local baseline

Executed November 2, 2026 on final runtime
`e6301f30ce67990e1807f7f70b4594c88239ea36`. **Strict mode passed 42/42
authored acceptance cases; the independent literal/calculator baseline passed
25/42.** This is not a hosted LLM comparison or clinical validation.

Strict mode passed all 24 cases containing supported answerable tasks and all
18 cases requiring a nonanswer. The baseline passed 14/24 and 11/18,
respectively. Partial batch cases require the exact expected per-task statuses;
they are not counted as fully answered batches. Correct nonanswers are reported
separately so always refusing cannot appear to solve supported cases.

The baseline independently implements canonical whole-record lookup and Decimal
arithmetic. It receives the same original queries and source records. It has no
aliases, joins, batch interpretation or clinical reasoning. The comparison
therefore measures the implemented extensions relative to a deliberately simple
local baseline, not superiority over production RAG systems or hosted models.

## What was exercised

Fictional strength, ingredient, storage, recorded diagnosis/allergy, expiry,
interval and batch facts; possessive/has/for paraphrases; conflicting values,
negative and uncertain facts; exact mass-unit equivalence; missing evidence;
unsupported medical advice; decimal arithmetic; proof-backed scalar arithmetic;
batch references, partial and ambiguous tasks; explicit universal joins and
average-rule refusal; multi-attribute overviews; multisentence qualifier refusal.

Scoring checks expected statuses, complete expected task-status lists, visible
literal values, required proofs, source text offsets and full-chunk hashes.
Scorer tests reject missing proofs and wrong visible numeric formatting. This
is an executing-agent-authored acceptance suite, not blind held-out evaluation
or independently reviewed clinical gold. Passing cannot prove arbitrary prompt
coverage, complete conflict detection, source truth or medical safety.

## Reproducibility and retained runs

`first-run/` records `83e3cab` with the same 42/42 and 25/42 scores.
`final-run/` records `e6301f3` after the inline comparison follow-up. The case
files are byte-identical between runs. Every directory includes the case file,
pre-execution freeze receipt, runner snapshot, raw responses, summary, execution
log and SHA-256 manifest. Final run also includes the complete test-suite log:
**854 passed, 2 skipped, 3 xfailed**, six existing NumPy overflow warnings.

The actual runnable entry point is `tools/benchmarks/evidence_v2.py`; snapshots
are evidence of the source, not standalone relocated tools. Use a new output
directory and disposable database with `VECTORPRISM_PG_DSN`, cached model
assets and offline settings. Both runs used Windows/PostgreSQL 18 and new local
databases. PostgreSQL was stopped after execution. No hosted calls were made.

## Clinical and comparison gates

`clinical_release_gate.ready_for_clinical_decisions` remains **false**.
Authoritative medical source validation, external clinical gold and independent
clinical sign-off are absent. The hosted arm remains **unrun by user choice**.
See [healthcare acceptance requirements](../../healthcare-evidence-acceptance.md).
