# Evidence v2 and domain gap validation

Final complete live suite: **844 passed, 2 skipped, 3 xfailed**, six existing
NumPy overflow warnings, 109.58 seconds, exit 0. Windows / PostgreSQL 18, fresh
disposable database `evidence_v2_1102_r3`, real cached encoder and spaCy assets,
`CPU_LLM_LIVE_TESTS=1`, offline model settings, plugin autoload disabled.
The local raw log is `build/evidence-v2-tests-r3.log`; PostgreSQL was stopped
after the run. No hosted calls or real patient data were used.

New tests cover recognized paraphrase conflicts, exact unit equivalence,
uncertain/negative source facts, batch references and partial outcomes,
one-hop universal joins, complete direct-attribute overviews, exact arithmetic,
source-calculation conflict refusal, and unsupported clinical advice.
Public API tests exercise finance ownership with both inferred and explicit
selection, incomplete requests, zero denominators, threshold precision, and
the previously wrong-relation conversational color request in rules mode.
The benchmark scorer has independent proof/value checks and baseline/gold
separation tests.

Earlier local runs are retained: `build/evidence-v2-tests.log` exposed a rewrite
of a spatially qualified color request; a guarded rewrite fixed it.
`build/evidence-v2-tests-r2.log` exposed a newly authored refund fixture missing
its required invoice number; the fixture was completed. These runs are not
reported as successful validation. Structured payload spelling correction was
also disabled before the final full run.

No runtime source changes are permitted between this passing suite and the
recorded benchmark revision. Fresh synthetic benchmarking and replay use
committed runtime, cases and runner hashes. Their outputs must remain separate
from this software regression count.

This does not establish clinical source truth, diagnostic accuracy, prescribing
safety or universal semantic contradiction detection. See
[the clinical acceptance gate](../../healthcare-evidence-acceptance.md) and
[the strict v2 contract](../../strict-evidence-spec.md).
