# Deepen research strengthening: implementation and verification

Date: 2026-11-21. These changes are unreleased source changes after 1.15.0;
the already published 1.15.0 artifacts were not modified or republished.

Specification: [seven enhancements](../../deepen-research-strengthening-spec.md).
Usage: [Deepen](../../deepen-node.md).

## Implementation

The existing Frontier and Deepen routes are retained. Research assessment lives
in `src/cpu_llm/deepen_review.py`; it annotates candidates rather than pruning or
re-ranking them. No new competing specialist or KB-writing route was introduced.

- Endpoint labels that differ from their requested bridge receive review notes
  with original citations. Explicit differing source settings also require review.
- Component verdict, composition assessment, interaction status and scientific
  validity are distinct. Source support is not empirical validation.
- Plans contain variable roles, cited measurement hints, bounded user-supplied
  definitions/protocol, missing requirements, readiness and `executed: false`.
  Interaction falsification is distinguished from individual-effect falsification.
- Outcome predictors, candidate shared causes and possible downstream variables
  are distinguished with evidence. None are adjusted automatically. A prior
  gerund heuristic that discarded valid terms such as cooling demand was removed.
- Source qualifications remain cited; structured context and plain-text context
  labels are retained. Scope differences are review concerns, not silent rejection.
- Scoped session follow-ups re-read authorized sources, focus on distinct unmet
  requirements, track content changes and stop claiming progress when inputs
  are missing. Presenting a requirement does not mark it resolved. Different
  requests supersede the previous Deepen focus; alternatives can use separate
  sessions.
- Optional novelty review finds potential co-mention overlap in the snapshot.
  An operator-supplied literature callback additionally requires explicit request
  opt-in. External records remain separate, unverified overlap candidates. No
  external literature service was configured or contacted in the replay.

## Tests

Final related routing, policy, access, planning, research, Frontier and Deepen
selection: **321 passed, 1 skipped, 1 deselected** (7.79 seconds).
The skipped case requires a named spaCy English model in the host installation;
the live replay used the compatible model stored in the workspace.

Local HTTP strict-policy tests: **3 passed** (2.03 seconds). Their first sandboxed
attempt could not connect to localhost; rerunning with local network access
passed. This gives 324 passing checks across the two final selections.

The deselected benchmark assertion already fails at HEAD: the fresh gold
generator's contract is `request-pipeline-gold-v3-fresh`, while its test expects
`request-pipeline-gold-v2-fresh`. Neither file was changed by this implementation.
The initial broader run exposed this mismatch. It remains unrelated outstanding
test maintenance, not a changed Deepen behavior.

A full-suite attempt was interrupted after progress stalled early. No complete
full-suite pass is claimed. Compilation and `git diff --check` also passed.

## Real AI-bottlenecks replay

Ran the existing isolated PostgreSQL corpus at the recorded snapshot, with the
real encoder and workspace spaCy dependency model. No source records were changed.
The [replay script](replay.py) records SHA-256 hashes of the five implementation
files and verifies that they did not change during execution.

- Full corpus: 64 sources, 1,054 chunks.
- Focused energy/memory source scope: 25 sources, 360 chunks.
- Frontier returned **7 hypotheses** both without and with leading Deepen checks.
  Candidate IDs, texts, ordering and all scores matched exactly.
- The leading H2O/vLLM proposal remained available. Its legacy verdict was
  `all_links_supported`, composition was `requires_review`, interaction was
  `untested`, and plan readiness was `needs_input`.
- The hardware-memory-access/institutional-compute-access proposal also remained
  available but received an explicit bridge warning. It was not certified valid.
- Two `Go deeper` turns focused respectively on bridge review and intervention
  levels for implementation of H2O. Both reported unchanged source content and
  did not repeat the full initial plan.

Raw results: `build/deepen-strengthening-replay/results.json`.
Exact responses: `build/deepen-strengthening-replay/responses.md`.
Execution log: `build/deepen-strengthening-replay.log`.
Test logs: `build/deepen-strengthening-final-tests.log` and
`build/deepen-strengthening-http-tests.log`.

## Limits

Semantic and context checks are conservative heuristics, not a complete ontology
or causal identification method. Measurement hints require review. A specified
plan is not a power analysis or a completed experiment. Novelty scanning is
bounded by available sources; absence is not novelty. External adapter timeouts
are cooperative, checked before/after the call. No new scientific discovery,
accuracy percentage, or arbitrary computational execution is claimed.
