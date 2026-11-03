# Medication and healthcare: local comparison

This dedicated benchmark separates **16 fictional medication-label tasks**
from **16 fictional healthcare-record tasks**. It compares ordinary public
`Appliance.ask`, strict evidence mode, and the independent canonical
literal-lookup/Decimal calculator baseline. No local generative decoder is
installed and none is included in this run. No hosted calls are made.

Medication cases cover label facts, recognized paraphrases, unit equivalence,
conflicting values/units/negation, exact arithmetic, proof-backed arithmetic,
an explicitly supplied numeric limit, missing interactions and medical-advice
refusal. Healthcare cases cover recorded diagnoses/allergies/status/room,
conflicting and uncertain records, wrong-patient isolation, missing clinical
facts, unsupported treatment advice, ambiguous references, batches and overview.
Recorded diagnosis lookup is not diagnostic inference. Every record is authored
fictional test data; no actual medication guidance or patient data is used.

All arms receive the same original query and the same source records. The two
cpu-llm arms use the same tenant/source scope and reset session state before each
call. The baseline reads the same authorized records directly. Normal and strict
status vocabularies are normalized by a common scorer; ordinary `answered` is
not penalized merely for differing from strict `evidence_quote`.

Report full contract success, task success without proof requirements, retained
proofs, answerable success, nonanswer success and categories separately for each
domain. Full success requires correct visible values/outcomes and required
source retention. A baseline that always refuses fails supported cases.
Equivalent decimal formatting is accepted for arithmetic; a hidden correct
number does not replace the visible result. Conflicts require explicit conflict
status, while general safe abstention is recorded separately. No semantic
LLM judge scores correctness.

Freeze cases, runtime revision, runner hash and baseline hash before execution.
Save raw replies, exceptions and timings. Do not tune the runtime or scorer to
the results without a separate recorded revision/run. These are authored
acceptance tests, not blind held-out evaluation, clinical sign-off, a comparison
with a medical professional, or evidence of superiority over generative LLMs.

Run locally after the usual dependencies, checkpoint and PostgreSQL setup:

```powershell
$env:VECTORPRISM_PG_DSN = 'postgresql://user:password@localhost:5432/disposable_benchmark'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
python tools/benchmarks/medical_local.py --out build/medical-local-new-run
```

The output directory must be new. Use a disposable database with pgvector and
cached encoder assets. The ordinary arm may attempt its configured fallback;
missing optional generation assets are recorded as failures, not silently
replaced with strict output. See the [healthcare deployment boundary](healthcare-evidence-acceptance.md).
