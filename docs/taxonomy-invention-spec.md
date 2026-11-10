# Taxonomy-driven invention

Status: implemented in Git source. The current node uses bounded proposal templates with vector ranking.

## Activation

Use `invent=True` in Python or `"invent": true` in HTTP. Natural prompts include “Invention: Helios,” “Invention for Helios,” “Imagine Helios,” “Imagine a new design from the relationships around Helios,” and “Create a new concept from Helios.” The classifier routes each task to one invention path. “Imagine a story about Helios” keeps the existing `gather → imagine` route. Quoted trigger words, negated instructions, factual uses of “new,” and ordinary report requests leave invention off. An explicit invention command without a subject asks for one. The strict-evidence policy disables invention.

## Candidate generation

Explicit hypothesis requests also activate the same route. Examples include
“Guess: Fernhouse,” “Take a guess about Fernhouse,” “Speculate about Fernhouse,”
“Hypothesize about Fernhouse,” and “Brainstorm ideas for Fernhouse.” The same
hypothesis disclosure applies. Factual questions and quoted or negated uses
continue through their existing routes.

1. Start from the named entity and follow one explicit taxonomy level. Gather related words, phrases, and typed edges across authorized chunks. Preserve relation direction, source subjects, and source spans. Category premises retain their category subject. Merge equivalent links while keeping distinct citations. Keep multiword concepts such as “encrypted backups” intact.
2. Use the six slices of the VectorPrism tensor to find and rank promising pairs. Generate candidate typed relationships that are absent from the inspected source graph. Check candidates against direct evidence, duplicates, and contradictions before presentation. Absence from the inspected graph establishes the scope of novelty.
3. Evaluate each candidate with the six channel functions. Record symbolic support, calibrated vector scores where available, and unknown or inapplicable results separately. Dense and identity are the vector heads enabled by the shipped checkpoint. The other four channels can contribute supported symbolic signals. Similarity can rank a hypothesis but cannot establish its truth or prove causality.
4. Compose proposals with cited premises, the proposed relationship, assumptions, tradeoffs, and a way to test it. Keep hypotheses separate from verified claims and out of the factual graph. For example, source facts about Helios using PostgreSQL and storing encrypted backups can motivate a proposal to track key versions in backup metadata. The proposal retains both source citations as premises.

The node reuses scoped snapshot retrieval, the graph fact extractor, channel evaluation, and response rendering. The invention-specific source pass also extracts explicit `uses` and `stores` premises and retains their source spans. Candidate selection uses up to 32 premise records and emits up to eight proposals. Pairs already connected or discussed together in a source sentence are conservatively excluded. The existing Imagine path arranges source material.

## Response contract

Set `invention.triggered=true` and `invention.potentially_nondeterministic=true` whenever the node runs. Append this note after the response body in every supported layout, including when the node returns zero candidates or stops after partial work:

> Invention note. Proposals from the invention node are hypotheses. They may contain errors and can vary between runs.

The structured flag and visible note must survive formatting and mixed-request aggregation. Keep factual claims and their citations distinct from hypotheses throughout the response. Use existing request budgets to bound candidate generation and report partial coverage when a limit is reached.

## Fernhouse test record

The run used the shipped CPU encoder and five fictional source chunks supplied through a fixture snapshot.

```text
[greenhouse-p0001] Fernhouse is a greenhouse controller.
[greenhouse-p0002] Fernhouse uses soil moisture sensors.
[greenhouse-p0003] Fernhouse stores irrigation event logs.
[greenhouse-p0004] Fernhouse uses outdoor weather forecasts.
[greenhouse-p0005] A greenhouse controller uses a valve scheduler.
```

Exact prompt:

```text
Invention: Fernhouse.
```

The run returned `hypotheses` and six proposals. This is the first proposal exactly as returned:

