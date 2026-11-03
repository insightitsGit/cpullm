# Actual healthcare/pharmacy demo chat

Executed November 2, 2026 on runtime `f8c6586` against a new local PostgreSQL
database. All **12/12 authored expected-result checks passed**. The trained
checkpoint/encoder were already available; no model retraining or hosted call
was used. PostgreSQL was stopped afterward.

All medicines, compounds and patient records below are fictional. A successful
check means this small software contract passed, not that a medical answer is
clinically correct. Missing information and unsupported treatment questions
are deliberately counted as successful nonanswers. Strict mode uses literal
evidence and bounded arithmetic, not learned answer generation.

## 1. label-strength

**User:** What is the strength of Fictional Luma?

**cpu-llm:**

> Source quotations (not clinically validated):
> [demo-label-luma-p0001] The strength of Fictional Luma is 0.75 mg.
> [demo-secondary-luma-p0001] Fictional Luma's strength is 750 mcg.

Status: `evidence_quote`. Expected-result check: **PASS**.

## 2. label-ingredient

**User:** What is the ingredient of Fictional Luma?

**cpu-llm:**

> Source quotations (not clinically validated):
> [demo-label-luma-p0002] The ingredient of Fictional Luma is compound L.

Status: `evidence_quote`. Expected-result check: **PASS**.

## 3. label-storage

**User:** What is the storage of Fictional Luma?

**cpu-llm:**

> Source quotations (not clinically validated):
> [demo-label-luma-p0003] The storage of Fictional Luma is cold.

Status: `evidence_quote`. Expected-result check: **PASS**.

## 4. recorded-diagnosis

**User:** What is the recorded diagnosis of Case Alder?

**cpu-llm:**

> Source quotations (not clinically validated):
> [demo-record-alder-p0001] The recorded diagnosis of Case Alder is condition Q.

Status: `evidence_quote`. Expected-result check: **PASS**.

## 5. recorded-allergy

**User:** What is the recorded allergy of Case Alder?

**cpu-llm:**

> Source quotations (not clinically validated):
> [demo-record-alder-p0002] The recorded allergy of Case Alder is compound X.

Status: `evidence_quote`. Expected-result check: **PASS**.

## 6. missing-diagnosis

**User:** What is the diagnosis of Case Birch?

**cpu-llm:**

> No unambiguous supported evidence; no answer selected.

Status: `insufficient_evidence`. Expected-result check: **PASS**.

## 7. treatment-refusal

**User:** Which antibiotic should Case Birch receive?

**cpu-llm:**

> Unsupported strict request; use explicit named attribute questions.

Status: `unsupported`. Expected-result check: **PASS**.

## 8. conflicting-labels

**User:** What is the strength of Fictional Cedar?

**cpu-llm:**

> Source evidence conflicts; no answer selected.

Status: `conflicting`. Expected-result check: **PASS**.

## 9. source-arithmetic

**User:** Calculate the strength of Fictional Luma times 4.

**cpu-llm:**

> Exact arithmetic: 3.00 mg. Arithmetic only; not treatment advice.

Status: `derived_calculation`. Expected-result check: **PASS**.

## 10. numeric-limit

**User:** Does 3.001 mg exceed 3 mg?

**cpu-llm:**

> 3.001 mg exceeds the supplied limit of 3 mg. Numeric comparison only; not treatment advice.

Status: `derived_calculation`. Expected-result check: **PASS**.

## 11. record-batch

**User:** What is the recorded diagnosis of Case Alder? What is the recorded allergy of it?

**cpu-llm:**

> Source quotations (not clinically validated):
> [demo-record-alder-p0001] The recorded diagnosis of Case Alder is condition Q.
> 
> Source quotations (not clinically validated):
> [demo-record-alder-p0002] The recorded allergy of Case Alder is compound X.

Status: `evidence_quote`. Expected-result check: **PASS**.

## 12. label-overview

**User:** List documented attributes of Fictional Luma.

**cpu-llm:**

> Source quotations (not clinically validated):
> [demo-label-luma-p0004] The dose interval of Fictional Luma is 12 hours.
> 
> Source quotations (not clinically validated):
> [demo-label-luma-p0002] The ingredient of Fictional Luma is compound L.
> 
> Source quotations (not clinically validated):
> [demo-label-luma-p0003] The storage of Fictional Luma is cold.
> 
> Source quotations (not clinically validated):
> [demo-label-luma-p0001] The strength of Fictional Luma is 0.75 mg.
> [demo-secondary-luma-p0001] Fictional Luma's strength is 750 mcg.

Status: `evidence_quote`. Expected-result check: **PASS**.

## Inspect or reproduce

`responses.json.gz` contains the full real API replies, proof spans/hashes and
per-question checks. `receipt.json` pins the dataset/runner hashes and runtime
revision. `summary.json` records the aggregate result. The manifest hashes the
saved artifacts. The dataset and runner are one directory above.

Follow [the setup instructions](../README.md) and run
`python examples/healthcare/run_demo.py --out build/healthcare-demo-new-run`
from the repository root with a configured demo database and a new output directory.
