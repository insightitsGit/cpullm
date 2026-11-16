"""Contracts for the Nammade channel and equilibrium node."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

import numpy as np


class NammadeRegime(str, Enum):
    EQUILIBRIUM_LOCKED = "EQUILIBRIUM_LOCKED"
    DYNAMIC_CYCLE = "DYNAMIC_CYCLE"
    MATTER_INVARIANT = "MATTER_INVARIANT"
    NAMMADE_FRONTIER = "NAMMADE_FRONTIER"


class FrontierStatus(str, Enum):
    EVIDENCE_EXHAUSTED = "EVIDENCE_EXHAUSTED"
    RESOURCE_CAPPED = "RESOURCE_CAPPED"


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


@dataclass(frozen=True)
class ResourceBudget:
    """Scan limits. ``cpu_budget_ms`` is milliseconds."""

    max_candidates: int = 32
    cpu_budget_ms: float = 250.0

    def __post_init__(self) -> None:
        if isinstance(self.max_candidates, bool) or type(self.max_candidates) is not int or self.max_candidates < 1:
            raise ValueError("max_candidates must be an integer of at least 1")
        if not math.isfinite(self.cpu_budget_ms) or self.cpu_budget_ms <= 0:
            raise ValueError("cpu_budget_ms must be a positive finite number of milliseconds")


@dataclass(frozen=True)
class NammadeChannel4D:
    """4D channel ``e_nammade = [a, b, c, d]``.

    ``r = (a, b, c)`` is the spatial state. ``d`` is the zero-free density in
    ``(-inf, -1] U [1, +inf)``.
    """

    a: float
    b: float
    c: float
    d: float

    def __post_init__(self) -> None:
        a = _finite_number("a", self.a)
        b = _finite_number("b", self.b)
        c = _finite_number("c", self.c)
        d = _finite_number("d", self.d)
        if -1.0 < d < 1.0:
            raise ValueError(f"Zero-free invariant violated: density {d} cannot lie in (-1.0, 1.0).")
        object.__setattr__(self, "a", a)
        object.__setattr__(self, "b", b)
        object.__setattr__(self, "c", c)
        object.__setattr__(self, "d", d)

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
    displacement_norm: float
    volumetric_residual: float
    cycle_phase_ratio: float
    candidate_density: float
    is_polarity_bridge: bool
    dense_similarity: float | None = None
