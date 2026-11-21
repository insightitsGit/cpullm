# Frontier on an open problem: why do overparameterized networks generalize?

Date: 2026-11-21. Knowledge base: `tests/fixtures/dl_generalization/` (106 arXiv papers, 60 full text, 46
abstracts; 1652 chunks), namespace `dl_generalization_frontier`. Raw receipts: `raw-*-run{1,2,3}.json`; run log:
`runs.json`; scripts: `scripts/`.

There is no ground truth: the question is open. Hypotheses are reviewed by hand for whether they are coherent,
cross-paper, testable and not already stated in the corpus.

## Runs

Code: `feature/frontier-node` after the argument-relation commit and the "double descent" cue fix (the first run
split "double descent" at "double"; it was re-run without re-ingesting). Ingestion took 742 s; each prompt ran
three times with identical output.

| Prompt | Status | Returned | Generated | Passed abductive | Passed deductive | Passed pre-thinker | Seconds |
|---|---|---|---|---|---|---|---|
| deep learning generalization | hypotheses | 50 | 1235 | 875 | 875 | 467 | 6.2–6.4 |
| generalization of overparameterized networks | hypotheses | 50 | 1132 | 801 | 801 | 412 | 5.7–6.3 |
| benign overfitting | shortage | 7 | 41 | 24 | 24 | 7 | 4.8–5.2 |
| grokking | hypotheses | 50 | 258 | 105 | 105 | 61 | 4.7–5.0 |
| implicit bias of gradient descent | hypotheses | 50 | 236 | 148 | 148 | 56 | 5.1–5.9 |

## Hypotheses worth a look

Each is cross-paper (no single source states it), cites exact passages, and carries a falsification test in the raw
file. "Known?" is my judgement from the literature; the node only checks this corpus.

| Prompt | Hypothesis | Sources (arXiv) | Known? |
|---|---|---|---|
| grokking | Intrinsic task symmetries and larger initializations may jointly drive grokking. | 2603.01968, 2210.01117 | Not that I know of: symmetry and initialization scale are studied separately. |
| grokking | Gains in grokking from intrinsic task symmetries may be offset by weight decay. | 2603.01968, 2502.01774 | Not that I know of. Testable by varying symmetry and weight decay together. |
| grokking | Training partition (data fraction) and weight decay may interact in their effect on grokking. | 2610.00620, 2502.01774 | Largely known (Omnigrok and effective-theory work vary both). |
| implicit bias | Simple features (simplicity bias) may constrain the degree of sharpening, via the network. | 2311.02622, 2103.00065 | Links simplicity bias to edge-of-stability sharpening; I know of no direct test. |
| implicit bias | The implicit bias of SGD may affect the degree of sharpening. | 2407.03848, 2103.00065 | Partly discussed; a clean separation of SGD noise from sharpening would test it. |
| implicit bias | Flatter minima and sparser solutions may move together because both depend on SGD. | 1805.08522, 2402.08344 | Plausible and partly known; testable by measuring both under noisy and noiseless training. |

## Problems seen

- Fragments still anchor many entries ("below how these particular loss landscapes", "including", "Q3",
  "behavior", "mentioned above", "considerations").
- One method name (ResMem) dominates the broad prompts because one sentence about it bridges to many generic
  "generalization" terms.
- Several entries restate known pairings (data fraction × weight decay for grokking).
- "benign overfitting" returned only 7: few sentences in the corpus state relations with that phrase.

The remedy is the same as in the AI-bottlenecks review: dependency parsing for subjects and objects, an encoder
check on bridges, and down-weighting hub terms that link to everything.
