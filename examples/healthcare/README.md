# Small fictional healthcare and pharmacy demo

This repo includes six small documents (11 paragraphs) and 12 questions with
explicit expected results in `dataset.json`. The names, compounds and records
are fictional. They demonstrate software behavior, **not real medicines,
patients, clinical advice or externally validated medical accuracy**.

The examples cover label/record lookups, equivalent units with both proofs,
conflicting labels, missing diagnosis data, treatment refusal, exact arithmetic,
supplied-number comparison, a two-question batch and a longer fact overview.
Retrieving a recorded diagnosis is different from diagnosing a patient.

## Run locally

From the repository root, install this checkout and complete the usual
PostgreSQL/pgvector and cached model setup described in the main README.
Use a disposable/demo database; do not use real patient records for this demo.

```powershell
$env:VECTORPRISM_PG_DSN = 'postgresql://user:password@localhost:5432/demo_database'
# Set these after the pretrained encoder assets have been cached:
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
python examples/healthcare/run_demo.py --out build/healthcare-demo-new-run
```

The output directory must be new. The script creates a fresh isolated namespace,
ingests only this dataset, restricts the demo caller to its sources, enables
strict evidence mode and prints each actual answer/status/check. It saves full
responses, a summary and dataset/runner hashes. It exits nonzero if any authored
expectation fails. All arithmetic is labeled separately from medical advice.
No FLAN-T5 or other answer-generation model is used by the strict answer path.

The trained retrieval checkpoint and pretrained encoder assets are still needed
for appliance setup/ingestion. You do not retrain a model for this demonstration.
First startup can take longer while assets load; reuse the appliance for queries.
The Python entry point uses a Windows-compatible guarded `main()`.

## Interpreting the result

For example, the strength lookup should retain both `0.75 mg` and its equivalent
`750 mcg` source. The conflicting Cedar labels should yield `conflicting`, not a
selected strength. A missing diagnosis should yield `insufficient_evidence`;
the antibiotic question should yield `unsupported`. A correct refusal counts
as a passed expectation, not a correct medical answer.

The saved pass count measures adherence to these 12 authored contracts, including
visible values and source proofs. It is not a general accuracy rate, a blind
benchmark or approval for clinical use. See
[the strict contract](../../docs/strict-evidence-spec.md) and
[clinical acceptance requirements](../../docs/healthcare-evidence-acceptance.md).
