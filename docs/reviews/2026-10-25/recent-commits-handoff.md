# Consolidated recent-commit review and fix handoff

Date: 2026-10-25. Reviewed base: `ddca204`; reviewed HEAD: `8d915db`.
The fixes described here are working-tree changes following that HEAD. This
document combines the earlier review findings and the follow-up implementation.
No commit or push is part of this handoff.

## Scope and design understood

Reviewed commits:

- `8d011cf`: source boundaries, ingest paths, service/session behavior, and rule verdicts.
- `abb9464`: article PDF rebuilding and removal of generated preview images.
- `8d915db`: sentence resonance tags, sense clarification, and retrieval admission.

The implementation uses the frozen CPU encoder and VectorPrism's 1,024-dimensional
tensor, six independent channel assessments, a source-backed fact graph,
dictionary-assisted query variants, bounded retrieval repair, and constrained
sentence realization. Resonance sentence tags add candidates and identify some
ambiguous words; a tag connection is not a factual inference or a verified answer.

The SQL-style join is a bounded evidence join: an explicit membership fact and
an applicable explicit universal rule can support a requested attribute. Both
premises must remain authorized, temporally valid, and cited. A type association
alone does not license copying every attribute of the type to every member.

The earlier join-focused review is retained in [join-review.md](join-review.md).
This handoff covers the recent changes and carries forward the remaining limits.
The PDF builder source was reviewed; this was not a page-by-page visual PDF audit.

## Review findings and fixes

### R1 — P1: concurrent resonance scope leakage

`ResonanceTags._load` assigned caller scope to shared `self._allowed`; the SQLite
callback consulted that mutable field while another request could overwrite it.
An interleaved unrestricted lookup could expose restricted words in sense labels.

Fixed: each lookup captures an immutable scope in its own connection callback.
There is no shared request scope on the store. A deterministic two-thread
regression pauses a scoped lookup, performs an unrestricted lookup, and checks
that the scoped result is unchanged and contains no private fixture words.

### R2 — P1: directory ingestion root escape

The entry point confined the directory itself, but discovered child files were
read without checking their resolved paths. A linked child could escape the root.

Fixed: `open_source` accepts a path-check callback and applies it to every file
before reading. Entry supplies its root confinement check for path ingestion.
The portable regression simulates a child link resolving outside the root and
asserts rejection before any file read. Native Windows symlink creation was not
available in the review environment; the test does not claim a native-link exploit.

### R3 — P2: repeated corrections retain retired evidence

Tag replacement searched only the original ID even when the live sentence was
under a version ID. Raw `get_by_ids` could then re-admit retired vector rows.
Follow-up inspection also found that a second correction retired the base vector
again instead of retiring the current version's vector.

Fixed: tag replacement removes earlier version tags in the exact correction
family; correction closes the replaced live vector's interval; resonance admission
uses `current_chunks_by_ids`, which checks persistent validity intervals. This
also prevents stale tag IDs from loading retired rows left by an older installation.
Unit coverage checks repeated tag replacement and filtered admission. A live test
checks two corrections, the intermediate interval, current tags, current candidate
rows, and historical/current answers.

### R4 — P2: five-digit paragraphs break source boundaries

Ingestion emits `large-p10000`, but source matching/deletion required exactly four
digits. Scoped access missed later paragraphs and deletion/replacement left them.

Fixed: shared Python and PostgreSQL boundaries accept at least four digits while
remaining anchored to the complete paragraph/version ID. Tests cover generated
paragraph 10,000, scope, graph/tag deletion, and live vector deletion while keeping
the neighboring `review-large-policy-p10000` source.

### R5 — P2: authorization rejects ingestion's exact IDs

`index_chunks` accepted IDs such as `join-type`, but `CallerContext.make` rejected
them. The full live suite failed before checking authorization of both premises.

Fixed: caller scopes accept safe exact document IDs as well as paragraph IDs and
source prefixes. Exact IDs use equality, not prefix matching: scope `agent` cannot
authorize `agentic-ledger-p0001`. The original live join authorization test is
retained, rather than changing its fixtures to hide the API regression.

### R6 — P2: sense clarification bypasses the prompt guard

Sense clarification returned source-derived labels before the guarded graph ran.

Fixed: the raw prompt is checked before conversation/source lookup. A blocked
prompt returns a blocked response without labels, evidence, or conversation-state
mutation. The resolved prompt is checked before sense lookup and remains guarded
by the graph before retrieval. Regression coverage makes any conversation or
encoder access fail if a blocked prompt reaches it.

### R7 — P2: short new questions swallowed as criteria

The blanket six-word exemption consumed `What is gravity` as a ranking criterion.

