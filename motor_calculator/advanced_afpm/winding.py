"""Explicit AFPM winding semantics without inferred factors."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


class WindingType(str, Enum):
    CONCENTRATED = "concentrated"
    DISTRIBUTED = "distributed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AFPMWinding:
    turns_per_coil: int | None
    coils_per_phase: int | None
    turns_per_phase: int | None
    parallel_branches: int | None
    connection: str | None
    winding_factor: float | None
    pitch_factor: float | None
    distribution_factor: float | None
    winding_type: WindingType
    stator_interconnection: str | None = None

    def __post_init__(self) -> None:
        for name in ("turns_per_coil", "coils_per_phase", "turns_per_phase", "parallel_branches"):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive when provided")
        for name in ("winding_factor", "pitch_factor", "distribution_factor"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or not 0.0 < value <= 1.0):
                raise ValueError(f"{name} must be within (0, 1]")
