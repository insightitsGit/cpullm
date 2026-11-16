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
| `NO_GAP` | forbidden | A compared passage already links both regimes, or the comparisons do not show incompatible bounds. A named model in the prompt does not by itself select this status. |
| `INSUFFICIENT_EVIDENCE` | forbidden | The same observable has incompatible bounds, and no regime variable in the chunk schemas or the active ontology takes different values. An abstention reason is required. |

`NO_GAP` reasons, in decision order:

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

1. If any compared passage contains the observable and already carries two
   regime labels, or two qualitative regime marks, return `NO_GAP`.
2. Extract at most 32 comparison passages. Keep a sentence when it names an
   active observable, a recognized unit, and a recognized bound.
3. Walk every pair from different sources that share an observable. A pair
   whose intervals overlap is a shared-constant reading. A pair whose
   intervals are disjoint and that differs on a regime variable is a bridge.
   The receipt keeps the first bridge. Up to eight bridges and eight
   shared-constant pairs are returned for the option list.
4. If a disjoint pair had no differentiating regime variable, remember that
   tension. When no pair becomes a bridge, return `INSUFFICIENT_EVIDENCE`.
5. Otherwise return `NO_GAP` because the comparisons do not show incompatible
   bounds. Overlapping pairs can still appear as shared-constant options.

A prompt that names `velocity-dependent`, `temperature-dependent`,
`halo-mass-dependent`, or a dependence on relative velocity, velocity,
temperature, or halo mass does not suppress the walk. That named model is
assembled later as its own stated-premise option.

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

`resolve_hypotheses` appends every distinct reading to the options already
produced by hypothesis generation. Source predictions and the core-size
joiner stay in the list.

The stated-premise option is added when the prompt names a mediating model
and at least two constraints of one observable come from different sources.
Its origin is `prompt_premise`. The test checks that premise against the
first two extracted constraints and does not replace the other readings.

Each bridge is an option with `origin: abductive_bridge`. Its prediction is
`Unverified hypothesis:` plus the scaling sentence, for example
`cross section per mass decreases as relative velocity increases`. The test
asks for one relative velocity-dependent scaling, keeps a parameter set only
when it satisfies both quoted constraints, and repeats the claim status.
Recorded contradiction ids are appended with the instruction that they do
not promote the claim.

Each overlapping pair is an option with `origin: compatible_bounds` and
`claim_status: CONSISTENCY_CHECK`. The prediction says a single constant
can satisfy both stored bounds. The test does not introduce a mediating
variable.

`INSUFFICIENT_EVIDENCE` appends the abstention reason under Hypothesis
generation. Shared-constant options from other pairs still appear.

The user-facing reply still begins `Three research methods ran in parallel`.
Hypothesis generation numbers every reading and labels it `Stated premise`,
`Abductive bridge`, `Shared constant`, `Cited premises`, or
`Source prediction`. The bridge is the fourth recorded method.
`research_methods.abductive_bridge` is `{status, promotion: blocked}`. The
full result is `abductive_bridge` on the response, and its `candidate` is
the first bridge. `routing.post_stages` ends with `abductive_bridge` after
`taxonomy_invention`, `research_hypotheses`, and, when the scan ran,
`nammade_equilibrium`.

The older self-interacting-dark-matter joiner in `hypothesis_options` still
runs when one chunk states core sizes of `(LOW–HIGH) kpc` and another chunk
states the Bullet Cluster bound together with the mass-peak and
galaxy-centroid phrases. That cited-premises option stays beside any bridge
or shared-constant option.

## Recorded snapshot

The following run used a memory snapshot of authorized rows. It did not use
the encoder and it did not use PostgreSQL. The water sentence was stored and
was not admitted.

Corpus A stored the dwarf requirement, ≳ 1 cm²/g, and the Bullet Cluster
upper bound of 1.25 cm²/g at 68% confidence.

- Open question, prefixed `Research how can self-interacting dark matter form cores in dwarf galaxies without violating the Bullet Cluster merger bound?` The receipt is `NO_GAP` because the intervals overlap. The reply has one `compatible_bounds` option: a single constant can satisfy both stored bounds. Nammade quotes the two physics sentences.
- Closed question, prefixed `Research can a single velocity-dependent self-interacting dark matter model explain dwarf-galaxy cores and satisfy Bullet Cluster merger constraints?` The receipt is `NO_GAP` for the same overlap. The options are the `prompt_premise` check against the dwarf sentence and the 1.25 cm²/g sentence, then the same shared-constant option.

Corpus B added: `A cluster merger sample limits the dark matter cross section per mass to < 0.47 cm²/g at 95 percent confidence.`

- The same open question returns `BRIDGED`. The first option is the bridge. Anchors are the dwarf sentence and the 0.47 sentence. `shared_observable` is `cross_section_per_mass`, `mediating_variable` is `relative_velocity`, and `proposed_relation` is `inverse_monotonic`. The prediction is `Unverified hypothesis: cross section per mass decreases as relative velocity increases.` The later options are shared-constant checks for the dwarf requirement with the 1.25 cm²/g bound, and for the 1.25 cm²/g bound with the 0.47 cm²/g bound.
- The same closed question keeps that bridge and those shared-constant checks, and places the stated velocity-dependent premise first. The premise is checked against the dwarf sentence and the 1.25 cm²/g sentence.

These outcomes are schema-bound readings of the stored sentences. They do
not identify a dark-matter particle and they do not establish a physical law.
