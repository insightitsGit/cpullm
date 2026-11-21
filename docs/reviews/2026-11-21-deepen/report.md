# Deepen on selected Frontier hypotheses

Date: 2026-11-21. Inputs: hypothesis objects from the v2 Frontier runs (`../2026-11-21-frontier-v2/`). Script:
`scripts/deepen_run.py`. Results: one JSON per hypothesis. Knowledge bases were not re-ingested. Each run took
1.7–14.5 s; the first run in each process includes the corpus parse.

| Knowledge base | Frontier hypothesis | Link statuses | Verdict | Predictions / setups |
|---|---|---|---|---|
| DL generalization | Distribution shifts and misaligned low-loss regions may jointly drive grokking. | supported, supported | all links supported | 5 / 6 |
| DL generalization | Low weight decay may increase generalization through the grokking phase. | **contested**, supported | **contested** | 1 / 6 |
| DL generalization | Additional noise may reduce generalization error for diagonal linear networks through implicit bias. | supported, **counter only** | **contested** | 0 / 5 |
| AI bottlenecks | Inadequate access may reduce the performance gap through the ability of large compute investors. | supported, supported | all links supported | 0 / 2 |
| AI bottlenecks | Computing resources and tens of thousands of GPUs may jointly constrain training large dense models. | supported, supported | all links supported | 0 / 0 |
| Consciousness | Attention and operational criteria may jointly constrain integrated information theory. | supported, supported | all links supported | 0 / 3 |
| Consciousness | Experience may constrain integrated information through cause. | weak, supported | partly supported | 2 / 6 |

## What Deepen caught

- **Weight decay (contested).** Frontier chained "low weight decay delays the emergence phase" (2408.08944) with a
  phase-diagram sentence (2205.10343). Deepen found that 2408.08944 also states that *increasing* weight decay leads
  to the emergent phase, which reverses the first link. The hypothesis as Frontier worded it is likely wrong in
  direction.
- **Implicit bias (contested).** The second link rests on 2505.21423, which says "*neither* implicit bias alone
  minimizes the generalization error". Read correctly, that counts against the link. The first version of the
  parser missed the negation; the fix is part of this branch.
- **Grokking (supported, with a test design).**
  - Both links have direct support, and five predictions name both sides.
  - The setups include "we construct two synthetic datasets where distribution shifts … can be precisely
    controlled to reproduce grokking" (2502.01774).
  - The confounders to control include intrinsic task symmetries, larger datasets and the difficulty of
    optimization.
  - The test plan is a 2×2 factorial: vary distribution shift and low-loss misalignment, and measure grokking.

## Limits

- **"Supported" means each link has at least one source edge**, not that the combined hypothesis is true.
- **Two links rest on a single sentence each.** Corroboration across papers is rare in these corpora.
- **Some anchors are still loose** ("certain groups ability", "neural behavioral co"), inherited from Frontier's
  extraction.
- **Confounders are taken as stated.** They may themselves be weak claims.
