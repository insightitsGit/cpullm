wcpu-llm Abductive-Deductive Reversal Inference Engine — Design Specification
Technical Architecture & Deterministic Logic Specification for Coding Agent Implementation
1. Executive Summary & Architectural Philosophy
1.1 Objective
The cpu-llm Abductive-Deductive Reversal Inference Engine is a deterministic, closed-world symbolic inference module designed to run efficiently on standard CPU architectures without probabilistic neural token generation. It replaces non-deterministic LLM generation with explicit constraint satisfaction, formal logical elimination, paraconsistent contradiction management, and reversed backward projection.

The engine executes four distinct formal phases:

Broad Abductive Expansion: Hypothesizes candidate causes from domain/regime knowledge retrieved via an exhaustive full-scope domain/regime sweep across all KB chunks matching the active domain scope (e.g., retrieving all physics chunks in scope rather than top-k snippet truncation, because true abductive expansion and cross-document contradiction detection require evaluating the entire domain scope so valid candidates or conflicting bounds are not missed due to narrow top-k cutoffs) via Nammade span matching. If total in-scope chunk count exceeds a fast-path threshold ($N_{fast\_threshold} = 50$), a Pre-Execution Latency & Scope Alert is emitted to notify users of potential scan latency.
Deductive Elimination & Epistemic Demotion: Applies Modus Tollens to hard observations while isolating mutually contradictory observations into an unvalidated clue pool without invoking the Principle of Explosion ($P \land \neg P \implies Q$).
Reversed Integration of Non-Validated Facts: Projects expected consequences backward from surviving candidate hypotheses to explain, reconcile, or soft-penalize unvalidated and demoted observations.
Plausibility Ranking: Evaluates surviving candidates through an auditable, deterministic scoring formula to isolate the "Most Possible" candidate(s) or issue standard zero-candidate safety terminations.
1.2 Core Principles
Zero Neural/Probabilistic Hallucination: Computations depend strictly on finite set operations, graph traversal, and logical evaluation over Pydantic data schemas.
Strict Epistemic Isolation: The engine maintains explicit taxonomy boundaries between four states:
CERTAINTY: Immutable, hard-validated knowledge base facts and non-contradictory query observations.
POSSIBILITY: Hypotheses or demoted/conflicting observations requiring further validation.
ELIMINATED: Candidates formally falsified via Modus Tollens against hard facts.
HYPOTHESIS: Synthesized candidate representations formed via abductive expansion and backward projection.
Paraconsistent Resilience: Contradictions in input sources cause epistemic demotion to an unvalidated clue pool rather than logic engine collapse or arbitrary candidate discard.

Epistemic State
Formal Definition
Mutability
Operational Path
CERTAINTY
$K \models O_{hard}$ (Validated Facts)
Immutable
Falsifies candidates via Modus Tollens
POSSIBILITY
$h \in H_0 \lor (C_1 \land C_2 \implies \bot)$
Dynamic
Quarantined in Unvalidated Clue Pool
ELIMINATED
$h_i \implies \neg O_{hard}$
Permanent
Removed from candidate ranking; logged in trace
HYPOTHESIS
$h_i \in P_{surviving}$
Evaluated
Scored via backward consistency projection

2. Four-Stage Inference Pipeline Architecture
                                INFERENCE PIPELINE
+-----------------------------------------------------------------------------------+
| Stage 1: Broad Abductive Expansion                                                |
|   Input: Query + Nammade Spans -> Candidates H_0 (epistemic_status = POSSIBILITY)  |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 2: Deductive Elimination & Epistemic Demotion                               |
|   2A: Hard Negation Pruning (Modus Tollens against O_hard)                        |
|   2B: Mutual Contradiction Demotion (Paraconsistent Quarantine to Pool U)         |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 3: Reversed Integration of Non-Validated Facts                              |
|   For each h_i in P_surviving: Project E(h_i) backward against Pool U             |
|   Partition: explained_clues, reconciled_conflicts, unexplained_residuals, soft   |
+-----------------------------------------------------------------------------------+
                                         |
                                         v
