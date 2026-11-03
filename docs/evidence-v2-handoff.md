# Five-workstream delivery and remaining external gate

Runtime revision: `e6301f3`. Final complete suite: 854 passed, 2 skipped,
3 expected failures. The implementation and benchmark datasets/runners are
committed; saved reports retain both initial and final runs.

1. **Broader strict coverage delivered within explicit contracts.** Batches,
   field lists, unique within-batch references, direct-attribute overviews,
   one-hop membership/universal joins, exact arithmetic and supplied-limit
   comparisons. Unknown or ambiguous requests remain nonanswers. There is no
   claim of unrestricted natural-language coverage or cross-turn strict memory.
2. **Broader conflict checks delivered within recognized grammars.** Canonical,
   possessive, has and for forms share one value/conflict check; exact scalar
   unit equivalence avoids false differences. Negative, uncertain, direct and
   joined evidence are checked together. Arbitrary prose contradictions and
   unrestricted semantic equivalence remain unsupported.
3. **Healthcare engineering acceptance delivered; clinical approval pending.**
   Fictional records exercise proof retention, numeric fidelity, missing-data
   abstention, conditional advice refusal and context boundaries. Clinical source
   truth, external clinical gold, independent clinical sign-off and validated
   treatment/diagnostic rules cannot be produced by a code test. The clinical
   release gate explicitly remains false. Requirements are in
   [healthcare acceptance](healthcare-evidence-acceptance.md).
4. **Confirmed pipeline gaps fixed and replayed.** Structured finance reaches
   its specialist without generic pronoun/spelling corruption; ratio presentation
   retains deciding digits; rules-mode conversational color normalization binds
   the requested relation; inline supplied numeric context reaches math without
   requiring manual Context/Questions formatting. The unchanged original domain
   cases now pass 24/24, including all 12 finance cases.
5. **Local comparison completed as chosen by the user.** Strict evidence passes
   42/42 authored cases; the simple independent literal/calculator baseline
   passes 25/42. This is not a blind benchmark or hosted-model comparison. The
   hosted arm is explicitly unrun by agreement, not silently counted as a pass.

Read [the strict v2 spec](strict-evidence-spec.md),
[the software validation record](reviews/2026-11-02/evidence-v2-validation.md),
[the evidence report](benchmarks/2026-11-02-evidence-v2/REPORT.md), and
[the domain replay](benchmarks/2026-11-02-domain-replay-v2/REPORT.md).

The original artifacts are immutable. Any later parser, rule, scorer or gold
change needs a new recorded revision and output directory. Continue to report
answerable coverage and nonanswer correctness separately. Do not turn these
acceptance scores into claims of 100% accuracy, clinical safety or universal
zero hallucination.

The three pre-existing expected failures are ordinary resonance sense-grouping
limitations (`tests/test_resonance_groups.py`), not repaired by strict-mode SQL
lookup. Two optional trained-extractor tests skip because their checkpoints are
absent. These counts are retained rather than described as universal coverage.