Fixed: shortness alone no longer exempts a question. The bounded continuation
forms `how it ...` and `what it ...` remain usable; unrelated question forms
abandon the pending request and set `clarification_abandoned`.

### R8 — P2: natural criteria lose their explicit subject

After `Which lobster is best?`, `how it tastes` reached reference resolution with
an unbound `it`, because the initial early return had not established reference
context.

Fixed: this bounded ranking form binds `it`/`its` to its explicitly named singular
subject before reference resolution. It does not choose between subjects joined
by `and` or `or`. An end-to-end lightweight regression reaches evidence
clarification for taste instead of asking again which entity was intended.

### R9 — P2: session lock registry grows indefinitely

The registry retained every session lock after its turns completed, independent
of the bounded conversation-state stores.

Fixed: the session context manager counts holders and queued waiters and removes
the registry entry only when the last user exits, including exceptions. Nested
same-session calls preserve their shared reentrant lock. Tests cover 1,000 completed
sessions, exception cleanup, and nested use.

### R10 — design gap: stateless ambiguity silently ignored

Without `session_id`, sense clarification was skipped and dense retrieval could
choose an answer from one meaning of an ambiguous word.

Fixed: ambiguity returns a sense question even without a session. No pending state
is retained; the caller must restate a complete question with the intended meaning.
With a session, numbered/worded choices continue as before. Tests check both the
response and absence of retained stateless conversation state.

## Validation

Before fixes, the full suite at `8d915db` returned **446 passed, 1 failed,
2 skipped, 3 expected failures, 6 warnings**. The failure was R5. Six other live
join/alias/conversation/lifecycle/history tests passed.

The focused post-fix run returned **61 passed, 3 expected failures**. The final
complete suite returned **459 passed, 0 failed, 2 skipped, 3 expected failures,
6 warnings in 61.40 seconds**. All nine opt-in live join/lifecycle/history tests
passed against a fresh isolated PostgreSQL 18 database with pgvector. No tests
were deselected. The two skips require unavailable trained extractor checkpoints;
the six warnings are the existing NumPy overflow warnings in three pipeline tests.

Retained evidence: [before fixes](recent-commits-before.txt) and
[final full suite](recent-commits-after.txt). The final run included the original
join authorization test, both added live tests, and all ten consolidated unit
regressions. `git diff --check` also passed.

The regression tests are in `tests/test_review_regressions.py`, with live additions
in `tests/test_join_pipeline.py` and updated contracts in the existing access,
clarification, and resonance tests. Live validation requires a disposable PostgreSQL
database with pgvector, cached encoder assets, and:

```powershell
$env:CPU_LLM_LIVE_TESTS = '1'
$env:VECTORPRISM_PG_DSN = '<disposable PostgreSQL DSN>'
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
python -m pytest tests -ra
```

Use a fresh working directory/namespace for full validation. The local Windows
sandbox required a writable workspace TEMP/TMP directory for the evaluation
subprocess. The isolated cluster was started only for validation and stopped afterward.

## Remaining limitations and next benchmark handoff

These are not claimed fixed by the ten review changes:

- Three strict expected failures remain: accidental shared words merge crane
  senses; bare crane then fails to request disambiguation; comparison clustering
  cannot simultaneously keep all groups pure and unfragmented.
- The author-written resonance corpus has 33 sentences and 17 queries. Its
  spreading precision/recall gate is not an independent end-to-end accuracy
  benchmark or a comparison against the actual dense retrieval baseline.
- Resonance component construction remains quadratic. Default-on behavior needs
  realistic latency, memory, wrong-answer, and clarification-rate measurements.
- General source-text coreference, broad comparison reasoning, exceptions and
  quantifiers, unit/range reconciliation, hypotheticals, and free-form sentence
  generation remain outside the demonstrated bounded implementation.
- Edibility, permission to eat, and personal safety are distinct questions; a
  retrieved relationship is not sufficient evidence for a personal safety answer.
- Ingestion/correction/deletion are not one atomic transaction across every store.
  Shared relation files, the PrismResonance ledger, backups, and external artifacts
  are not covered by a complete-erasure guarantee.
- Session serialization prevents overlap for a given key; the caller still
  supplies semantic turn order. This is not a new general concurrency guarantee
  for ordinary `ask` calls on a shared appliance.

Next agent: start from the eventual commit containing these fixes; retain the
regressions and strict xfails. Run a fresh full suite, then an independently written
real-document evaluation with dense-only and resonance-enabled baselines. Include
ambiguous prompts, missing criteria/facts, scope isolation, multi-premise join
authorization, correction/restart/history, five-digit source lifecycle, and
stateless requests. Report wrong answers, appropriate abstentions/clarifications,
citation completeness, latency percentiles, memory, and ingestion cost separately.
Do not count a clarification as a factual answer or a graph edge as an inference.