+-----------------------------------------------------------------------------------+
| Stage 4: Plausibility Ranking & Output Formatting                                 |
|   Score(h_i) -> Audit Trace -> Standard Safeguard (Empty Set) or Final EngineResponse|
+-----------------------------------------------------------------------------------+
2.1 Stage 1: Broad Abductive Expansion (Possibility Pool Generation)
Trigger: Input query string combined with retrieved domain/regime spans (SourceSpan).
Execution Logic & Full-Scope Sweep:
Perform an exhaustive full-scope domain/regime sweep across all KB chunks matching the active domain scope (e.g., retrieving all physics chunks in scope rather than top-k snippet truncation). True abductive expansion and cross-document contradiction detection require evaluating the entire domain scope so valid candidates or conflicting bounds are not missed due to narrow top-k cutoffs.
Pre-Execution Latency & Scope Alert Gate: Right when Stage 1 detects a broad/full-scope domain sweep (e.g., when total in-scope chunk count $M_{scope}$ exceeds a fast-path threshold such as $N_{fast\_threshold} = 50$ chunks), the engine must emit a structured user-facing latency notice before or at the start of the exhaustive scan (e.g., "Scope Notice: Searching across all [N] chunks in the [Domain] scope for full abductive/deductive coverage. This operation may take longer than a standard single-hop lookup.") and record the scope size and latency alert status in InferenceTrace.
Extract structural entities, attributes, and relationships referenced in the retrieved SourceSpan set.
Construct the initial candidate set $H_0 = \{h_1, h_2, \dots, h_n\}$ consisting of all domain entities or mechanisms that share at least one causal or structural link with the query context.
Initialize every candidate $h_i \in H_0$ with epistemic_status = EpistemicStatus.POSSIBILITY.
State Rule: No candidate may be marked as CERTAINTY during Stage 1. Abductive expansion is purely generative across closed-world spans.
2.2 Stage 2: Deductive Elimination & Epistemic Demotion (Conflict Resolution)
Sub-step 2A: Hard Negation Pruning (Modus Tollens)
Given the set of hard, non-contradicted observations $O_{hard} \subset \text{KB}$, evaluate each candidate $h_i \in H_0$.

Rule: If $h_i \implies \neg O_{hard}$ (i.e., a necessary structural property of $h_i$ violates an immutable fact in $O_{hard}$):
$$\frac{h_i \implies P, \quad \neg P}{\therefore \neg h_i}$$
Transition: Set h_i.epistemic_status = EpistemicStatus.ELIMINATED.
Trace Log: Record an explicit FalsificationTrace recording the violating fact, the failed candidate requirement, and the target candidate ID.
Sub-step 2B: Mutual Contradiction Demotion (Paraconsistent Quarantine)
Given two observations or retrieved claims $C_1$ and $C_2$ present in the input context:

Rule: If $C_1 \land C_2 \implies \bot$ (direct contradiction):
Do not delete $C_1$ or $C_2$.
Do not apply standard classical explosion ($P \land \neg P \implies Q$).
Demote both $C_1$ and $C_2$ from CERTAINTY to POSSIBILITY.
Encapsulate the conflict as a ConflictPair(clue_a_id, clue_b_id, conflict_type) with tag CONFLICT_DEMOTED.
Transfer $C_1$, $C_2$, and their ConflictPair into the Unvalidated Clue Pool ($U$).
2.3 Stage 3: Reversed Integration of Non-Validated Facts (Backward Consistency Projection)
Forward chaining from unvalidated or contradictory clues produces compounding errors. The engine inverts the direction of inference, projecting backward from each surviving candidate $h_i \in P_{surviving}$ onto the Unvalidated Clue Pool ($U$).

                 REVERSED BACKWARD PROJECTION MECHANISM
                 
       Unvalidated Clue Pool (U)           Surviving Candidate h_i
      +-------------------------+         +-----------------------+
      |  Clue A   |   Clue B    |         |  Expected             |
      | (Demoted) | (Demoted)   |         |  Consequences E(h_i)  |
      +-------------------------+         +-----------------------+
                   \   /                              |
                    \ /                               v
                     v                    Projects backward onto U
         +-----------------------+                    |
         | Conflict Pair (A, B)  | <------------------+
         +-----------------------+
                     |
                     v
  Reconciles Contradiction via Underlying Mechanism:
  e.g., h_i -> "retractable_claws" explains both A ("claw marks") & B ("no claws")

