# Benchmark v3: prompt understanding, response depth and rendered evidence

Prepared 2026-10-29. **Design and execution specification; no v3 run has occurred.**
The [agent handoff](handoff-benchmark-v3.md) gives the execution sequence and scope.
[Machine-readable protocol](benchmark-v3-spec.json) fixes the intended experiment.
This evaluates the combined changes, not just their development examples.

## 1. Question to answer

Can an application send supported human wording directly to `Appliance.ask()` and
receive a responsive, properly scoped, source-backed answer in its requested
length/layout, without an external prompt wrapper?

Measure each stage independently: interpretation, task coverage, retrieval,
licensed inference, response composition, citation retention and visible rendering.
More words or a valid-looking table are not evidence of a better answer. A safe
nonanswer is different from answering a supported question correctly.

Read the implementation boundaries in [prompt ingestion](prompt-ingestion.md),
[response depth](response-depth.md), [output layouts](output-layouts.md), and the
[clean-install audit](reviews/2026-10-28/clean-install-audit.md). Preserve the
existing v2 artifacts and specifications as historical measurements.

## 2. Freeze the actual implementation

At design time HEAD is `a9c4591`; prompt interpretation, dependency corrections,
length flags and Tabulate/Jinja2 rendering are still working-tree changes. **Do
not evaluate HEAD alone and label it the new system.** Prefer a user-provided
commit containing these changes. Otherwise capture an immutable source bundle
including tracked modifications and nonignored untracked files, then execute
only its extracted contents. Do not silently commit or alter the user's branch.

Record base HEAD, Git status, binary diff, full file hashes, source-bundle hash,
checkpoint/config hashes, package metadata, Python/OS/architecture and dependency
lock. Assert imported `cpu_llm` paths resolve inside the extracted snapshot or its
built wheel, never the original checkout. Hash the runtime files again at exit.
Keep the same source and dependency resolution across experimental arms.

The last development validation was 695 passed, 2 skipped and 3 expected failures,
with six NumPy warnings. That is context, **not a benchmark score or guaranteed
count for a later snapshot**. Execute the complete live suite on the frozen source
and publish its actual counts, skips, expected failures and warnings. Do not
deselect failing tests to create a clean result.

## 3. Entry gates: installation and evaluator integrity

### Clean consumer install

Use a fresh virtual environment without system packages. Build an sdist and wheel
from the frozen source, then install the wheel with dependency resolution. Do not
install the source editable for the wheel smoke test. From an unrelated working
directory, test imports, `cpu-llm-serve --help`, three-record ingestion, a direct
attribute answer, a two-premise join and a requested table/report.

Verify metadata declares `prismrag-patch[graph]`, Tabulate and Jinja2. Confirm
`community` imports, the checkpoint is packaged and `pip check` passes. A successful
build/import is insufficient: the prior missing python-louvain error appeared
only during ingestion. Test rebuilding a wheel from the sdist too.

The current public PyPI wheel shares version 1.9.1 with newer source but contains
older code. Package version alone cannot identify the evaluated implementation.
Do not substitute the public wheel for the new source build. Record this release
distinction; publishing a package is outside this benchmark task.

### Local assets and setup matrix

Prepare encoder and optional spaCy assets explicitly before offline execution.
Record exact library/model versions. The previously tested combination was
Python 3.12, spaCy 3.8.18 and `en_core_web_sm` 3.8.0; this is an observation, not
a requirement to use unverified availability on another machine.

Check `prompt_backend="auto"` in isolated configurations: no spaCy, spaCy without
the model, and both installed. The first two must report a rules fallback and
reason; the last must actually use spaCy. Explicit `"spacy"` without assets must
raise the documented setup error, not claim successful NLP. Explicit `"rules"`
must not load a model. Test no database connectivity separately as a runtime
prerequisite failure. Do not score setup failures as factual reasoning failures.

### Scorer and gold gate

