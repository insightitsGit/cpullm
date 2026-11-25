# Frontier and Deepen v2: screening, composition gate and research review

Status: implemented on `feature/frontier-deepen-v2` (target release 1.17.0). Motivated by the
[quantum computing run and audit](reviews/2026-11-25-quantum-computing/report.md) and an external review of its
receipts. Each item lists the observed failure, the change, whether existing output changes, and acceptance tests.

Every Frontier and Deepen output stays an `UNVERIFIED_HYPOTHESIS` with `promotion: blocked`, and nothing is written to
the index. Strict evidence mode still disables both routes.

## Summary

| # | Change | Existing output changes? |
|---|---|---|
| 1 | Artefact filter for relation terms and candidate controls | Yes: removes entries and controls built from document artefacts |
| 2 | Composition gate: `bridge_mismatch` verdict, `lead_status`, quarantined test plans | Yes: some `contested` verdicts become `bridge_mismatch`; quarantined leads get a resolution plan instead of an experiment |
| 3 | Coverage-gap labelling | Additive: new fields; `lead_status: coverage_gap` |
| 4 | Suggested procedures from existing setups | Additive |
| 5 | Variable typing and design routing | Yes: designs change when a variable is a fixed property or a noise source |
| 6 | Frontier `screen` option | Opt-in |
| 7 | Topic-match report and drift warning | Additive |
| 8 | Time reserved for leading checks | Yes, only on runs that would otherwise exhaust the time budget |
| 9 | Free-form Deepen hypotheses and a direct (one-link) pattern | Yes: prompts that returned `needs_clarification` are now read |
| 10 | Opt-in arXiv prior-art reviewer, `prior_art_status` | Opt-in; off by default |
| 11 | Axiom sources | Opt-in |
| 12 | Scale and abstraction-level warnings | Additive: new `scope_differences` entries (can turn `conditional` into `requires_review`) |
| 13 | Ingestion speed | Edge-file cache: none. Deferred consolidation: opt-in |

## 1. Artefact filter

**Observed.** 37 of 300 distinct quantum entries used document artefacts as terms:
- section headers: "D. Implications for Future Processors";
- author names: "S. Bravyi", "Eliya Nachmani", "Dae - Young Yun";
- merged words: "Tothebestofour knowledge", "theavailabilityofnoisyintermediate";
- meta or filler phrases: "definition", "issues", "Recent experiments", "less than 10 mEh", "majority of error".

The same strings appeared in Deepen's candidate controls.

**Change.** A shared `artefact_reason(term)` in `frontier.py` detects:
- header prefixes such as `D. `, `IV. `, `3.2 `, plus `Fig.`, `Table`, `Section`, `Appendix` and `Eq.`;
- initial-plus-surname names;
- merged function words: an alphabetic token of 12 or more letters containing two or more distinct embedded
  function words;
- meta nouns: issues, results, definition, implications, knowledge, advances, line of work, former, latter;
- phrases led by "recent", "previous" or "our";
- bare comparator quantities: "less than", "more than", "at least", "up to", followed by a number;
- partitive phrases: "majority of", "fraction of", "portion of".

When the spaCy parser is active, a phrase whose root token is a `PERSON` entity is also rejected at extraction.
Frontier's pre-thinker rejects candidates whose terms are artefacts, under a new reason `pre_thinker:artefact`.
Deepen skips them as candidate controls.

**Acceptance.**
- Unit tests reject each example above.
- Unit tests keep real terms: "surface code", "weight decay", "Cosmic rays", "Integrated Information Theory",
  "T1 decay", "qLDPC codes".
- On the quantum corpus, the share of returned entries with artefact terms falls to under 2%.

## 2. Composition gate

**Observed.** All three contested results in the corrected quantum run came from a bridge that changed a term's
meaning:
- "taking into account the correlated errors" read as "correlated errors";
- "leakage-induced correlated errors" matched to "X, Y errors";
- pairwise defects matched to stabilizer defects.

Contested and incompatible-direction leads still received a mediation or factorial experiment.

**Change.**
- A contrary citation is **genuine** when its endpoints match the requested terms exactly by `term_key`, or by an
  encoder cosine of at least 0.8 when an encoder is present. Otherwise it is **bridged**.
- If every contrary citation behind a `contested` link, or behind a contradicted direction, is bridged, the link
  status and the verdict become `bridge_mismatch` instead of `contested`.
- New `lead_status` on every Deepen receipt and every Frontier `check`:
  - `testable`: all links supported, composition `conditional`;
  - `needs_semantic_resolution`: a `bridge_mismatch` verdict, or composition bridges that change a term's meaning;
  - `contested_tension`: a genuine contested link or a contradicted direction (`incompatible_direction`);
  - `coverage_gap`: see item 3;
  - `insufficient_evidence`, `needs_review` (other review concerns) or `incomplete`.
