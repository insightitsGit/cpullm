# PrismLexicon pilot evaluation

The hand-reviewed regression set in `tests/test_prismlexicon.py` covers
eight contextual examples across two senses of bright, geographic and
non-geographic uses of reside, three verb forms, and a temporal expression.
Six expected edits and two expected abstentions matched the annotated
outputs. Protection tests cover explicit locks, quote and citation
preservation, numbers, units, dates, URLs, code, and modality. The delivery
test checks preservation of evidence and research output.

A local Python microbenchmark cycled seven short synthetic answers for
10,000 calls per requested level. Approximate p50/p95 latency in microseconds
was 0.5/4.6 for off, 4.4/8.3 for A2, 4.6/9.6 for B1, and 0.9/1.0 for C2.
A separate 1,000-call tracemalloc loop observed less than 4 KiB peak tracked
allocation for each policy. This measures the adapter in isolation.

Release decision: keep the feature experimental and disabled by default.
This fixture has zero observed semantic regressions. It is too small to
estimate production substitution precision. CEFR-fit coverage is unmeasured
because the rule data carries no independently sourced CEFR ratings. A wider
human-reviewed release gate and live end-to-end evaluation remain open.

The final focused run passed 102 tests covering PrismLexicon, invention,
Nammade, output rendering and access. The offline full-suite attempt was
stopped after it stopped making progress. Two cycle-document tests had
already failed because their snapshot mock was called twice. Both failures
were reproduced from a clean archive of the pre-change HEAD.

## Recorded level comparison

The same synthetic answer was passed to `adapt_output` for all eight settings.

**Original display text (`off`, B2, C1, C2)**

> The researchers resided in Oslo prior to the study. A bright light appeared. The effect may recur. The source states: "A bright light appeared after a 10 mg dose." [study-p0001]

**Adapted display text (`auto`, A1, A2, B1)**

> The researchers lived in Oslo before the study. A strong light appeared. The effect may recur. The source states: "A bright light appeared after a 10 mg dose." [study-p0001]

Each active setting applied three replacements. The test checked that the
quoted text, `10 mg` dose, citation and “may recur” stayed identical. This
exercise calls the adapter directly with synthetic text.
