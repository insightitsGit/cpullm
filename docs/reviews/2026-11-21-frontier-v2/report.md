# Frontier before and after the parser, encoder and spread improvements

Date: 2026-11-21. Code at `ef79462` (`feature/frontier-node`).

The knowledge bases are the same as in the first runs and were not re-ingested. "Before" is the regex reader with
head-noun bridges and no spread: the reviews in `2026-11-21-frontier*`. "After" uses:
- the `en_core_web_lg` dependency parser;
- the encoder bridge check (cosine ≥ 0.6);
- the anchor spread;
- the term-hygiene rules;
- the parse cache;
- a 60 s budget.

Every "after" prompt ran three times with identical output and none hit a budget. The first prompt in each area
takes about 30–38 s because it parses the corpus; later prompts take 1–4 s.

| Area | Prompt | Before | After |
|---|---|---|---|
| AI bottlenecks | AI bottlenecks | 19 | 50 |
| | AI energy bottlenecks | 23 | 50 |
| | memory bandwidth bottlenecks | 0 | 7 (shortage) |
| | training data supply | 50 | 50 |
| | AI compute cost | 50 | 50 |
| DL generalization | deep learning generalization | 50 | 50 |
| | generalization of overparameterized networks | 50 | 50 |
| | benign overfitting | 7 | 7 |
| | grokking | 50 | 50 |
| | implicit bias of gradient descent | 50 | 50 |
| Consciousness | hard problem of consciousness | 12 | 33 |
| | phenomenal consciousness | 50 | 7 (shortage) |
| | integrated information theory | 50 | 50 |
| | global workspace theory | 50 | 50 |
| | illusionism | 0 | 0 |

## What improved

- **Anchors are mostly real noun phrases.** For example, "additional noise may reduce generalization error for
  diagonal linear networks through implicit bias", "intrinsic dimension may constrain learning performance through
  learning rate", "low weight decay may increase generalization through the grokking phase", "inadequate access may
  reduce the performance gap through the ability of large compute investors".
- **Fewer false bridges.** The encoder rejects head-noun links whose terms differ in meaning, and the earlier
  "Japan's investment" reading is gone.
- **Recall where the regex reader failed.** The memory and hard-problem prompts now produce entries.

## What did not improve, or got worse

- **Phenomenal consciousness fell from 50 to 7.** The parser is stricter, and most of the earlier 50 were
  fragments.
- **Generic hubs still lead several lists.** "brain", "compute", "training" and "access" link many entries. The
  spread moves repeats down but cannot make the leading entries specific.
- **ResMem still appears 3 times** in the leading entries of the two broad generalization prompts. That is the
  spread limit working as designed.
- **Some anchors are still weak:** "behavior", "P for hypotheses", "wave", "neural behavioral co".
- **Support scores barely discriminate.** Most edges rest on one sentence, so source support is 0.80 for most
  entries.

## Verdict

The output is cleaner and more often readable as a research idea. It is still a candidate generator that needs a
human to choose among its entries. The next gains would come from:
1. penalizing generic hub terms by their document frequency in the relevance score;
2. merging paraphrased edges, so that corroboration can raise source support;
3. a reader for definitional and identity prose, for philosophy.
