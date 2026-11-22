# Deepen research strengthening

Status: implementation specification, 2026-11-21.

## Preserve breadth

Frontier's enumeration, ranking, diversity rules, result cap and existing filters
remain unchanged. New assessments annotate candidates; they do not select a single
answer or silently discard alternatives. Every proposal remains an
`UNVERIFIED_HYPOTHESIS`, promotion blocked, with no KB write.

## Seven enhancements

1. Semantic bridges: inspect source endpoint labels and explicit source context.
   Flag changed modifiers and differing meanings/settings for review. Lexical or
   embedding agreement is not proof of semantic identity. Retain the hypothesis.
2. Separate component-link verdict from composition and interaction assessment.
   Surface counter-evidence, unsupported bridges and assumptions independently.
   No new assessment claims causal validity.
3. Operational plans: accept user-supplied variable definitions, intervention
   levels, units, measurements, feasibility and experimental protocol. Missing
   values become explicit requirements; no invented units, samples or thresholds.
   User definitions remain assumptions, not source evidence. Distinguish a test
   of interaction from a test of individual effects.
4. Candidate controls: an additional outcome cause is not automatically a
   confounder. Look for source-stated causes of both exposure and outcome, and
   identify downstream variables that should not be controlled automatically.
5. Preserve cited qualifications and context: retain source condition/quantifier
   sentences, hedging and optional row `research_context` metadata (domain,
   population, workload, model, version, regime, temperature). Plain-text labels
   such as `Workload: long prompts` survive normal ingestion and are also read.
   Scope differences
   require review rather than universalizing source claims.
6. Progressive session follow-ups: `Go deeper` / `Explain more` after Deepen
   re-read an authorized snapshot and focus on unresolved requirements. Record
   source changes and addressed actions; do not claim new evidence when unchanged.
   Once the queue is exhausted, explicitly request missing inputs. Keep session
   isolation by tenant, caller, allowed sources and snapshot request, TTL and caps.
7. Optional novelty review: scan the authorized KB for cited potential overlap.
   Never equate absence in the KB with scientific novelty. An operator-configured
   literature reviewer may be invoked only by an explicit external-review option;
   its bounded source records are separate from KB evidence. Default: no network.
   Return overlap candidates for human inspection, not certified novelty.

## API

Existing text and structured Frontier hypotheses remain valid. New envelope:

```python
app.ask('Examine this proposal.', session_id='research-1', deepen={
    'hypothesis': selected_hypothesis,
    'definitions': {
        'throughput': {'measurement': 'completed tokens / elapsed time', 'unit': 'tokens/s'},
        # Use exact labels from the selected hypothesis, not inferred aliases.
        'implementation of H2O': {'levels': ['disabled', 'enabled'], 'feasible': True},
    },
    'protocol': {'replicates': 10, 'acceptance_criterion': 'pre-registered interaction contrast'},
    'novelty': True,
    'external_review': False,
})
app.ask('Go deeper.', session_id='research-1')
```

Definitions and protocol are optional, bounded, validated JSON. Unknown envelope
fields request clarification. Novelty review is off unless requested. Registered
reviewer contract: `reviewer(query=..., max_results=6, timeout_seconds=...)`
returns a list of records with `title`, HTTPS `url`, and `excerpt`. It must honor
the timeout; in-process callbacks cannot be forcibly interrupted. No credentials
or arbitrary request-supplied endpoints are accepted. Registration is deployment
authorization to send hypothesis terms; request opt-in is also required.

## Verification

Regress semantic collisions, qualifications, distinct source contexts, positive
and negative composition, outcome-only versus shared-cause controls, missing and
provided operational definitions, interaction-specific falsification, session
progress/exhaustion and isolation, strict/guard precedence, KB novelty overlap,
reviewer off/opt-in/failure, invalid inputs and shared-budget exhaustion. Compare
Frontier candidate texts and scores before/after; breadth must remain unchanged.

These checks strengthen literature-based proposal review; no arbitrary simulation
execution, literature completeness guarantee, or statistical identification claim
is introduced.
