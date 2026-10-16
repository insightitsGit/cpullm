# Handoff: v1.8 event-frame correctness and design gaps

**ID:** HO-cpullm-002  
**Date:** 2026-10-16  
**Baseline:** `dfeb132fa7b03b344a180762c2cbbe72e12e8cef`  
**Status:** Review complete; fixes proposed, not implemented.  
**Audience:** Agent implementing the next correctness patch.

## Assignment

Fix the seven reproduced stage-1 failures below, preserve the existing supported apple examples, and add regression tests. Start by reading [design v1.8](cpu-llm-v1.8-semantic-memory.md), `tests/test_frames.py`, and the relevant pipeline/reply functions. Recheck findings against your current checkout if HEAD has moved.

Keep this patch focused on stage-1 correctness. Stages 2–5 are explicitly deferred in the design. Do not implement entity resolution, general semantic parsing, a new embedding, ownership inference, or multi-user serving as a prerequisite to these fixes. Reject unsupported constructions safely until their semantics are represented.

The review covered the latest diff and the surrounding ingestion, retrieval, cognition, realization, audit, grounding, and lexical-memory paths. It was not an exhaustive audit of every repository path. No production code was changed during the review.

## Core invariant

A source word occurring in the output does not prove the output preserves the source's meaning. A sentence round-tripping through the realizer does not prove its internal roles were parsed correctly.

Every visible frame claim must preserve the source event's participants, attachments, polarity, modality, conditions, and temporal scope. An unsupported construction must produce a clear non-answer. A final delivery rejection must remain authoritative.

## Required fixes, in priority order

### F1 · P1 · Frame output overrides a Shine rejection

**Where:** `_shine`, `_after_shine`, `_else_frame`, `_frame` in `src/cpu_llm/pipeline.py`; `compose_reply` in `src/cpu_llm/agents/reply.py`.

**Current behavior:** Shine checks `answer` before the frame node. A rejection can set `shine_ok=False`, replace `answer` with the fallback, and set `shine_enforced=True` without setting `delivery_blocked`. Frame routing checks only `delivery_blocked`. Reply then replaces the visible text with the frame sentence.

**Reproduction:** Construct a state with the normal apple passage, `frame=True`, `shine_ok=False`, `shine_enforced=True`, and the grounding fallback as `answer`. `_after_shine` returns `frame`; `_frame` followed by `compose_reply` emits `The apple John ate was yellow.` This is a node/state reproduction; the review did not establish that live Shine rejects that ordinary apple passage.

**Suggested fix:** Explicitly propagate the final delivery decision and enforce it at routing and composition. A rejected state must not gain a factual Event section or replace the fallback. Verify frame candidates against their own evidence and transformation before delivery; simply rerunning a lexical gate is insufficient for F2–F5. Add a frame-specific verification status so `audit_passed` on the original `answer` is not mistaken for verification of `reply.text`.

**Acceptance:** Test the rejected state above, normal frame success, blocked guard/audit/grammar paths, and a combined optional-agent reply. Assert on the actual delivered string, not just routing or `answer`.

### F2 · P1 · Object head is guessed from the last content token

**Where:** `_roles`, `_head`, `_agent_answer`, `_grounded` in `src/cpu_llm/memory/frames.py`.

**Reproduction:**

- Source: `John ate a picture of the apple in his house.`
- Question: `Who ate the apple?`
- Actual: `John ate the apple.`

Also, `John ate the apple with Mary in his house.` records Mary as the patient.

**Suggested fix:** Define a closed stage-1 clause grammar and full-match its components. Accept only object forms whose head and attachments are established by that grammar. Initially reject nested objects, unsupported prepositional attachments, coordination, and subordinate clauses. Keep the accepted direct object span intact; remove the last-token fallback for arbitrary phrases. A small explicit grammar is sufficient; a general parser/model is not required.

**Acceptance:** Neither source may produce an incorrect apple/Mary event. The first should be rejected unless picture-as-object is explicitly supported. Retain the apple color/location/who examples.

### F3 · P1 · Conditional text becomes an unconditional event

**Where:** `frame_from_chunk`, `_roles`; inspect `proposition_from_chunk` in `src/cpu_llm/clauses.py` to understand why opaque object text can round-trip.

**Reproduction:**

- Source: `John ate a yellow apple if Mary cooked dinner.`
- Question: `Who ate the dinner?`
- Actual: `John ate the dinner.`

**Suggested fix:** Until stage 2, reject conditional, hypothetical, uncertain, and reported constructions at frame extraction. Prefer an explicit accepted grammar over a growing blacklist. Round-trip success remains necessary but is not sufficient. Avoid expanding the existing proposition parser's behavior across the entire engine unless required and separately tested.

**Acceptance:** The conditional source must not create an unconditional frame or answer. Add supported/rejected fixtures for conditions, uncertainty, negation, and contractions; label new fixtures as proposed tests rather than previously reproduced failures.

### F4 · P1 · A prefixed year is ignored