The evaluator must not import library extraction, answer selection, query
normalization, rendering or template code as its semantic oracle. Use authored
typed facts and independently specified expected requests and proof sets. Reusing
the v2 runner's transport/logging is fine; its scorer alone does not cover v3.

Before running the appliance, freeze scorer fixtures covering wrong entity,
relation, direction, polarity, scope/time, missing join premise, retrieval-only
proof, wrong format/media, display omission hidden by correct canonical text,
escaped pipes/newlines, leading zeros, invalid HTML, and an unexecuted pending
child falsely marked complete. Also test legitimate source quotation/conflict,
question text and clarification options so they do not become false endorsements.
Each fixture needs its expected pass/fail and failure category. An evaluator that
cannot distinguish these cases must be repaired before official scoring.

## 4. Experimental arms

Primary paired comparison uses the same new corpus, cases, caller scopes,
checkpoint, source order, reference backend and response budgets:

- `rules`: `Appliance(prompt_backend="rules", resonance_tags=False)`.
- `spacy`: `Appliance(prompt_backend="spacy", resonance_tags=False)` with the real
  local dependency parser. Fake annotations do not count as this arm.

Reference resolution stays disabled in both primary arms to isolate prompt
parsing. Existing explicit/unique-reference rules still apply. If testing the
optional coreference backend, create a separate, identically configured paired
experiment; do not mix it into the primary totals.

Auto selection is a setup/conformance matrix, not a third independent quality
arm. Optional resonance runs a prespecified 60-case development subset in both
parser arms and is reported separately. It must not replace the dense/tag-off
baseline or be pooled to inflate sample size. Record enabled projection heads:
six symbolic channels do not imply six trained heads.

Use distinct SQL databases/namespaces, local graph directories and sessions for
each arm/split. Share model assets, not ingested state or conversation state.
Counterbalance arm order. Use the same deterministic source-order seed for pairs.

## 5. Data and exact core counts

Create three new fictional domains with new names, values, aliases and source
wording. Do not reuse the subjects or prose in existing gold, unit tests or the
examples in these documents. Known examples belong only in the regression replay.

Author at least 180 initial factual paragraphs: per domain at least 40 ordinary
public, 10 private and 10 historical-prior paragraphs. Each historical prior has
an explicit correction; keep returned corrected IDs in the manifest. Add 300
distractor paragraphs (100/domain), including similar names and true but
wrong-relation facts. These counts describe initial input; record corrected,
retired and currently valid versions separately instead of conflating them.

Cover explicit aliases, type membership/universal rules, scalar attributes,
main-clause identities versus actions, conflicts, criterion-bound rankings,
local glosses, explicit unknown attribute values, leading-zero strings and
source characters such as pipes, newlines and HTML/template-like text.

The standalone core is **240 cases**: each family below has exactly 20, split
12 development / 8 holdout. Total: **144 development / 96 holdout**.

1. Conversational normalization: inquiry shells, indirect copulas/residence,
   noun subjects, request-position versus quoted genre words; matched direct forms.
2. Explicit field lists and task coverage: 1/2/3/8 fields/tasks, original offsets,
   unknown fields, multiple subjects, ninth task/overlong input, no silent omission.
3. Meaning and reference: proper identity, action-versus-definition, unlinked
   classes, unique/ambiguous antecedents, references before and after named tasks.
4. Joins and retrieval repair: direct facts, authorized membership + universal
   rule, alias proof, repair beyond the initial shortlist, wrong-class/some/average
   negatives, contradictory rules, no unlicensed transitive inference.
5. Attribute slots: color, shape, material, possession and both declared weight
   forms; type/location/ranking distractors, ambiguous bare material/color words.
6. Response depth and size: brief/standard/detailed, long/extended/elaborate,
   counts/word-allocation estimates, few eligible facts, no padding, mandatory proof.
7. Layout/media flags: Markdown tables/reports, HTML tables/reports, bullets,
   numbering, global versus local style, direct facts versus broad overviews.
