# Response cases and evidence-join contract

Implementation review, 2026-10-25. This checklist covers the scenarios discussed
during development. A passing fixture establishes that example, not arbitrary
language understanding or real-world truth of a supplied source.

## What the SQL inner-join analogy means

The stored fact table contains a subject, relation, object, source ID, and source
sentence. Production answer selection performs a bounded evidence join in Python
over those facts. It is not a natural-language-to-SQL engine and does not join
words merely because their embedding coordinates are close.

For fictional example data:

- Membership: "The fictional lobster is a fictional crustacean."
- Applicable rule: "Every fictional crustacean lives for 12 years."
- Question: "How long does the fictional lobster live?"
- Result: cite both premises. The rule's class must match the membership's class,
  optionally through explicitly supported aliases. Keep "up to", units, and other
  supported qualifiers. Do not manufacture a species-specific statistic.

`tests/test_join_contract.py` independently executes an actual SQLite `INNER JOIN`
on stored fixture facts and compares its premises with production selection for
lifespan, location, color, and possession. `tests/test_join_pipeline.py` exercises
the full Appliance, real encoder, and PostgreSQL when `CPU_LLM_LIVE_TESTS=1`.
Only run that opt-in suite against a disposable database.

Alias resolution permits at most two identity hops, independently of source row
order. Identity premises appear in `supporting_evidence`; selected answer and
universal-membership premises appear in `answer_evidence`. An alias does not make
two different members of the same class identical. Class aliases used by a join
retain their source premise. A direct color/lifespan value cannot suppress a
conflicting applicable universal rule.

## Implemented response cases

1. **Definition/type.** Select a supported definition or taxonomic source. A
   common-name binding that is absent from a shortened realization can require
   quoting the original source instead of returning an audited shortened answer.
   Covered by `test_prompt_intent.py`, `test_answerability.py`, and live pipeline tests.
2. **Direct attributes.** Lifespan, geographic location, color, and possession
   select the requested entity and relation. A different entity's fact cannot
   substitute. Covered by `test_prompt_intent.py` and `test_attribute_search.py`.
   Older direct-action location forms also accept supported spatial prepositions
   such as on/above/under; `test_response_cases.py` covers positive and negative cases.
3. **Equivalent wording.** The packaged expressions can route "Where would I
   encounter X?" to geographic retrieval. This does not guarantee an encounter.
   Antonyms and known ambiguous senses do not become synonyms. Covered by
   `test_query_dictionary.py`, including combined retrieval and reply tests.
4. **Missing initial retrieval.** Repair searches the subject and verified classes,
   at most three queries. A newly found membership can re-plan the remaining
   budget. Missing evidence stays missing. Covered by `test_attribute_search.py`.
5. **Applicable fact join.** One type-membership hop plus an explicit All/Every
   rule can support the four attributes. Both premises and any class-alias bridge
   remain attributable. Covered by the SQL-oracle and live join tests.
6. **Rejected joins.** Some/most/unquantified class descriptions, averages,
   conditional/modal claims, sibling attributes, reversed membership, missing
   premises, and unrelated classes do not establish an individual fact. General
   transitive class inheritance is not enabled. Covered by `test_join_contract.py`.
7. **Conflict.** Incompatible supported color/lifespan strings, including a direct
   fact versus an applicable universal rule, return conflicting evidence. General
   reconciliation of ranges, units, times, and exceptions remains open.
8. **References.** Resolve a supported reference with the optional backend or ask
   for a name. Preserve the original input. A single confirmation cannot merge
   a person and an object in "Where did he put it?"; request an explicit restatement.
   Covered by `test_references.py`, boundary regressions, and live confirmation tests.
9. **Subjective ranking.** "Which lobster is best?" asks for criteria, then supporting
   comparison evidence. User-supplied sources are attributed and unverified.
   Reference and typo rewrites update both the query and ranking topic. Covered by
   `test_clarification.py`, `test_design_connections.py`, and live conversation tests.
10. **Causes.** Explicit directed cause/because clauses can answer recognized forms.
    Do not reverse causes or infer arbitrary causal chains. Covered by
    `test_prompt_intent.py` and `test_join_contract.py`.
11. **Access, history, lifecycle.** Every join premise must be authorized. Historical
    searches avoid current-only graph/tag/article expansion. Replacement/deletion
    remove current fact premises; correction validity must follow its supplied
    timestamp, including after opening a new index. Live join tests cover these
    cases; this is still not an atomic snapshot across all stores.
12. **Execution and delivery.** Errors, partial execution, and delivery holds cannot
    become ranking answers. Cancellation clears both conversation stores.
    Evidence/status metadata must agree with the displayed result. Covered by
    `test_design_connections.py` and reply/access review tests.
13. **Other established producers.** Event roles, policy permission/prohibition,
    bounded arithmetic, finance validation, and copied-sentence layouts retain
    separate contracts. Their test files and consumer guide define their scope;
    a passing fact join does not validate these producers automatically.

## Cases still missing or only partially supported

- **Edibility versus permission versus personal safety:** resolving "it" in
  "Can I eat it?" identifies an entity, not which of these intentions was meant.
  The existing policy reader must not be advertised as a food-safety assessment.
  A general intent-clarification policy for this remains open.
- **References inside documents:** connecting "it" or descriptions in source
  paragraphs to facts is separate from conversation-prompt reference resolution.
- **General comparisons and recommendations:** arbitrary numerical comparisons,
  preference tradeoffs, tie handling, and a defensible winner require more than
  the current explicit source-ranking quote.
- **Negation, quantifiers, and exceptions:** arbitrary negative questions, "not all",
  defaults with exceptions, and multi-clause scope are not general supported logic.
- **Temporal applicability and numerical reconciliation:** class changes over time,
  unit conversion, compatible overlapping ranges, and differently dated assertions
  need explicit semantics. String-level conflict detection is conservative.
- **General inference and predictions:** more than the licensed join, arbitrary
  taxonomy chains, causal chaining, hypothetical worlds, and forecasts remain open.
- **Broad language and construction:** unrestricted paraphrases, unknown word senses,
  multilingual questions, and general prose generation remain open.
- **Operational proof:** Fastcoref model accuracy, six-channel calibration/training,
  realistic scale/concurrency, durable sessions, and cross-store atomicity are not
  established by these regression cases.

Keep these items in the [support backlog](intent-support-backlog.md). Expand one
case with agreed semantics, positive and negative examples, and measured evidence
before marking it supported.