**Where:** frame question regexes, `frame_trigger`, `_parse`, `_matches`.

**Reproduction:**

- Source: `John ate a yellow apple in his house.` (undated)
- Question: `In 2020, what color was the apple John ate?`
- Actual: yellow.

Regex `search` matches a suffix and discards the year. The design requires matching time evidence when the question names a year.

**Suggested fix:** Parse the entire supported question into a single query record shared by trigger and resolution. Either support the prefix and enforce it, or explicitly classify it as unsupported. Never silently drop an unconsumed semantic constraint. Apply the same rule to location and agent questions if dated variants are accepted.

**Acceptance:** Undated evidence cannot satisfy a dated query. Test matching/different years, prefix/suffix positions, and unsupported date forms. Unsupported questions must visibly abstain rather than silently falling through to a seemingly responsive event sentence.

### F5 · P2 · Present evidence becomes a past color claim

**Where:** `_color_answer`, query tense matching.

**Reproduction:** `The apple is yellow.` plus `What color was the apple?` produces `The apple was yellow.`

**Suggested fix:** Preserve source tense and match the requested temporal scope. For this past question, abstain on present-only evidence. Do not fix it merely by changing `was` to `is` while ignoring the question's past constraint. If present questions are added, treat that as an explicit supported grammar extension. Function words must follow permitted transformation rules; their presence on an allowlist does not authorize changing tense.

**Acceptance:** Past color evidence still answers a supported past question; present-only evidence cannot assert a past state. Test plural agreement if plural subjects remain accepted.

### F6 · P2 · Missing requested roles do not visibly abstain

**Where:** `_empty`, `resolve_frames`, `compose_reply`.

**Reproduction:** `John ate an apple in his house.` plus `What color was the apple John ate?` returns a resolver gap with empty text and `abstained=False`; reply falls back to `John ate an apple in his house.`

**Suggested fix:** Give results an explicit status such as `answered`, `missing`, `ambiguous`, `conflicting`, or `unsupported`. Preserve existing result keys for compatibility where practical. For a recognized role request, put a clear missing-role/non-answer message in `reply.text`, preserve evidence and gaps, and keep `answer`'s existing checked-sentence meaning. Do not infer success from nonempty result text because conflict messages are also nonempty.

**Acceptance:** Assert both structured result and delivered reply for missing color/location/agent, no matching frame, conflict, and successful response. Test the same outcomes with another optional agent enabled.

### F7 · P2 · Provenance identifies the wrong occurrence

**Where:** `_locate`, `_spans_match`, role extraction.

**Reproduction:** `The apple seller ate a yellow apple in his house.` records patient `apple` at `[4:9]` within the subject; the actual object is `[30:35]`. The slice check passes because both mentions contain the same text.

**Suggested fix:** Retain offsets directly from grammar captures in the original sentence. Validate that patient/color spans lie within the parsed object and agent within the subject. Avoid unrestricted `sentence.find`. State whether ranges are sentence-relative or chunk-relative, and retain sentence origin when these differ.

**Acceptance:** Check exact expected offsets for repeated nouns and substring collisions, not merely `sentence[start:end] == text`.

## Suggested patch structure

1. Add regressions demonstrating F1–F7 before changing behavior.
2. Close the delivery bypass and enforce it again at reply composition.
3. Introduce a conservative extraction grammar with capture offsets; solve F2, F3, and F7 together.
4. Use one complete query parser for triggering and matching; solve F4 and F5.
5. Add explicit outcomes and visible abstention for F6. Ensure blocked delivery takes precedence over all outcomes.
6. Add candidate verification and evidence/derivation metadata without representing the frame as a newly stored fact.
7. Update documentation and run focused tests, then ingest → ask → reply integration tests.

Small internal typed models for frame, query, outcome, and derivation are recommended. Keep any public dictionary representation stable where possible, and document schema changes. A derivation should identify the source/proposition, role bindings and spans, source tense/scope, and the allowed transformation. Validate those bindings before rendering the candidate.

`_assimilation` stores `event_frame`, but `_frame` currently reparses retrieved text and discards the appliance. Decide and document the authoritative record path. Prefer versioned stored frames with explicit legacy extraction/backfill; avoid two independent extractors that can disagree. A durable role index is still stage 4 and is not required for this patch.

## Design recommendations for follow-up work

These are architectural recommendations, not additional reproduced regressions in the latest commit:

