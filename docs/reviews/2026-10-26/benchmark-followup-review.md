# Benchmark and follow-up commit review

Reviewed 2026-10-26 at `32b0e5d`, with a clean source tree. Baseline report:
[`2026-10-25-baseline/REPORT.md`](../../benchmarks/2026-10-25-baseline/REPORT.md).
That evaluation ran `3d3c054`; runtime fixes are in `8c42d4a`.
`32b0e5d` itself adds benchmark artifacts, not runtime changes.

## Verification performed

Read the baseline report, scorer, source snapshot, metrics, raw response summaries,
and changes since its recorded checkout. Replayed all 41 evaluation turns for
each arm on current code, using the original corpus, questions, and scorer without
overwriting the baseline artifacts. Ran the complete suite with live tests enabled.
Used a new local PostgreSQL 18 database with no preinstalled vector extension;
the application installed vector into public. The cluster was stopped afterward.

- Full suite: **471 passed, 2 failed, 2 skipped, 3 strict expected failures,
  6 existing NumPy warnings**, 65.76 seconds. No deselection.
- Dense factual cases: **16/18**, up from baseline **14/18**.
- Resonance factual cases: **16/18**, up from baseline **7/18**.
- Conversation completion: **5/5** in each arm, up from **4/5** and **3/5**.
- Both arms still fail the possession join and town-operated synonym cases.
- The remaining sense questions include the missing-captain question and explicit
  comparison with resonance enabled.

These are replays of a now-known small corpus, not independent generalization
measurements. The original scorer has the defects described below, so its
wrong-answer aggregates are not endorsed. No 10,000-paragraph ingest, original
scale workload, or external memory measurement was repeated.

Local evidence (ignored build directory):

- `build/benchmark-review-1026.log`: full suite, both replay arms, and response fields.
- `build/benchmark-review-1026/dense.json` and `resonance.json`: all replay summaries/verdicts.
- `build/benchmark-review-extra-1026.log`: additional live ambiguity and causal probes.
- `build/probe_benchmark_gaps.py`, `probe_join_1026.py`, and
  `probe_resonance_scale_1026.py`: focused reproductions.

## Are the fixes related to the measured failures?

Yes. They address real failures in this benchmark:

- Named-attribute requests bypassing the sense gate restore Cedar color, kind,
  location, lifespan, and reference-follow-up answers. The bypass is overbroad; see R1.
- Shared plural normalization restores the retrieved fuel-economy ranking in both
  inline and conversational forms. Both replay cases now pass.
- Possession repair now continues past a direct possession to search for type rules.
  Its unit test passes, but the real answer still drops the rule; see R2.
- Final reply refusal suppresses unrelated copied answers for unsupported when/count
  requests and dense comparisons. Public answer fields remain inconsistent; see R3.
- Creating vector in public fixes fresh multi-namespace extension initialization.
  The current suite no longer has the baseline extension errors or reopen failure.
  The review database used trust authentication; password preservation was reviewed
  in the code rather than independently exercised with a password-required server.
- Word-index union replaces pairwise component comparisons, a useful optimization.
  Other ambiguity work remains quadratic; see R4.

## Actionable findings

### R1 — P2: an attribute question suppresses genuine ambiguity

Location: `src/cpu_llm/pipeline.py:2192-2211`.

`_named_attribute` checks only whether a recognized relation and a nonempty entity
exist. It does not establish that the name identifies one sense. The live probe
stores a mammal bat and a wooden-club bat, then asks `What kind of thing is the bat?`.
The resonance store reports ambiguity, but the gate returns no clarification and
the appliance quotes `The bat is a mammal.` It silently selects one meaning.

Distinguish multiple facts about one identified entity from multiple entities
sharing a name. Do not suppress ambiguity solely because a requested slot exists.
Add this negative case alongside the repeated-Cedar positive test. Also check the
remaining missing-captain and comparison early returns; the patch only bypasses
five recognized attribute relations.

### R2 — P2: possession joins are lost at delivery

Location: `src/cpu_llm/agents/reply.py:242-253`, interacting with
`src/cpu_llm/attribute_search.py:20-75`.

Both live replay arms retrieve the membership, universal life-raft rule, and direct
diesel-engine fact. A direct call to `select_channel_answer` with these three rows
correctly returns `universal_membership_join` and all three evidence spans. Yet
`ask('What does the Cedar have?')` returns only `The Cedar has a diesel engine.`

The final query assessment accepts an already audited partial `answer`, replaces
its richer decision text with that partial sentence, and filters evidence down to
what was spoken. Additional retrieval cannot fix this delivery preference.
Test the complete Appliance path, not only `retrieve_missing_attribute` plus
the standalone generator. Preserve the licensed join and both premises through
auditing and final delivery, without treating partial possession lists as complete.

### R3 — P2: refusal text and public answer fields disagree