- **Quarantine.** For `needs_semantic_resolution` and `contested_tension`, `test_plan.design` becomes
  `resolve_first`, and `blocked_design` keeps the design that would otherwise apply. The steps say what to resolve:
  the listed meaning differences, or the cited contrary evidence. Readiness stays `needs_input`. The reply leads
  with the reason. Summaries cannot present these leads as ready experiments, because the status sits in the
  receipt.
- Frontier's reply prints `lead_status` for checked entries.

**Acceptance.**
- A unit test where the counter-evidence uses a different endpoint phrase yields `bridge_mismatch` and
  `needs_semantic_resolution`.
- A unit test with an exact-term contrary source stays `contested` and `contested_tension`.
- Both get `resolve_first`. The weight-decay regression case remains contested.

## 3. Coverage gaps

**Observed.** Six of eight quantum open problems came back `unsupported` because the relevant papers were
abstracts only.

**Change.** Each link with status `weak` or `missing` reports
`coverage = {source_documents, target_documents, short_source_share}`:
- the two counts are the documents that mention each term;
- `short_source_share` is the share of those documents with at most two chunks, which marks likely abstract-only
  sources.

When such a link has no contrary evidence and either term appears in fewer than three documents, or more than half
of the mentioning documents are short, `lead_status` is `coverage_gap`. An `add_sources` research action names the
terms. The verdict itself is unchanged.

**Acceptance.** A unit test with abstract-length sources yields `coverage_gap` and the action.

## 4. Suggested procedures

**Observed.** Deepen lists existing setups, but test plans stay `needs_input` with empty measurement procedures.

**Change.** `test_plan.suggested_procedures` lists, for each manipulated or measured variable, up to three cited
setups and measurement hints that name it. Each is labelled `suggested_not_validated`. Nothing is copied into the
user-definition fields, and readiness does not change. A setup can come from an unrelated study: in the quantum run,
2203.04948 is a decoder paper, not a cosmic-ray measurement.

## 5. Variable typing and design routing

**Observed.** In QC-4, Deepen proposed a 2×2 factorial that varied Pauli weight, which is a property of the
observable, not a dial.

**Change.** `variable_types.py` assigns each term one of five types:
- `intervention`: a protocol or resource choice, such as initialization, measurements, reset, distillation rate,
  learning rate, weight decay, samples or shots;
- `observable_property`: fixed by the problem, such as weight, locality, degree, dimension, geometry, connectivity
  or symmetry;
- `noise_channel`: noise, decoherence, radiation, cosmic rays, leakage, crosstalk, drift, defects, quasiparticles;
- `outcome_metric`: rate, error, fidelity, threshold, cost, overhead, variance, accuracy, latency, throughput,
  generalization;
- `unknown`.

Users can override a type with `definitions[term].type`. Routing:

| Pattern | Types | Design |
|---|---|---|
| convergent | intervention × intervention | 2×2 factorial (unchanged) |
| convergent | intervention × property or noise | `stratified`: vary the intervention within strata of the property, or with noise injected at two levels; compare effects across strata |
| convergent | property × property, or noise × property | `observational_regime_map`: compare instances across regimes; no manipulation |
| chain or direct | exposure is a property | `stratified` mediation over selected instances |
| chain or direct | exposure is noise | mediation with noise injection or selected exposure levels |
| any | outcome is not an `outcome_metric` | adds the requirement "define a measurable outcome" |

`test_plan.variable_types` and `test_plan.design_reason` record the decision.

**Acceptance.**
- QC-4's terms route to `stratified`.
- QC-2 (two interventions) stays a 2×2 factorial.
- A `type` override is honoured.

## 6. Frontier `screen` option

**Observed.** Frontier ranks by source support first, so generic, widely supported entries take the leading slots.
In the quantum run, the useful entries sat at ranks 5–26.

**Change.** `frontier={"screen": true}`, or `{"screen": {"shortlist": n}}` with n from 5 to 30 (default 15):
1. drops generic entries: an anchor outside the topic that appears in at least 8% of chunks, unless the entry's
   relevance is at least 0.8;
2. re-ranks the rest by `0.6 × deductive_relevance + 0.4 × novelty`;
3. checks the first `deepen_top` entries with Deepen with the novelty review on, so leading checks report knowledge-base
   overlap.

`screen` records `applied`, `dropped_generic`, the removed IDs and the formula. Without the option, the order and
contents are unchanged, apart from items 1, 2 and 8.

## 7. Topic match and drift warning

`topic_match = {focus_terms, matched_chunks, on_topic_share, drift_warning}`. `on_topic_share` is the share of
returned entries whose terms contain a focus stem. When it is below 0.3, `drift_warning` names the most frequent
anchor terms and the reply suggests rephrasing the topic. In the quantum run, "two-level systems" matched
"system size".

## 8. Time reserved for leading checks

