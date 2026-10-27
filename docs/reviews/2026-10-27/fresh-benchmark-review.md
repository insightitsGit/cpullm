# Fresh request-pipeline benchmark review

Reviewed 2026-10-27 against HEAD `f399f79`. Run under review:
`build/benchmark-request-pipeline-2026-10-27`. The run records `cab025e` plus an
archived budget patch, so it is correctly labeled exploratory. Original artifacts
were not modified. No library fix or full benchmark rerun was performed here.

## Assessment

The raw results expose important failures, but the headline 135/274 supported
successes and 19 false assertions are not reliable quality estimates. Gold and
scoring defects both inflate failures and permit incorrect passes. Repair and
version the evaluator before using those totals to prioritize runtime changes.
Do not interpret a passing development suite as benchmark accuracy.

Read the source runner/scorer/gold, report, failure catalog, manifest, suite log,
and selected full raw responses from both phases. Ran independent adversarial
probes against the scorer, without importing or executing the library. This is
targeted verification, not manual adjudication of all 460 rows.

## Required evaluator corrections

### R1 — P1: word presence accepts wrong subjects and negation

`tools/benchmarks/request_pipeline/scorer.py:188` matches expected claims as
substrings. An answer containing `gray` with the gold citation passes both
`The WrongEntity is gray.` and `The Helion is not gray.` when the expected fact
is Helion's gray color. Forbidden word lists do not establish assertion truth.
Use typed entity/relation/value/polarity bindings and check actual claims against
source spans. Keep quotation, endorsed assertion, irrelevance, and incompleteness
separate. The letter fixture labels sourced gray facts as false solely because
the requested genre is classified unsupported; a supported source-backed letter
is a contract disagreement, not a factual falsehood. The runtime has a specialist
letter path. Do not remove that path simply to satisfy this gold.

### R2 — P1: claimed expiry/restart defects are not established

`run_eval.py:188` and `:366` replace or advance clarification/request-plan clocks
but never bind the clock of `app.references`. The reset also does not clear or
recreate `app.references.states`. A supposed reopen merely calls this reset on
the existing appliance; no process restart occurs. The stored reference prompt
therefore survives by construction. Recreate the appliance/local session stores
for an actual reopen, use a fresh process for a restart claim, and inject the same
clock into all relevant stores. Reset all state between independent scripts.
The current expiry/restart outputs are harness artifacts, not verified library
TTL or restart bugs.

### R3 — P1: gold scripts demand ambiguity and ranking unsupported by sources

`gold.py:570`: `What color is the Sextant? Where does it live? What color is the
Azimuth?` has a unique earlier antecedent for `it`. Raw output correctly binds
Sextant, answers Orinth, then answers Azimuth yellow. Gold instead forbids yellow
and demands a pause. `gold.py:631` similarly forbids Caldera after `What is the
Helion? Where does it live?`, despite the explicit singular antecedent. These
cases do not demonstrate wrong binding or premature task execution. Use two
plausible preceding entities for a real middle/last-child clarification probe.

`gold.py:543` and `:592` expect `color` to complete a best-ranking question using
an ordinary color sentence. It establishes color, not which rover/telescope is
best by that criterion. The raw request for comparison evidence is appropriate.
Supply an explicit ranking with that criterion for a positive completion case.

### R4 — P1: child retrieval can masquerade as cited evidence

`scorer.py:78` recursively walks the entire child result, including `related`
and other retrieval/diagnostic fields. A result with no public citations passes
proof checking if a child merely contains `related: [{document_id: gold}]`.
Recurse through child *evidence fields*, not arbitrary child objects; distinguish
accepted proof, displayed attribution, retrieval candidates, and rejected data.
The reported 86 retrieved-then-lost rows are not an audited delivery-loss count:
they include safe abstentions after extraction misses, and child evidence checks
can miss actual loss. Categorize the actual failing stage before counting.

### R5 — P2: budget tests allow absent metadata and do not measure overflow

`scorer.py:223-225` explicitly permits missing combined allocation/total metadata.
A gray answer without any budget plan passes a fixture requiring a q1 allocation
of one. Child metadata is checked only when present. `:251` reads an
`optional_overflow` flag from the result; the runner does not independently
measure and set it. Scorer selftests manually set that flag, which does not test
real overflow detection. Missing required metadata should fail; compare actual
child ceilings and optional producer selections, while preserving required proof.
Do not claim full combined-budget benchmark validation from these passes alone.

### R6 — P2: the planned full evaluation remains incomplete

The report candidly states that scale does not re-score gold, test a join beyond
the first shortlist, or measure peak RSS. Atomic raw queries exist for development
but no holdout atomic files are present and no paired effect metric is reported.
The script called concurrent is sequential interleaving; the separate threaded
scale probe does expose SQLite affinity, but does not establish concurrent parent
plan correctness. `manual_review_queue.json` is a queue, not a completed signed
adjudication record. Initial/final retrieval precision/recall and mandatory proof
coverage are not fully reported. Finish or explicitly mark these phases untested.

Manifest hashes match LF-normalized UTF-8 text, not the CRLF file bytes on this
machine. Specify canonicalization or hash the written bytes for reproducibility;
this mismatch alone is not evidence of corpus tampering.

## Runtime findings supported by raw outputs

1. **P1 — successful unrelated delivery:** `separation-obs-25` asks Quill's kind;
   q2 returns `The Quill is found in Rimward.` and the aggregate says complete.
   The task is present, so the precise issue is wrong-relation success, not literal
   removal of a planned task. `auth-obs-08` also asks a current mount-shape question
   and receives Helion's type. The report's statement that all history text is
   correct is too broad. Enforce relation/entity checks on fallback deliveries.
2. **P1 — unbound possession questions bypass the relation gate:** `join-wh-03`
   and `join-obs-03` have judgment entity/relation null and reason
   `no_channel_relation`, then mark `Some display rovers have a beacon.` or
   `Every survey telescope has a filter.` answered for an individual. These are
   true source sentences but do not settle the asked individual possession.
   Fix recognized yes/no possession binding and refuse an unlicensed application.
   The traces do not show that the licensed membership-join engine itself inferred
   an individual from `some`; do not diagnose that engine without a reproduction.
3. **P2 — sense clarification missed:** `ambiguity-obs-01` quotes one Lumen class
   despite competing unlinked senses. Review sense candidate coverage and binding.
4. **P2 — extraction/normalization coverage:** `direct-wh-01` finds amber but
   withholds it; `cause-wh-01` withholds stopped/battery-failed evidence for
   `Why did the Vesper stop?`. These are missed answers, not hallucinations.
5. **P2 — evidence delivery gaps:** multiple historical shape answers have correct
   words but no `answer_evidence`. Inspect producer and public verification scope;
   do not equate display-only words with a complete cited proof.

## Recommended order

First repair gold scripts, assertion/proof scoring, budget checks and reference
clock/reset probes. Preserve this run and write a new scorer/adjudication output
directory. Re-score saved raw results where possible, rerunning only invalid
experiments. Then fix the verified wrong-relation and possession-routing failures,
add focused regressions, and evaluate on a new frozen holdout. Keep resonance
opt-in: these results do not establish a quality benefit, and scale traces show
a substantial CPU latency cost. No absolute production SLA is established.

The recorded suite log confirms **554 passed, 2 skipped, 3 xfailed**. That suite
was not rerun during this review. No new corrected accuracy total is claimed.