8. Proof and display fidelity: per-row claims, all join premises, exact values,
   leading zeros, pipe/newline escaping, literal Jinja syntax, escaped HTML,
   correct visible output versus merely correct hidden `canonical_text`.
9. Access and historical validity: empty scope, private near-neighbor, mixed-scope
   premises, historical correction, deletion, reopened stores, distinct callers.
10. Instructions versus input data: quoted/code examples, structured finance
    fields, conditional/negative/modal/quantified questions, format/depth as subject.
11. Existing specialists/templates: supported source-backed letters/reports,
    checklists/FAQs, arithmetic/finance; distinguish legacy draft report from the
    new post-judgment report layout; preserve existing refusal contracts.
12. Missing/conflicting/unsupported evidence: supported question lacking its fact,
    conflicting values, genuinely unsupported wording, unsupported qualifiers,
    ambiguity versus absence, safe outcome with correct reason and no invented fact.

Declare before execution which forms are supported in both arms, spaCy-specific,
or expected to be rejected/clarified. Do not count a deliberate rules rejection of
a spaCy-only form as a baseline correctness bug; report capability coverage and
safe handling separately. Do not retroactively mark a failed supported case
unsupported after seeing its output.

Add **24 conversation scripts**, 12 development / 12 holdout. Each of six groups
has four scripts, two per split: reference confirmation; ranking criterion and
evidence; meaning choice; batch first/middle/last continuation; cancel/new-question/
reset boundaries; and changed caller/scope/as-of/TTL/restart. Use 2–4 turns each
and freeze the exact turn count in the manifest. An actual process restart needs
a new process with a distinct PID; an in-process reset is not a restart.

Run all core cases and script turns in both primary arms. Thus there are 480
standalone attempts plus twice the frozen script-turn count. Report scripts as
scripts as well as turns; do not pretend dependent turns are independent samples.

## 6. Gold records and freezing

Each case needs ID/family/split, original prompt, independently authored expected
tasks/contracts, constraints that must survive, expected presentation flags/media,
allowed outcomes, licensed typed claims and forbidden claims, minimal alternative
proof sets, caller/source scope, as-of time, and budget expectations. Include
expected visible rows/items and missing/pending states for compound cases.

Typed claims bind subject, predicate, object/value, direction, polarity and
quantifier. Scope/time and identity premises belong to proof obligations. Do not
require one surface wording when several source-backed expressions are valid.
Record approved alternatives before execution. Do not use returned runtime
`request`, `judgment` or `rendered_response.rows` as expected gold.

Use seeds in the machine-readable specification. Generate development and
holdout names/values independently; use equal relation/format difficulty. Holdout
is hidden from exploratory tuning, then hashed with the scorer, case files and
corpus before any official call. If a gold error is found later, preserve the
original expectation, adjudication/reason and separately versioned rescore. A
change to runtime or gold creates a new run ID; never edit an existing run.

## 7. Observe the actual public result

Call `ask()` with the original prompt. No agent-written wrapper may normalize,
split, enrich or pre-fill it. Ingest only the frozen corpus. Use unique explicit
session IDs for scripts and isolate standalone cases from conversational memory.

Save the complete JSON-safe result, not a summary of `reply.text`. Capture initial
and repair search queries, IDs and timings through non-mutating instrumentation;
also record allowed scope/as-of, effective parser/backend/model, task boundaries,
interpretation transformations, response flags/budgets, chosen contracts, accepted
proof, final judgment, render template/renderer/media and all public answer fields.
Never expose private retrieved text through public benchmark examples.

Score all of: `reply.text`, `reply.body`, `answer`, task results, accepted evidence
and `rendered_response`. A claim hidden in another public factual field is still
a failure. Empty output, exception, timeout and aborted child remain in their
denominators and have distinct categories.

For Markdown tables, use an independent parser with fixtures for escaped pipes
and generated line breaks, not naive `split('|')` or Tabulate itself. For HTML,
parse with an independent DOM/HTML parser; decode entities and inspect visible
cell/article text and source references. `reply.media_type` must agree with output.
Reject literal executable script nodes; literal `{{ 7 * 7 }}` must stay text,
not become `49`. Header/control markup is not a factual claim.