For each candidate $h_i \in P_{surviving}$:

Backward Projection: Generate the set of expected observable consequences:
$$E(h_i) = {e_1, e_2, \dots, e_k}$$
Integration against Pool U: Evaluate intersections between $E(h_i)$ and all unvalidated clues, partial observations, and conflict pairs in $U$.
Contradiction Reconciliation: If a candidate $h_i$ contains a structural property or conditional mechanism $M$ such that $M \implies (C_1 \text{ under Context } X) \land (C_2 \text{ under Context } Y)$, mark the ConflictPair(C_1, C_2) as resolved by $h_i$.
Outcome Partitioning: Partition the interactions of $h_i$ into four explicit sets:
explained_clues: $C_k \in U$ where $e_j \in E(h_i)$ directly entails $C_k$.
reconciled_conflicts: ConflictPair instances in $U$ whose apparent contradiction is resolved by $h_i$.
unexplained_residuals: $C_k \in U$ that are neither confirmed nor contradicted by $E(h_i)$.
soft_contradictions: $C_k \in U$ that conflict with non-essential assumptions of $h_i$ (insufficient to trigger hard Modus Tollens elimination).
2.4 Stage 4: Plausibility Ranking & Epistemic Output Formatting
2.4.1 Deterministic Scoring Formula
Every surviving candidate $h_i \in P_{surviving}$ is assigned a numeric score calculated deterministically:

$$\text{Score}(h_i) = (W_{rec} \cdot |R_i|) + (W_{exp} \cdot |E_i|) - (W_{soft} \cdot |S_i|) - (W_{res} \cdot |U_i|)$$

Where:

$R_i = \text{reconciled_conflicts}(h_i)$
$E_i = \text{explained_clues}(h_i)$
$S_i = \text{soft_contradictions}(h_i)$
$U_i = \text{unexplained_residuals}(h_i)$
Default Weight Parameters:
$W_{rec} = 3.0$ (Highest reward for resolving conflicting evidence)
$W_{exp} = 2.0$ (Reward for explaining unvalidated clues)
$W_{soft} = 2.5$ (Penalty for soft conflicts)
$W_{res} = 0.5$ (Minor penalty for unaddressed residual clues)
2.4.2 Deterministic Tie-Breaking Rules
If $\text{Score}(h_a) == \text{Score}(h_b)$, break ties using the following strict priority sequence:

Higher count of $|R_i|$ (reconciled_conflicts).
Lower count of $|S_i|$ (soft_contradictions).
Higher total source_span_density (total number of distinct SourceSpan IDs supporting candidate $h_i$).
Lexicographical ordering of candidate_id.
2.4.3 Edge Case: Empty Surviving Set
If $|P_{surviving}| == 0$ (all candidates eliminated via Modus Tollens during Stage 2A), the engine must cease execution and return:

No testable hypothesis option was found

The output response must include the complete falsification_trace details mapping every eliminated candidate to its specific logical contradiction.
2.4.4 Mandatory Epistemic Guardrails
Outputs must explicitly separate retrieved knowledge base facts from synthesized hypotheses using formal headers and standard disclaimers.


================================================================================
SCOPE & LATENCY ALERT BANNER [Triggered: scope_alert_triggered == True]
================================================================================
Scope Notice: Searching across all [N] chunks in the [Domain] scope for full 
abductive/deductive coverage. This operation may take longer than a standard 
single-hop lookup.

================================================================================
EPISTEMIC TRACE HEADER: VERIFIED KB SPANS
================================================================================
[SPAN-001] (CERTAINTY): Verified observation data from input context.