```text
1. Proposed design: Prototype a shared interface between soil moisture sensors and irrigation event logs.
This assumes both components expose an interface that can be adapted.
A shared interface could reduce coordination work and introduce an additional dependency.
Test: Compare a small integration prototype with the existing workflow and measure failures and manual steps.
Cited premises:
[greenhouse-p0002] Fernhouse uses soil moisture sensors.
[greenhouse-p0003] Fernhouse stores irrigation event logs.
```

The proposals followed this order. Scores below are dense-channel similarities rounded to three decimals.

1. Soil moisture sensors and irrigation event logs (0.745).
2. Soil moisture sensors and outdoor weather forecasts (0.650).
3. Irrigation event logs and a valve scheduler (0.624).
4. Irrigation event logs and outdoor weather forecasts (0.607).
5. Soil moisture sensors and a valve scheduler (0.557).
6. Outdoor weather forecasts and a valve scheduler (0.516).

All six used the same shared-interface wording, assumption, tradeoff, and test, substituting the corresponding pair and citations. The response ended with the invention note above. “Create a new concept from Fernhouse.” also returned six hypotheses.

The proposed connections were new within these five records. For example, the fixture documents the sensors and event logs separately. The proposed interface joins those premises. The valve-scheduler citation continues to describe greenhouse controllers as a category, so the response does not attribute a scheduler to Fernhouse. The test measures novelty within this fixture, with no search for prior designs elsewhere.

The repeated template limits the diversity and specificity of these results. A more developed design could compare soil moisture before and after each watering event to detect watering that failed to reach the soil. That was a design example discussed after the run. The recorded node output was the shared-interface proposal above.

## From research brief to hypothesis

When a source labels a candidate mechanism and explicitly connects it to an outcome, the invention node uses the research brief to retrieve nearby typed relationships. It preserves the original mechanism quote and distinguishes proposed mechanisms from other source statements. The six channel results are recorded for the candidate and related links. Vector similarity ranks related links and cannot establish causation or supply a missing outcome.

The hypothesis asks whether a parameter region can reproduce the target outcome while satisfying independent empirical constraints. The node looks for reported numeric bounds in separate chunks that mention an observable linked by the mechanism citation. It retains the experimental quote and span. A model must map the same parameters to the cosmological outcome and the laboratory observables before a numerical boundary can be computed. An empty intersection would exclude the tested parameter range under the model's assumptions. Missing bounds are reported explicitly. If the outcome cannot be extracted, the node returns a research question. If several mechanisms match equally, it asks which one to investigate.

## Conversation follow-ups

Use the same `session_id` for `Invention: Helios` and `Can you explain more?`. The node retains the proposal's endpoints, relation direction, channel results, and cited premises. If several proposals are available, it asks which one to expand. Use `Explain proposal 2` to select one, then `Go deeper` to continue with it.

The first follow-up outlines a prototype test and searches authorized source records for typed relationships that touch the proposal endpoints. The second adds controls and looks for relationships connected to terms found in the first follow-up. Each expansion adds up to four cited relationships. After two expansions, the node asks for a constraint, test result, or additional source.

Follow-up state is held in memory for up to 30 minutes of inactivity and scoped by tenant, caller, allowed sources, session, and snapshot time. Each follow-up rechecks the original premise hashes against the authorized snapshot. Proposed relationships stay labeled as hypotheses, while cited relationships retain their source identifiers and spans. Follow-up text does not enter the knowledge base or answer evidence. Strict evidence mode bypasses invention follow-ups.

## Acceptance checks

- Both natural-language invention examples and the API flag route to the same node exactly once per task. Story prompts keep the existing Imagine route. Factual, quoted, negated, and strict-evidence prompts leave invention off.
- A Helios fixture combines typed premises from separate chunks and produces a testable proposal absent from the inspected graph. The proposal retains source references and the six channel outcomes.
- The flag and final note appear for successful, empty, and partial runs in plain text and structured layouts, including a mixed request.
