# Original domain pilot replay

Final runtime: `e6301f30ce67990e1807f7f70b4594c88239ea36`.
The original 24 authored cases and scorer were retained. **Final result: 24/24**:
finance 12/12, fictional medication-label/arithmetic 8/8, clinical-record/missing
evidence 4/4. Clinical positives retrieve already recorded fictional diagnoses;
these are not diagnostic accuracy results. No treatment safety is established.

Historical runtime `273ab48` passed 11/24: finance 0/12, medication 7/8,
clinical-record 4/4. The original archived results remain unchanged at
`../2026-11-02-domain-pilot/`.

`first-run/` on `83e3cab` passed 23/24: finance improved to 12/12 after fixing
specialist request ownership and visible ratio precision. The remaining inline
limit question still asked for Context/Questions formatting. That failure is
retained, not rescored away.

`final-run/` on `e6301f3` passed 24/24 after a bounded explicit same-unit numeric
comparison path preserved the supplied limit and total through request planning,
reference handling and math delivery. It returns an arithmetic comparison,
explicitly not treatment advice. The case files are byte-identical between the
two replay runs; gold and scorer were unchanged.

Each run saves cases, source records, pre-execution freeze receipt, runner
snapshot, compressed raw canonical/style responses, scores, execution log and
SHA-256 manifest. Every one of the 24 stylistic companions skipped, as before:
specialist outputs and these clinical attributes are outside the existing style
adapter. Successful canonical outcomes do not establish stylistic generation.

The runnable entry point is `tools/benchmarks/domain_pilot.py` with a new
`--database` and `--out`; archived snapshots are evidence, not standalone
relocated tools. Both runs used new local PostgreSQL databases and cached
parser/encoder assets. No hosted model was called. A local baseline comparison
for the separate strict evidence suite is saved in
[the evidence v2 report](../2026-11-02-evidence-v2/REPORT.md).