================================================================================
SYNTHESIZED HYPOTHESIS: [Candidate Name]
================================================================================
Invention note: The following structural hypothesis is an abductively 
synthesized projection based on closed-world constraint satisfaction. 
It does not represent an immutable Knowledge Base fact.
3. Reference Walkthroughs (Validation Benchmarks)
3.1 Test Case A: Conceptual Logic Benchmark — Jungle Animal Identification
Initial Input Context
Query: "Identify track maker in sector 4."
Retrieved Spans: Spans describing animal track phenotypes, footprint scale, and observer reports.
Observations:
$O_1$ (Hard): "Big footstep observed" (impression area $> 200\text{ cm}^2$).
$C_1$ (Witness 1): "Claw marks clearly visible in mud."
$C_2$ (Witness 2): "No claw marks visible in track impression."
Stage-by-Stage Trace Execution
Stage 1: Broad Abductive Expansion
Candidate set $H_0$ populated from domain spans:
$$H_0 = {\text{Snake}, \text{Ant}, \text{Frog}, \text{Jaguar}, \text{Elephant}, \text{Tapir}}$$
Status for all candidates: epistemic_status = POSSIBILITY.
Stage 2A: Hard Negation Pruning
Hard Fact: $O_{hard} = \text{"Big footstep"} \implies \text{Mass} > 30\text{ kg} \land \text{Foot Structure} = \text{True}$.

Modus Tollens Rule Evaluation:
$\text{Snake} \implies \text{No feet} \implies \neg O_{hard} \implies$ ELIMINATED
$\text{Ant} \implies \text{Micro footstep} \implies \neg O_{hard} \implies$ ELIMINATED
$\text{Frog} \implies \text{Small footstep} \implies \neg O_{hard} \implies$ ELIMINATED
Surviving Candidates: $P_{surviving} = {\text{Jaguar}, \text{Elephant}, \text{Tapir}}$.
Stage 2B: Mutual Contradiction Demotion
Evaluate $C_1$ ("Claw marks present") vs. $C_2$ ("No claw marks visible").
$$C_1 \land C_2 \implies \bot$$

Action: Demote $C_1$ and $C_2$ to POSSIBILITY. Tag as CONFLICT_DEMOTED.
Construct ConflictPair(clue_a="C1_claw_marks", clue_b="C2_no_claw_marks", conflict_type="MORPHOLOGICAL_CONTRADICTION").
Move $C_1$, $C_2$, and ConflictPair into Unvalidated Clue Pool $U$.
Stage 3: Reversed Backward Projection
Project expected consequences for candidates in $P_{surviving}$ against Pool $U$:

