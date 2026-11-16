"""Zero-free encoder and the volumetric residual.

The residual is a strictly increasing function of the Euclidean distance
between the 3D spatial states. It is zero only when that distance is zero.
``R_eq = sqrt(3 / (4 π κ))`` scales the cycle ratio. It is not a second root.
"""
from __future__ import annotations

import math

import numpy as np

from cpu_llm.nammade.types import NammadeChannel4D, _finite_number


def require_kappa(kappa: object) -> float:
    """Stiffness in m^-2. It must be finite and strictly positive."""
    number = _finite_number("kappa", kappa)
    if number <= 0.0:
        raise ValueError("kappa must be finite and strictly positive")
    return number


def equilibrium_radius(kappa: float = 1.0) -> float:
    stiffness = require_kappa(kappa)
    return math.sqrt(3.0 / (4.0 * math.pi * stiffness))


class NammadeChannelEncoder:
    """Encode a relational vector and an epistemic weight into ``[a, b, c, d]``."""

    EQUILIBRIUM_RADIUS = math.sqrt(3.0 / (4.0 * math.pi))

    @staticmethod
    def enforce_zero_free(raw_density: float) -> float:
        """Snap onto ``(-inf, -1] U [1, +inf)``. Exact 0 lands on +1."""
        number = _finite_number("density", raw_density)
        if number >= 0.0:
            return max(1.0, number)
        return min(-1.0, number)

    @classmethod
    def encode_from_relational(
        cls,
        rel_vector: np.ndarray,
        projection_matrix: np.ndarray,
        raw_epistemic_weight: float,
    ) -> NammadeChannel4D:
        vector = np.asarray(rel_vector, dtype=np.float32).reshape(-1)
        matrix = np.asarray(projection_matrix, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[0] != 3 or matrix.shape[1] != vector.shape[0]:
            raise ValueError("projection_matrix must have shape (3, K) for a relational vector of length K")
        if not np.isfinite(matrix).all() or not np.isfinite(vector).all():
            raise ValueError("projection inputs must be finite")
        projected = (matrix @ vector).astype(np.float32)
        density = cls.enforce_zero_free(raw_epistemic_weight)
        return NammadeChannel4D(
            a=float(projected[0]),
            b=float(projected[1]),
            c=float(projected[2]),
            d=density,
        )

    @classmethod
    def batch_volumetric_metrics(
        cls,
        q_channel: NammadeChannel4D,
        kb_nammade_soa: np.ndarray,
        kappa: float = 1.0,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return distances, residuals, cycle ratios, and polarity bridges.

        ``kb_nammade_soa`` is contiguous ``float32`` of shape ``(N, 4)``.
        The residual uses the 3D spatial displacement only:

        ``‖Δr‖ + κ (4/3) π ‖Δr‖³``
        """
        stiffness = require_kappa(kappa)
        channels = np.asarray(kb_nammade_soa, dtype=np.float32)
        if channels.ndim != 2 or channels.shape[1] != 4 or not np.isfinite(channels).all():
            raise ValueError("kb_nammade_soa must be a finite float array of shape (N, 4)")
        query = q_channel.spatial_vec()
        displacement = channels[:, :3] - query
        distances = np.linalg.norm(displacement, axis=1)
        residuals = distances + stiffness * (4.0 / 3.0) * math.pi * np.power(distances, 3)
        cycle_ratios = distances / equilibrium_radius(stiffness)
        density = channels[:, 3]
        if q_channel.d <= -1.0:
            bridges = density >= 1.0
        else:
            bridges = density <= -1.0
        return distances, residuals, cycle_ratios, bridges
