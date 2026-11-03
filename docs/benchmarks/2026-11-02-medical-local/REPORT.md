# Medication vs healthcare: executed local comparison

Executed November 2, 2026 on repository revision `26a5215`. Runtime source is
unchanged from the previously tested `e6301f3` implementation. This benchmark
adds no runtime fixes. All data are fictional authored acceptance fixtures;
the results do not measure medical correctness, diagnostic accuracy or treatment
safety. No hosted API or local generative decoder was used.

## Separate domain results

**Medication-label tasks, 16 cases:** ordinary cpu-llm 9/16 full-contract passes;
strict evidence 16/16; independent literal/calculator baseline 9/16.

Of 11 supported answerable cases, ordinary passed 7, strict 11, baseline 7.
Of five conflict/refusal cases, ordinary passed 2, strict 5, baseline 2.
Baseline task success without proof requirements was 10/16; one additional
correct-value result did not retain all required corroborating sources.

**Healthcare-record tasks, 16 cases:** ordinary cpu-llm 15/16 full-contract
passes; strict evidence 16/16; literal/calculator baseline 10/16.

Of seven supported answerable cases, ordinary passed 7, strict 7, baseline 4.
Of nine conflict/refusal cases, ordinary passed 8, strict 9, baseline 6.
These include explicit recorded diagnosis/allergy lookup and missing-evidence
abstention, not diagnosis from symptoms. Scores from the two domains should not
be interpreted as their relative clinical difficulty or medical safety.

All three arms executed every case without an execution exception. Full success
requires expected status semantics, correct visible values and retention of
required source proofs. The same common scorer accepts normal/strict API status
variants, ordinary span proofs, and strict hashed-offset proofs. It accepts
equivalent arithmetic decimal formatting. Overall success is not equivalent to
an independently assessed hallucination or clinical accuracy rate.

## Differences reproduced

The ordinary medication path failed these seven contracts:

- It treated `0.875 mg` and `875 mcg` as conflicting rather than equivalent.
- Two differing-value/unit cases displayed both sources without an explicit
  conflict outcome. A negated-value case quoted only the positive source.
- With no authorized retrieval chunks, multiplication and supplied-limit
  comparison displayed the correct arithmetic text while the final judgment
  remained `insufficient_evidence`. These are status/delivery inconsistencies,
  not demonstrated number drift; both visible numeric checks passed.
- Source-based multiplication quoted the source strength rather than returning
  the requested product and retaining its required proof.

The sole ordinary healthcare failure quoted a positive allergy record without
retaining/detecting its explicit negative counterpart. Other tested healthcare
lookups, missing records, ambiguous reference clarification, batch and overview
cases passed their contracts. Unrecognized contradictions outside this small
fixture set may still be missed in either mode.

The baseline is intentionally simple canonical whole-record lookup and Decimal
arithmetic, without paraphrase interpretation, unit equivalence, source-based
calculation or batch/overview planning. Its scores do not represent a production
RAG system, a clinician or an external LLM. Strict success measures implemented
bounded contracts on authored data, not unrestricted language understanding.

## Preserved runs and scoring correction

`first-run/` records revision `70d7d2b`: medication 9/16, 16/16, 9/16 and
healthcare 14/16, 16/16, 10/16 in ordinary/strict/baseline order. Its scorer failed
to recognize ordinary `status=needs_clarification` when `answer_status` was
absent. The response was a valid nonanswer, so this was a scorer defect.

`final-run/` records `26a5215` after adding typed status normalization and two
regression tests. The dataset is byte-identical, runtime sources unchanged, and
the only score improvement is that correctly recognized ordinary clarification.
The old run is retained unchanged. Six benchmark/scorer tests pass; the runtime's
last full-suite result remains 854 passed, 2 skipped, 3 expected failures. The
entire full suite was not rerun for these benchmark-only changes.

Each directory saves cases, pre-execution freeze receipt, runner/baseline
snapshots, raw responses/timings, categorized summary, execution log and SHA-256
manifest. All 96 final arm scores were recomputed from saved responses. Case,
runner and baseline hashes were verified. No result was substituted for a failed
call. PostgreSQL was stopped after execution.

## Running locally

Use the real entry point `tools/benchmarks/medical_local.py`, not the relocated
source snapshots. Configure a disposable PostgreSQL/pgvector database, cached
encoder/checkpoint assets and the usual project dependencies, then run:

```powershell
$env:VECTORPRISM_PG_DSN = 'postgresql://user:password@localhost:5432/disposable_benchmark'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
python tools/benchmarks/medical_local.py --out build/medical-local-new-run
```

The output directory must be new. Session state is reset between arms and the
same authorized source records are used. Recorded timings exclude appliance
initialization; the baseline reads records directly while cpu-llm also incurs
database/pipeline work, so this is not an equal-work latency contest.

See [the benchmark design](../../medical-local-benchmark-design.md) and
[the clinical acceptance gate](../../healthcare-evidence-acceptance.md).
Independent clinical review and medical source validation remain absent. A
local generative LLM arm would require a separately installed model and a new
clearly labeled run; none is implied by these results.
