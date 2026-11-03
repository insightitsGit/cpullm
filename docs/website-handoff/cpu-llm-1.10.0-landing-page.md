# CPU LLM landing page implementation handoff

## Request and deliverables

The product owner requests a cpu-llm landing page on **www.insightits.com**, under
**Research & Proof**, with a downloadable whitepaper and developer guidance for
nodes/APIs. This is inbound SEO for developers evaluating local document QA,
not a paid product-shop SKU or a claim of clinically certified AI.

Create the page in the existing website repository using its established styles,
routes, authorization/deployment workflow and current repository instructions.
This handoff does not move or restart a project checkout. It supplies new work
for the website agent; do not resume unrelated payment/resume work for this task.

Deliver:

1. A server-rendered/indexable product/research landing page.
2. A Research Tools index card and appropriate Research & Proof navigation links.
3. A readable full HTML whitepaper page plus a public downloadable PDF.
4. Working PyPI/GitHub/demo/evidence links, metadata and honest structured data.
5. Tests, screenshots/preview, link/indexability checks and a completion report.
   Follow existing deployment rules and distinguish implemented from published.

## Files to consume

Shared local checkout: `C:\code\cpullm`.

- `docs/whitepapers/cpu-llm-1.10.0-whitepaper.md`: canonical full text.
- `docs/whitepapers/cpu-llm-1.10.0-whitepaper.pdf`: verified publication PDF.
- `docs/whitepapers/cpu-llm-1.10.0-api-reference.json`: extracted signatures/nodes.
- `docs/website-handoff/cpu-llm-seo-plan.json`: page metadata, intent clusters,
  source observations, internal link candidates and event names.
- `docs/website-handoff/cpu-llm-claims-register.json`: approved claims, evidence
  revisions and mandatory limitations.
- `docs/releases/1.10.0-build-validation.md`: final release verification scope.
- `examples/healthcare/sample-run/README.md`: actual fictional sample chat.
- `docs/examples/2026-11-02-tone-chat/TRANSCRIPT.md`: actual tone outputs/limits.
- `docs/examples/2026-11-02-conversation/TRANSCRIPT.md`: actual basic chat/routing.

Copy required publication assets into the website's normal public asset tree;
do not publish `file://`, local drive paths, build logs, credentials or private
patient data. Versioned GitHub links below are suitable evidence links.

## Verified placement and proposed URLs

The public site has `https://www.insightits.com/research-tools/`, labeled
"Insight ITS · Research & Proof". It already lists research pages including
ChorusFace, PrismSQL and financial tools. Reuse this section and its page
conventions rather than adding cpu-llm to the paid shop.

Proposed landing canonical: `https://www.insightits.com/research-tools/cpu-llm`.
Proposed full guide: `https://www.insightits.com/research-tools/cpu-llm/whitepaper`.
Proposed PDF: `/assets/whitepapers/cpu-llm-1.10.0-whitepaper.pdf`.
Check existing routes and normalize trailing slashes using site conventions.
These are proposed routes, not a claim they already exist.

Use a PDF HTTP `Link: <HTML-whitepaper-URL>; rel="canonical"` only when that HTML
page contains the matching full paper; do not point a full technical PDF's
canonical to an unrelated short summary. Make the PDF accessible without an
email wall. Keep the landing page and full guide separately self-canonical with
distinct titles and purposes.

## Positioning and search intent

Primary audience: Python/application developers and engineering evaluators
looking for local document question answering, self-hosted document search,
RAG-style source retrieval, and inspectable calculations or refusals.

Primary phrase hypothesis: **local document question answering**.
Supporting phrases: **CPU document QA**, **Python document QA library**,
**document question answering with citations**, **self-hosted document search**,
**local RAG Python**, **strict evidence mode**, **financial document validation**.
Developer-specific long tails: **healthcare document QA with source evidence**,
**pharmacy label lookup demo**, **exact financial calculations Python**,
**PostgreSQL pgvector document questions**, and **source-grounded AI responses**.

These are qualitative intent hypotheses informed by observed search vocabulary
and primary documentation, not Keyword Planner/Search Console measurements.
No search volume, keyword difficulty, ranking guarantee or conversion forecast
has been measured. Validate actual demand in Search Console after launch.

Use these terms naturally in descriptive titles, headings, examples, anchors and
the developer guide. Do not build near-duplicate doorway pages for every phrase.
"Local RAG" needs a clear scope explanation: strict selection is bounded SQL
evidence matching, not a bundled general-purpose local generative LLM.

## Metadata and proposed opening copy

