# Node responsibilities and inference expansion review

Reviewed against main commit `7c8f6a3`, 2026-11-18.
This is a source review and proposed refactoring plan, not an implemented redesign
or a latency benchmark. No runtime behavior changes in this review.

## Existing graph inventory

The core graph registers 28 stages in `pipeline._compile`. Public request
workflows also run outside that graph, so 28 is not the count of every service.

- `guard`: request admission; retain separately from answer verification.
- `retrieve`: initial candidate retrieval and evidence expansion.
- `resonate`: resonance-based candidate processing.
- `dense`, `relational`, `disentangled`, `hyperbolic`, `identity`, `causal`:
  six distinct channel readings using a shared adapter. These are retrieval
  signals, not six independent logical proofs. In particular, a causal channel
  score does not establish a causal effect.
- `catalog`: retrieval labels and categories.
- `detail`: aggregates channel readings into a report.
- `spans`: constructs the allowed source-span/value grammar.
- `inference`: bounded rule-proof graph adapter; currently requires an internal
  validated `inference_request`. Public explicit requests return through
  `execute_inference` before the core graph.
- `think`: PrismThinker regime/evaluator selection and directives.
- `cognize`: proposition deliberation, synthesis and delivered-output auditing.
- `grammar`: checks answer numbers against the source grammar.
- `shine`: grounding verification and delivery gate.
- `deep`: optional expanded retrieval.
- `gather`: article evidence assembly.
- `imagine`: optional creative realization.
- `compare`: gathers and realizes evidence per comparison side.
- `brief`: summary/list selection and realization.
- `math`: deterministic prompt arithmetic.
- `finance`: finance-specific validation.
- `frame`: joins stored event roles.
- `model01`: additional sentence construction using relevant sources/results.
- `reply`: composes delivery and clears rejected answers/evidence.
- `discover`: optional discovery output after delivery composition.

Important workflows outside this core graph include strict evidence answering,
document generation, relational cycles, Innovation, hypothesis generation,
Nammade, AbductiveBridge, CrossDomin/constraint checks, numerical scans,
PrismLexicon delivery and the optional external-model route. A reduced graph
stage count alone would not establish lower runtime cost.

## Confirmed redundant work and integration edges

1. Combined research calls `execute_nammade`, which attaches inference. The
   enclosing `execute_invention` attaches inference again on the same snapshot.
   This repeats discovery and proof checking; its rendered Nammade section can
   also repeat the inference lines. Compute once and share the receipt.
2. `attach_inference` extracts facts and builds a discovery closure, then calls
   `deduce` separately for up to eight targets. Each call re-extracts facts and
   rebuilds a closure. Introduce a request-scoped prepared inference context,
   while retaining independent receipt replay for verification.
3. Public explicit inference bypasses the graph, while the graph adapter has no
   public request-state producer in the reviewed pipeline. Choose one execution
   owner; retain an adapter only where an actual caller uses it.
4. Each channel adapter reconstructs passages and the identity anchor. Prepare
   immutable shared request inputs once, retaining six separate readings.
5. CrossDomin has a separate entry point and does not call `attach_inference`.
   Its existing domain/constraint checks are not duplicates of general rule
   deduction. A shared inference service must be invoked explicitly if needed.
6. Classifier logic is distributed across the central classifier and specialized
   seed/plan parsers. Centralize the routing decision and explain its reasons;
   retain specialized parsers for typed node inputs. Preserve negation, quoted
   background, explicit overrides and strict-mode precedence.

## Overlap that needs profiling, not immediate deletion

`cognize`, `imagine`, `brief`, `model01`, and the document workflow all construct
text, but have different inputs and delivery contracts. Give one response plan
an explicit primary producer; run secondary producers only for an unmet task.
Do not remove a producer before checking its regression cases.

`grammar`, cognition auditing, and `shine` overlap in verification but check
different properties. Consolidate orchestration and receipt representation,
not their guarantees. The same applies to `math`, `finance`, and numerical
constraint scans: shared numeric utilities must preserve each rounding/unit
policy and domain-specific validation.

## Additional inference capabilities, in priority order

1. Taxonomic inheritance: an entity's class plus an explicit subclass relation
   establishes membership in the parent class. Reuse registered deduction rules.
   Do not inherit class-average lifespan or other statistical properties as
   individual facts; healthcare exceptions must remain explicit.
2. Typed relation composition: inverse relations and approved property chains
   support joins such as component-of plus located-in. Declare valid composition
   and transitivity per relation; arbitrary relatedness is never transitive.
3. Constraint inference: compatible units, bounds, intersections and empty
   feasible regions. Reuse the existing constraint checker/evaluator rather than
   adding another independent arithmetic engine. Preserve temporal/model scope.
4. Conditional deduction: explicit application-owned `if P then Q`, with all
   antecedents established. Source text must not install executable rules.
   Missing evidence for P does not establish not-P.
5. Temporal inference: ordering and interval overlap over sourced dates with
   explicit precision and timezone. Avoid treating earlier observations as
   current facts.
6. Broader abductive explanation: extend the existing AbductiveBridge's domain
   registry and alternatives instead of adding another abduction node. Output
   candidate explanations, counterevidence, assumptions and distinguishing tests.
7. Inductive/statistical inference: a separate optional capability over structured
   observations, with sample size, uncertainty and holdout evaluation. A pattern
   or analogy remains a hypothesis, never a deductive proof.

Counterfactual causal inference should wait for explicit causal models and
assumptions; semantic proximity and a channel named causal are insufficient.

## Proposed lean execution contract

One request plan -> one authorized/versioned source context -> shared retrieval
and fact preparation -> selected methods -> independent verification -> delivery.

Keep proof, computation, source quote and unverified hypothesis claim types
distinct. Request-scoped caches include source version, scope, rule version and
budgets. Never reuse receipts across authorization or snapshot boundaries.
Do not eagerly scan the full KB on every greeting or ordinary lookup.

Implement redundant-inference removal first, then prepared facts/closures,
then routing/producer ownership. Add new rule families only after these changes.
Acceptance checks should count extraction/closure invocations, verify unchanged
receipts and answer contracts, exercise strict/scope/snapshot/conflict/resource
cases, and measure latency/memory before and after. No speedup is claimed yet.

## References

- W3C OWL 2 Primer: https://www.w3.org/TR/owl2-primer/
- W3C OWL 2 property-chain/transitivity specification:
  https://www.w3.org/TR/owl-syntax/
- Stanford CS227 abduction lecture:
  https://web.stanford.edu/class/cs227/Lectures/lec12.pdf
