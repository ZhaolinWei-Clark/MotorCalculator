"""Schema for local, validation-only user evidence records."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class ValidationEvidenceType(str, Enum):
    BENCH_MEASUREMENT = "BENCH_MEASUREMENT"
    PUBLISHED_EXPERIMENT = "PUBLISHED_EXPERIMENT"
    FEA = "FEA"
    MANUFACTURER_DATA = "MANUFACTURER_DATA"
    ANALYTICAL_REFERENCE = "ANALYTICAL_REFERENCE"
    OTHER = "OTHER"


class EvidenceQuality(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNVERIFIED = "UNVERIFIED"


class FeedbackComparability(str, Enum):
    DIRECT = "DIRECT"
    SAFE_TRANSFORM = "SAFE_TRANSFORM"
    BLOCKED = "BLOCKED"


class DuplicateStatus(str, Enum):
    UNIQUE = "UNIQUE"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"


class ExternalValidationCoverage(str, Enum):
    NONE = "NONE"
    VERY_LIMITED = "VERY_LIMITED"
    LIMITED = "LIMITED"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


class BiasCandidateStatus(str, Enum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_CLEAR_BIAS = "NO_CLEAR_BIAS"
    POSSIBLE_POSITIVE_BIAS = "POSSIBLE_POSITIVE_BIAS"
    POSSIBLE_NEGATIVE_BIAS = "POSSIBLE_NEGATIVE_BIAS"


class EnvelopePosition(str, Enum):
    INSIDE_MONTE_CARLO_P10_P90 = "INSIDE_MONTE_CARLO_P10_P90"
    INSIDE_PARAMETER_BOUNDS_ONLY = "INSIDE_PARAMETER_BOUNDS_ONLY"
    OUTSIDE_BOTH = "OUTSIDE_BOTH"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class MetricSemantics:
    quantity_scope: str | None = None
    rms_peak_semantics: str | None = None
    waveform_semantics: str | None = None
    torque_boundary: str | None = None
    current_basis: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "quantity_scope": self.quantity_scope,
            "rms_peak_semantics": self.rms_peak_semantics,
            "waveform_semantics": self.waveform_semantics,
            "torque_boundary": self.torque_boundary,
            "current_basis": self.current_basis,
        }


@dataclass(frozen=True)
class FeedbackOperatingPoint:
    speed_rpm: float
    current_a: float | None = None
    voltage_v: float | None = None
    temperature_c: float | None = None
    load_torque_nm: float | None = None

    def to_dict(self) -> dict[str, float | None]:
        return {
            "speed_rpm": self.speed_rpm,
            "current_a": self.current_a,
            "voltage_v": self.voltage_v,
            "temperature_c": self.temperature_c,
            "load_torque_nm": self.load_torque_nm,
        }


@dataclass(frozen=True)
class FeedbackModelIdentity:
    calculator_version: str
    model_version: str
    model_track: str
    topology: str
    software_version: str
    git_commit: str | None
    model_family: str
    calculation_mode: str
    origin: str
    formula_version: str

    def to_dict(self) -> dict[str, str | None]:
        return {
            "calculator_version": self.calculator_version,
            "model_version": self.model_version,
            "model_track": self.model_track,
            "topology": self.topology,
            "software_version": self.software_version,
            "git_commit": self.git_commit,
            "model_family": self.model_family,
            "calculation_mode": self.calculation_mode,
            "origin": self.origin,
            "formula_version": self.formula_version,
        }


@dataclass(frozen=True)
class FeedbackSubmission:
    metric_name: str
    predicted_value: float
    reference_value: float
    predicted_unit: str
    reference_unit: str
    predicted_semantics: MetricSemantics
    reference_semantics: MetricSemantics
    operating_point: FeedbackOperatingPoint
    evidence_type: ValidationEvidenceType
    model_identity: FeedbackModelIdentity
    full_input_snapshot: Mapping[str, Any]
    source_name: str | None = None
    source_reference: str | None = None
    notes: str = ""
    uncertainty_snapshot: Mapping[str, Any] | None = None
    source_file_hash: str | None = None


@dataclass(frozen=True)
class ValidationFeedbackRecord:
    schema_version: str
    record_id: str
    created_at: str
    calculator_version: str
    model_version: str
    model_track: str
    topology: str
    software_version: str
    git_commit: str | None
    model_family: str
    calculation_mode: str
    origin: str
    formula_version: str
    metric_name: str
    predicted_value: float
    reference_value: float
    normalized_reference_value: float | None
    unit: str
    reference_unit: str
    quantity_scope: str | None
    rms_peak_semantics: str | None
    waveform_semantics: str | None
    torque_boundary: str | None
    current_basis: str | None
    reference_quantity_scope: str | None
    reference_rms_peak_semantics: str | None
    reference_waveform_semantics: str | None
    reference_torque_boundary: str | None
    reference_current_basis: str | None
    speed_rpm: float
    current_a: float | None
    voltage_v: float | None
    temperature_c: float | None
    load_torque_nm: float | None
    evidence_type: ValidationEvidenceType
    source_name: str | None
    source_reference: str | None
    notes: str
    evidence_quality: EvidenceQuality
    full_input_snapshot: Mapping[str, Any]
    uncertainty_snapshot: Mapping[str, Any] | None
    comparability: FeedbackComparability
    safe_transformation: str
    validation_messages: tuple[str, ...]
    signed_error: float | None
    absolute_error: float | None
    relative_error: float | None
    absolute_percentage_error: float | None
    duplicate_status: DuplicateStatus
    input_snapshot_hash: str
    record_content_hash: str
    source_file_hash: str | None = None


@dataclass(frozen=True)
class FeedbackSubmissionResult:
    record: ValidationFeedbackRecord
    duplicate_status: DuplicateStatus


@dataclass(frozen=True)
class EnvelopeComparison:
    metric_name: str
    reference_value: float | None
    unit: str
    position: EnvelopePosition
    notes: tuple[str, ...]


@dataclass(frozen=True)
class BiasCandidate:
    group_key: str
    status: BiasCandidateStatus
    record_count: int
    median_signed_percentage_error: float | None
    notes: str


@dataclass(frozen=True)
class FeedbackAggregate:
    group_key: str
    record_count: int
    mean_signed_percentage_error: float | None
    median_signed_percentage_error: float | None
    mean_absolute_percentage_error: float | None
    median_absolute_percentage_error: float | None
    minimum_signed_percentage_error: float | None
    maximum_signed_percentage_error: float | None
    p10_signed_percentage_error: float | None
    p50_signed_percentage_error: float | None
    p90_signed_percentage_error: float | None
    bias_candidate: BiasCandidate
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ValidationSummary:
    total_records: int
    compatible_records: int
    blocked_records: int
    high_quality_records: int
    metric_counts: Mapping[str, int]
    median_error_by_metric: Mapping[str, float | None]
    validation_coverage: ExternalValidationCoverage
    bias_candidates: tuple[BiasCandidate, ...]
    recent_records: tuple[ValidationFeedbackRecord, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class FeedbackFormModel:
    metric: str = ""
    predicted_value: str = ""
    reference_value: str = ""
    evidence_source: str = ""
    speed_rpm: str = ""
    current_a: str = ""
    voltage_v: str = ""
    temperature_c: str = ""
    notes: str = ""
    validation_messages: tuple[str, ...] = field(default_factory=tuple)

    def validate_for_display(self) -> tuple[str, ...]:
        messages: list[str] = []
        if not self.metric.strip():
            messages.append("请选择要验证的指标。")
        for label, value, required in (
            ("预测值", self.predicted_value, True),
            ("参考值", self.reference_value, True),
            ("转速", self.speed_rpm, True),
            ("电流", self.current_a, False),
            ("电压", self.voltage_v, False),
            ("温度", self.temperature_c, False),
        ):
            if required and not value.strip():
                messages.append(f"{label}不能为空。")
                continue
            if value.strip():
                try:
                    float(value)
                except ValueError:
                    messages.append(f"{label}必须是数值。")
        return tuple(messages)