Check visible values and proof against gold, then check structured rows and
canonical claims for agreement. Correct hidden metadata cannot excuse missing,
altered or extra visible claims. Citations must support the right row/task and
each inference premise, not simply exist somewhere in retrieval. Questions,
options and conflict quotations are not endorsed facts; private canary text is
still a disclosure even inside a quotation.

Counts are ceilings for optional units. Mandatory proof may exceed a requested
one-sentence limit when the documented budget explicitly preserves it. Score
word requests on allocation/flag behavior, not an unsupported exact word count.
When only a few facts exist, do not reward padding. Report output length separately
from claim accuracy and requested-field coverage.

## 8. Measurements and acceptance targets

Publish counts and rates per family, split, arm and expected capability class:
responsive supported-answer coverage; interpretation/task agreement; recall of
required evidence; licensed claim precision; proof completeness; correct
clarification/abstention/conflict; continuation completion; layout/media validity;
visible/canonical agreement; optional-budget compliance; disclosure and invalid
inference counts. Give strict whole-case pass = all applicable dimensions pass.
Also report script-all-turns pass. Do not merge all dimensions into one score.

Report paired rules/spaCy deltas on the same cases. Keep shared-form correctness
separate from newly supported wording. Use confidence intervals with appropriate
case/script units, not each table cell as an independent observation. No claim of
general-language accuracy or production readiness follows from synthetic results.

Prospective acceptance targets: zero unauthorized disclosure, wrong-meaning or
wrong-relation endorsements and unlicensed joins; complete proof for every
endorsed factual conclusion; 100% required task accounting and faithful layout;
at least 90% strict pass on prespecified supported standalone cases in each arm.
A safe refusal still fails supported-answer coverage. Publish failures against
these targets; do not adjust thresholds after inspecting the holdout.

Measure application/model cold startup separately from warm requests. For 30
prespecified balanced cases, take five warm repetitions per arm and report p50/p95
total, parser, encoding, retrieval/repair and composition/render latency plus
query counts. Report process-tree memory where measurable; unavailable is not
zero. Distinguish layout/depth classes and answered/nonanswered outcomes.

Optional scale: fixed 24-case development subset (two/family), with the same
gold facts among 1,000 then 10,000 distractors. Preserve the core output directory;
use new databases and separate artifacts. Stop an optional arm at the prespecified
30-minute cap, retain partial results/timeouts and label incomplete. Core quality
does not wait for an unbounded scale run. Optional resonance uses its fixed
60-case subset and is not pooled into core results.

## 9. Regressions, independent review and deliverables

Replay known cases separately: Mary action versus identity, scientific names,
wrong-relation but true facts, criterion ranking, unique-reference batches,
scorer entity boundaries, 695-suite regressions, dependency graph-extra failure,
shape/material/weight repair, global list-format propagation, and source strings
that resemble Jinja/HTML. Label these known regressions, not fresh holdout.

Review every failure/uncertain verdict and a seeded five passing case IDs per
family (60 paired IDs across both arms, fewer only when insufficient passes).
Adjudication must inspect original prompt, authorized source facts, visible output
and proof. Copying the automatic score is not an independent review. If no second
reviewer is available, label the review single-agent and leave uncertainty visible.

Produce immutable source/lock/model manifests; corpus and gold with hashes;
scorer fixtures/version/source; setup and live-suite logs; JSONL raw outputs and
stage traces; corrected-ID mapping; metrics and timing files; a per-failure catalog;
review/adjudication log; and a human-readable report. Show representative successes
and failures for conversational prompts, long answers, Markdown tables, HTML
reports and clarification/resume. Each example needs its prompt, expected intent,
actual visible response, citations and verdict. Report lessons and rank next
improvements by root cause, not by names/phrases in failed fixtures.
