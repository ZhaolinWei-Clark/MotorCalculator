"""FEA raw results, provenance, and extraction of the three validated quantities.

Every stored number carries provenance. In particular every result records
whether it came from a real solver or from the mock pipeline: ``is_mock`` is a
required field, not an optional flag, so mock data can never quietly present
itself as validation evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping

import numpy as np

from .models import FEAValidationTarget

FEA_RESULT_SCHEMA_VERSION = "phase10a.fea.result.v1"


@dataclass(frozen=True)
class FEAPositionSample:
    """One solved rotor position."""

    rotor_angle_mech_deg: float
    phase_flux_linkage_wb_turn: Mapping[str, float]
    circumferential_force_n: float | None
    element_count: int | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.rotor_angle_mech_deg):
            raise ValueError("rotor angle must be finite")
        for name, value in self.phase_flux_linkage_wb_turn.items():
            if not math.isfinite(value):
                raise ValueError(f"flux linkage for phase {name} must be finite")
        if self.circumferential_force_n is not None and not math.isfinite(
            self.circumferential_force_n
        ):
            raise ValueError("circumferential force must be finite")


@dataclass(frozen=True)
class FEAResultProvenance:
    """Who produced this result, from what, and how."""

    solver: str
    solver_version: str
    is_mock: bool
    case_id: str
    analytical_fingerprint: str
    schema_version: str
    mesh_policy_name: str
    requested_mesh_sizes_m: Mapping[str, float]
    reported_element_count: int | None
    symmetry_applied: bool
    sector_fraction: float
    sample_count: int
    extraction_method: str
    material_assumptions: tuple[str, ...]
    operating_point_summary: Mapping[str, float]
    timestamp_utc: str
    solve_seconds: float | None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.solver.strip() or not self.solver_version.strip():
            raise ValueError("solver identity must be explicit")
        if not self.case_id.strip():
            raise ValueError("a result must be bound to a case hash")
        if self.is_mock and "MOCK" not in self.solver.upper():
            raise ValueError("a mock result must name a mock solver")
        if not self.is_mock and "MOCK" in self.solver.upper():
            raise ValueError("a real result must not name a mock solver")


@dataclass(frozen=True)
class FEARawResult:
    """A complete solved position sweep with its provenance."""

    target: FEAValidationTarget
    provenance: FEAResultProvenance
    samples: tuple[FEAPositionSample, ...]
    mechanical_speed_rpm: float
    mean_radius_m: float
    pole_pairs: int
    span_mech_deg: float

    def __post_init__(self) -> None:
        if len(self.samples) < 8:
            raise ValueError("at least eight solved positions are required")
        if len(self.samples) != self.provenance.sample_count:
            raise ValueError("sample count does not match the recorded provenance")
        angles = [sample.rotor_angle_mech_deg for sample in self.samples]
        if any(right <= left for left, right in zip(angles, angles[1:])):
            raise ValueError("rotor angles must be strictly increasing")
        step = self.span_mech_deg / len(self.samples)
        tolerance = max(abs(step) * 1e-9, 1e-12)
        for index, angle in enumerate(angles):
            expected = angles[0] + step * index
            if abs(angle - expected) > tolerance:
                raise ValueError("rotor angles must be uniformly spaced over the declared span")

    @property
    def is_mock(self) -> bool:
        return self.provenance.is_mock

    def phase_names(self) -> tuple[str, ...]:
        return tuple(sorted(self.samples[0].phase_flux_linkage_wb_turn))

    def flux_linkage_series(self, phase: str) -> np.ndarray:
        return np.array(
            [sample.phase_flux_linkage_wb_turn[phase] for sample in self.samples], dtype=float
        )

    def torque_series_nm(self) -> np.ndarray | None:
        """Circumferential force converted to torque as ``T = F_x * r_mean``."""

        if any(sample.circumferential_force_n is None for sample in self.samples):
            return None
        forces = np.array(
            [float(sample.circumferential_force_n) for sample in self.samples], dtype=float
        )
        return forces * self.mean_radius_m


@dataclass(frozen=True)
class FEABackEmfExtraction:
    """Back-EMF derived from the no-load flux-linkage waveform."""

    phase_rms_v: float
    phase_peak_v: float
    phase_fundamental_rms_v: float
    line_rms_v: float
    back_emf_constant_phase_rms_v_per_rad_s: float
    flux_linkage_peak_wb_turn: float
    flux_linkage_fundamental_peak_wb_turn: float
    mechanical_speed_rpm: float
    method: str
    speed_scaling_note: str


@dataclass(frozen=True)
class FEATorqueExtraction:
    """Average torque and ripple over the sampled span."""

    average_torque_nm: float
    peak_torque_nm: float
    minimum_torque_nm: float
    peak_to_peak_torque_nm: float
    ripple_percent: float | None
    sample_count: int
    method: str


@dataclass(frozen=True)
class FEACoggingExtraction:
    """Cogging waveform descriptors over one cogging period."""

    peak_positive_nm: float
    peak_negative_nm: float
    peak_to_peak_nm: float
    amplitude_nm: float
    rms_nm: float
    fundamental_amplitude_nm: float
    sample_count: int
    method: str


#: A magnetostatic solve carries no eddy-current reaction and no frequency
#: dependence, so flux linkage is speed-independent and the induced voltage
#: scales exactly linearly with speed. That is a property of the formulation,
#: not an approximation added here.
SPEED_SCALING_NOTE = (
    "magnetostatic flux linkage is speed-independent, so back-EMF scales exactly "
    "linearly with mechanical speed; no eddy-current reaction, no frequency "
    "dependent permeability and no rotational time-domain effect is represented"
)


def _spectral_derivative(values: np.ndarray, span_rad: float) -> np.ndarray:
    """d/dtheta of a periodic waveform sampled uniformly over one period.

    Spectral differentiation is used rather than finite differences because the
    waveform is exactly periodic over the sampled span and the derivative is the
    quantity being validated; a finite-difference stencil would add its own
    truncation error to the number under test.
    """

    count = values.size
    spectrum = np.fft.rfft(values)
    wavenumbers = np.fft.rfftfreq(count, d=span_rad / count) * 2.0 * math.pi
    derivative_spectrum = spectrum * 1j * wavenumbers
    if count % 2 == 0:
        # The Nyquist bin of an even-length real signal has no signed frequency
        # partner; differentiating it would inject a spurious real component.
        derivative_spectrum[-1] = 0.0
    return np.fft.irfft(derivative_spectrum, n=count)


def _fundamental_amplitude(values: np.ndarray) -> float:
    count = values.size
    spectrum = np.fft.rfft(values)
    if spectrum.size < 2:
        return 0.0
    return float(2.0 * np.abs(spectrum[1]) / count)


def extract_back_emf(result: FEARawResult, phase: str | None = None) -> FEABackEmfExtraction:
    """Derive back-EMF from the no-load flux-linkage sweep."""

    if result.target is not FEAValidationTarget.NO_LOAD_BACK_EMF:
        raise ValueError("back-EMF extraction requires a no-load back-EMF sweep")
    name = phase if phase is not None else result.phase_names()[0]
    linkage = result.flux_linkage_series(name)
    span_rad = math.radians(result.span_mech_deg)
    mechanical_angular_speed = result.mechanical_speed_rpm * 2.0 * math.pi / 60.0
    voltage = mechanical_angular_speed * _spectral_derivative(linkage, span_rad)

    phase_rms = float(np.sqrt(np.mean(voltage**2)))
    phase_peak = float(np.max(np.abs(voltage)))
    fundamental_peak = _fundamental_amplitude(voltage)
    fundamental_rms = fundamental_peak / math.sqrt(2.0)
    return FEABackEmfExtraction(
        phase_rms_v=phase_rms,
        phase_peak_v=phase_peak,
        phase_fundamental_rms_v=fundamental_rms,
        # A balanced three-phase Y connection with no triplen path: the line
        # voltage is sqrt(3) times the phase voltage for the non-triplen content.
        line_rms_v=math.sqrt(3.0) * fundamental_rms,
        back_emf_constant_phase_rms_v_per_rad_s=(
            phase_rms / mechanical_angular_speed if mechanical_angular_speed else 0.0
        ),
        flux_linkage_peak_wb_turn=float(np.max(np.abs(linkage))),
        flux_linkage_fundamental_peak_wb_turn=_fundamental_amplitude(linkage),
        mechanical_speed_rpm=result.mechanical_speed_rpm,
        method=(
            "spectral d(lambda)/d(theta_mech) over one endpoint-excluded electrical "
            "period, scaled by omega_mech"
        ),
        speed_scaling_note=SPEED_SCALING_NOTE,
    )


def extract_average_torque(result: FEARawResult) -> FEATorqueExtraction:
    """Average electromagnetic torque over the sampled span."""

    if result.target is not FEAValidationTarget.AVERAGE_TORQUE:
        raise ValueError("torque extraction requires an average-torque sweep")
    torque = result.torque_series_nm()
    if torque is None:
        raise ValueError("the sweep carries no circumferential force samples")
    average = float(np.mean(torque))
    peak = float(np.max(torque))
    minimum = float(np.min(torque))
    ripple = None
    if abs(average) > 0.0:
        ripple = float((peak - minimum) / abs(average) * 100.0)
    return FEATorqueExtraction(
        average_torque_nm=average,
        peak_torque_nm=peak,
        minimum_torque_nm=minimum,
        peak_to_peak_torque_nm=peak - minimum,
        ripple_percent=ripple,
        sample_count=int(torque.size),
        method=(
            "mean of T = F_x * r_mean over one endpoint-excluded electrical period; "
            "F_x is the weighted Maxwell stress tensor force on the rotor blocks"
        ),
    )


def extract_cogging(result: FEARawResult) -> FEACoggingExtraction:
    """Cogging descriptors over one cogging period."""

    if result.target is not FEAValidationTarget.COGGING_TORQUE:
        raise ValueError("cogging extraction requires a zero-current cogging sweep")
    torque = result.torque_series_nm()
    if torque is None:
        raise ValueError("the sweep carries no circumferential force samples")
    peak_positive = float(np.max(torque))
    peak_negative = float(np.min(torque))
    return FEACoggingExtraction(
        peak_positive_nm=peak_positive,
        peak_negative_nm=peak_negative,
        peak_to_peak_nm=peak_positive - peak_negative,
        # The analytical model reports a single-sided peak amplitude, so the
        # comparable FEA quantity is the largest absolute excursion.
        amplitude_nm=float(np.max(np.abs(torque))),
        rms_nm=float(np.sqrt(np.mean(torque**2))),
        fundamental_amplitude_nm=_fundamental_amplitude(torque),
        sample_count=int(torque.size),
        method=(
            "T = F_x * r_mean sampled over one cogging period at zero stator current; "
            "the amplitude reported for comparison is max|T|"
        ),
    )


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
