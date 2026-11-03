# CPU LLM: Evidence-Based AI Engine

## 1.11.0 whitepaper update material

**Author:** Amin Parva, Independent Engineer

**Release:** cpu-llm 1.11.0, published November 3, 2026.

This addendum supplies the new edition's material; it is not a complete replacement
PDF. Merge it into the full implementation whitepaper and developer guide,
preserving unaffected setup/API sections and correcting their version references.

### Separate facts from expression

The knowledge base supplies facts and source records. A user's request for a
friendly tone supplies a presentation preference. CPU LLM separates that explicit
preference from the topic before evidence selection; the source documents do not
need matching tone words or finished sentences. API style settings override prompt
tone. Strict evidence settings disable generated wording. The system does not
infer an emotional state or remember tone across requests.

### Evidence-backed document planning

Report, article and design-document requests select a shared plan for genre,
topic, sections, length and output format. Evidence comes from a bounded SQL
snapshot, constrained by caller source permissions and historical validity.
Selection uses declared lexical topic matching rather than an unrestricted graph
walk. The snapshot cap is 10,000 chunks and 8,000,000 source-text characters;
overflow fails without selecting an incomplete scan.

Section organization is deterministic and does not prove a source's architecture.
Design sections such as Requirements, Architecture, Interfaces and Validation
remain explicitly missing when no selected source supports them. The workflow
does not invent decisions or fill gaps merely to produce a polished document.

### New wording with independently checked meaning

The document tone path extends the existing `stylistic -> style_verify` output
graph with reviewed technical predicate constructions. The lexicon now contains
twelve constructions: ten for the original five factual relations and two for
technical document predicates. Eligibility and relationship exclusions precede
the semantic/intensity/tone/genericness ranking. Ranking scores are not confidence
that a source is true.

The generator can combine complete predicates about one subject with additive
conjunctions, use limited friendly contractions and use an explicitly licensed
same-subject pronoun. An independent inverse grammar recovers the original
predicates and verifies complete claim coverage and source fingerprints.
Numbers, negatives and qualifiers are retained. Unsupported or complex records
remain attributed source quotations, rather than being discarded or simplified.

For example, the fictional source statements “Helios stores encrypted backups.”
and “Helios uses PostgreSQL for metadata.” produce the new sentence:

> Helios stores encrypted backups and uses PostgreSQL for metadata.

The prompt is:

> Write a detailed article about Helios in a friendly tone.

Neither source contains the requested friendly style. The recorded twelve-fact
article/report retained every claim, including the negative failover statement.
This validates bounded construction behavior on those fixtures, not arbitrary
language generation or independent factual accuracy.

### Output and integration contract

For ordinary documents, `reply.text` can publish verified derived prose with
literal fallbacks. `document.sections[].prose` holds generated sentences and
their source IDs. `document.sections[].quotes` and `answer_evidence` retain the
original source text, offsets and chunk SHA-256 values.
`rendered_response.canonical_text` preserves the quotation-only view.
`stylistic` records actual node execution, status, selected construction, score
components, tone alignment and verification. The older single-fact path still
publishes a companion without replacing its canonical reply.

An HTTP message can contain the same explicit tone instruction; no new HTTP style
field is introduced. Strict reports remain quotation-only even when tone is
requested. No generated wording inherits a clinical or world-truth audit.

### Length, layouts and missing coverage

Standard, detailed and brief documents allow eight, sixteen and three atomic
source units, capped at twenty for explicit numeric requests. String tone profiles
use the document budget; explicit StyleOptions limits are honored without deleting
claims. Exact word/sentence counts are not guaranteed. Records and necessary
qualifiers are never clipped to pad or fit a response. Selected atomic text over
200,000 characters fails closed.

The same document representation renders to Markdown/HTML reports, tables,
bullets and numbered lists. Coverage includes missing sections, recognized
attribute conflicts, included records and further pages. Continuation preserves
page size, section outline and time validity while rechecking current permissions.
It is not an immutable signed database snapshot.

### Release verification and scope

The published wheel and source archive match the hashes of the tested artifacts.
A fresh Windows Python 3.12.10 environment installed the wheel without system
site packages, passed dependency checks and all four CLI help checks. Real
database queries verified friendly generation, strict bypass, HTML/lowercase
topic handling, literal conditional fallback and caller-source exclusions.
Packaged healthcare and conversation demos each passed 12/12 authored software
checks. Sixty-four targeted source regressions accompanied release preparation.

These checks do not establish clinical safety, authoritative source truth or
superiority to a hosted model. Earlier benchmark counts belong to their recorded
revisions and fixture sets. Typed object-category queries, general aliases/joins,
arbitrary prose conflict detection, general expressive writing and novel design
proposals remain explicit limitations.

Install the published version with `python -m pip install --upgrade "cpu-llm==1.11.0"`.
PostgreSQL/pgvector, encoder assets and ingested documents remain setup requirements.
The trained projection is bundled; the demonstration does not require retraining.

Primary release: https://pypi.org/project/cpu-llm/1.11.0/

Implementation and manuals: https://github.com/insightitsGit/cpullm/tree/75425fc