When `deepen_top > 0`, candidate generation stops at 80% of `max_seconds`, so the leading checks can run. A stop
is recorded as `candidate_search_complete: false` with stop reason `generation_time_reserved`. Runs that finish
within that time are unaffected.

## 9. Free-form Deepen hypotheses

**Observed.** Five of seven open problems written as plain sentences returned `needs_clarification`.

**Change.**
- New **direct** pattern (one link A → C), with a one-factor intervention design.
- Accepted forms, in addition to the Frontier forms:
  - "A may/can/could/might/will <verb> C" and "A <verbs> C", where the verb is one of increase, raise, drive,
    reduce, lower, decrease, limit, constrain, bound, affect, cause, lead to, support, undermine, improve,
    degrade, suppress or enhance;
  - "A <verb> C through/via/by B" (a chain);
  - "C may increase/grow/scale (exponentially/polynomially/linearly) with A" (a direct increase from A to C);
  - "A implies C" (direct support).
- `limit`, `bound`, `suppress` and `degrade` map to the existing relation kinds.
- Anything else still returns `needs_clarification`. When the message has two or more noun phrases, the reply
  suggests a rephrasing in Deepen's forms.

## 10. Prior-art reviewer (opt-in)

**Observed.** Novelty was checked only against the 155-paper snapshot. An external check found prior art for QC-6
(arXiv:2405.00146) and partial prior art for QC-1 (arXiv:2505.05249).

**Change.**
- `cpu_llm.literature_arxiv.ArxivReviewer` implements the existing `literature_reviewer` hook using the arXiv
  API. Operators enable it with `app.literature_reviewer = ArxivReviewer()`.
- Requests opt in with `deepen={"hypothesis": ..., "novelty": True, "external_review": True}`. It is never called
  during Frontier generation.
- The novelty review adds `prior_art_status`:
  - `potential_prior_art` when an external record's title or abstract contains at least two of the hypothesis's
    core terms;
  - otherwise `none_found`, `not_checked` or `unavailable`.
- Records are cited with their arXiv URL. **No record is ever marked as established prior art automatically;** a
  reviewer decides.
- Privacy: the hypothesis terms are sent to export.arxiv.org, which is why this is off by default.

## 11. Axiom sources (opt-in)

`deepen={"hypothesis": ..., "axiom_sources": ["review-"]}` and `frontier={"axiom_sources": [...]}` name source
prefixes that hold background knowledge, such as review articles and textbooks. `Appliance.axiom_sources` can set an
operator default.
- Deepen uses axiom citations as evidence and labels them `tier: axiom`.
- Frontier drops candidates whose every edge comes from axiom sources (background, not frontier), and its novelty
  document spread counts only non-axiom documents.

## 12. Scale and abstraction-level warnings

For each pair of adjacent links, the composition review compares the cited sentences:
- **time scale:** units from ns to hours with a magnitude. A difference of three orders of magnitude or more adds a
  `scope_difference` of type `time_scale`.
- **abstraction level:** device, gate, code or algorithm, from keyword families. A different level adds a
  `scope_difference` of type `abstraction_level`.

These are warnings for review. They do not reject the lead.

## 13. Ingestion speed

**Observed.** Per-document ingest time grew with knowledge-base size, from 0.5 s to 7 s for abstracts at 3,369
chunks. Profiling one abstract ingest (3.6 s) found two costs that are not encoding:
- `merge_passage_edges` re-reads and parses the whole edge file (0.65 s);
- `bind_word_taxonomy` runs a full resonance consolidation and checkpoint inside the third-party `prismresonance`
  library (1.9 s, mostly a SQLite rewrite).

**Change.**
1. `load_edges` caches parsed edges by path, size and modification time, and `save_edges` refreshes the cache. No
   behaviour change.
2. `Appliance.ingest(..., consolidate="each" | "end")`. The default `"each"` keeps today's behaviour. `"end"` runs the
   resonance consolidation once after all documents in the call, for folder or list ingests. This changes the
   resonance state, which goes through fewer decay cycles, so it is opt-in.

**Acceptance.**
- Edges are identical with and without the cache.
- A timing receipt shows lower per-document time on the quantum namespace.

## Evaluation

| Check | Method |
|---|---|
| Full test suite | No new failures |
| Before/after on four corpora | Re-ingest is not needed. Frontier on the original prompts: artefact share, `bridge_mismatch` versus `contested` counts, `lead_status` distribution, screen output, timings |
| Determinism | Three repeated runs per prompt give identical IDs |

Results are recorded in `docs/reviews/2026-11-26-frontier-deepen-v2/`.

## Out of scope

- Physical-regime reasoning beyond the cue-based warnings in item 12.
- Automatic conversion of `potential_prior_art` into a finding.
- Any change to Frontier's candidate generation other than the artefact filter and the time reserve.
