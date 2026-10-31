# Stylistic generation node: integration design

Status: staged implementation specification, reviewed against runtime `b603485` on October 30, 2026. **Stage 1 now implements a two-construction, verified companion-output node.** The broader lexicon, ten-channel tone classifier and ranked surface-generation system below remain proposed. No production-readiness or universal meaning-invariance claim is made.

## Implemented stage 1 and measured scope

`Appliance.ask(..., style="formal" | "friendly")` adds an opt-in `stylistic` result. `None` takes the unchanged default path and imports/compiles no style graph. The new `stylistic -> style_verify` ChorusGraph subgraph runs after request dispatch has settled canonical judgments and repair, before rendering. On batches it visits completed child results separately. Because stage 1 emits only companion metadata, existing aggregation and visible replies remain unchanged; it does not yet implement the later publication/subgraph placement described below.

The adapter snapshots a very small direct-decision subset: affirmative individual `has_color` or `lives_in` decisions, a matching named subject, one literal accepted source proof, no added constraints or nested clauses. It supports `X is COLOR.` -> `The color of X is COLOR.` for formal style, and `X is found in PLACE.` -> `You can find X in PLACE.` for friendly style. Article capitalization is adjusted at the interior sentence position. A separate inverse grammar checks subject/value identity, construction ID, snapshot fingerprint and the entire proof tuple. No learned model, lexicon similarity, tone/intensity scoring or external service is used.

Generated text is in `result["stylistic"]["text"]` with a closed-construction verification record and original source proof. It is a **derived paraphrase**, not a source quotation. `reply.text`, `answer`, audit/judgment/status fields and source evidence stay canonical, including when the original status is `evidence_quote`. The sidecar cannot establish source truth. Unsupported frames/profiles/constructions skip safely; graph failures reject style without rewriting the answer. The feature does not repair wrong retrieval, infer missing facts, generate long creative passages or automatically turn user tone into instructions. Profile selection is explicit API-only, request-local; it is not inherited into future session turns and is not exposed through HTTP request models yet.

See the [machine-readable stage-1 spec](stylistic-generation-spec.json) and [saved smoke evaluation](benchmarks/2026-10-30-stylistic-smoke/REPORT.md). The rest of this document describes the target architecture and outstanding work; its proposed `StylePlan`, general `CanonicalEnvelope`, SoA lexicon and atomic visible publisher are not delivered stage-1 APIs.

## Intent retained

Add a CPU-oriented agentic node that realizes already accepted meaning in a requested tone and relationship register. Preserve the proposal's ten tone channels, POS masks, three intensity axes, relationship constraints, deterministic ranking, specificity preference and array-oriented lexicon. Separate reasoning from expression: style is never a source of new facts or an authority to change an answer's meaning.

Tone is separate from VectorPrism's six retrieval/semantic channels. Neither vectors nor a high lexical score prove equivalence. The feature initially supports English and a finite, audited construction/lexical set. Broader creative composition is a separate capability and must not inherit factual verification.

## Existing implementation and boundaries

- `src/cpu_llm/pipeline.py::_compile` registers the current ChorusGraph nodes. `model01` precedes `reply`; the graph ends after optional `discover`. `_ask_single` can subsequently apply a realizer or replace the reply with a ranking quote/clarification. Inserting style immediately after `model01` or `reply` would therefore be premature.
- `src/cpu_llm/ir/schema.py::EIRProposition` already carries subject/predicate/object, polarity, negation scope, modality, quantifier, condition tree, temporal validity, epistemic status, source span and premise derivation. Reuse it through adapters rather than renaming it or making existing constructors supply style fields. Frozen Pydantic objects can still contain mutable lists; take a deep immutable snapshot at the new boundary.
- `src/cpu_llm/realizer/evidence_schema.py` defines source records, span IDs, plans, actions and derivations; `derivation_check.py` checks constructed realizations. Preserve these contracts. They are a basis for certified constructions, not proof that arbitrary synonym replacement is valid.
- `src/cpu_llm/evidence_judge.py::finalize_turn` checks the delivered sentence against licensed wording and specialist producer contracts. A paraphrase is not currently an accepted alternative merely because it means something similar. Do not loosen `_enforce_licensed` globally or reuse a canonical `shine_final` verdict for rewritten text.
- `request_planner.py` executes child tasks and continuations; `output_rendering.py` renders the resulting answers. Style must respect child-task status, ordered coverage, pending requests and shared response budgets.
- `flag_contract.py::enforce_response_flags` checks an exact set of presentation flags. Adding tone keys to `response-plan-v1.flags` would break the current validator. Use a separately versioned style plan and extend only the new routing boundary.

