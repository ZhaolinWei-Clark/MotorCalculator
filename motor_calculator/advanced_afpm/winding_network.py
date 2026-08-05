"""Explicit AFPM coil, branch, stator, and phase connection physics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from .winding import WindingType


class StatorConnection(str, Enum):
    SERIES = "series"
    PARALLEL = "parallel"
    INDEPENDENT = "independent"
    UNKNOWN = "unknown"


class PhaseConnection(str, Enum):
    Y = "Y"
    DELTA = "Delta"
    UNKNOWN = "unknown"


class WindingFactorMethod(str, Enum):
    DIRECT = "direct_source_kw"
    DERIVED_KP_KD = "derived_kw_equals_kp_times_kd"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class WindingFactorResolution:
    value: float | None
    method: WindingFactorMethod
    notes: tuple[str, ...]


@dataclass(frozen=True)
class StatorEMFCombination:
    per_stator_phase_emf_v: float
    terminal_phase_emf_v: float | None
    independent_stator_phase_emfs_v: tuple[float, ...]
    connection: StatorConnection
    notes: tuple[str, ...]


@dataclass(frozen=True)
class AFPMWindingNetwork:
    turns_per_coil: int | None
    coils_per_phase: int | None
    series_coils_per_branch: int | None
    parallel_branches: int | None
    number_of_stators: int
    stator_connection: StatorConnection
    phase_connection: PhaseConnection
    winding_type: WindingType
    winding_factor: float | None
    pitch_factor: float | None
    distribution_factor: float | None
    winding_type_description: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "turns_per_coil",
            "coils_per_phase",
            "series_coils_per_branch",
            "parallel_branches",
            "number_of_stators",
        ):
            value = getattr(self, name)
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive when provided")
        for name in ("winding_factor", "pitch_factor", "distribution_factor"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or not 0.0 < value <= 1.0):
                raise ValueError(f"{name} must be within (0, 1]")
        if (
            self.coils_per_phase is not None
            and self.series_coils_per_branch is not None
            and self.parallel_branches is not None
            and self.coils_per_phase != self.series_coils_per_branch * self.parallel_branches
        ):
            raise ValueError(
                "coils_per_phase must equal series_coils_per_branch * parallel_branches"
            )

    @property
    def effective_series_turns_per_phase(self) -> int | None:
        if self.turns_per_coil is None or self.series_coils_per_branch is None:
            return None
        return self.turns_per_coil * self.series_coils_per_branch

    def resolve_winding_factor(self) -> WindingFactorResolution:
        if self.winding_factor is not None:
            return WindingFactorResolution(
                self.winding_factor,
                WindingFactorMethod.DIRECT,
                ("Direct source-equivalent kw has priority; kp/kd are not substituted.",),
            )
        if self.pitch_factor is not None and self.distribution_factor is not None:
            return WindingFactorResolution(
                self.pitch_factor * self.distribution_factor,
                WindingFactorMethod.DERIVED_KP_KD,
                ("Safely derived as kw = kp * kd because both factors are explicit.",),
            )
        return WindingFactorResolution(
            None,
            WindingFactorMethod.UNAVAILABLE,
            ("Geometry or winding type alone is insufficient to invent kw.",),
        )

    def combine_identical_stator_phase_emf(self, per_stator_phase_emf_v: float) -> StatorEMFCombination:
        if not math.isfinite(per_stator_phase_emf_v) or per_stator_phase_emf_v < 0.0:
            raise ValueError("per_stator_phase_emf_v must be finite and non-negative")
        values = (per_stator_phase_emf_v,) * self.number_of_stators
        if self.stator_connection is StatorConnection.SERIES:
            return StatorEMFCombination(
                per_stator_phase_emf_v,
                per_stator_phase_emf_v * self.number_of_stators,
                values,
                self.stator_connection,
                ("Identical stator phase EMFs add in series.",),
            )
        if self.stator_connection is StatorConnection.PARALLEL:
            return StatorEMFCombination(
                per_stator_phase_emf_v,
                per_stator_phase_emf_v,
                values,
                self.stator_connection,
                ("Parallel stators preserve terminal EMF; only current capability changes.",),
            )
        if self.stator_connection is StatorConnection.INDEPENDENT:
            return StatorEMFCombination(
                per_stator_phase_emf_v,
                None,
                values,
                self.stator_connection,
                ("Independent stators have no single combined terminal phase EMF.",),
            )
        return StatorEMFCombination(
            per_stator_phase_emf_v,
            None,
            values,
            self.stator_connection,
            ("Unknown stator connection blocks terminal EMF aggregation.",),
        )

    def phase_rms_to_line_rms(self, phase_rms_v: float) -> float | None:
        if not math.isfinite(phase_rms_v) or phase_rms_v < 0.0:
            raise ValueError("phase_rms_v must be finite and non-negative")
        if self.phase_connection is PhaseConnection.Y:
            return math.sqrt(3.0) * phase_rms_v
        if self.phase_connection is PhaseConnection.DELTA:
            return phase_rms_v
        return None
