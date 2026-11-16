# Abductive bridge node

Status: implemented in `cpu_llm.abductive_bridge` on 2026-11-16. The node sits
after the Nammade comparison and before the hypothesis reply is sealed.
`Research <topic>`, `Investigate <topic>`, and invention or hypothesis
commands already enter `execute_invention` with Nammade stiffness. After the
three parallel branches return, `resolve_hypotheses` calls
`AbductiveBridgeNode.execute` on the Nammade evaluations.

A standalone `Nammade:` scan does not run the bridge. A bare question that
does not match those commands stays on the ordinary route. Strict Evidence
Mode skips invention, and with it the bridge. CrossDomain and numeric
constraint routes keep their own contracts. The bridge is not a prompt flag,
it is not in `FLAG_BINDINGS`, and it adds no OpenAPI field.

The node does not call a language model. It reads bounds and regime marks
written in the compared passages. A candidate may use only an observable and
a regime variable from those passages and the active domain ontology. The
claim stays `UNVERIFIED_HYPOTHESIS`. Nothing is written back to the vector
index or the Nammade span table.

## Statuses

| Status | Candidate | When |
| --- | --- | --- |
| `BRIDGED` | required | Two passages share an observable, their bounds have an empty intersection, and they differ on one regime variable allowed by the passages or the active ontology. |
| `NO_GAP` | forbidden | The prompt already names the mediating model, a compared passage already links both regimes, or the comparisons do not show incompatible bounds. |
| `INSUFFICIENT_EVIDENCE` | forbidden | The same observable has incompatible bounds, and no regime variable in the chunk schemas or the active ontology takes different values. An abstention reason is required. |

`NO_GAP` reasons, in decision order:

- `The prompt already names the mediating model.`
- `A compared passage already links both regimes.`
- `The diagnostic comparisons do not show incompatible bounds.`

The insufficient-evidence reason is: `The same observable has incompatible
bounds, and no regime variable in the chunk schemas or the active ontology
takes different values.`

## Schema

`RelationalBridge` and `AbductiveBridgeResult` use Pydantic with
`extra=forbid`.

`RelationalBridge` fields:

- `anchor_chunk_ids`: exactly two source ids, ordered low regime then high regime.
- `shared_observable`: a symbol extracted from the two anchor passages.
- `regime_a_constraint` and `regime_b_constraint`: the two source sentences.
- `mediating_variable`: a regime symbol allowed for those passages.
- `proposed_relation`: `inverse_monotonic`, `direct_monotonic`, `threshold_piecewise`, or `regime_conditional`.
- `claim_status`: locked to `UNVERIFIED_HYPOTHESIS`.

`AbductiveBridgeResult` fields:

- `status`: `BRIDGED`, `NO_GAP`, or `INSUFFICIENT_EVIDENCE`.
- `candidate`: present only for `BRIDGED`.
- `abstention_reason`: required for `INSUFFICIENT_EVIDENCE`. `NO_GAP` also records its reason.
- `contradiction_source_ids`: later comparisons that disagree with the candidate. They are recorded. They do not remove the candidate and they do not promote it.

## Decision order

1. If the prompt names a mediating model class, return `NO_GAP`. The class
   patterns are `velocity-dependent`, `temperature-dependent`, and
   `halo-mass-dependent`, plus `dependent on` or `as a function of`
   relative velocity, velocity, temperature, or halo mass. This check runs
   before any bound comparison.
2. If any compared passage contains the observable and already carries two
   regime labels, or two qualitative regime marks, return `NO_GAP`.
3. Extract at most 32 comparison passages. Keep a sentence when it names an
   active observable, a recognized unit, and a recognized bound.
4. Take the first pair of constraints that share an observable, come from
   different sources, have disjoint intervals, and differ on a regime
   variable. That pair becomes the candidate.
5. If a disjoint pair had no differentiating regime variable, remember that
   tension. When no pair becomes a candidate, return `INSUFFICIENT_EVIDENCE`.
6. Otherwise return `NO_GAP` because the comparisons do not show incompatible
   bounds.

Intervals are disjoint when no single constant satisfies both. A lower bound
of ≳ 1 and an upper bound of 1.25 overlap, so they are `NO_GAP`. A lower
bound of ≳ 1 and an upper bound below 0.47 are disjoint. The node does not
treat an overlapping pair as tension.

## Active ontology

One domain is active: self-interacting dark matter. It activates on
`self-interacting dark matter` or `sidm`.

The observable is `cross_section_per_mass`. Its surfaces include `σ/m`,
`sigma/m`, `cross section per mass`, `square centimeters per gram`, and
`cm²/g`. A recognized unit is stored as `cm^2/g`.

The regime variable is `relative_velocity`. Explicit surfaces are
`relative velocity` and `v =`. Ordered labels, low then high, are:

- `dwarf`, from `dwarf`, `dwarf galaxy`, or `dwarf galaxies`.
- `cluster`, from `Bullet Cluster` or the exact singular phrase `cluster merger`.

Qualitative marks are `low relative velocity` and `high relative velocity`.
Numeric marks are `relative velocity of NUMBER km/s` and `v = NUMBER km/s`.