- **Separate ambiguity from contradiction.** Two people eating apples or two locations may describe distinct events. Do not choose a winner; retain conservative abstention until identity and temporal overlap establish that values actually conflict. Define event IDs before relaxing current behavior.
- **Qualify evidence completeness.** Stage 1 sees retrieved candidates only. One value in a shortlist does not prove corpus-wide uniqueness. Stage 4 needs role-key recall and coverage metadata, with dense retrieval as an additional candidate path.
- **Plan lifecycle fields early.** Tenant/source IDs, source revision/hash, sentence/role offsets, extractor/schema version, and event IDs should support later deletion and correction. Define invalidation of frames, aliases, lexical definitions, derived edges, and caches before multi-user serving.
- **Keep phrase semantics separate from lexical recall.** `consolidation/sleep.py` currently creates Cartesian products of subject/object words as `INSTANCE_OF`. Individual adjective/noun tokens are not necessarily logical instances of each object token. Use phrase/entity nodes for inference; retain word associations for recall. Review separately from the frame patch.
- **Use measurable acceptance.** Add a labeled corpus of supported and rejected constructions. Track extraction precision and coverage, unsupported answers, abstention correctness, candidate recall, and CPU latency. Zero unsupported answers on a curated release set is a useful gate; it is not a universal soundness proof.
- **Reconcile current documentation.** Add frame routing to the white paper, document `frame_result` and Event reply behavior, synchronize dependency pins with `pyproject.toml`, and align numeric/descriptive routing descriptions with the implemented handoff. Mark historical contracts clearly.

Stages deliberately deferred: stage 2 negative/conditional/uncertain frames; stage 3 entity IDs/aliases; stage 4 durable role indexing; stage 5 tenant boundaries/deletion/corrections. Stage 1 is a single-sentence role projection, not a general cross-sentence join. Do not infer ownership from `his house`, invent a causal edge or target, or expand embeddings to address these correctness issues.

## Reproduction starter

Run from the checkout with the installed dependencies. This prints current behavior; after a fix, the bad cases should abstain or become unsupported rather than reproduce the shown claims.

```python
from cpu_llm.memory.frames import frame_from_chunk, resolve_frames
from cpu_llm.pipeline import _after_shine, _frame
from cpu_llm.agents.reply import compose_reply

cases = [
    ("John ate a picture of the apple in his house.", "Who ate the apple?"),
    ("John ate a yellow apple if Mary cooked dinner.", "Who ate the dinner?"),
    ("John ate a yellow apple in his house.",
     "In 2020, what color was the apple John ate?"),
    ("The apple is yellow.", "What color was the apple?"),
    ("John ate an apple in his house.", "What color was the apple John ate?"),
]
for source, question in cases:
    frame = frame_from_chunk("review-1", source)
    result = resolve_frames(question, [frame] if frame is not None else [])
    reply = compose_reply({
        "message": question, "frame": True,
        "answer": source, "frame_result": result,
    })
    print(source, question, result, reply["text"], sep="\n")

print(frame_from_chunk(
    "review-offsets", "The apple seller ate a yellow apple in his house."
))

state = {
    "message": "What color was the apple John ate?", "frame": True,
    "shine_ok": False, "shine_enforced": True,
    "answer": "I don't have enough grounded evidence to answer that confidently.",
    "passages": [{"document_id": "review-1",
                  "chunk_text": "John ate a yellow apple in his house."}],
}
print("route:", _after_shine(state))
state.update(_frame(None)(state))
print("delivered:", compose_reply(state)["text"])
```

## Validation already performed and remaining

- All 6 existing frame tests passed.
- All 42 focused tests passed across `test_frames`, `test_invariants`, `test_clauses`, `test_reply`, `test_descriptive_regime`, `test_lexical_relations`, and `test_cortex_sleep`.
- F1–F7 were reproduced through actual extraction/resolution/routing/composition functions. These are not live end-to-end claims.
- The full suite was interrupted after setup errors and a prolonged stall. A sandbox temp-directory issue was resolved for the focused suite using a writable `--basetemp`. Local PostgreSQL access was denied in the sandbox; an unsandboxed pipeline retry also stalled and was interrupted. No end-to-end pass is claimed.

Suggested focused command:

```powershell
python -m pytest tests/test_frames.py tests/test_invariants.py tests/test_clauses.py tests/test_reply.py tests/test_descriptive_regime.py tests/test_lexical_relations.py tests/test_cortex_sleep.py -q
```

Use a fresh writable `--basetemp` if required. Provision the existing local PostgreSQL/encoder dependencies for integration testing; do not silently replace the real ingestion/retrieval path with mocks and call that an integration pass.

## Definition of done for the receiving agent

- F1–F7 regressions pass and original supported examples remain correct.
- Every delivered frame claim has explicit verification against its own source roles and permitted transformation.
- Rejected delivery cannot be overridden by frame or mixed-mode composition.
- Missing/unsupported/ambiguous/conflicting outcomes are visible and machine-readable.
- No unsupported condition, role attachment, date, or tense is silently discarded.
- Tests cover actual `reply.text` and provenance offsets, not only intermediate success flags.
- Run a real ingest → ask → reply check for success and abstention, plus controlled delivery-rejection integration coverage. Report exact commands, outcomes, and any remaining environmental limitations.
- Documentation states supported grammar, outcome fields, source-of-truth behavior, and remaining stage limits.
- Report changed files, validation, compatibility/migration decisions, and remaining risks. Do not claim full-corpus soundness from example tests.
