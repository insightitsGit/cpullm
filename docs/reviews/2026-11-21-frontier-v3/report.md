# Frontier with specificity ranking and the automatic leading-entry check

Date: 2026-11-21. Code: `feature/frontier-node` at `3c6bd25`. The knowledge bases are the same and were not
re-ingested. Each prompt ran three times with identical output; none hit a budget. The first prompt per area takes
25–40 s (it parses the corpus); later prompts take 5–9 s, of which about 3 s is the check on five entries.

## What changed in the ranking

The leading entries move toward specific terms. For example, the grokking list now opens with misaligned low-loss
regions, particular loss landscapes and intrinsic task symmetries. The v2 list opened with "grokking may undermine
traditional machine learning theory". Entries built on very common terms ("brain", "compute") lose relevance.

Source support is still the first ranking key, so a generic entry with higher support can still lead. "brain and
wave may jointly drive consciousness" stays first for IIT and GWT with support 0.96.

## What the check found (5 entries × 14 prompts = 70 checks)

| Verdict | Count |
|---|---|
| all links supported | 65 |
| partly supported (one link missing or weak) | 4 |
| contested | 1 |

- **Contested.** "Low weight decay may increase generalization through the grokking phase." The first link is
  contradicted by arXiv 2408.08944: "increasing weight decay directly leads to an emergent phase and reduces the
  delayed generalization gap". The reply flags it with that quote.
- **Missing links.** Three benign-overfitting entries joined "harmful overfitting" and "benign overfitting" through
  their shared head noun; Deepen found no source for the link to benign overfitting. One IIT entry has only a weak
  first link.

**How to read "supported".** A Frontier entry is built from source edges, so each of its links has at least its
own premise. "All links supported" is therefore close to guaranteed for Frontier's entries and says little on its
own. The informative signals are **contested** (a source states the opposite or negates the link) and
**missing/weak** (a link rests on a bridge that no source states).

## Bug found and fixed during this evaluation

The first version of the check reused Frontier's similarity lookup, which covers only the topic-scoped terms. It
rejected contrary edges outside that scope, and in the first run 69 of 70 checks reported "all links supported",
including the weight-decay entry above. The check now encodes the bridge terms of the whole graph once. A
regression test (`test_leading_check_sees_contrary_evidence_outside_the_topic_scope`) fails on the previous code.