Title: **CPU LLM: Local Document QA with Citations | Insight ITS**

Meta description: **Explore cpu-llm, a local Python library for document questions,
source evidence and exact checks. See fictional healthcare demos, APIs and limits.**

Eyebrow: **Research & Proof · Open-source Python library · Version 1.10.0**

H1: **CPU LLM for local document question answering**

Hero copy:

> Build supported document lookups and explicit rule checks into your Python
> application. cpu-llm combines CPU-first retrieval, source evidence, bounded
> calculations and clear nonanswers. Inspect the data and execution contract
> behind a response instead of relying only on its wording.

Primary CTA: **Install from PyPI** → `https://pypi.org/project/cpu-llm/1.10.0/`.
Secondary CTAs: **Read the whitepaper**, **See the healthcare sample chat**,
**Inspect the source**. Show `python -m pip install "cpu-llm==1.10.0"` with copy
interaction and text fallback. Do not add mandatory signup or checkout steps.

One-sentence boundary near the hero:

> A bounded document-and-rule engine, with explicit evidence and limits.
> It is not a clinical decision system or a guarantee that source data are true.

## Landing page content sequence

### What developers can build

Use short paragraphs for document/manual lookup, fictional healthcare/label
evaluation, exact supplied financial checks and controlled response presentation.
Avoid implying that generic clinical diagnosis or full financial legal reasoning
is implemented. Link to the fuller APIs rather than hiding setup requirements.

### Three paths with different contracts

1. **Strict evidence:** recognized source facts, quoted evidence chains, bounded
   arithmetic or nonanswers. FLAN-T5/other learned answer generation is bypassed.
2. **Ordinary graph:** supported retrieval, planning, summaries/frames and selected
   math/finance producers. Optional learned fallback can exist outside strict mode.
3. **Conversation and tone:** original built-in social replies; opt-in factual
   tone companions for five supported relations. Tone does not add missing facts.

Clarify that six retrieval channels are not ten output tone preferences. The
shipped learned projection enables dense and identity heads; do not claim all
six learned heads are trained. Page diagram should show decisions and proof
boundaries, not an invented transformer/autoregressive decoder diagram.

### Show actual fictional healthcare exchanges

Label the panel **Recorded fictional demo output**, not a live clinical chatbot.
Display source labels, status and limitations alongside the readable answer.

> User: What is the strength of Fictional Luma?
>
> Source quotations (not clinically validated):
> [demo-label-luma-p0001] The strength of Fictional Luma is 0.75 mg.
> [demo-secondary-luma-p0001] Fictional Luma's strength is 750 mcg.
>
> Status: evidence_quote.

Then show the actual nonanswer example:

> User: Which antibiotic should Case Birch receive?
>
> Unsupported strict request; use explicit named attribute questions.
>
> Status: unsupported.

Link the full 12-question transcript rather than showing only positive lookups.
No form should encourage public visitors to submit patient-identifiable data.
If a static example is used, clearly label it recorded; do not fabricate live UI.

### Show numerical presentation without hiding the boundary

Use the supplied LedgerCovenant example from the paper. Under its declared
six-place half-up decision policy, numerator 9000001 / denominator 2000000 is
stored as 4.500001 against an lte threshold 4.500000. Quote the actual prefix:

> LedgerCovenant: BREACH. The computed value is 4.500001x and the test is lte
> 4.500000x.

Label it an arithmetic/precedence component result, not authentication of the
certificate, a legal default finding or an autonomous financial action.

### Reproduce before adopting

```shell
python -m pip install "cpu-llm==1.10.0"
python -m pip check
cpu-llm-demo healthcare --out healthcare-demo-new-run
cpu-llm-demo conversation --out conversation-demo-new-run
```

Explain that PostgreSQL/pgvector and encoder setup/caching come before the demos;
the output directories must be new. The trained projection and demo data ship;
the external pretrained encoder and optional NLP/decoder assets do not. No
model retraining is required for these examples. Link the setup section.

### Evidence with visible denominators and scope

Use the claims register, not unsupported accuracy badges. Lead with current
release verification: 897 passing source tests, 2 skipped, 3 expected failures;
installed healthcare and conversation demos each 12/12 authored checks. Keep
Windows/Python 3.12 scope and correct refusals visible. These are different
denominators and must not be aggregated into an accuracy rate.

The historical 32-case local comparison may appear in a methodology section:
16 fictional medication cases and 16 healthcare-record cases; ordinary, strict,
literal/calculator arms. It is not a comparison with a generative LLM or clinician.
Do not headline 16/16 as medical accuracy. Link frozen cases/scorer/raw evidence.

