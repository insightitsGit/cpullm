# Strict evidence policy validation

Date: 2026-11-02. Implementation built on `b248dfa`.

Final full-suite run: **806 passed, 2 skipped, 3 xfailed**, 6 warnings,
110.68 seconds. Exit status 0. The warnings were NumPy overflow warnings in
three existing ordinary pipeline tests; those tests passed. This is a software
regression result, not a clinical accuracy score or clinical validation.

Environment: Windows, PostgreSQL 18 on loopback port 55433, a new disposable
database `strict_evidence_1102_r2`, existing isolated benchmark virtualenv,
cached encoder/parser assets, `CPU_LLM_LIVE_TESTS=1`, Hugging Face and
Transformers offline. PostgreSQL was stopped after the run. No hosted model
was used. Full command was `python -m pytest` with plugin autoload disabled.
Local raw logs: `build/strict-evidence-tests-r2.log`.

New coverage comprises 13 unit scenarios, 3 real HTTP header scenarios and
2 live PostgreSQL/appliance scenarios:

- Strict dispatch bypasses the ordinary graph even with neural realization,
  style, imagination and arithmetic options supplied.
- Exact decimal quotations retain source IDs, offsets and full-chunk hashes.
- Distinct 0.75/0.25 values abstain rather than rounding into agreement.
- Missing facts, unsupported medical advice, references, compound questions,
  conditions, multisentence sources and scan overflow do not generate answers.
- Prompt markers activate only in the documented standalone first-line form.
- Header and body controls reach the actual HTTP service; invalid values fail.
- Appliance/server floors cannot be disabled by false flags or standard headers.
- Real SQL applies source permissions before the limit; similarly named source
  prefixes do not collide; historical validity intervals select old/new evidence.
- A real strict appliance returns one authorized source, while an unscoped
  lookup sees both conflicting values and abstains.

The first full run exposed a newly registered pre-graph consumer being treated
as a missing graph node, plus an invalid short paragraph ID in a new SQL fixture.
Both were corrected before the successful fresh-database rerun. Its local
failure log is retained at `build/strict-evidence-tests.log`.

Remaining limits are intentional and documented in
[the contract](../../strict-evidence-spec.md): source truth is unverified;
conflict detection recognizes only the exact supported template; no semantic
paraphrase coverage or clinical decision support is claimed. Strict mode is
stateless and returns source quotations rather than synthetic propositions.
