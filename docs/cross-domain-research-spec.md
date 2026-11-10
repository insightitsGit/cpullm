# CrossDomain research joins

CrossDomain checks whether claims from separate knowledge bases can support the same calculation. Retrieval may suggest candidates. A checked join requires matching quantity, conditions, convention, and units that a trusted operation can normalize. The existing complex-orthogonality route stays available.

## First milestone

**CrossDomain** joins cited premises across KBs and handles the existing
orthogonality check. **Constraint Check** evaluates typed numeric intervals.
Use `Constraint Check: <topic> using KBs: physics, math, experiment.` to request
the numerical node directly. It requires structured claims and never falls back
to the orthogonality check. A CrossDomain request over structured claims
delegates to Constraint Check and records both stages. Both paths return the
same comparison receipt. The existing strict-evidence policy applies to both.

Use `CrossDomain: <topic> using KBs: physics, math, experiment.` with source names prefixed by their KB name. Each participating KB contributes exactly one authorized record to the join. The topic anchors the first KB. Store a record as a complete paragraph with the prefix `CrossDomain claim: ` followed by a JSON object.

- Common fields are `topic`, `quantity`, `conditions`, `convention`, and `role`. These are nonempty strings. The selected records must agree on the first four fields after case and whitespace normalization.
- A `prediction` or `measurement` supplies decimal strings `lower` and `upper`, a `unit`, and an `interval_basis` describing its uncertainty convention. A `bound` uses the same fields but may omit one endpoint. Bounds are inclusive. An absent uncertainty or interval basis prevents a checked join.
- A `method` supplies `operation` equal to `compare_intervals`. The cited method authorizes a known operation. Source text supplies no executable code.
- A prediction plus bound yields `within_bound`, `outside_bound`, or `overlaps_bound`. Two measurements yield `overlapping_intervals` or `disjoint_intervals`. Disjoint intervals flag a discrepancy under the stated basis. They establish no broader scientific contradiction.

Use exact rational arithmetic for decimal inputs and allowlisted linear units. The initial adapter supports energy, mass, length, and dimensionless quantities. Each response retains the original quote, document ID, offsets, and chunk hash from each KB, plus the normalized intervals and operation version. Missing or incompatible records, conflicting candidates, and unsupported units yield an explicit unresolved result. Strict evidence mode keeps its existing policy.

## Later milestones

Preserve page numbers, table headers, equation labels, and figure captions during ingestion. Convert extracted claims into the same typed contract with extraction confidence and provenance. Add symbolic equivalence, uncertainty propagation, and approved adapters for simulations and statistical packages. Keep model or population differences separate from apparent contradictions.

Use indexed candidate retrieval per KB with explicit budgets before scaling across papers and lab collections. Benchmark citation fidelity, missed evidence, abstention, and latency. The initial structured-record milestone uses the existing bounded authorized snapshot.
