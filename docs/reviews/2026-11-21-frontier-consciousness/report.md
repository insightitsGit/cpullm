# Frontier on a philosophical open problem: consciousness

Date: 2026-11-21. Knowledge base: `tests/fixtures/consciousness/` (153 arXiv papers, 48 full text, 105 abstracts;
1241 chunks), namespace `consciousness_frontier`. Raw receipts: `raw-*-run{1,2,3}.json`; run log: `runs.json`.

Code: `feature/frontier-node` with the argument relations (supports / undermines). This run started before the
"double descent" cue fix, which does not affect this corpus. Ingestion took 733 s; each prompt ran three times with
identical output.

| Prompt | Status | Returned | Generated | Passed abductive | Passed deductive | Passed pre-thinker | Seconds |
|---|---|---|---|---|---|---|---|
| hard problem of consciousness | hypotheses | 12 | 28 | 18 | 18 | 12 | 4.5–4.7 |
| phenomenal consciousness | hypotheses | 50 | 532 | 193 | 193 | 147 | 4.7–5.2 |
| integrated information theory | hypotheses | 50 | 519 | 202 | 202 | 122 | 4.5–4.8 |
| global workspace theory | hypotheses | 50 | 396 | 153 | 153 | 97 | 4.8–5.1 |
| illusionism | insufficient_evidence | 0 | 0 | 0 | 0 | 0 | 3.8 |

## Result

This is the weakest of the three domains tested.

- **Argument relations were rare.** Only 2 of the 50 phenomenal-consciousness entries use supports/undermines.
  The papers mostly state their positions as questions ("how do physical processes give rise to…") or as
  identities ("consciousness is…"), and the node reads neither.
- **Question fragments become anchors.** "how do physical processes", "what enables the brain", "ignored the
  question of why NCC" are all malformed but passed the filter.
- **Hub terms dominate.** "engram theories" in GWT, and "attention" and "nonclassical information theory" in IIT,
  each bridge to many entries.
- **Illusionism returned nothing.** Only two openly licensed illusionism papers are in the corpus, and none states
  a relation the node can read.

## Hypotheses worth a look

| Prompt | Hypothesis | Sources (arXiv) | Note |
|---|---|---|---|
| IIT | Higher-order representations and integrated information theory may stand or fall together because both depend on attention. | 2406.06143, 2506.19057 | A coherent bridge between two rival theory families through attention. Close to existing arguments that both theories need attention, but I have not seen it framed as a shared dependency. |
| GWT / IIT | Comparing a theory's predicted experience with reports, and our inability to access experience directly, may jointly constrain the testing of consciousness theories. | 2004.03541, 2512.19155 | A reasonable reading of the falsification debate. The anchor "inability" is a fragment, so the hypothesis is only partly formed. |
| IIT | An irreducible substrate and a learned self-model may jointly constrain integrated information. | 2412.10626, 2512.19155 | Interesting if taken seriously, but the source term ("zself") is garbled. |

## What would help

Philosophy needs readers for copula and identity claims ("X is Y", "X consists in Y") and for rhetorical
questions, both missing in the current lexicon. Beyond that, it needs the same dependency-parse and encoder bridge
check as the other domains.