## Execution placement: a real node in an output subgraph

Keep the existing reasoning graph and canonical delivery judgment intact. Add a small output subgraph, entered per completed child after canonical finalization and post-retrieval repair have settled, and before task aggregation/layout escaping:

```text
existing graph -> existing realization/ranking replacement
 -> canonical finalize_turn -> post-retrieval repair/status decision
 -> [style eligibility -> stylistic node -> independent style verifier -> publication]
 -> existing task aggregation -> existing render_response
```

The stylistic transformer is an actual ChorusGraph node with the existing adapter pattern, not a helper advertised as a graph node. Its invocation belongs at this later lifecycle boundary. The output subgraph must not run another retrieval or alter the established optional-agent order. Canonical early returns must be inspected before entering it.

The independent verifier is the final factual delivery gate for styled text. The old judge remains authoritative for canonical text. Its evidence/status decision is preserved, but its wording verdict cannot certify the new surface. If the new verifier rejects a candidate, publish the already accepted canonical response and record the style failure; never copy the earlier audit flags onto a rejected rewrite.

A registration/enablement check prevents entering the new subgraph twice. Batch children are styled once; aggregation must not restyle them. Sources are escaped only by the existing final renderer.

## Additive, request-local data contracts

Introduce `cpu_llm/stylistic/` inside the existing package. Do not fork a second EIR system or require a new database schema. The following names are new proposed types, not current library APIs.

1. **StylePlan (`style-plan-v1`)**: enabled flag, ten normalized tone affinities, magnitude/valence/arousal, relationship constraints, English locale, profile origin, explicit instruction spans, supported-policy and lexicon versions. Keep style metadata separate from factual query text, retrieval vectors, inference records and `response-plan-v1`. Default: disabled. Explicit API values override explicit output instructions; quoted/document text supplies no style commands. The user's emotional wording is not an instruction to mimic it. Unknown audience defaults to a neutral, restricted register; it does not imply romance.
2. **CanonicalEnvelope (`canonical-envelope-v1`)**: immutable accepted answer, outcome, task ID, canonical text, ordered claim snapshots, proof spans/premise IDs, caller/scope/as-of binding, budgets, producer identity and trusted delivery decision. Every required claim and premise must remain accounted for. Build it from accepted decisions and producer records, never by reparsing arbitrary reply text and calling the result verified.
3. **SemanticFrame**: an adapter view of an accepted EIR proposition, supported event frame or specialist contract. Preserve entity/referent IDs, semantic roles and direction, tense/aspect, polarity and negation scope, modality, quantifiers, conditions, time, numbers/units, uncertainty, source attribution and inference dependencies. Unknown/unrepresentable fields make the frame ineligible for rewriting. Source quotations stay literal. Do not invent a universal SISF adapter for producers whose semantics cannot yet be represented.
4. **StyleCandidate (`style-candidate-v1`)**: proposed text, construction ID, lexicon-entry IDs/senses, per-token or per-clause claim alignment, explicit operations, score components, tie-break key and input fingerprint. No authority to set `audit_passed`, alter evidence, or publish a reply.
5. **StyleVerification (`style-verification-v1`)**: independently recomputed claim/role/coverage checks, relation and register constraints, locked-span checks, complete proof binding, budget check, rejection reasons and verifier version. An input hash detects stale candidates; it does not establish semantic equivalence. Never accept a user-supplied or cached `verified=True` as authority.
6. **StyleResult**: `applied`, `unchanged`, `skipped` or `rejected`, canonical/candidate hashes, applied policy/construction IDs, verifier result and bounded diagnostics. Existing `answer`, `reply.text`, statuses and proof fields keep their public meanings. Once verified, the trusted publisher updates the visible response and relevant wording fields atomically, preserving proof/status and explicitly recording new-surface verification. It must not leave a styled `text` beside an inconsistent `body` or `supported_text`.