Candidate: Tapir
Expected: 3-toed front / 4-toed rear footprints, non-retractable claws.
Modus Tollens / Constraint check: Target track shows 4-toed symmetrical pad structure. Tapir anatomy violates pad geometry.
Result: Demoted/Eliminated via structural constraint.
Candidate: Elephant
Expected: Round pillar footprints ($> 1000\text{ cm}^2$), massive canopy breakage, deep mud sinkage ($> 15\text{ cm}$).
Evaluation against $U$: Fails to explain claw mark reports; penalized heavily for missing expected deep sinkage and canopy breakage (soft_contradictions = 2, unexplained_residuals = 1).
Score: $(3.0 \cdot 0) + (2.0 \cdot 0) - (2.5 \cdot 2) - (0.5 \cdot 1) = -5.5$.
Candidate: Jaguar
Expected: 4-toed padded tracks, retractable claws (claws extend during steep ascent/stalking; claws retract during flat locomotion).
Evaluation against Pool $U$:
Reconciles ConflictPair(C1, C2): Jaguar's retractable claw mechanism explains why Witness 1 observed claw marks (soft mud/ascent) while Witness 2 observed no claw marks (firm ground/retracted walk).
reconciled_conflicts: ["CP_CLAWS_01"]
explained_clues: ["C1_claw_marks", "C2_no_claw_marks"]
soft_contradictions: []
unexplained_residuals: []
Score: $(3.0 \cdot 1) + (2.0 \cdot 2) - (2.5 \cdot 0) - (0.5 \cdot 0) = 3.0 + 4.0 = 7.0$.
Stage 4: Ranking & Output Selection
Rank #1: Jaguar ($\text{Score} = 7.0$) $\implies$ Marked as Most Possible.
Rank #2: Elephant ($\text{Score} = -5.5$).
3.2 Test Case B: Physics KB Benchmark — SIDM Across Dwarf Galaxies & Bullet Cluster
Test Sub-case B1: Constant Cross-Section ($\sigma/m = \text{const}$)
Input Context
Query: "Determine dark matter cross-section model fitting both dwarf galaxy rotation curves and Bullet Cluster constraints."
Domain Scope: domain_scope = "physics" (Full-scope scan across all $N = 75$ in-scope physics chunks; $N > N_{fast\_threshold}$ triggers latency alert).
Observations (KB Spans):
$O_{dwarf}$ (Hard): Dwarf galaxy core bounds require self-interaction cross-section $\sigma/m \in [0.5, 10.0]\text{ cm}^2/\text{g}$ at low velocities ($v \sim 30\text{ km/s}$).
$O_{bullet}$ (Hard): Bullet Cluster merger bounds enforce $\sigma/m \le 0.1\text{ cm}^2/\text{g}$ at high velocities ($v \sim 1000\text{ km/s}$).
Constraint: Model Candidate $H_1$ = "Constant SIDM Cross-Section" ($\sigma/m(v) = c$).
Execution Trace
Stage 1 Abductive Expansion & Full-Scope Sweep: Sweeps all $N = 75$ chunks in domain_scope = "physics". Emits Pre-Execution Latency & Scope Alert: "Scope Notice: Searching across all 75 chunks in the physics scope for full abductive/deductive coverage. This operation may take longer than a standard single-hop lookup." Candidate set initialized: $H_0 = \{\text{Constant\_SIDM}\}$.
Stage 2A Deductive Elimination:
For $H_1$, $\sigma/m(v=30) = \sigma/m(v=1000) = c$.
$O_{dwarf} \implies c \ge 0.5$.
$O_{bullet} \implies c \le 0.1$.
Logical Evaluation: $(c \ge 0.5) \land (c \le 0.1) \implies \bot$.
Candidate $H_1$ generates a direct contradiction against $O_{hard}$.
Transition: Constant_SIDM.epistemic_status = ELIMINATED.
Stage 4 Output Execution:
$|P_{surviving}| == 0$.
Final Standard Output:

No testable hypothesis option was found

Falsification Trace Logged: Constant_SIDM eliminated: required cross-section [0.5, 10.0] cm^2/g at v=30 km/s directly violates upper bound <= 0.1 cm^2/g at v=1000 km/s.
Test Sub-case B2: Velocity-Dependent Cross-Section ($\sigma/m \propto v^{-a}$)
Input Context
Same observations as B1, plus additional Candidate $H_2$ = "Velocity-Dependent SIDM (VD-SIDM)" retrieved during full-scope sweep across all $N = 75$ chunks in domain_scope = "physics" (triggering latency alert prior to Stage 2 elimination).
Execution Trace
Stage 1 Abductive Expansion & Full-Scope Sweep: Sweeps all $N = 75$ chunks in domain_scope = "physics", emitting latency alert. Candidate set initialized: $H_0 = \{\text{Constant\_SIDM}, \text{VD\_SIDM}\}$.
Stage 2A Deductive Elimination:
Constant_SIDM $\implies$ ELIMINATED (same trace as B1).
For $H_2$ (VD_SIDM): $\sigma/m(v) = \sigma_0 / (1 + (v/v_0)^b)$.
At $v = 30\text{ km/s}$, $\sigma/m \approx 2.0\text{ cm}^2/\text{g}$ (satisfies $O_{dwarf}$).
At $v = 1000\text{ km/s}$, $\sigma/m \approx 0.05\text{ cm}^2/\text{g}$ (satisfies $O_{bullet}$).
$H_2$ does not violate hard constraints.
Transition: $P_{surviving} = {\text{VD_SIDM}}$.
Stage 3 Reversed Backward Projection:
$H_2$ projects backward onto unvalidated/tension observations:
Explains core radius sizes ($0.3 - 1.5\text{ kpc}$) in dwarf galaxies.
Reconciles apparent contradiction between low-velocity interaction scales and high-velocity collisionless behavior.
Outcome Partitioning for $H_2$:
explained_clues: ["dwarf_core_radii_0.3_1.5kpc", "bullet_cluster_substructure_offset"]
reconciled_conflicts: ["CP_DWARF_VS_BULLET_CROSS_SECTION"]
soft_contradictions: []
unexplained_residuals: []
Stage 4 Ranking & Output:
$\text{Score}(\text{VD_SIDM}) = (3.0 \cdot 1) + (2.0 \cdot 2) = 7.0$.
Output Format:


