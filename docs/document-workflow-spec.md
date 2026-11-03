# Evidence-backed document workflow

Implemented contract: `document-plan-v1` / `evidence-document-v1`.

## Activation and placement

Explicit commands such as `Write a detailed report about Helios`, `Write an
article about Helios`, and `Write a design document about Helios` select one
document workflow. A detailed overview requested as a report uses the same
plan. Supported long whole-topic explanations/overviews also use this path;
specific factual slots and compound factual questions retain normal judgment.
Negated commands and ordinary questions containing format words do not activate it.

Caller validation and the raw-prompt guard precede evidence access. A document
does not execute payment, hypothesis, causal or other specialist proposals;
submit those separately. The ordinary graph and its optional generation stages
are not used for document bodies. The flag registry records `request.document`.

## Evidence acquisition and coverage

The workflow uses the existing SQL snapshot reader with caller source scope and
historical validity. It scans at most 10,000 chunks / 8,000,000 text characters;
overflow fails without selecting an incomplete document. This is a bounded,
authorized snapshot strategy, not a top-k similarity search or unrestricted
graph walk. `document.retrieval` records this distinction even with `deep=True`.

All meaningful topic tokens must occur in an included chunk. This lexical
contract does not infer aliases, subclass membership or semantically related
topics. Complete source chunks are deduplicated and organized by deterministic
section cues. The underlying text is quoted, not converted into a potentially
lossy proposition or invented design decision. Numbers, negatives, conditions
and qualifications remain in each atomic quotation.

Reports have Overview, Operations and Limitations sections. Articles have
Overview, Details and Limitations. Design documents add Requirements,
Architecture, Interfaces and Validation. An explicit `, including Architecture,
Interfaces and Costs` outline selects those sections plus Overview. Section
assignment is organizational lexical matching, not proof of architectural
meaning or completeness. Missing sections explicitly say they are not stated.

Every quote retains document ID, original text, character offsets and the stored
chunk SHA-256. Recognized literal attribute conflicts are flagged without
choosing an authoritative value. Arbitrary prose conflicts are not universally
detected. Source truth and clinical correctness are never certified.

## Length and continuation

Standard documents allow eight atomic quote units, detailed documents sixteen,
brief documents three, and explicit numeric requests at most twenty. Sentence,
item and word requests guide atomic quote budgets; they are not hard sentence
or word guarantees. Full records, qualifiers and citations are never clipped
to meet an exact count. Coverage exposes requested limits, actual rendered word
count and word-budget overruns. Selected quotation text above 200,000 characters
fails closed rather than returning a truncated record.

Sections are interleaved before pagination to avoid starving later sections.
`has_more`, `next_page` and `continuation_prompt` disclose remaining evidence.
The continuation retains topic, quote-unit page size and the snapshot's `as of`
timestamp. The reader reapplies the caller's current permissions; no continuation
can grant access. The caller must restate/use the generated continuation request;
bare “continue” is not a new cross-turn document-state protocol. History can be
affected by later backdated corrections/deletions; timestamps are not immutable
signed database snapshots.

## Results and formats

`document.sections[].quotes` and `document.coverage` are the canonical document
representation. Markdown/HTML reports, tables, bullets and numbered lists render
that same representation, without selecting different facts. HTML escapes all
source values; Markdown escapes source markup. `answer` remains null and
`audit_passed` remains false. Source quotations are not inherited clinical audits.

`evidence_quote` means selected source quotes cover the declared section slots
on that page without detected attribute conflict or additional pages. `partial`
marks missing sections, conflicts, additional pages or a later page;
`insufficient_evidence` marks no selected records or a scan/output limit.
Neither status proves comprehensive semantic coverage of a whole topic.

Strict evidence supports explicit document genres through this separate
quotation-only contract (`document-quotes-v1`). It bypasses learned generation
and the tone node. Ordinary requests may select tone through an explicit prompt
directive or `style=`. The document tone graph constructs new prose from a
reviewed finite-predicate subset, inverse-verifies complete predicates/numbers/
negation/qualifiers and uses the same lexicon ranking as the original tone node.
Unrecognized, conditional, ambiguous or complex atomic chunks remain labeled
source quotations. Tone words are presentation instructions, not evidence terms.
`document.sections[].prose` identifies derived sentences with original source IDs;
all original `quotes` and `answer_evidence` remain, and `rendered_response.canonical_text`
retains the quotation view. The ordinary document body publishes the verified
derivation with any literal fallbacks; ordinary single-fact tone remains a companion.
String profiles use the document's budget; explicit StyleOptions budgets are
honored and never permit silent claim deletion. Friendly contractions and
same-subject predicate conjunctions are allowed; `It` requires an explicit
nonhuman class in the source and a same-section antecedent. Unsupported expressive
tones expose neutral fallback. No proof establishes real-world source truth.

## Verification and remaining boundaries

Unit regressions cover genre/depth recognition, technical verb preservation,
qualifiers/numbers, missing sections, outlines, source hashes, conflict flags,
format parity/escaping, atomic budgets, pagination, guard/scope/time and strict
precedence. A real PostgreSQL test verifies scoped document creation, exclusion
of private records, historical empty results, strict/HTML evidence parity and
nonoverlapping continuation. The original ten-request probe is replayed against
the same fictional corpus in the saved review directory.

This addresses document coverage without claiming arbitrary prose generation.
Typed questions such as “What database does Helios use?” remain with the existing
factual matcher; a source that says “Helios uses PostgreSQL” is preserved in
documents but does not add a new general object-category inference engine.
Exact-topic lexical matching, cue-based section organization, broader semantic
joins and novel proposed architectures remain explicit boundaries.