Expose no new required parameters. A future optional style argument is keyword-only and threaded explicitly through planner children/continuations. Define serialization/version rejection before adding it to HTTP APIs. A style setting does not enter the fact store or broaden caller scope. Its session lifetime follows existing tenant/caller/session isolation and reset/TTL rules; per-task overrides do not bleed into siblings.

## Meaning eligibility before scoring

POS eligibility and relationship masks are cheap prefilters. Before weighted ranking, require an approved lexical sense and construction that preserves the frame's full denotation. A semantic cosine is only a ranking aid within this eligible pool.

Meaning-bearing adjectives/adverbs, intensifiers, politeness presuppositions, metaphors and causal connectives cannot be added merely to achieve a tone. `said -> bellowed` adds loudness; `miss -> anticipate` changes the predicate; `can -> must` changes modality. Hyperbole is incompatible with locked factual quantities. Different surface expressions need a construction-specific equivalence license, not just synonym labels.

The initial supported transformations should be deliberately small: approved syntactic variants, grammatical inflection and register equivalents with explicit sense/argument constraints. Leave proper names, numbers/units, dates, identifiers, technical terms and quotations locked. Pronoun introduction requires a unique referent and preserved role binding; otherwise retain names.

After constructing the entire sentence, independently check complete claim coverage, roles, scope, attribution, modality and polarity. Slot-local eligibility is insufficient when combined slots change sentence meaning. The verifier checks an allowlisted derivation against the original frame, not the style node's own interpretation of its output. If verification cannot establish the finite construction's contract, retain canonical wording.

## Lexicon and score corrections

Each versioned lexical entry needs a stable ID, lemma, sense/concept ID, POS mask, valency/argument constraints, morphology, register restrictions, approved equivalence classes, base vector, intensity values, tone affinity values and genericness penalty. Define how these labels/vectors are sourced, licensed, curated and reviewed. The original document supplies examples, not a usable dictionary or trained model. Fixed curated entries are sufficient for an initial implementation; no training is implied.

Store arrays of masks, intensities, normalized base vectors, affinities and penalties, with string/sense tables indexed by entry ID. Precompute norms. Do not claim a Python-object list or a Python loop is SoA/SIMD. Validate shapes, finite values, bounds, array consistency, embedding-model ID and dimensions. Define quantization error tolerances before claiming INT8 equivalence; Float32 is the initial reference.

- For a multi-POS request, use `(entry.pos_mask & required_mask) != 0` and deduplicate eligible entry IDs; do not perform an exact lookup of a combined mask in a single-bit index.
- Relationship exclusions use bit membership, not equality. Intersect restrictions for combined contexts; permission never overrides an exclusion. Document the allowed neutral register for unknown contexts and missing labels. Distinguish affectionate familial language from explicitly romantic/sexual diction rather than banning warmth.
- Separate a word's permitted-tone mask from its continuous tone affinities. The proposed mask-only dot product rewards a word marked for every tone and ignores the promised soft profile.
- Normalize valence distance by two consistently in specification and code. Validate intensity bounds and normalized nonnegative tone inputs; reject NaNs/zero-vector invalid inputs rather than quietly scoring them.
- Genericness is a bounded preference penalty among meaning-equivalent options. A common precise word can win; a rare inaccurate word can never win.
- Define deterministic candidate ordering and stable entry-ID/construction-ID tie-breaking. Pin lexicon/model/policy versions and numerical tolerances. Cross-CPU bit-for-bit floating-point identity is a separate, unproven claim; deterministic tie policy must tolerate near-equal scores.
- Empty/masked/low-confidence candidate sets yield canonical wording. Never return `[MISSING_TOKEN]`, a filtered-out first candidate, invented replacement or a partially formed sentence.

