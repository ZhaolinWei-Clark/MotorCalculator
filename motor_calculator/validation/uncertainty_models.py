"""Explicit uncertainty semantics for validation-only propagation."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class UncertaintyKind(str, Enum):
    EXACT = "EXACT"
    RANGE = "RANGE"
    NORMAL = "NORMAL"
    UNIFORM = "UNIFORM"
    UNKNOWN = "UNKNOWN"


class UncertaintyCategory(str, Enum):
    PARAMETER_UNCERTAINTY = "PARAMETER_UNCERTAINTY"
    NUMERICAL_UNCERTAINTY = "NUMERICAL_UNCERTAINTY"
    MODEL_FORM_UNCERTAINTY = "MODEL_FORM_UNCERTAINTY"
    EXTERNAL_VALIDATION_UNCERTAINTY = "EXTERNAL_VALIDATION_UNCERTAINTY"


class ModelFormUncertaintyStatus(str, Enum):
    UNQUANTIFIED = "UNQUANTIFIED"
    EVIDENCE_BOUNDED = "EVIDENCE_BOUNDED"


class ResultConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class ParameterUncertainty:
    parameter_name: str
    nominal_value: float
    unit: str
    uncertainty_kind: UncertaintyKind
    lower_bound: float | None
    upper_bound: float | None
    mean: float | None
    standard_deviation: float | None
    provenance: str
    confidence: str
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.parameter_name.strip() or not self.unit.strip() or not self.provenance.strip():
            raise ValueError("parameter name, unit, and provenance must be explicit")
        if not math.isfinite(self.nominal_value):
            raise ValueError("nominal value must be finite")
        kind = self.uncertainty_kind
        has_bounds = self.lower_bound is not None or self.upper_bound is not None
        has_normal = self.mean is not None or self.standard_deviation is not None
        if kind is UncertaintyKind.EXACT:
            if has_bounds or has_normal:
                raise ValueError("EXACT uncertainty cannot declare variation")
        elif kind is UncertaintyKind.RANGE:
            self._require_bounds()
            if has_normal:
                raise ValueError("RANGE cannot declare a statistical distribution")
        elif kind is UncertaintyKind.NORMAL:
            if self.mean is None or self.standard_deviation is None:
                raise ValueError("NORMAL requires explicit mean and standard deviation")
            if not math.isfinite(self.mean) or not math.isfinite(self.standard_deviation):
                raise ValueError("NORMAL parameters must be finite")
            if self.standard_deviation <= 0.0:
                raise ValueError("NORMAL standard deviation must be positive")
            if not math.isclose(self.nominal_value, self.mean, rel_tol=0.0, abs_tol=1e-12):
                raise ValueError("NORMAL nominal value must equal its explicit mean")
            if has_bounds:
                self._require_bounds()
        elif kind is UncertaintyKind.UNIFORM:
            self._require_bounds()
            if has_normal:
                raise ValueError("UNIFORM uses explicit bounds, not normal parameters")
        elif kind is UncertaintyKind.UNKNOWN:
            if has_bounds or has_normal:
                raise ValueError("UNKNOWN must not hide an assumed range or distribution")

    def _require_bounds(self) -> None:
        if self.lower_bound is None or self.upper_bound is None:
            raise ValueError(f"{self.uncertainty_kind.value} requires explicit lower and upper bounds")
        if not math.isfinite(self.lower_bound) or not math.isfinite(self.upper_bound):
            raise ValueError("uncertainty bounds must be finite")
        if self.lower_bound >= self.upper_bound:
            raise ValueError("lower_bound must be less than upper_bound")
        if not self.lower_bound <= self.nominal_value <= self.upper_bound:
            raise ValueError("nominal value must lie within declared bounds")

    @property
    def statistically_sampleable(self) -> bool:
        return self.uncertainty_kind in {UncertaintyKind.NORMAL, UncertaintyKind.UNIFORM}

    @property
    def has_parameter_bounds(self) -> bool:
        return self.lower_bound is not None and self.upper_bound is not None


@dataclass(frozen=True)
class UncertaintySpecification:
    specification_id: str
    assumption_label: str
    parameters: tuple[ParameterUncertainty, ...]
    model_form_uncertainty_status: ModelFormUncertaintyStatus
    external_validation_status: str
    assumptions: tuple[str, ...]

    def __post_init__(self) -> None:
        names = tuple(parameter.parameter_name for parameter in self.parameters)
        if len(names) != len(set(names)):
            raise ValueError("uncertainty parameter names must be unique")

    def nominal_values(self) -> dict[str, float]:
        return {parameter.parameter_name: parameter.nominal_value for parameter in self.parameters}


@dataclass(frozen=True)
class AccuracyEnvelopeResult:
    metric_name: str
    nominal_value: float
    unit: str
    parameter_bound_min: float
    parameter_bound_max: float
    monte_carlo_available: bool
    p10: float | None
    p50: float | None
    p90: float | None
    standard_deviation: float | None
    dominant_uncertainty_parameters: tuple[str, ...]
    numerical_uncertainty: float | None
    model_form_uncertainty_status: ModelFormUncertaintyStatus
    external_validation_status: str
    confidence_level: ResultConfidence
    warnings: tuple[str, ...]
    assumptions: tuple[str, ...]


def load_uncertainty_specification(path: Path) -> UncertaintySpecification:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    parameters = tuple(
        ParameterUncertainty(
            parameter_name=item["parameter_name"],
            nominal_value=float(item["nominal_value"]),
            unit=item["unit"],
            uncertainty_kind=UncertaintyKind(item["uncertainty_kind"]),
            lower_bound=item.get("lower_bound"),
            upper_bound=item.get("upper_bound"),
            mean=item.get("mean"),
            standard_deviation=item.get("standard_deviation"),
            provenance=item["provenance"],
            confidence=item["confidence"],
            notes=tuple(item.get("notes", ())),
        )
        for item in raw["parameters"]
    )
    return UncertaintySpecification(
        specification_id=raw["specification_id"],
        assumption_label=raw["assumption_label"],
        parameters=parameters,
        model_form_uncertainty_status=ModelFormUncertaintyStatus(raw["model_form_uncertainty_status"]),
        external_validation_status=raw["external_validation_status"],
        assumptions=tuple(raw["assumptions"]),
    )


def classify_result_confidence(
    *,
    nominal_available: bool,
    topology_supported: bool,
    unknown_parameter_count: int,
    numerical_convergence_available: bool,
    external_validation_status: str,
    model_form_status: ModelFormUncertaintyStatus,
) -> ResultConfidence:
    if not nominal_available or not topology_supported:
        return ResultConfidence.INSUFFICIENT
    external = external_validation_status.upper()
    if (
        external == "STRONG"
        and unknown_parameter_count == 0
        and numerical_convergence_available
        and model_form_status is ModelFormUncertaintyStatus.EVIDENCE_BOUNDED
    ):
        return ResultConfidence.HIGH
    if external in {"MODERATE", "PARTIAL"} and unknown_parameter_count <= 1 and numerical_convergence_available:
        return ResultConfidence.MEDIUM
    return ResultConfidence.LOW