A rank prefers a numeric value, then one qualitative mark, then one label.
Ranks of different kinds are not compared. Equal numeric velocities, within
`1e-6 * max(1, abs(value))`, do not differentiate that variable. A passage
with two labels, or two qualitative marks, is the linking passage in step 2.
One stored sentence that says `Bullet Cluster merger` matches both cluster
patterns, so that sentence is treated as already linking both regimes and
the node returns `NO_GAP` for the whole comparison. `The Bullet Cluster` and
`A cluster merger sample` in separate sentences are two single labels.
`cluster mergers` does not match the singular label.

The relation grammar, using the low-regime constraint and the high-regime
constraint:

- The word `threshold` in the compared passages selects `threshold_piecewise`.
- A low-side lower bound with a high-side upper bound selects `inverse_monotonic`.
- A low-side upper bound with a high-side lower bound selects `direct_monotonic`.
- Two point values select `inverse_monotonic` when the low-side value is larger, and `direct_monotonic` otherwise.
- Every other disjoint pair selects `regime_conditional`.

A later comparison is recorded as a contradiction when it disagrees with
that direction. For `inverse_monotonic`, a passage at or above the high
regime with a lower bound at least the high upper value disagrees, and a
passage at or below the low regime with an upper bound at most the low
lower value disagrees. `direct_monotonic` has the matching high-side check.
Anchor passages are excluded. The claim status stays
`UNVERIFIED_HYPOTHESIS`.

## Hypothesis reply

`resolve_hypotheses` applies the bridge to the options already produced by
hypothesis generation.

On `BRIDGED`, a `cross_source_synthesis` option whose premise document ids
are exactly the two anchors is dropped. Other options stay. The bridge
option is prepended with `origin: abductive_bridge`. Its prediction is
`Unverified hypothesis:` plus the scaling sentence, for example
`cross section per mass decreases as relative velocity increases`. The test
asks for one relative velocity-dependent scaling, keeps a parameter set only
when it satisfies both quoted constraints, and repeats the claim status.
Recorded contradiction ids are appended with the instruction that they do
not promote the claim.

On `NO_GAP` with an empty option list, and only when the prompt names a
mediating model, `prompt_premise_hypothesis` compiles the user's sentence
against the first two extracted constraints of one observable from different
sources. Its origin is `prompt_premise`. The test says to reject the premise
when no shared parameter set satisfies both, and it says not to add a second
mechanism. When hypothesis generation already returned an option, `NO_GAP`
does not add another.

`INSUFFICIENT_EVIDENCE` leaves the option list unchanged and appends the
abstention reason under Hypothesis generation.

The user-facing reply still begins `Three research methods ran in parallel`.
The bridge is the fourth recorded method. `research_methods.abductive_bridge`
is `{status, promotion: blocked}`. The full result is `abductive_bridge` on
the response. `routing.post_stages` ends with `abductive_bridge` after
`taxonomy_invention`, `research_hypotheses`, and, when the scan ran,
`nammade_equilibrium`.

The older self-interacting-dark-matter joiner in `hypothesis_options` still
runs first when one chunk states core sizes of `(LOW–HIGH) kpc` and another
chunk states the Bullet Cluster bound together with the mass-peak and
galaxy-centroid phrases. The bridge replaces that option only when those two
document ids are the bridge anchors.

## Recorded snapshot

The following run used a memory snapshot of authorized rows. It did not use
the encoder and it did not use PostgreSQL. The water sentence was stored and
was not admitted.

Corpus A stored the dwarf requirement, ≳ 1 cm²/g, and the Bullet Cluster
upper bound of 1.25 cm²/g at 68% confidence.

- Open question, prefixed `Research how can self-interacting dark matter form cores in dwarf galaxies without violating the Bullet Cluster merger bound?` The bridge returned `NO_GAP`: `The diagnostic comparisons do not show incompatible bounds.` The reply had no hypothesis. Nammade quoted the two physics sentences.
- Closed question, prefixed `Research can a single velocity-dependent self-interacting dark matter model explain dwarf-galaxy cores and satisfy Bullet Cluster merger constraints?` The bridge returned `NO_GAP`: `The prompt already names the mediating model.` One `prompt_premise` option compiled that sentence against the dwarf sentence and the 1.25 cm²/g sentence.

Corpus B added: `A cluster merger sample limits the dark matter cross section per mass to < 0.47 cm²/g at 95 percent confidence.`

- The same open question returned `BRIDGED`. Anchors were the dwarf sentence and the 0.47 sentence. `shared_observable` was `cross_section_per_mass`, `mediating_variable` was `relative_velocity`, and `proposed_relation` was `inverse_monotonic`. The prediction was `Unverified hypothesis: cross section per mass decreases as relative velocity increases.` `contradiction_source_ids` was empty. The 1.25 cm²/g sentence remained a Nammade excerpt because its interval overlaps the dwarf requirement.
- The same closed question stayed `NO_GAP` and kept the single `prompt_premise` check against the dwarf sentence and the 1.25 cm²/g sentence.

These outcomes are schema-bound readings of the stored sentences. They do
not identify a dark-matter particle and they do not establish a physical law.