Bound vocabulary scans, candidates per slot, slots per sentence, diagnostics, latency and memory. A style timeout/asset absence/candidate rejection is an observable fallback, not a partial factual response. Do not hide programmer/contract errors as successful style application. No CPU performance claims until measured on named hardware, including cold loads and concurrent requests.

## Scope and activation

Initially style only successfully finalized, fully representable factual constructions with explicit style intent. Skip verbatim quotations, conflicts, blocked/unsupported/insufficient-evidence turns, pending clarification/cancellation, execution failures, finance/math outputs, code, formulas and specialist/draft outputs without a matching adapter. These skips preserve content; they do not turn nonanswers into answers. Extend producer adapters one by one with tests.

Requested long/short response budgets remain authoritative. Style cannot add new claims or increase retrieval merely to satisfy a word count. If safe style expansion exceeds a budget, choose a smaller approved construction or retain canonical text; do not truncate a condition, premise or negation. Tables/reports receive styled child content as data; no new template execution is permitted.

Keep the legacy 28-flag registry and response-plan-v1 schema unchanged initially. Add a separately versioned style routing record describing requested/effective profile, eligible/skipped status, actual node execution, verification and fallback. Do not report intent classification as node execution. A later registry revision must explicitly update the mapping, snapshot tests and consumers.

## Missing design requirements and acceptance work

The supplied document's production-ready label is unsupported: its reference code lacks the frame contract, complete sentence realizer, actual runtime wrapper, lexicon provenance, independent verifier, conflict/session policies and meaningful performance validation. Its five acceptance examples add unlicensed facts and cannot be used as semantic-equivalence gold.

Replace them with licensed, independently authored pairs. For example, `The Aster is found in coastal waters.` may allow `You can find the Aster in coastal waters.` only under a reviewed locative construction. `The Aster thrives in pristine coastal waters.` must fail because it adds thriving and pristine conditions. For an input expressing only missing someone, references to a scheduled meeting, returning home, food or shared memories must fail unless those claims are separately supplied and explicitly included in the frame.

Required validation before enabling the node:

1. Disabled/default differential tests preserve current results, status/proof fields, graph order and latency within a declared measured overhead budget; no lexicon/model load or classifier work on the disabled path. Run the existing suite.
2. Structural tests cover multi-POS masks, combined relationships, unknown/missing affinity labels, all-candidates-excluded behavior, input bounds, stable ties and cross-request isolation.
3. Adversarial semantic tests reject dropped/added claims, role reversal, identity change, modality/negation/quantifier shifts, temporal/condition changes, invented emotion and unsupported intensity/metaphor. Verify minimal join proofs and all premise IDs survive.
4. Integration tests cover current exact-wording judge compatibility, later ranking/repair replacements, child batches, continuation/reset/TTL, canonical fallback, atomic publication, injection in style instructions/lexicon/source text, missing assets and HTML/Markdown escaping. Treat the new verifier as a new trusted boundary requiring its own tests.
5. Separate scoring for style adherence, meaning preservation, coverage/proof fidelity, safe fallback and runtime cost. Do not combine them into one quality percentage or claim five examples establish 100% semantic preservation. Use fresh gold and preserve the provisional October 29 benchmark unchanged.

Implementation order: immutable adapters and tests; versioned curated lexicon/constructions; deterministic scorer and whole-sentence verifier; opt-in output-subgraph integration; API/planner/routing documentation; paired neutral/styled benchmark; expand eligible producers only after their contracts pass. Every stage keeps the default path operational.
