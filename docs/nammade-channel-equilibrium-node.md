# CPU LLM Nammade channel and equilibrium node

Status: implemented in `cpu_llm.nammade` on 2026-11-15. `Nammade: <query>` or
`ask(..., nammade=True)` runs `NammadeEquilibriumNode` on the caller's
authorized snapshot. `PossibilityHorizonNode` is still not in source.
`PrismThinker` and `StylisticGenerationNode` are unchanged. The scan quotes
up to three relevant stored spans with source IDs and hashes. Channel labels,
scoring, and word-pair diagnostics stay in the Nammade receipt. These
excerpts attribute claims to the source. They do not test the claims.

The landed residual includes stiffness `κ`, default `1`. The formula is the
one in [The Nammade Continuum (Verified Edition)](nammade-continuum-verified-edition.md)
and in [Open point: volumetric stiffness](#open-point-volumetric-stiffness).
Pass `nammade_kappa` to use another positive finite value.

An explicit chunk beginning `Nammade span:` plus a JSON object stores that
`a, b, c, d`. Those records are admitted by the residual cap. Every other
chunk uses the fixed lexical projection in `cpu_llm.nammade.encode` for its
density band. When the caller has the trained encoder, ordinary paragraphs
are eligible at the dense-core cosine floor of `0.62` or by topical token overlap. Dense retrieval uses the caller’s source scope and snapshot date. Heading-only chunks are excluded.
The residual cap does not drop those paragraphs, and a missing lexical marker
is not treated as spatial lock. The projection is a reading of the text, not
a measurement of the treatise. A query density is `-1`, so an open probe can
bridge to a stored positive-density span. The reply names the density band
and does not add that label to factual evidence.

The Nammade scan is the only reader of word relations. It builds them from
the evaluated authorized spans. These word pairs represent co-occurrence and span polarity. The relation kind is the channel's logical
polarity: `entails` when `b > 0`, `contradicts` when `b < 0`, and
`orthogonal` when `b = 0`. The same record keeps `a`, `c`, and `d`. A pair
is a polarity bridge when one of those spans has `d <= -1` and another has
`d >= 1`. Ingest does not write these relations, and the category-hop file
and relational tail stay unchanged.


## Research routing

Explicit `Nammade: <query>` runs a standalone scan. `Research <topic>`,
`Investigate <topic>`, and invention or hypothesis commands run three branches
from one authorized snapshot. The calling thread assembles innovation proposals
while two bounded workers generate source-attributed hypothesis options and run
Nammade diagnostics. The Nammade worker uses its topical and explicit-span
comparisons in memory. Its standalone route also supports dense retrieval and
persistence. The workers avoid concurrent writes to the appliance database.

After the three branches return, `resolve_hypotheses` runs
[the abductive bridge](abductive-bridge-node.md) on the Nammade evaluations.
The bridge can prepend one unverified relational candidate, or it can compile
the user's named model against stored bounds. It does not write the index.
A standalone Nammade scan does not call it. The recorded stage order is
`taxonomy_invention`, `research_hypotheses`, `nammade_equilibrium`,
`abductive_bridge`.

The combined reply names all three methods and shows each result, including empty branches. It includes the leading Nammade source excerpts and the comparison count. A bridged candidate is printed under Hypothesis generation with the line that the mechanism is an unverified hypothesis and is not a stored fact. The API also exposes per-method outcomes in `research_methods`, including `abductive_bridge` with `promotion: blocked`. API
clients can inspect `invention.proposals`, `research_options`,
`nammade.evaluations`, and `abductive_bridge`. Hypothesis options preserve the source prediction and
suggest a test. They do not report that an experiment was run. Research
documents can attach diagnostics using the document topic. Strict Evidence Mode
skips the branches. CrossDomain and numeric constraint routes keep their own
source-selection contracts.

## Placement against the current pipeline

A prompt today is encoded once into a 1024-d VectorPrism tensor. That tensor is
the query for pgvector and for every later channel rank. Six readings then
share the retrieved shortlist: dense, relational, disentangled, hyperbolic,
identity, and causal. The dense core stays the encoded vector. Training writes
second- and third-hand word relations into the tail of the relational channel
and does not replace that core.

The layout in this design is a new partitioned representation:

```text
v_w = [ e_base || e_pos || e_intensity || f_tone || e_nammade ]
```

Those four existing names are the design's names. They are not the six channel
readings above, and they are not slices of the stored 1024-d tensor.
`e_nammade` is an additional orthogonal `float32` channel of length 4. It must
be stored and scanned beside `e_base`. It must not overwrite the denotative
core or change the width of the existing pgvector column.

`NammadeEquilibriumNode` is specified as one resource-bounded ChorusGraph node,
run in the same pass as `PrismThinker` and `PossibilityHorizonNode`, before
`StylisticGenerationNode`. `PossibilityHorizonNode` is part of this proposal.
The stylistic node may render the enriched frame. It may not add, drop, or
rewrite the frame's source facts. The frame keys in this document are this
node's contract. They are not a universal semantic-frame adapter for every
other producer.

## 1. Multi-channel vector extension (`e_nammade`)

Every word, span, and axiom appends a dedicated orthogonal 4D `float32`
Nammade channel beside the existing channels. The denotative core is unchanged.

```text
e_nammade = [a, b, c, d]
v_w = [ e_base || e_pos || e_intensity || f_tone || e_nammade ]
```

### 3D spatial state

`r = a x̂ + b ŷ + c ẑ`, with `r = (a, b, c) ∈ R³`.

- **`a` (structural topology).** Projection along domain-invariant causal and mathematical primitives.
- **`b` (logical polarity).** Directional alignment from contradiction (`-1.0`) through orthogonal independence (`0.0`) to direct entailment (`+1.0`).
- **`c` (horizon scale).** Continuous scale from local specificity (`-1.0`) to universal cross-science invariance (`+1.0`).

The type below enforces a range only on `d`. The descriptions of `b` and `c`
are the intended scale. They are not a constructor check in the reference.

### Zero-free density scalar

`d ∈ (-∞, -1.0] ∪ [1.0, +∞)`.

- No vector entry and no query state may hold a density in `(-1.0, 1.0)`.
- A raw scalar at or above `0` snaps to `max(1.0, raw)`. Exact `0` and every value in `(0, 1)` become `+1.0`.
- A raw scalar below `0` snaps to `min(-1.0, raw)`. Every value in `(-1, 0)` becomes `-1.0`.
- Values already outside `(-1, 1)` are unchanged.
- **Matter regime** (`d ≥ +1.0`, increasing toward `+∞`). Compressed, verified empirical facts and invariants. `+∞` is the Diamond certainty limit.
- **Nammade regime** (`d ≤ -1.0`, decreasing toward `-∞`). Uncompressed open wave potential and exploratory hypotheses. `-∞` is the Nammade ocean.

The reference encoder does not reject non-finite input. `NaN` fails both
range comparisons, so the constructor as written can accept it. An
implementation must reject non-finite `a`, `b`, `c`, and `d`.

## 2. Spherical volumetric balance

The balance is computed on the 3D spatial state only. Density is not part of
the displacement. For a query `r₁ = (a₁, b₁, c₁, d₁)` and a knowledge-base
candidate `r₂ = (a₂, b₂, c₂, d₂)`:

```text
Δr = (a₂ - a₁, b₂ - b₁, c₂ - c₁)
‖Δr‖ = sqrt(Δa² + Δb² + Δc²)
```

The design states the equilibrium equation as:

```text
r₁ - r₂ = (4/3) π (r₂ - r₁)³
```

A cube of a 3D vector is not defined. The reference does not cube the vector,
and it does not cube the components. It reduces the equation to the scalar
residual of the Euclidean norm:

```text
Residual(i) = ‖Δrᵢ‖ + (4/3) π ‖Δrᵢ‖³
            = ‖Δrᵢ‖ (1 + (4/3) π ‖Δrᵢ‖²)
```

For every real norm, `(1 + (4/3) π ‖Δr‖²) ≥ 1`. The residual is therefore `0`
only at `‖Δr‖ = 0`. That is the only real root. `EQUILIBRIUM_LOCKED` is the
closed neighborhood of that root.

`R_eq = sqrt(3 / (4π)) ≈ 0.4886025119` is the positive solution of the
magnitude balance `‖Δr‖ = (4/3) π ‖Δr‖³`, which rearranges to
`‖Δr‖² = 3 / (4π)`. It is the cycle-phase scale. It is not a second root of
the signed residual. The reference constant is:

```text
EQUILIBRIUM_RADIUS = sqrt(3 / (4π))
φ_cycle = ‖Δr‖ / R_eq
```

### Regime classification (`NammadeRegime`)

Defaults: `ε_eq = 1e-3`, `diamond_threshold = 10.0`. The reference node applies
these tests in order, so a locked displacement wins over a Diamond density:

1. `EQUILIBRIUM_LOCKED` when `‖Δr‖ ≤ ε_eq`. Exact local volumetric balance, including when `|d₂|` is past the Diamond threshold.
2. `MATTER_INVARIANT` when `d₂ ≥ diamond_threshold` (default `10.0`). High-density verified empirical law.
3. `NAMMADE_FRONTIER` when `d₂ ≤ -diamond_threshold` (default `-10.0`). Deep uncompressed wave potential.
4. `DYNAMIC_CYCLE` otherwise: `‖Δr‖ > ε_eq` and `|d₂| < diamond_threshold`. No static real root exists, so the proposition stays in active wave propagation. The cycle phase ratio is `φ_cycle`.

Candidates with `Residual > max_residual` (default `2.5`) are removed before
classification. Polarity bridges are a separate flag. A bridge can occur in
any regime.

### Polarity-bridge detection

`is_polarity_bridge` is true when the query and the candidate sit on opposite
sides of the excluded gap:

- `(d₁ ≤ -1.0 and d₂ ≥ +1.0)`, or
- `(d₁ ≥ +1.0 and d₂ ≤ -1.0)`.

The reference uses the same test. Because a constructed channel cannot have
`d` inside `(-1, 1)`, `d₁ ≤ -1` selects candidates with `d₂ ≥ +1`, and every
other legal query selects candidates with `d₂ ≤ -1`.

## 3. ChorusGraph pipeline

`NammadeEquilibriumNode` runs as a single-pass, resource-bounded native node
in parallel with `PrismThinker` and `PossibilityHorizonNode`.
`StylisticGenerationNode` renders after the three results are joined.

```text
[Raw User Prompt + ResourceBudget]
       │
       ▼
[Front-End Tone, Context & Nammade State Encoder]
 • Emits NammadeChannel4D r1 = (a1, b1, c1, d1)
 • d1 is in (-∞, -1] ∪ [1, +∞)
       │
       ├────────────────────────────────┬────────────────────────────────┐
       ▼                                ▼                                ▼
[Scoped PrismThinker]       [PossibilityHorizonNode]        [NammadeEquilibriumNode]
 • Local deduction           • Unbiased full-KB sweep        • SIMD 3D volumetric balance
 • Emits base SISF           • Cross-science isomorphisms    • Polarity-bridge detection (-1 <-> +1)
                             • FrontierStatus boundary       • Regime classification
       │                                │                                │
       └────────────────────────────────┼────────────────────────────────┘
                                        ▼
                        [Unified Enriched SISF Frame]
                         • Primary Local Proposition
                         • Unbiased Horizon Possibilities
                         • Nammade Volumetric Evaluations & Polarity Bridges
                                        │
                                        ▼
                          [StylisticGenerationNode]
                           • Renders grounded certainty vs. open wave possibility
                           • Does not alter SISF facts
```

Frame keys written by the equilibrium node:

| Key | Value when the node runs | Value when it cannot scan |
| --- | --- | --- |
| `nammade_evaluations` | `NammadeEvaluation` records, smallest residual first | `[]` |
| `has_static_equilibrium` | `True` if any emitted record is `EQUILIBRIUM_LOCKED` | `False` |
| `polarity_bridges_found` | Count of emitted bridges | `0` |
| `nammade_frontier_status` | `RESOURCE_CAPPED` or `EVIDENCE_EXHAUSTED` | `EVIDENCE_EXHAUSTED` |

`EVIDENCE_EXHAUSTED` means no evaluation was emitted. That covers a missing
channel, a missing query state, an empty knowledge base, and a scan whose
every residual exceeded `max_residual`. `RESOURCE_CAPPED` means the survivor
list was cut to `budget.max_candidates`, or the per-record loop stopped
because elapsed time exceeded `budget.cpu_budget_ms`. The budget field is in
milliseconds. `ResourceBudget` and `FrontierStatus` are named by this design
and are not defined in the reference `types.py` block. An implementation must
define them, including the defaults used by `ResourceBudget()`.

## 4. Reference implementation

The relational encoder takes a projection matrix of shape `(3, K)` and a
relational vector of shape `(K,)`. Those widths are not fixed here. The
knowledge-base array is contiguous `float32` of shape `(N, 4)`, column order
`[a, b, c, d]`. Each scanned row has metadata `source_id`, `span_text`, and
`span_hash`.

### `types.py`

```python
from dataclasses import dataclass
from enum import Enum
import numpy as np


class NammadeRegime(str, Enum):
    EQUILIBRIUM_LOCKED = "EQUILIBRIUM_LOCKED"   # Volumetric balance achieved (||dr|| <= eps)
    DYNAMIC_CYCLE      = "DYNAMIC_CYCLE"        # Non-zero displacement: continuous wave propagation
    MATTER_INVARIANT   = "MATTER_INVARIANT"     # High positive density (+inf Diamond certainty)
    NAMMADE_FRONTIER   = "NAMMADE_FRONTIER"     # Deep negative density (-inf open wave potential)


@dataclass(frozen=True)
class NammadeChannel4D:
    """
    4D Nammade vector channel: e_nammade = [a, b, c, d]
      - r = (a, b, c): 3D spatial state vector
      - d: zero-free density scalar in (-inf, -1.0] U [1.0, +inf)
    """
    a: float
    b: float
    c: float
    d: float

    def __post_init__(self):
        if -1.0 < self.d < 1.0:
            raise ValueError(f"Zero-free invariant violated: density {self.d} cannot lie in (-1.0, 1.0).")

    def spatial_vec(self) -> np.ndarray:
        return np.array([self.a, self.b, self.c], dtype=np.float32)

    def as_channel_vec(self) -> np.ndarray:
        return np.array([self.a, self.b, self.c, self.d], dtype=np.float32)


@dataclass(frozen=True)
class NammadeEvaluation:
    source_id: str
    span_text: str
    span_hash: str
    regime: NammadeRegime
    displacement_norm: float       # ||r2 - r1||
    volumetric_residual: float     # ||dr|| + (4/3)*pi*||dr||^3
    cycle_phase_ratio: float       # ||dr|| / sqrt(3 / (4*pi))
    candidate_density: float       # d2 in (-inf, -1.0] U [1.0, +inf)
    is_polarity_bridge: bool       # True if crossing -1.0 <-> +1.0 boundary
```

### `nammade_channel.py`

```python
import math
from typing import Tuple
import numpy as np
from .types import NammadeChannel4D


class NammadeChannelEncoder:
    """
    Encodes relational embeddings and epistemic verification weights into
    the zero-free 4D Nammade channel e_nammade = [a, b, c, d].
    """
    EQUILIBRIUM_RADIUS = math.sqrt(3.0 / (4.0 * math.pi))  # ~0.48860251

    @staticmethod
    def enforce_zero_free(raw_density: float) -> float:
        """
        Enforces the zero-free continuum (-inf, -1.0] U [1.0, +inf)
        with a discrete unit jump across zero.
        """
        if raw_density >= 0.0:
            return max(1.0, float(raw_density))
        return min(-1.0, float(raw_density))

    @classmethod
    def encode_from_relational(
        cls,
        rel_vector: np.ndarray,
        projection_matrix: np.ndarray,
        raw_epistemic_weight: float,
    ) -> NammadeChannel4D:
        r3 = (projection_matrix @ rel_vector.astype(np.float32)).astype(np.float32)
        d = cls.enforce_zero_free(raw_epistemic_weight)
        return NammadeChannel4D(a=float(r3[0]), b=float(r3[1]), c=float(r3[2]), d=d)

    @classmethod
    def batch_volumetric_metrics(
        cls,
        q_channel: NammadeChannel4D,
        kb_nammade_soa: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        SIMD-vectorized computation over contiguous float32 array of shape (N, 4):
        Returns (distances, residuals, cycle_ratios, polarity_bridges).
        """
        q_r = q_channel.spatial_vec()
        kb_r = kb_nammade_soa[:, :3]
        kb_d = kb_nammade_soa[:, 3]

        dr = kb_r - q_r
        distances = np.linalg.norm(dr, axis=1)
        residuals = distances + (4.0 / 3.0) * math.pi * np.power(distances, 3)
        cycle_ratios = distances / cls.EQUILIBRIUM_RADIUS

        if q_channel.d <= -1.0:
            polarity_bridges = kb_d >= 1.0
        else:
            polarity_bridges = kb_d <= -1.0

        return distances, residuals, cycle_ratios, polarity_bridges
```

### `nammade_node.py`

```python
import time
from typing import Dict, Any, List
import numpy as np
from .types import (
    NammadeRegime,
    NammadeChannel4D,
    NammadeEvaluation,
    ResourceBudget,
    FrontierStatus,
)
from .nammade_channel import NammadeChannelEncoder


class NammadeEquilibriumNode:
    """
    Native ChorusGraph execution node inside cpu-llm.
    Evaluates the 4D Nammade vector channel across the entire SoA KB using
    the spherical volumetric balance equation r1 - r2 = (4/3)*pi*(r2 - r1)^3.
    """
    def __init__(
        self,
        soa_kb: Dict[str, Any],
        eq_epsilon: float = 1e-3,
        diamond_threshold: float = 10.0,
        max_residual: float = 2.5,
    ):
        self.kb = soa_kb
        self.eq_epsilon = eq_epsilon
        self.diamond_threshold = diamond_threshold
        self.max_residual = max_residual

    def execute(
        self,
        sisf_frame: Dict[str, Any],
        budget: ResourceBudget = ResourceBudget(),
    ) -> Dict[str, Any]:
        t_start = time.perf_counter()
        channels: np.ndarray | None = self.kb.get("nammade_channels")
        q_channel: NammadeChannel4D | None = sisf_frame.get("nammade_query_channel")

        if channels is None or len(channels) == 0 or q_channel is None:
            sisf_frame["nammade_evaluations"] = []
            sisf_frame["has_static_equilibrium"] = False
            sisf_frame["polarity_bridges_found"] = 0
            sisf_frame["nammade_frontier_status"] = FrontierStatus.EVIDENCE_EXHAUSTED
            return sisf_frame

        distances, residuals, cycle_ratios, bridges = NammadeChannelEncoder.batch_volumetric_metrics(
            q_channel=q_channel,
            kb_nammade_soa=channels,
        )

        valid_idx = np.where(residuals <= self.max_residual)[0]
        if len(valid_idx) == 0:
            sisf_frame["nammade_evaluations"] = []
            sisf_frame["has_static_equilibrium"] = False
            sisf_frame["polarity_bridges_found"] = 0
            sisf_frame["nammade_frontier_status"] = FrontierStatus.EVIDENCE_EXHAUSTED
            return sisf_frame

        order = np.argsort(residuals[valid_idx])
        frontier_status = FrontierStatus.EVIDENCE_EXHAUSTED
        if len(order) > budget.max_candidates:
            order = order[: budget.max_candidates]
            frontier_status = FrontierStatus.RESOURCE_CAPPED

        scan_indices = valid_idx[order]
        evaluations: List[NammadeEvaluation] = []
        has_static_eq = False
        bridge_count = 0

        for idx in scan_indices:
            if (time.perf_counter() - t_start) * 1000.0 > budget.cpu_budget_ms:
                frontier_status = FrontierStatus.RESOURCE_CAPPED
                break

            dist = float(distances[idx])
            res = float(residuals[idx])
            c_ratio = float(cycle_ratios[idx])
            d2 = float(channels[idx, 3])
            is_bridge = bool(bridges[idx])

            if dist <= self.eq_epsilon:
                regime = NammadeRegime.EQUILIBRIUM_LOCKED
                has_static_eq = True
            elif d2 >= self.diamond_threshold:
                regime = NammadeRegime.MATTER_INVARIANT
            elif d2 <= -self.diamond_threshold:
                regime = NammadeRegime.NAMMADE_FRONTIER
            else:
                regime = NammadeRegime.DYNAMIC_CYCLE

            if is_bridge:
                bridge_count += 1

            meta = self.kb["metadata"][idx]
            evaluations.append(NammadeEvaluation(
                source_id=meta["source_id"],
                span_text=meta["span_text"],
                span_hash=meta["span_hash"],
                regime=regime,
                displacement_norm=dist,
                volumetric_residual=res,
                cycle_phase_ratio=c_ratio,
                candidate_density=d2,
                is_polarity_bridge=is_bridge,
            ))

        sisf_frame["nammade_evaluations"] = evaluations
        sisf_frame["has_static_equilibrium"] = has_static_eq
        sisf_frame["polarity_bridges_found"] = bridge_count
        sisf_frame["nammade_frontier_status"] = frontier_status
        return sisf_frame
```

`ResourceBudget` and `FrontierStatus` are imported by this reference and are
not declared in the `types.py` block. The node reads `max_candidates` and
`cpu_budget_ms`.

## 5. PostgreSQL and SoA storage

Proposed table `cpullm_kb_spans`, which is not a current table in this checkout:

- `nammade_a`, `nammade_b`, `nammade_c`, and `nammade_d` are `FLOAT4`.
- `CHECK (nammade_d <= -1.0 OR nammade_d >= 1.0)`.
- Index on `nammade_d`.
- The node also reads `source_id`, `span_text`, and `span_hash` for each row. Those fields are part of the runtime metadata contract even though they are not Nammade columns.

The CPU runtime streams `(nammade_a, nammade_b, nammade_c, nammade_d)` into a
contiguous `float32` NumPy array of shape `(N, 4)` and runs the volumetric
scan on that array.

## Open point: volumetric stiffness

[The Nammade Continuum (Verified Edition)](nammade-continuum-verified-edition.md)
writes the same balance with a dimensional stiffness `κ` in `m⁻²`:

```text
r₁ - r₂ = κ (4/3) π (r₂ - r₁)³
R_eq = sqrt(3 / (4πκ))
```

The landed node takes `κ` as a positive finite constructor argument, scales
the cubic term by `κ`, and uses `R_eq = sqrt(3 / (4πκ))`. The default is
`κ = 1`, which keeps `EQUILIBRIUM_RADIUS = sqrt(3 / (4π))`. `κ` must be
finite and strictly positive so that radius is real.
