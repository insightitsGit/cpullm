# Frontier and Deepen on quantum computing open problems

Date: 2026-11-25. Code: `main` at `17a1315` (version 1.16.0). Parser `en_core_web_lg`, encoder `all-mpnet-base-v2`.
Every output here is an `UNVERIFIED_HYPOTHESIS`. Nothing was resolved, and nothing here is a finding.

## Knowledge base

- 155 arXiv quant-ph papers (`tests/fixtures/quantum_computing`, sources and licences in `SOURCES.md`): 58 in full
  text (CC BY/BY-SA), 97 as abstracts only. 3,369 chunks.
- Selected by keyword search on ten open problems:
  - fault-tolerance thresholds and overhead;
  - surface-code decoders;
  - qLDPC codes;
  - magic-state distillation;
  - leakage;
  - correlated errors and cosmic rays;
  - two-level-system (TLS) defects;
  - barren plateaus;
  - error-mitigation limits;
  - quantum advantage under noise.
- Ingestion: 33 minutes, one paper at a time while downloading (`scripts/ingest_incremental.py`). Full-text papers
  took about 30 s each and abstracts 0.5–7 s.

## Runs

| Step | Result |
|---|---|
| Frontier, 12 topics | 9 topics returned 50 entries, barren plateaus 28, leakage 19, TLS 15. Each took 11–15 s, except "quantum error correction", which hit the 60 s deadline before its leading check. Peak RSS 2.7 GB |
| Distinct entries | 300 distinct among 512 returned. Generic entries repeat across topics |
| Leading checks (Frontier's automatic Deepen) | 55 checks: 50 all links supported, **5 contested** |
| Full Deepen, 26 distinct top seeds | all links supported 26; composition `requires_review` 23, `conditional` 3; novelty review: no overlap in the snapshot for all |
| Deepen, 8 open problems phrased as hypotheses | 1 contested, 1 partly supported, 6 unsupported |

Deepen only reads the Frontier forms ("A may reduce C through B."). In the first run, five open problems written
as free sentences ("Error mitigation cost may increase exponentially with circuit size.") returned
`needs_clarification`. They were rephrased and re-run (`scripts/deepen_open.py`).

## Open problems as hypotheses

| Hypothesis | Verdict | What the evidence says |
|---|---|---|
| Cosmic rays may reduce the error threshold through correlated errors | **contested** (direction contradicted) | Link 1 is supported: cosmic rays caused correlated errors at about one per 10 minutes, 17±1% of such events (2402.03208). Link 2 is the contradiction: in concatenated codes, "taking into account the correlated errors significantly reduces the logical error rate and increases the error threshold" (2407.16176). |
| Leakage may increase logical error rates through correlated errors | partly supported | The leakage → correlated-error link is weak in this corpus; the second link uses the same 2407.16176 sentence. |
| Noise → quantum advantage via classical simulation; barren plateaus → VQAs via simulability; circuit size → mitigation cost via sampling overhead; qLDPC → overhead via rate; qLDPC → decoder complexity via connectivity; TLS → coherence via dielectric loss | unsupported (weak or missing links) | The corpus discusses these, but mostly in abstracts and not as directed relation sentences that the parser extracts. This is a coverage limit of the knowledge base and parser, not evidence against the claims. |

The contested case deserves a careful reading. 2407.16176 is about a decoder that *models* correlations. Its
sentence does not say correlated errors raise the threshold; it says accounting for them does. Deepen's direction
check is technically right about the quoted text but rests on a meaning slip. The research question the conflict
points to is real: how much of the cosmic-ray penalty can a correlation-aware decoder recover? That is a known
direction in the field, not a discovery.

## Seeds worth a researcher's look

| Seed | Evidence | Assessment |
|---|---|---|
| Chemical initialization and mid-circuit measurements may jointly constrain barren plateaus (composition `conditional`) | Chemically initialized starting points show polynomial, not exponential, decay of gradient variance (2609.22729). Mid-circuit measurements, pretraining and entanglement regularization mitigate barren plateaus (2406.14285). | The two mitigations come from different papers, and the knowledge base has no study that combines them. Deepen proposes a 2×2 factorial: low/high chemical initialization × with/without mid-circuit measurements, measuring gradient variance against system size. A cheap simulation study. Check first whether either regime is classically simulable. That is a known caveat for barren-plateau-free models (Cerezo et al., arXiv:2312.09121), and that paper is not in this corpus. |
| Physical qubit counts may constrain the decoder through qLDPC codes | qLDPC codes needing thousands of physical qubits (2607.27644); decoders needing particular code structure (2503.05003) | The qubit-count/decoder trade-off is well known. Not novel. |
| Erasure conversion may raise the error threshold through shuttling-based QEC | A paper title (2601.10461) bridged to the 2407.16176 sentence | The bridge is a title fragment matched to "correlated errors"; the composition review flags it. Not a real chain. |

## Failure modes seen

- **PDF artefacts as terms.** Section headers ("D. Implications for Future Processors"), author names ("S. Bravyi"),
  merged words ("Tothebestofour knowledge") and "definition" entered relation edges. A header/author filter before
  edge extraction would remove most of these.
- **Off-topic retrieval.** "Two-level systems" matched "system size" (Lie-algebra dimension) rather than TLS defects,
  because TLS papers were mostly abstracts. "Correlated errors" and "error mitigation" returned the same generic
  leading entries.
- **Hub entries.** "Qubit count", "noise" and "sampling cost" generate many high-support, low-information entries
  that lead several topics.
- **Supported is weak evidence.** All 26 seeds were "all links supported", as expected for entries built from
  source edges. The informative signals were the 5 contested checks and the composition review (23 of 26
  `requires_review`).

## Execution review and corrected re-run

We audited how the engine was used. The configuration was correct throughout:
- the spaCy `en_core_web_lg` parser and the encoder bridge check were active;
- each chunk carries its source prefix, so single-source detection works;
- the Deepen calls used the documented envelope `deepen={"hypothesis": <Frontier entry>, "novelty": True}`.

Four usage mistakes were ours:

1. **Seed selection.** The first run sent only ranks 1–3 per topic to Deepen. Frontier ranks by source support
   first, so those slots went to generic multi-document entries. 110 of the 300 distinct entries appear under several
   topics, and 37 contain PDF artefacts. The topic-specific entries sat at ranks 5–26 and were never checked.
2. **Open-problem phrasing.** The first open-problem prompts were not in Deepen's sentence forms. They were rephrased
   (above).
3. **Budget.** "Quantum error correction" hit the 60 s default. With `frontier={"limits": {"max_seconds": 120}}`
   it finished in 42 s, and its leading check found 1 contested entry among 5.
4. **Topic phrasing.** "Two-level systems" matched "system size". "Two-level system defects" (19 entries),
   "dielectric loss" (8) and "quasiparticles" (2) retrieved the right papers. These knowledge bases are thin
   because most TLS papers were abstracts only.

**Corrected Deepen pass** (`scripts/rerun_qc.py`): up to four entries per topic from anywhere in the list of 50.
Entries were dropped if they were cross-topic, contained artefacts, were already contested, or were duplicates.
The rest were ranked by 0.6 × relevance + 0.4 × novelty. That gave 53 reviews:

- verdicts: 50 all links supported, 2 contested, 1 partly supported;
- composition: 47 `requires_review`, 5 `conditional`, 1 insufficient evidence;
- novelty review: 51 found no overlap in the knowledge base, 2 found potential overlap.

What the checks caught:
- **Both new contested cases are meaning slips.** "Leakage-induced correlated errors" was bridged to "X, Y errors",
  and "uncorrelated pairwise defects" to stabilizer defects. The composition review flagged the bridges. Discard
  both.
- **Both novelty overlaps were correct.** "Charge noise drives flux noise through quasiparticles" is stated almost
  verbatim in 2407.21177. "Quantum computers depend on error correction" is a truism.

**Entries worth a researcher's look**, found below the top ranks:

| Entry | Rank | Evidence | Note |
|---|---|---|---|
| Mid-circuit measurements may reduce the exponential scaling of gradient-free optimizers through barren plateaus | #23 in barren plateaus, relevance 0.975 | Barren plateaus also affect gradient-free optimizers, and mid-circuit measurements mitigate barren plateaus (two papers) | Testable in simulation: does a mitigation shown for gradients also cut the shot count of gradient-free optimizers? |
| Chemical initialization and mid-circuit measurements jointly constrain barren plateaus (composition `conditional`) | #1 | 2609.22729, 2406.14285 | As above: a 2×2 factorial simulation |
| Low-weight Pauli operators and the sample count jointly constrain error mitigation (`conditional`) | #8 in error mitigation | — | A sampling-budget trade-off; likely known in the field, but stated in no single paper here |
| Rapid distillation speed may increase circuit error through discarded magic states | #6 in magic state distillation | — | A speed/fidelity trade-off in factories; plausible and known in outline |
| Cosmic rays and faulty magic states may jointly drive correlated errors | #25 in magic state distillation | — | Asks whether radiation bursts correlate failures inside distillation factories. Speculative, but specific |

All of these are `UNVERIFIED_HYPOTHESIS`. Novelty to the field has not been checked against the literature outside
this knowledge base.

**Lesson for users.** Do not read only the top of a Frontier list:
- filter out entries that repeat across topics and entries built from header or author-name artefacts;
- rank the remainder by relevance and novelty;
- deepen those, and use the composition and novelty reviews to discard meaning slips and restatements.

This workflow could become a Frontier option.

## Conclusion

No open problem was resolved, and none could be: the engine recombines what the papers state. One seed (combining
chemical initialization with mid-circuit measurements against barren plateaus) is a concrete, cheap simulation
study absent from this knowledge base. One contested case points at a real nuance (correlation-aware decoding versus
cosmic-ray errors). Most other output was noise from PDF extraction and hub terms.

## Reproduce

`scripts/fetch_all.sh` (with `ids.txt`), `scripts/ingest_incremental.py`, `scripts/run_qc.py`,
`scripts/deepen_open.py`. Raw outputs are in `frontier/` and `deepen/`, with a summary in `runs.json`.