### Read the architecture and API guide

Expose an HTML contents list for the full whitepaper: setup, ingestion, six
channels, node inventory, strict mode, result envelopes, tone, finance, HTTP,
Python API, evidence and deployment. Include the download next to the HTML link.
The whitepaper is an implementation guide with AI-assisted drafting, not a
peer-reviewed research paper or independent clinical/security certification.

### FAQ copy

- **Is cpu-llm a general local LLM?** It is a bounded document-and-rule engine.
  A trained encoder/projection supports retrieval; not every response uses an
  unrestricted generative decoder.
- **Does strict mode guarantee zero hallucinations?** It bypasses learned answer
  generation. Incorrect sources and unsupported/unrecognized semantics remain
  possible; clinical or universal accuracy is not guaranteed.
- **Can I use it for healthcare or pharmacy?** Evaluate the fictional label and
  record demos. Production clinical claims require validated sources, intended
  use and independent review; the package does not approve diagnosis/prescribing.
- **Does it require a GPU?** The documented CPU-first strict examples do not.
  Provision the required database, dependencies and encoder assets separately.
- **Can it run offline?** After required assets are cached/provisioned, offline
  deployment can be configured. The default installation is not a certified
  air-gapped or no-egress environment.
- **Can it produce friendlier sentences?** Its optional Python tone companion
  handles five relations and reviewed constructions; unsupported expressive
  styles can fall back to neutral. Strict mode disables that companion.
- **Do I need to train it?** The retrieval projection is packaged and the encoder
  is pretrained. Ingestion is required; retraining is not required for the demos.

Render FAQs as visible helpful HTML. Do not promise FAQ rich-result eligibility
or manufacture reviews/ratings to obtain software rich results.

## Technical SEO and measurement acceptance

Use one descriptive H1 and unique title/description; self-canonical HTTPS URLs;
working breadcrumb/internal links; crawlable HTML content rather than PDF-only
copy; accessible link labels and code; sitemap inclusion and no accidental
robots/noindex blocks. Verify the final URL responds 200 with substantive content
in the initial HTML, and verify the PDF has a real PDF content type.

Use honest `SoftwareSourceCode`/`WebPage`/`BreadcrumbList` structured data and a
`TechArticle` for the full guide where appropriate. Only add a supported software
application rich-result shape when actual required properties are satisfied.
Do not invent ratings, reviews, offers, author credentials or compliance badges.
Validate JSON-LD and test relevant Google structured-data support. Structured
data does not guarantee a search enhancement or ranking.

Link the Research Tools index to this page and add contextual links from existing
VectorPrism, Python Libs and relevant finance/clinical research pages after
checking editorial fit. Do not alter those products' claims or imply identical
implementations. Avoid cannibalizing existing library pages with duplicated copy.

Track installation/source link clicks, whitepaper downloads and sample-demo
expansions using existing consent/analytics conventions. Do not log private
medical questions as analytics events. In Search Console, segment the page's
queries, impressions, clicks and CTR by developer/use-case intent after launch.
Report observed performance rather than predicted traffic. Use search data to
revise ambiguous headings/FAQs, not to remove material limitations.

## Claims that must not appear

No "100 percent accurate healthcare AI", "clinically validated", "FDA approved",
"HIPAA compliant", "SOC 2 certified", "zero errors", "all contradictions
detected", "beats GPT/Claude", guaranteed energy/carbon/latency/cost savings,
or "all six learned heads trained". No inference that every ordinary-mode path
is generator-free. No fake testimonials or patient outcomes. Do not claim
arbitrary PDF-page citations when the actual evidence is document/chunk IDs,
spans and stored-chunk offsets/hashes.

## Primary links and final check

Published package: https://pypi.org/project/cpu-llm/1.10.0/
Repository: https://github.com/insightitsGit/cpullm
Release source: https://github.com/insightitsGit/cpullm/tree/0102bc0
Release verification: https://github.com/insightitsGit/cpullm/blob/40ead1e/docs/releases/1.10.0-build-validation.md
Actual healthcare chat: https://github.com/insightitsGit/cpullm/blob/0102bc0/examples/healthcare/sample-run/README.md

Before reporting completion, check the claims register against page text and
metadata, test every CTA and asset, ensure the nav/index placement is correct,
and state whether the result is a local preview or live deployment. Return the
implemented paths/URLs, tests and any remaining limitation. Do not report a live
page merely because this handoff exists.