Location: `src/cpu_llm/agents/reply.py:116-124` and
`src/cpu_llm/pipeline.py:1125-1141`.

The live departure question returns `reply.text = "This question type is not
supported yet."` and `answer_status = "unsupported"`, while `answer` still contains
unrelated Cedar location, kind, ranking, color, and engine facts. `audit_passed`
remains true. A live why/Rowan question likewise retains irrelevant color facts.
The missing-captain abstention can also retain a positive unrelated `answer`.

The refusal changes the reply only; `_reply` clears `answer` for a few statuses
but not unsupported or all other abstentions. Make delivery outcome authoritative
for answer, reply, status, evidence, and verification/audit metadata. Retain rejected
candidates only in clearly identified diagnostics. Add assertions over the full
public result, since the benchmark currently reads reply text first and misses this.

### R4 — P2: ambiguity labels retain quadratic cost and unbounded output

Location: `src/cpu_llm/resonance_groups.py:231` and `497-511`.

The indexed component builder improves one stage. But `recall_spread` calls
`_sense_words` once per lit component, and each call scans the whole unit list.
With many small components, this is still quadratic and produces an option for
every component, including blank `another meaning` labels.

A synthetic frequent-word probe measured 200/800/1,600 independent components at
approximately 0.0056/0.0546/0.2073 seconds and returned exactly 200/800/1,600 choices.
These are diagnostic local samples, not latency promises. Compute labels from
component members in one pass, cap work and choices, and expose an explicit budget
outcome rather than an enormous clarification. Remeasure the original 10,000-tag
workload before claiming the reported 8.8-second cliff has been resolved.

### R5 — validation gap: two suite expectations conflict with the changed behavior

The failures are:

- `test_six_channel_nodes_quote_the_passages_and_suggest_discovery_for_a_why_question`
  expects an identity sentence for a why/difference question, while delivery now
  returns the unsupported notice.
- `test_questions_about_an_uploaded_pdf_answer_from_that_file` requires the
  `Explanation:` heading, which the patch deliberately removes for duplicate causes.

These are not evidence that restoring unrelated identity answers or duplicated
explanations is desirable. Reconcile the intended contract and tests explicitly,
retain useful citation/cause assertions, and make the full suite green before the
next baseline. Do not simply weaken tests until they accept any text.

## Benchmark integrity findings

### B1: the scorer confuses incomplete answers and clarification labels with false claims

`run_eval.py:412` marks an answered but incomplete required-phrase set as wrong,
so a true diesel-engine answer missing a life raft becomes a false-answer count.
The abstention branch at line 416 also marks forbidden words in clarification
choices as a wrong answer, even when `needs_clarification` is true. The report
recognizes those false positives but its corrected headline still retains the
original 4/41 and 3/41 aggregates. Subtracting a counted case must change the count.

Track false assertions, incomplete answers, unnecessary clarifications, and
abstentions separately. Recognize `No stored sentence names who did that.` through
a machine-readable status rather than adding more wording exceptions. Check the
entire public response contract, including R3, rather than only `reply.text`.

### B2: the why-case expectation conflicts with the implemented supported causal path

The benchmark requires the fixed unsupported sentence for a question whose exact
cause is explicitly in the corpus. Current code intentionally preserves a cited
cause. The replay still labels that correct quote a wrong answer. Agree whether
explicit source-backed causes are supported; version the expectations and report
the contract change separately from performance improvement. Do not silently
rewrite the old benchmark to make the new implementation pass.

### B3: the reproduction command overwrites its baseline artifacts

`run_eval.py:32` fixes OUT to the script's directory and `write_json` overwrites
files there. Repeating the documented command at a new commit replaces snapshots,
metrics, and raw responses under the dated baseline while REPORT.md still describes
the old run. Add a required fresh output directory/run ID and refuse an existing
result directory. Keep corpus/scorer versions and source hashes with each run.
The review replay deliberately called the harness functions and wrote under build.

## Recommended next work

1. Fix R3 and R2 first: one authoritative response contract and complete evidence
   delivery. Add a live regression using the benchmark's missing possession case.
2. Replace blanket ambiguity bypass with entity/sense discrimination and bounded
   label generation. Keep resonance opt-in; its default remains off.
3. Resolve suite and scorer contracts, preserve the original baseline, then rerun
   both arms on an independent holdout as well as this regression corpus.
4. Add source-scoped, provenance-preserving dictionary definitions such as
   `Municipal means town-operated in this manual.` The benchmark already retrieves
   that gloss but neither arm can use it. Do not globalize a manual-specific synonym.
5. Add persistent-extension namespace checks for databases created by older code;
   `IF NOT EXISTS` does not relocate an extension already installed in a tenant schema.
6. After correctness, repeat the large-corpus ingestion, memory, and latency runs;
   separate actual answers from early clarifications in latency summaries.

No library or test implementation was changed during this review.