================================================================================
SCOPE & LATENCY ALERT BANNER
================================================================================
Scope Notice: Searching across all 75 chunks in the physics scope for full 
abductive/deductive coverage. This operation may take longer than a standard 
single-hop lookup.

================================================================================
EPISTEMIC TRACE HEADER: VERIFIED KB SPANS
================================================================================
[SPAN-PHYS-01] (CERTAINTY): Dwarf core cross-section requirement: 0.5 - 10.0 cm^2/g (v ~ 30 km/s).
[SPAN-PHYS-02] (CERTAINTY): Bullet cluster cross-section limit: <= 0.1 cm^2/g (v ~ 1000 km/s).

================================================================================
SYNTHESIZED HYPOTHESIS: Velocity-Dependent SIDM (VD_SIDM) [Most Possible]
================================================================================
Invention note: The following structural hypothesis is an abductively 
synthesized projection based on closed-world constraint satisfaction. 
It does not represent an immutable Knowledge Base fact.

Score: 7.0
Reconciled Conflicts:
  - CP_DWARF_VS_BULLET_CROSS_SECTION: Reconciles low-velocity core expansion with high-velocity collisionless cluster dynamics via differential power-law suppression.
Explained Clues:
  - dwarf_core_radii_0.3_1.5kpc
  - bullet_cluster_substructure_offset
4. Data Contracts & Pydantic Schemas
The implementation must strictly adhere to Pydantic v2 schemas. Copy the following specification into cpu_llm/engine/schemas.py.


from enum import Enum
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field, ConfigDict


class DomainScopeConfig(BaseModel):
    domain_name: str = Field(..., description="Target domain scope identifier.")
    full_scope_scan: bool = Field(default=True, description="Enable exhaustive scope sweep without top-k truncation.")
    latency_alert_threshold: int = Field(default=50, description="Chunk count threshold triggering pre-execution latency alert.")


class EpistemicStatus(str, Enum):
    CERTAINTY = "CERTAINTY"
    POSSIBILITY = "POSSIBILITY"
    ELIMINATED = "ELIMINATED"
    HYPOTHESIS = "HYPOTHESIS"


class ConflictTag(str, Enum):
    HARD_NEGATION = "HARD_NEGATION"
    CONFLICT_DEMOTED = "CONFLICT_DEMOTED"
    SOFT_TENSION = "SOFT_TENSION"


class SourceSpan(BaseModel):
    model_config = ConfigDict(frozen=True)

    span_id: str = Field(..., description="Unique identifier for the source span.")
    doc_id: str = Field(..., description="Document origin identifier.")
    text: str = Field(..., description="Raw text snippet extracted via Nammade matching.")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ClueNode(BaseModel):
    clue_id: str = Field(..., description="Unique clue identifier.")
    statement: str = Field(..., description="Factual or reported observation content.")
    epistemic_status: EpistemicStatus = Field(default=EpistemicStatus.POSSIBILITY)
    source_span_ids: List[str] = Field(default_factory=list)
    attributes: Dict[str, Any] = Field(default_factory=dict)


