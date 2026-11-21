# Frontier Node Design — CPU-LLM

Draft 1. Author: Amin Parva. Based on cpu-llm 1.14.0 (PyPI), which is a few commits behind GitHub main.

Source: https://claude.ai/artifact/HWbQdYLwpz5VZyFUhibLBT (saved verbatim; decisions on the open questions are recorded at the end).

## Purpose

Frontier is a new research node that proposes possible unknown realities about a topic. It works from a large body of ingested material on that topic. Example topic: AI bottlenecks. The node does not depend on any source stating the answer. It builds new meanings from the relations between words and chunks, and keeps a candidate only if it survives the existing reasoning checks. Every output stays labelled `UNVERIFIED_HYPOTHESIS`.

## How it differs from existing nodes

- **Invention** combines cited relationships across chunks and proposes new connections to test.
- **Abductive bridge** emits a hypothesis only when two quoted bounds on one observable conflict and differ on a named regime variable.
- **Frontier** explores the whole relation space instead of one trigger pattern. It generates every combination of related words and chunks, filters them through abductive, deductive and pre-thinker checks, and returns a ranked set of 10 to 50 possibilities.

## Pipeline

1. **Snapshot.** Take one authorized snapshot of the knowledge base for the topic, as the research routes already do.
2. **Relation graph.** Collect related words and chunks for the topic, reusing relationship-loop search and its round limits (default 1,000, ceiling 100,000).
3. **Exhaustive generation.** Enumerate candidate combinations of relations across chunks. Do not prune by preference up front. Generate in streamed batches so the full set never sits in memory at once.
4. **Abductive check.** Each candidate must form a coherent explanatory relation between its anchors.
5. **Deductive check.** Each candidate must not contradict its cited premises, and must follow from them under the stated assumptions. This step also gives a relevance score.
6. **Pre-thinker validation.** A further sanity layer rejects candidates that are malformed, circular, or trivially restate a source.
7. **Scoring and ranking.** Score the survivors and keep the top N.
8. **Reply.** Return the ranked list with citations, scores and a falsification check for each.

## Scoring

Each surviving hypothesis carries three visible scores, shown at the end of its entry:

- **Source support:** how strongly cited passages back its premises. This is the primary ranking factor.
- **Deductive relevance:** how directly it follows from the premises and fits the question.
- **Novelty:** how far it goes beyond anything stated in a single source.

Default order: source support, then deductive relevance, then novelty. The user sees all three, so they can judge each possibility for themselves.

## Output

- Between 10 and 50 possibilities, with 50 as the hard cap. Fewer are returned if fewer survive, and that shortage is reported rather than padded.
- Each entry: hypothesis text, cited source IDs and quotes, the three scores, and a proposed falsification test.
- The standard invention note is appended: proposals are hypotheses, may contain errors, and can vary between runs.
- Strict evidence mode disables Frontier.

## Trigger

Proposed prompt forms: `Frontier: <topic>.` in chat, `frontier=True` in Python, and `"frontier": true` over HTTP.

## Budgets and limits

- Generation runs under round, time, memory and candidate-count budgets, like cycle search.
- If a budget stops generation early, the reply says the search was incomplete.
- The node never promotes a claim to verified and never writes hypotheses into the index.

## Open questions

- Exact formulas for the three scores, and their weights.
- Batch size and default budgets for streamed generation.
- What the pre-thinker layer checks, in detail.
- Whether Frontier runs alongside the existing Research methods or as its own route.
- Benchmark: an AI-bottlenecks corpus with held-out facts, to see whether Frontier rediscovers them.

## Decisions on the open questions (implementation, 2026-11-21)

Implemented in `src/cpu_llm/frontier.py`; tests in `tests/test_frontier.py`; evaluation in
`docs/reviews/2026-11-21-frontier/report.md`.

