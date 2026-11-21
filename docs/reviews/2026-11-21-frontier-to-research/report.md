# Frontier ideas as seeds for the research route

Date: 2026-11-21. Code: `feature/frontier-node` at `0e98df6`. Script: `scripts/frontier_to_research.py`. Results:
`*.json`, one file per Frontier prompt.

## Method

For each of four open questions, Frontier ran once and its top 5 hypotheses (after the anchor spread) became seeds.
Each seed has the form "Investigate A, B and C.", built from the hypothesis's anchors and its bridge term. Each seed
then ran through the existing research route over the same knowledge base:
- invention;
- source hypotheses;
- the Nammade comparison;
- the abductive bridge;
- rule inference.

Nothing was written to the index, and no node was changed.

| Open question | Frontier | Research runs | Time per seed |
|---|---|---|---|
| AI compute cost | 50 hypotheses (44.6 s, first parse) | 5 | 0.9–1.2 s |
| grokking | 50 (12.9 s) | 5 | 1.4–1.7 s |
| implicit bias of gradient descent | 50 (12.1 s) | 5 | 1.4–1.6 s |
| integrated information theory | 50 (10.5 s) | 5 | 1.1–1.2 s |

## What the research route returned, per method

| Method | Result over the 20 seeds |
|---|---|
| Innovation (invention) | `research_question` 18, `partial` 2. 0 usable proposals; the 2 partial runs produced one broken proposal. The typed-fact extractor finds no edges in this prose. |
| Hypothesis generation | 3 cited "source prediction" options per seed. These are the useful part of the dossier. |
| Nammade comparison | 32 comparisons per seed (the scan cap). |
| Abductive bridge | `NO_GAP` for all 20. Its ontology covers only self-interacting dark matter. |
| Rule inference | `no_applicable_rule` for all 20. |

## Pairs where the dossier adds real evidence

| Frontier idea | Research-route option it surfaced | Use |
|---|---|---|
| Distribution shifts and misaligned low-loss regions may jointly drive grokking (2502.01774, 2610.00620). | "…we construct two synthetic datasets where distribution shifts between training and testing data can be precisely controlled to reproduce grokking…" (2502.01774) | An existing experimental setup for testing the joint claim: add the low-loss-misalignment measure from 2610.00620 to it. |
| Additional noise may reduce generalization error for diagonal linear networks through implicit bias (2402.08344, 2505.21423). | "This gap between implicit bias theory (which requires small initialization) and practice (where initialization is often not small but normalized)…" (2305.05448) | A confounder to control: initialization scale and normalization. |
| Investment may constrain AI applications through increased compute (2010.15581, 2402.08797). | "…increased importance of compute, data and AI talent would lower the KP [knowledge production] for non-elite universities." (2010.15581) | A measurable downstream outcome for the claim. |
| Experience may constrain integrated information through cause (2212.14787, 2412.10626). | "IIT is a hypothesis that consciousness can be explained in terms of integrated information." (1807.02103) | Context only; it restates IIT's premise. |

## Verdict

The chain is fast, and each idea gets cited context. A few seeds also surface a test design or a confounder. But
the research route does not deepen the Frontier hypothesis itself. Its options are chosen per term, not per
hypothesis, so unrelated seeds share options (the same 2010.15581 sentence appears for three compute seeds). Two of
its methods do not apply outside their original domain.

A dedicated deepening step would serve the goal better. For one selected Frontier hypothesis it would:
1. collect supporting and contradicting sentences for each link;
2. keep only the predictions that mention at least two of the hypothesis's anchors;
3. pull experimental setups that already measure one side;
4. produce a structured test plan with the variables to manipulate, measure and control.