class ConflictPair(BaseModel):
    conflict_id: str = Field(..., description="Unique contradiction pair identifier.")
    clue_a_id: str = Field(..., description="First contradictory clue ID.")
    clue_b_id: str = Field(..., description="Second contradictory clue ID.")
    conflict_type: str = Field(..., description="Domain category of the conflict.")
    tag: ConflictTag = Field(default=ConflictTag.CONFLICT_DEMOTED)
    description: str = Field(..., description="Explicit statement of mutual contradiction.")


class CandidateHypothesis(BaseModel):
    candidate_id: str = Field(..., description="Unique candidate identifier.")
    name: str = Field(..., description="Human-readable candidate label.")
    epistemic_status: EpistemicStatus = Field(default=EpistemicStatus.POSSIBILITY)
    necessary_conditions: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Properties required for Modus Tollens evaluation."
    )
    expected_consequences: List[str] = Field(
        default_factory=list, 
        description="Expected observations under backward projection E(h_i)."
    )
    source_span_ids: List[str] = Field(default_factory=list)


class FalsificationTrace(BaseModel):
    candidate_id: str = Field(..., description="ID of the eliminated candidate.")
    falsifying_fact_id: str = Field(..., description="ID of the immutable fact violated.")
    rule_violated: str = Field(..., description="Formal logic rule trace (Modus Tollens).")
    explanation: str = Field(..., description="Human-readable falsification path.")


class ReversedProjection(BaseModel):
    candidate_id: str = Field(..., description="Target candidate ID.")
    explained_clues: List[str] = Field(default_factory=list)
    reconciled_conflicts: List[str] = Field(default_factory=list)
    unexplained_residuals: List[str] = Field(default_factory=list)
    soft_contradictions: List[str] = Field(default_factory=list)


class CandidateScore(BaseModel):
    candidate_id: str = Field(...)
    final_score: float = Field(...)
    reconciled_count: int = Field(...)
    explained_count: int = Field(...)
    soft_contra_count: int = Field(...)
    residual_count: int = Field(...)
    span_density: int = Field(...)


class InferenceTrace(BaseModel):
    query: str = Field(...)
    domain_scope: str = Field(default="default", description="Active domain scope name.")
    total_chunks_in_scope: int = Field(default=0, description="Total count of chunks evaluated in domain scope.")
    latency_alert_triggered: bool = Field(default=False, description="True if full-scope scan exceeded fast-path threshold.")
    latency_alert_message: Optional[str] = Field(default=None, description="Pre-execution user latency notice.")
    initial_candidates: List[str] = Field(..., description="IDs of candidates in H_0.")
    eliminated_candidates: List[FalsificationTrace] = Field(default_factory=list)
    demoted_clues: List[str] = Field(default_factory=list)
    quarantined_conflicts: List[ConflictPair] = Field(default_factory=list)
    projections: Dict[str, ReversedProjection] = Field(default_factory=dict)
    scores: Dict[str, CandidateScore] = Field(default_factory=dict)
    winning_candidate_id: Optional[str] = Field(default=None)


class EngineResponse(BaseModel):
    status_code: str = Field(..., description="'SUCCESS' or 'NO_HYPOTHESIS_FOUND'")
    formatted_output: str = Field(..., description="Final text formatted with epistemic headers.")
    trace: InferenceTrace = Field(..., description="Complete audit trace for execution verification.")
4.1 Module Engine Interface
The core module must expose the following Python signature:


# cpu_llm/engine/reversal_engine.py

from typing import List, Optional, Callable
from cpu_llm.engine.schemas import SourceSpan, EngineResponse, InferenceTrace, DomainScopeConfig

class AbductiveDeductiveReversalEngine:
    def __init__(self, weight_reconciled: float = 3.0, weight_explained: float = 2.0,
                 weight_soft_contra: float = 2.5, weight_residual: float = 0.5):
        self.w_rec = weight_reconciled
        self.w_exp = weight_explained
        self.w_soft = weight_soft_contra
        self.w_res = weight_residual

    def run(self, query: str, spans: List[SourceSpan],
            scope_config: Optional[DomainScopeConfig] = None,
            on_status_update: Optional[Callable[[str], None]] = None) -> EngineResponse:
        """
        Executes the 4-Stage Symbolic Inference Pipeline.

        1. Stage 1: Broad Abductive Expansion (Full-Scope Domain Sweep & Latency Alert) -> Generate H_0
        2. Stage 2: Deductive Elimination (Modus Tollens) & Epistemic Demotion -> Pool U
        3. Stage 3: Reversed Backward Projection -> Partition interaction sets
        4. Stage 4: Scoring, Tie-Breaking & Output Formatting
        """
        ...