- **Score formulas.** Each is in [0, 1] and is shown on every entry.
  - *Edge support* = 0.80 for an assertive source sentence, 0.55 for a hedged one (may, could, suggests …),
    +0.10 per additional source document stating the same edge (at most +0.20), +0.05 when the sentence
    carries a numeric bound (detected with the abductive bridge's bound parser); capped at 1.
  - *Path support* = the weakest edge on the path.
  - **`source_support`** = noisy-or over up to five independent supporting paths:
    `1 − Π(1 − path_support)`.
  - **`deductive_relevance`** = `0.5 × composition certainty + 0.3 × share of focus words found in the cited
    sentences + 0.2 × share of focus words found in the hypothesis terms`. Certainty is 1.0 for exact
    same-sign composition, 0.95 when a `causes` edge is involved, 0.85 for constrain→increase, 0.7 for
    mixed readings (`affects`), 0.6 through `has`, ×0.8 per bridge that joins two different terms with the
    same head noun, ×0.9 per edge beyond two.
  - **`novelty`** = `0.5 × (1 − largest share of the hypothesis's content words found in one cited sentence)
    + 0.3 × min(1, (distinct source documents − 1) / 2) + 0.2 × separation`, where separation is 1.0 when
    the endpoints never share a chunk, 0.75 when they share a chunk but no sentence, 0.5 when they share
    a sentence without a relation cue.
  - **Weights/ranking.** Lexicographic, as specified: source support, then relevance, then novelty, each
    rounded to two decimals for the comparison, then the hypothesis ID for a stable tie-break.
- **Batch size and budgets.** `FrontierLimits` (validated like `CycleLimits`, charged on the shared
  `cycle_exploration.Budget` ledger): `max_rounds` 1,000 (ceiling 100,000; one round = one batch),
  `batch_size` 256 (≤ 10,000), `max_candidates` 200,000 (≤ 2,000,000), `max_edges` 50,000 (≤ 200,000),
  `max_bytes` 64 MiB (≤ 128 MiB, estimated as in cycle search), `max_seconds` 60 (≤ 120; raised from 20 once dependency parsing was added),
  `max_path_edges` 2 (2 or 3), `max_results` 50 (hard cap 50), `min_results` 10.
- **Pre-thinker checks.** Malformed (empty, over six words, leading/trailing preposition or determiner,
  pronoun, quantifier phrase, count or time span, broken token, bare adjective or comparative, vague head
  such as *way*, *method*, *result*); circular (an endpoint repeats or contains another term on the path, or
  the two sides of a pair share a head noun); single source (all premises from one source document,
  paragraphs of one file counting once); restatement (one snapshot sentence names both ends and carries a
  relation cue, following the invention node's abstention on co-mentioned pairs). PrismThinker is not
  called: its heads score retrieved evidence for the ordinary answer and need a reasoning context that
  Frontier candidates do not have.
- **Route.** Frontier is its own pre-graph route, not a fourth Research method. Adding it to Research would
  change that route's output and cost; the handoff asks not to change existing nodes without approval.
- **Benchmark.** Built: 64 arXiv papers, nine held-out findings. Results in the review report.

## Improvements after the first evaluations (2026-11-21)

- **Dependency parsing.**
  - With spaCy installed (the optional `prompt_nlp` extra) and an English model available, relations come from
    the dependency parse rather than regular expressions:
    - subject, verb and object from `nsubj`/`csubj`, `dobj` and particle verbs;
    - passive voice through the `agent`;
    - conjoined subjects and objects;
    - negation from `neg`;
    - noun phrases built from modifiers plus one *of*/*for* complement.
  - It also reads identity claims ("is a form of", "consists in", "is identical to", "is nothing but") and
    skips questions.
  - Only sentences with a relation cue are parsed.
  - The model is chosen as `en_core_web_lg` first, then `en_core_web_sm`. `FRONTIER_PARSER` names a model, or
    `regex` forces the original reader, which stays as the fallback.
  - The receipt records the parser in `parser`.
- **Encoder bridge check.**
  - When the appliance has an encoder, the node encodes every term that could join another term by head noun.
  - A bridge between two different terms is accepted only at cosine ≥ 0.6, and its certainty becomes that cosine
    (capped at 0.95) instead of a flat 0.8.
  - The receipt records `bridge_check` (`encoder` or `head_noun`) and `encoded_terms`.
- **Hub spread.**
  - At most three of the returned entries may share a bridge or hub term while other candidates remain; further
    entries for that term are moved behind them.
  - This only re-orders the list: no entry is dropped and nothing is padded. `hub_deferred` counts the moved
    entries.
- **Term hygiene.** Terms that start with a question word or subordinator, and bare symbols, are rejected.
