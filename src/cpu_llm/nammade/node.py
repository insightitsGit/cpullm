"""Resource-bounded volumetric scan over a contiguous Nammade channel array."""
from __future__ import annotations

import time
from typing import Any

import numpy as np

from cpu_llm.nammade.channel import NammadeChannelEncoder, require_kappa
from cpu_llm.nammade.types import (
    FrontierStatus,
    NammadeChannel4D,
    NammadeEvaluation,
    NammadeRegime,
    ResourceBudget,
)


class NammadeEquilibriumNode:
    """Score ``r1 - r2 = κ (4/3) π (r2 - r1)³`` on the 3D spatial channel.

    The cubic term is the scalar residual of the Euclidean norm. Density
    classifies the surviving spans and detects a cross-gap polarity bridge.
    A span marked ``force_admit`` already cleared the trained dense core, so the
    residual cap does not drop it and a lexical origin is not treated as a lock.
    This node writes scan keys onto the frame and does not change source text.
    """

    def __init__(
        self,
        soa_kb: dict[str, Any],
        eq_epsilon: float = 1e-3,
        diamond_threshold: float = 10.0,
        max_residual: float = 2.5,
        kappa: float = 1.0,
    ):
        self.kb = soa_kb
        self.eq_epsilon = float(eq_epsilon)
        self.diamond_threshold = float(diamond_threshold)
        self.max_residual = float(max_residual)
        self.kappa = require_kappa(kappa)
        if not np.isfinite(self.eq_epsilon) or self.eq_epsilon <= 0:
            raise ValueError("eq_epsilon must be a positive finite distance")
        if not np.isfinite(self.diamond_threshold) or self.diamond_threshold < 1.0:
            raise ValueError("diamond_threshold must be a finite number of at least 1")
        if not np.isfinite(self.max_residual) or self.max_residual <= 0:
            raise ValueError("max_residual must be a positive finite residual")

    def execute(
        self,
        sisf_frame: dict[str, Any],
        budget: ResourceBudget = ResourceBudget(),
    ) -> dict[str, Any]:
        if not isinstance(budget, ResourceBudget):
            raise ValueError("budget must be a ResourceBudget")
        started = time.perf_counter()
        channels = self.kb.get("nammade_channels")
        query = sisf_frame.get("nammade_query_channel")
        metadata = self.kb.get("metadata") or []

        def empty(status: FrontierStatus = FrontierStatus.EVIDENCE_EXHAUSTED) -> dict[str, Any]:
            sisf_frame["nammade_evaluations"] = []
            sisf_frame["has_static_equilibrium"] = False
            sisf_frame["polarity_bridges_found"] = 0
            sisf_frame["nammade_frontier_status"] = status
            return sisf_frame

        if channels is None or len(channels) == 0 or not isinstance(query, NammadeChannel4D):
            return empty()
        if len(metadata) != len(channels):
            raise ValueError("nammade metadata must align with nammade_channels")

        distances, residuals, cycle_ratios, bridges = NammadeChannelEncoder.batch_volumetric_metrics(
            q_channel=query,
            kb_nammade_soa=channels,
            kappa=self.kappa,
        )
        dense_gated = np.array([bool(item.get("dense_gated")) for item in metadata], dtype=bool)
        force_admit = np.array([bool(item.get("force_admit")) for item in metadata], dtype=bool)
        admitted = (dense_gated & force_admit) | (~dense_gated & (residuals <= self.max_residual))
        valid_idx = np.where(admitted)[0]
        if len(valid_idx) == 0:
            return empty()

        rank = np.empty(len(valid_idx), dtype=np.float64)
        for position, idx in enumerate(valid_idx):
            meta = metadata[int(idx)]
            if meta.get("force_admit"):
                rank[position] = -float(meta.get("topic_overlap") or 0) - float(meta.get("dense_similarity") or 0.0)
            else:
                rank[position] = float(residuals[idx])
        order = np.argsort(rank, kind="stable")
        if any(item.get("boundary_premise") for item in metadata):
            order = np.array(sorted(order, key=lambda index: not metadata[int(valid_idx[index])].get("boundary_premise")))
        frontier_status = FrontierStatus.EVIDENCE_EXHAUSTED
        if len(order) > budget.max_candidates:
            order = order[: budget.max_candidates]
            frontier_status = FrontierStatus.RESOURCE_CAPPED

        evaluations: list[NammadeEvaluation] = []
        has_static_eq = False
        bridge_count = 0
        for idx in valid_idx[order]:
            if (time.perf_counter() - started) * 1000.0 > budget.cpu_budget_ms:
                frontier_status = FrontierStatus.RESOURCE_CAPPED
                break
            distance = float(distances[idx])
            residual = float(residuals[idx])
            ratio = float(cycle_ratios[idx])
            density = float(channels[idx, 3])
            bridge = bool(bridges[idx])
            meta = metadata[int(idx)]
            if distance <= self.eq_epsilon and not meta.get("force_admit"):
                regime = NammadeRegime.EQUILIBRIUM_LOCKED
                has_static_eq = True
            elif density >= self.diamond_threshold:
                regime = NammadeRegime.MATTER_INVARIANT
            elif density <= -self.diamond_threshold:
                regime = NammadeRegime.NAMMADE_FRONTIER
            else:
                regime = NammadeRegime.DYNAMIC_CYCLE
            if bridge:
                bridge_count += 1
            similarity = meta.get("dense_similarity")
            evaluations.append(NammadeEvaluation(
                source_id=str(meta["source_id"]),
                span_text=str(meta["span_text"]),
                span_hash=str(meta["span_hash"]),
                regime=regime,
                displacement_norm=distance,
                volumetric_residual=residual,
                cycle_phase_ratio=ratio,
                candidate_density=density,
                is_polarity_bridge=bridge,
                dense_similarity=None if similarity is None else float(similarity),
            ))

        sisf_frame["nammade_evaluations"] = evaluations
        sisf_frame["has_static_equilibrium"] = has_static_eq
        sisf_frame["polarity_bridges_found"] = bridge_count
        sisf_frame["nammade_frontier_status"] = frontier_status
        return sisf_frame