5. Implementation Guidelines & Acceptance Criteria
5.1 Deterministic Execution Requirements
Zero Randomness: The algorithm must never invoke random, probabilistic sampling, or non-deterministic hash iteration.
Reproducible List Ordering: All set intersections and candidate lists must be explicitly sorted by identifier (candidate_id, clue_id, span_id) before iteration.
Structured JSON Audit Logging: Every execution run must construct a complete InferenceTrace embedded inside the EngineResponse.
5.2 Unit Test Checklist for Coding Agent
The implementation must pass all tests defined in the checklist below:


# tests/test_reversal_engine.py

import pytest
from cpu_llm.engine.reversal_engine import AbductiveDeductiveReversalEngine
from cpu_llm.engine.schemas import SourceSpan, EpistemicStatus, DomainScopeConfig

def test_single_hop_retrieval_passthrough():
    """Verify standard single-candidate projection without conflicts."""
    ...

def test_full_scope_scan_and_latency_alert():
    """Verify that an exhaustive domain sweep scans 100% of in-scope chunks
    without top-k truncation and fires the user-facing latency alert callback/message
    when chunk count exceeds latency_alert_threshold.
    """
    alerts = []
    engine = AbductiveDeductiveReversalEngine()
    scope_cfg = DomainScopeConfig(domain_name="physics", full_scope_scan=True, latency_alert_threshold=50)
    spans = [SourceSpan(span_id=f"span_{i}", doc_id="doc_1", text=f"Chunk {i}") for i in range(75)]
    response = engine.run(query="Test physics sweep", spans=spans, scope_config=scope_cfg, on_status_update=lambda msg: alerts.append(msg))
    assert response.trace.total_chunks_in_scope == 75
    assert response.trace.latency_alert_triggered is True
    assert len(alerts) > 0
    assert "Scope Notice:" in response.trace.latency_alert_message

def test_deductive_total_elimination():
    """Verify that when all candidates violate hard facts, the engine outputs
    'No testable hypothesis option was found' and logs complete falsification traces.
    """
    engine = AbductiveDeductiveReversalEngine()
    response = engine.run(query="Physics B1 Case", spans=[...])
    assert response.status_code == "NO_HYPOTHESIS_FOUND"
    assert "No testable hypothesis option was found" in response.formatted_output
    assert len(response.trace.eliminated_candidates) > 0

def test_conflict_demotion_paraconsistency():
    """Verify that contradictory clues C1 and C2 are demoted to EpistemicStatus.POSSIBILITY
    and placed into ConflictPair without raising an unhandled exception or dropping clues.
    """
    ...

def test_reversed_integration_reconciliation():
    """Verify Test Case A (Jungle Track): Jaguar correctly reconciles Witness 1 & Witness 2
    claw mark contradiction, yielding highest score (7.0).
    """
    ...

def test_deterministic_ranking_and_tie_breaking():
    """Verify identical scores break ties via reconciled_conflicts count, then soft_contradictions,
    then span density, then candidate_id lexicographical order.
    """
    ...
5.3 Code Construction Guidelines for Implementation Agent
Pydantic v2 Compliance: Use model_config = ConfigDict(...) syntax. Do not use legacy Pydantic v1 .dict() or class Config.
Graph Traversal: Implement candidate-to-clue constraint mapping using Python dict lookups and set operations to guarantee $O(N \cdot M)$ complexity where $N$ is candidate count and $M$ is clue count.
String Format Standard: Ensure epistemic trace output exact-matches the headers specified in Section 2.4.4.

