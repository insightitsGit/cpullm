# Deepen research review (a09952e): before/after check

Date: 2026-11-22. Compares the code before `a09952e` (at `d2ec9ca`) with `a09952e`, on the three evaluation
knowledge bases already ingested (AI bottlenecks, deep-learning generalization, consciousness). Same snapshot,
parser (`en_core_web_lg`) and encoder; nothing was re-ingested.

## Results

| Check | Before | After |
|---|---|---|
| Full test suite | 1,312 passed, 3 failed | **1,343 passed**, the same 3 failed (they predate both commits) |
| Frontier, 15 prompts × 3 runs | — | candidate IDs, texts, scores and order **identical** on all 15 prompts |
| Leading-entry checks (70) | 65 supported, 4 partly supported, 1 contested | identical |
| Deepen verdicts, 7 hypotheses | — | **identical**, including both contested cases |

Breadth is unchanged: the commit annotates hypotheses, it does not change which hypotheses are proposed. The
hypotheses are therefore exactly as novel as before. What changed is the quality of the review.

## What the review adds (7 hypotheses, `deepen={"hypothesis": ..., "novelty": True}`)

| Hypothesis | Composition | Bridge warnings | Novelty review |
|---|---|---|---|
| Computing resources and tens of thousands of GPUs jointly constrain training large dense models | requires review | 1: "training these large dense models" vs "training state-of-the-art models" | no overlap in the knowledge base |
| Inadequate access reduces the performance gap through certain groups' ability | requires review | 1: "certain groups ability" vs "ability of large compute investors" | no overlap |
| Attention and operational criteria jointly constrain IIT | requires review | 1: "Integrated Information Theory" vs "differentiating theories" | no overlap |
| Experience constrains integrated information through cause | insufficient evidence | 1: "cause" vs "intrinsic cause" | **potential overlap**: arXiv 2510.04084, IIT "identifying conscious experience with integrated information structure" |
| Additional noise reduces generalization error through implicit bias | insufficient evidence | 0 | no overlap |
| Distribution shifts and low-loss misalignment jointly drive grokking | requires review | 0 | no overlap |
| Low weight decay increases generalization through the grokking phase | **incompatible direction** | 3, including "Low weight decay" vs "increasing weight decay" | no overlap |

Notes on these results:
- Every test plan reports `readiness: needs_input`, with 11–13 `research_actions` (for example "Supply intervention
  levels for computing resources").
- Every novelty review reports `scientific_novelty: not_established`.

## Assessment

- **Improvements.**
  - The bridge warnings catch the meaning-slips previously found only by manual review, including the root of the
    contested weight-decay case.
  - "All links supported", which is near-automatic for Frontier's own entries, is no longer presented as if the
    combination held: 4 of 5 such entries are marked for composition review.
  - The novelty review correctly identified one hypothesis that restates an existing source.
- **Unchanged limits.**
  - Candidate controls are all classified as `outcome_predictor`; no shared causes were found in these corpora.
  - Some control terms are still fragments ("correlation", "neural behavioral co").
  - Plans stay at `needs_input` until a person supplies definitions and levels.
  - The novelty review covers the knowledge base only; no external literature reviewer was configured.

Raw Deepen results: `deepen/*.json`. Script: `scripts/deepen_run.py`. Frontier comparison: re-run of
`../2026-11-21-frontier-v3` prompts, compared on hypothesis IDs, texts, scores and order.
