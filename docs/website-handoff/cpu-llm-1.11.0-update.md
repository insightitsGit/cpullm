# Website and whitepaper update: published cpu-llm 1.11.0

Requested by the product owner on November 3, 2026. This supplements the original
landing-page brief and supersedes its release/activation/publication wording.

## Approved identity and placement

Use **CPU LLM: Evidence-Based AI Engine**. Subtitle: **Answer questions from your
documents and explicit rules, with source evidence and CPU-first execution.**
Credit the whitepaper to **Amin Parva, Independent Engineer**. Do not use the
company as the author's affiliation or describe the product as a “local” engine.
Keep the product under **Research & Proof / Research Tools** on www.insightits.com.
Continue the existing site repository styles, instructions and deployment workflow.

## Release is published

PyPI: https://pypi.org/project/cpu-llm/1.11.0/

```shell
python -m pip install --upgrade "cpu-llm==1.11.0"
```

The official PyPI metadata was checked after the owner's upload: the wheel and
source archive SHA-256 values match the exact tested artifacts. See
`docs/releases/1.11.0-publication.json`. The earlier build validation's “no upload”
statement describes what the build task did, not current publication status.

Implementation/manual/release source commit: `75425fc`. Runtime feature commit:
`71d1301`. Source setup still requires PostgreSQL/pgvector, encoder assets and
ingested records. The trained projection is bundled; demo use needs no retraining.

## What changed for users

1. Reports, articles and design documents use one bounded evidence-backed
   workflow for topic, sections, coverage, budget, formats and continuation.
2. Explicit tone instructions are extracted before searching. The KB needs the
   topic facts, not a finished “friendly” response. Python style overrides prompt
   tone. Tone does not persist or infer the user's emotional state.
3. The tone node constructs new technical sentences from supported source
   predicates. Additive conjunctions, limited contractions and explicitly licensed
   same-subject pronouns are independently inverse-verified. Numbers, negation,
   qualifiers and original source proofs remain. The same lexicon ranking uses
   semantic license, intensity, tone affinity and genericness.
4. Ordinary document `reply.text` can publish verified derived prose. Original
   quotes/proofs and `rendered_response.canonical_text` remain. Single-fact tone
   retains the older companion-only behavior. Do not say all tone is API-only or
   that visible replies can never change.
5. Unrecognized/conditional/ambiguous records remain attributed quotations.
   Missing design sections are explicit. No invented architecture or padding.
6. Markdown/HTML reports, tables, bullets and numbered output use the shared
   document representation. Length is evidence-bounded, not an exact word-count
   promise. Continuation exposes page size/time and rechecks permissions.
7. Strict reports are quotation-only, even when tone is requested. No generated
   tone, learned decoder or inherited clinical/world-truth audit is permitted.

## Real example to put on the page

Prompt, with no Python style argument:

> Write a detailed article about Helios in a friendly tone.

Actual output excerpt from the fictional demo:

> Helios stores encrypted backups and uses PostgreSQL for metadata.
>
> It stores backup files in object storage and verifies backup checksums.
>
> It retains backups for 30 days and runs backups every night.
>
> Helios doesn't support automatic regional failover.

The original KB contains no “friendly” wording. All twelve source claims were
retained and passed the bounded inverse grammar. This is generated wording from
source facts, not an unrestricted language model or independently validated truth.
Show citations/source IDs in expandable evidence and label this a recorded
fictional demonstration. Do not turn it into a public patient-chat endpoint.

Full captured article/report/JSON:
`docs/examples/2026-11-03-prompt-tone/`. Runnable user-manual demonstration and
literal fallback: `examples/document_workflows/demo.py` and
`docs/examples/2026-11-03-manual-demo/`.

## Whitepaper upgrade

Create a new **1.11.0 edition** of the full HTML whitepaper and downloadable PDF.
Retain the historical 1.10.0 paper as that release's record; do not relabel it as
1.11.0 without changing its content. The prepared
`docs/whitepapers/cpu-llm-1.11.0-whitepaper-addendum.md` supplies publication-ready
replacement material to merge with the original implementation guide.

Update: release/install version; prompt processing; node triggers; document
planning/coverage; technical sentence generation; single-fact vs document reply
publication; Python/HTTP examples; strict behavior; budgets/continuation;
verification evidence and limitations. The API `ask` signature remains compatible;
HTTP supports tone in message text, not a new style body field.

Suggested new PDF asset:
`/assets/whitepapers/cpu-llm-1.11.0-whitepaper.pdf`. Update all whitepaper CTAs,
metadata and the HTML edition label. Use the existing PDF builder as a starting
point, but change its source/output paths, footer/version, author metadata and
all edition-specific references. Render and visually inspect every page before
publishing. Keep Amin Parva's independent author credit. Report whether the site
and the new PDF are actually deployed; a completed handoff is not publication.

## Sources the website agent must read

- `docs/document-generation-user-guide.md`: executable recipes and field meanings.
- `docs/document-generation-findings-spec.md` and `.json`: findings, implementation
  requirements and remaining gaps; prompt cases are regression tested.
- `docs/document-workflow-spec.md`: snapshot scope, sections, budgets and layouts.
- `docs/stylistic-generation-spec.md` and `.json`: fact vs document generation,
  lexicon/relationship restrictions, inverse grammar and strict precedence.
- `docs/library-consumer-guide.md`: constructor/ask/HTTP contracts.
- `docs/prompt-flag-map.md` and `.json`: actual control consumers.
- `docs/releases/1.11.0.md`, `1.11.0-artifacts.json`, and
  `1.11.0-build-validation.md`: exact release and clean-install validation.
- `docs/reviews/2026-11-03-document-workflows/`: original failures and replay.
- Existing healthcare/finance examples and claims register: retain their limits.

## Evidence and SEO

The installed 1.11.0 wheel passed clean-environment pip/dependency checks, all four
CLI help checks, real database friendly/strict/HTML/source-scope checks and 12/12
checks in each packaged healthcare and conversation demo. The release update
also passed 64 targeted source regressions. The earlier working-tree full run
passed 890, skipped 56 and retained three existing expected failures; do not call
it an installed-wheel full-suite run or add counts into an accuracy percentage.
The later precommit run passed 68 focused/live checks. No hosted-model comparison
or clinical signoff was added.

Retain inbound terms such as evidence-based AI engine, Python document question
answering, document question answering with citations, knowledge-base report
generation, evidence-backed article generation, CPU-first AI, source-grounded
responses and verified sentence generation. Explain each in visible examples;
these are intent hypotheses without measured traffic/keyword-volume claims.
Update index card, hero, install CTA, FAQs, social metadata and software version
structured data to 1.11.0. Preserve indexable full HTML, canonical links, sitemap
and appropriate internal Research & Proof links. Use no fake reviews or pricing.

Do not claim universal zero hallucinations, guaranteed factual/clinical accuracy,
FDA/HIPAA/SOC2 status, all six retrieval heads trained, superior hosted-LLM scores,
or measured energy/cost savings. Broader alias/semantic joins, typed factual
matching, arbitrary prose conflicts and novel architecture generation remain
bounded/unsupported. Keep that distinction visible alongside the new demo.

## Acceptance

Install links resolve to the published version; prompt/output examples match
saved records; new HTML/PDF content agrees with the specs; historical scores are
properly scoped; navigation/metadata/assets/links pass checks. Return preview or
live URLs, tests and screenshots, plus remaining limitations and actual deployment
status. Apply this update to the existing CPU LLM task rather than unrelated work.
