"""Validation-record schema and provenance rules for Phase 4A."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping

from .assumptions import DEFAULT_CONNECTION_ZH, DEFAULT_TOPOLOGY_ZH, MODEL_NAME_ZH
from .electrical_semantics import MotorControlMode, normalize_motor_control_mode


class ValidationFrameworkError(ValueError):
    """Base error for the external validation framework."""


class ValidationRecordError(ValidationFrameworkError):
    """Raised when a validation record is structurally invalid."""


class ValidationSourceType(str, Enum):
    ANALYTICAL_REFERENCE = "analytical_reference"
    PUBLISHED_BENCHMARK = "published_benchmark"
    FEA_SIMULATION = "fea_simulation"
    BENCH_MEASUREMENT = "bench_measurement"
    MANUFACTURER_DATA = "manufacturer_data"
    USER_SUPPLIED_DATA = "user_supplied_data"


class ValidationEvidenceLevel(str, Enum):
    LEVEL_0_INTERNAL_REGRESSION = "LEVEL_0_INTERNAL_REGRESSION"
    LEVEL_1_ANALYTICAL = "LEVEL_1_ANALYTICAL"
    LEVEL_2_PUBLISHED_OR_FEA = "LEVEL_2_PUBLISHED_OR_FEA"
    LEVEL_3_CONTROLLED_MEASUREMENT = "LEVEL_3_CONTROLLED_MEASUREMENT"
    LEVEL_4_MULTI_SOURCE_VALIDATION = "LEVEL_4_MULTI_SOURCE_VALIDATION"


class ValidationFieldStatus(str, Enum):
    PROVIDED = "provided"
    INFERRED = "inferred"
    UNAVAILABLE = "unavailable"
    NOT_APPLICABLE = "not_applicable"


class ValidationComparabilityStatus(str, Enum):
    DIRECTLY_COMPARABLE = "directly_comparable"
    UNIT_CONVERSION_REQUIRED = "unit_conversion_required"
    SEMANTICS_MISMATCH = "semantics_mismatch"
    INSUFFICIENT_INPUT_DATA = "insufficient_input_data"
    WAVEFORM_MISMATCH = "waveform_mismatch"
    CONTROL_STRATEGY_MISMATCH = "control_strategy_mismatch"
    TOPOLOGY_MISMATCH = "topology_mismatch"
    NOT_AVAILABLE = "not_available"


class ValidationMetricMaturity(str, Enum):
    REVISED_DEFINED_PARALLEL = "revised_defined_parallel"
    LEGACY_OR_PROVISIONAL = "legacy_or_provisional"


SUPPORTED_INPUT_PARAMETER_NAMES = {
    "pole_pairs",
    "rated_speed_rpm",
    "rated_power_w",
    "dc_bus_voltage_v",
    "phase_current_a",
    "winding_connection",
    "back_emf_waveform",
    "stator_outer_diameter_m",
    "stator_inner_diameter_m",
    "air_gap_m",
    "magnet_thickness_m",
    "turns_per_phase",
    "winding_factor",
    "magnet_remanence_t",
}

SUPPORTED_VALIDATION_METRICS: Dict[str, ValidationMetricMaturity] = {
    "rated_torque_nm": ValidationMetricMaturity.REVISED_DEFINED_PARALLEL,
    "back_emf_phase_peak_v": ValidationMetricMaturity.REVISED_DEFINED_PARALLEL,
    "back_emf_phase_rms_v": ValidationMetricMaturity.REVISED_DEFINED_PARALLEL,
    "back_emf_line_rms_v": ValidationMetricMaturity.REVISED_DEFINED_PARALLEL,
    "back_emf_constant_line_rms_v_per_krpm": ValidationMetricMaturity.REVISED_DEFINED_PARALLEL,
    "torque_constant_nm_per_a": ValidationMetricMaturity.REVISED_DEFINED_PARALLEL,
    "phase_resistance_ohm": ValidationMetricMaturity.LEGACY_OR_PROVISIONAL,
    "phase_inductance_h": ValidationMetricMaturity.LEGACY_OR_PROVISIONAL,
    "rated_current_a": ValidationMetricMaturity.LEGACY_OR_PROVISIONAL,
    "copper_loss_w": ValidationMetricMaturity.LEGACY_OR_PROVISIONAL,
    "iron_loss_w": ValidationMetricMaturity.LEGACY_OR_PROVISIONAL,
    "mechanical_loss_w": ValidationMetricMaturity.LEGACY_OR_PROVISIONAL,
    "efficiency": ValidationMetricMaturity.LEGACY_OR_PROVISIONAL,
    "required_voltage_v": ValidationMetricMaturity.LEGACY_OR_PROVISIONAL,
}

SOURCE_TYPE_ALLOWED_EVIDENCE_LEVELS = {
    ValidationSourceType.ANALYTICAL_REFERENCE: {
        ValidationEvidenceLevel.LEVEL_0_INTERNAL_REGRESSION,
        ValidationEvidenceLevel.LEVEL_1_ANALYTICAL,
    },
    ValidationSourceType.PUBLISHED_BENCHMARK: {
        ValidationEvidenceLevel.LEVEL_2_PUBLISHED_OR_FEA,
        ValidationEvidenceLevel.LEVEL_4_MULTI_SOURCE_VALIDATION,
    },
    ValidationSourceType.FEA_SIMULATION: {
        ValidationEvidenceLevel.LEVEL_2_PUBLISHED_OR_FEA,
        ValidationEvidenceLevel.LEVEL_4_MULTI_SOURCE_VALIDATION,
    },
    ValidationSourceType.BENCH_MEASUREMENT: {
        ValidationEvidenceLevel.LEVEL_3_CONTROLLED_MEASUREMENT,
        ValidationEvidenceLevel.LEVEL_4_MULTI_SOURCE_VALIDATION,
    },
    ValidationSourceType.MANUFACTURER_DATA: {
        ValidationEvidenceLevel.LEVEL_2_PUBLISHED_OR_FEA,
        ValidationEvidenceLevel.LEVEL_4_MULTI_SOURCE_VALIDATION,
    },
    ValidationSourceType.USER_SUPPLIED_DATA: {
        ValidationEvidenceLevel.LEVEL_0_INTERNAL_REGRESSION,
        ValidationEvidenceLevel.LEVEL_3_CONTROLLED_MEASUREMENT,
        ValidationEvidenceLevel.LEVEL_4_MULTI_SOURCE_VALIDATION,
    },
}


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationRecordError(f"字段“{field_name}”必须是非空字符串。")
    return value.strip()


def _coerce_enum(enum_type: type[Enum], raw_value: Any, field_name: str) -> Enum:
    try:
        return enum_type(raw_value)
    except ValueError as exc:
        allowed_values = ", ".join(member.value for member in enum_type)
        raise ValidationRecordError(f"字段“{field_name}”的值“{raw_value}”无效；允许值：{allowed_values}。") from exc


def _ensure_mapping(raw_value: Any, field_name: str) -> Mapping[str, Any]:
    if not isinstance(raw_value, Mapping):
        raise ValidationRecordError(f"字段“{field_name}”必须是对象/字典。")
    return raw_value


def _normalize_control_mode(raw_value: Any) -> str:
    try:
        return normalize_motor_control_mode(raw_value).value
    except ValueError as exc:
        raise ValidationRecordError(
            f"字段“control_mode”当前值“{raw_value}”无效；只允许 PMSM_SINUSOIDAL / BLDC_120_DEGREE 语义。"
        ) from exc


def _normalize_connection(raw_value: Any) -> str:
    if raw_value is None:
        return DEFAULT_CONNECTION_ZH
    normalized = str(raw_value).strip().lower()
    aliases = {
        "y": "Y",
        "y-connected": "Y",
        "wye": "Y",
        "y接": "Y",
        "y 接": "Y",
        "delta": "Delta",
        "delta-connected": "Delta",
        "三角": "Delta",
        "delta接": "Delta",
        "delta 接": "Delta",
    }
    if normalized not in aliases:
        raise ValidationRecordError(f"字段“winding_connection”当前值“{raw_value}”无效；只允许 Y 或 Delta。")
    return aliases[normalized]


def _normalize_waveform(raw_value: Any) -> str:
    if raw_value is None:
        raise ValidationRecordError("字段“back_emf_waveform”不能为空。")
    normalized = str(raw_value).strip().lower()
    aliases = {
        "sinusoidal": "sinusoidal",
        "sine": "sinusoidal",
        "正弦": "sinusoidal",
        "正弦波": "sinusoidal",
        "trapezoidal": "trapezoidal",
        "trapezoid": "trapezoidal",
        "梯形": "trapezoidal",
        "梯形波": "trapezoidal",
        "legacy_provisional": "legacy_provisional",
        "legacy": "legacy_provisional",
    }
    if normalized not in aliases:
        raise ValidationRecordError(
            f"字段“back_emf_waveform”当前值“{raw_value}”无效；只允许 sinusoidal、trapezoidal 或 legacy_provisional。"
        )
    return aliases[normalized]


@dataclass(frozen=True)
class ValidationField:
    """A field that tracks both value and provenance status."""

    status: ValidationFieldStatus
    value: Any = None
    unit: str | None = None
    notes: str | None = None

    @property
    def is_available(self) -> bool:
        return self.status in {ValidationFieldStatus.PROVIDED, ValidationFieldStatus.INFERRED}

    @classmethod
    def from_dict(cls, raw_value: Mapping[str, Any], field_name: str) -> "ValidationField":
        raw_mapping = _ensure_mapping(raw_value, field_name)
        status = _coerce_enum(ValidationFieldStatus, raw_mapping.get("status"), f"{field_name}.status")
        value = raw_mapping.get("value")
        unit = raw_mapping.get("unit")
        notes = raw_mapping.get("notes")

        if status in {ValidationFieldStatus.UNAVAILABLE, ValidationFieldStatus.NOT_APPLICABLE} and value is not None:
            raise ValidationRecordError(
                f"字段“{field_name}”标记为 {status.value} 时，value 必须为 null，不能用 0 或其他占位值代替未知数据。"
            )
        if status in {ValidationFieldStatus.PROVIDED, ValidationFieldStatus.INFERRED} and value is None:
            raise ValidationRecordError(f"字段“{field_name}”标记为 {status.value} 时，必须提供非空 value。")

        return cls(status=status, value=value, unit=unit, notes=notes)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "value": self.value,
            "unit": self.unit,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ValidationMetricExpectation:
    """Expected output for one comparable metric."""

    metric_name: str
    status: ValidationFieldStatus
    value: Any = None
    unit: str | None = None
    quantity_scope: str | None = None
    value_kind: str | None = None
    current_basis: str | None = None
    notes: str | None = None

    @property
    def is_available(self) -> bool:
        return self.status in {ValidationFieldStatus.PROVIDED, ValidationFieldStatus.INFERRED}

    @classmethod
    def from_dict(cls, raw_value: Mapping[str, Any], field_name: str) -> "ValidationMetricExpectation":
        raw_mapping = _ensure_mapping(raw_value, field_name)
        metric_name = _require_non_empty_string(raw_mapping.get("metric_name"), f"{field_name}.metric_name")
        if metric_name not in SUPPORTED_VALIDATION_METRICS:
            supported = ", ".join(sorted(SUPPORTED_VALIDATION_METRICS))
            raise ValidationRecordError(
                f"字段“{field_name}.metric_name”当前值“{metric_name}”未注册；当前支持：{supported}。"
            )

        status = _coerce_enum(ValidationFieldStatus, raw_mapping.get("status"), f"{field_name}.status")
        value = raw_mapping.get("value")
        unit = raw_mapping.get("unit")
        quantity_scope = raw_mapping.get("quantity_scope")
        value_kind = raw_mapping.get("value_kind")
        current_basis = raw_mapping.get("current_basis")
        notes = raw_mapping.get("notes")

        if status in {ValidationFieldStatus.UNAVAILABLE, ValidationFieldStatus.NOT_APPLICABLE} and value is not None:
            raise ValidationRecordError(
                f"字段“{field_name}”标记为 {status.value} 时，value 必须为 null，不能把未知 expected 写成 0。"
            )
        if status in {ValidationFieldStatus.PROVIDED, ValidationFieldStatus.INFERRED} and value is None:
            raise ValidationRecordError(f"字段“{field_name}”标记为 {status.value} 时，必须提供 expected value。")

        return cls(
            metric_name=metric_name,
            status=status,
            value=value,
            unit=unit,
            quantity_scope=quantity_scope,
            value_kind=value_kind,
            current_basis=current_basis,
            notes=notes,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "status": self.status.value,
            "value": self.value,
            "unit": self.unit,
            "quantity_scope": self.quantity_scope,
            "value_kind": self.value_kind,
            "current_basis": self.current_basis,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ValidationUncertainty:
    """Uncertainty metadata that stays separate from model error."""

    absolute: float | None = None
    relative: float | None = None
    coverage_factor: float | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, raw_value: Mapping[str, Any], field_name: str) -> "ValidationUncertainty":
        raw_mapping = _ensure_mapping(raw_value, field_name)
        return cls(
            absolute=raw_mapping.get("absolute"),
            relative=raw_mapping.get("relative"),
            coverage_factor=raw_mapping.get("coverage_factor"),
            notes=raw_mapping.get("notes"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "absolute": self.absolute,
            "relative": self.relative,
            "coverage_factor": self.coverage_factor,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ValidationTolerance:
    """Metric tolerance configuration."""

    absolute: float | None = None
    relative: float | None = None
    notes: str | None = None

    @classmethod
    def from_dict(cls, raw_value: Mapping[str, Any], field_name: str) -> "ValidationTolerance":
        raw_mapping = _ensure_mapping(raw_value, field_name)
        return cls(
            absolute=raw_mapping.get("absolute"),
            relative=raw_mapping.get("relative"),
            notes=raw_mapping.get("notes"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "absolute": self.absolute,
            "relative": self.relative,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ValidationRecord:
    """Normalized validation record with traceable provenance."""

    validation_id: str
    source_type: ValidationSourceType
    evidence_level: ValidationEvidenceLevel
    motor_type: str
    control_mode: str
    topology: str
    source_title: str
    source_author_or_organization: str
    source_year: int | None
    source_identifier: str | None
    source_file: str | None
    source_page_or_section: str | None
    license_or_usage_note: str
    data_quality_notes: str
    model_assumptions: list[str]
    input_parameters: Dict[str, ValidationField]
    expected_outputs: Dict[str, ValidationMetricExpectation]
    uncertainty: Dict[str, ValidationUncertainty]
    tolerances: Dict[str, ValidationTolerance]
    excluded_comparisons: Dict[str, str]
    created_at: str
    synthetic: bool = False
    not_for_accuracy_claims: bool = False
    conversion_log: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw_value: Mapping[str, Any]) -> "ValidationRecord":
        raw_mapping = _ensure_mapping(raw_value, "validation_record")
        validation_id = _require_non_empty_string(raw_mapping.get("validation_id"), "validation_id")
        source_type = _coerce_enum(ValidationSourceType, raw_mapping.get("source_type"), "source_type")
        evidence_level = _coerce_enum(ValidationEvidenceLevel, raw_mapping.get("evidence_level"), "evidence_level")
        motor_type = _require_non_empty_string(raw_mapping.get("motor_type"), "motor_type")
        control_mode = _normalize_control_mode(raw_mapping.get("control_mode"))
        topology = _require_non_empty_string(raw_mapping.get("topology"), "topology")
        source_title = _require_non_empty_string(raw_mapping.get("source_title"), "source_title")
        source_author_or_organization = _require_non_empty_string(
            raw_mapping.get("source_author_or_organization"),
            "source_author_or_organization",
        )
        source_year = raw_mapping.get("source_year")
        source_identifier = raw_mapping.get("source_identifier")
        source_file = raw_mapping.get("source_file")
        source_page_or_section = raw_mapping.get("source_page_or_section")
        license_or_usage_note = _require_non_empty_string(raw_mapping.get("license_or_usage_note"), "license_or_usage_note")
        data_quality_notes = _require_non_empty_string(raw_mapping.get("data_quality_notes"), "data_quality_notes")
        raw_model_assumptions = raw_mapping.get("model_assumptions")
        if not isinstance(raw_model_assumptions, list) or not raw_model_assumptions:
            raise ValidationRecordError("字段“model_assumptions”必须是非空数组。")
        model_assumptions = [_require_non_empty_string(item, "model_assumptions[]") for item in raw_model_assumptions]

        raw_input_parameters = _ensure_mapping(raw_mapping.get("input_parameters"), "input_parameters")
        input_parameters = {
            key: ValidationField.from_dict(value, f"input_parameters.{key}") for key, value in raw_input_parameters.items()
        }
        unsupported_inputs = set(input_parameters) - SUPPORTED_INPUT_PARAMETER_NAMES
        if unsupported_inputs:
            unsupported = ", ".join(sorted(unsupported_inputs))
            raise ValidationRecordError(f"发现未注册的输入参数字段：{unsupported}。")

        raw_expected_outputs = _ensure_mapping(raw_mapping.get("expected_outputs"), "expected_outputs")
        expected_outputs = {
            key: ValidationMetricExpectation.from_dict(value, f"expected_outputs.{key}")
            for key, value in raw_expected_outputs.items()
        }

        raw_uncertainty = _ensure_mapping(raw_mapping.get("uncertainty", {}), "uncertainty")
        uncertainty = {
            key: ValidationUncertainty.from_dict(value, f"uncertainty.{key}") for key, value in raw_uncertainty.items()
        }

        raw_tolerances = _ensure_mapping(raw_mapping.get("tolerances", {}), "tolerances")
        tolerances = {
            key: ValidationTolerance.from_dict(value, f"tolerances.{key}") for key, value in raw_tolerances.items()
        }

        raw_excluded_comparisons = _ensure_mapping(raw_mapping.get("excluded_comparisons", {}), "excluded_comparisons")
        excluded_comparisons = {
            _require_non_empty_string(key, "excluded_comparisons.key"): _require_non_empty_string(
                value,
                f"excluded_comparisons.{key}",
            )
            for key, value in raw_excluded_comparisons.items()
        }

        created_at = _require_non_empty_string(raw_mapping.get("created_at"), "created_at")
        synthetic = bool(raw_mapping.get("synthetic", False))
        not_for_accuracy_claims = bool(raw_mapping.get("not_for_accuracy_claims", False))
        conversion_log = list(raw_mapping.get("conversion_log", []))

        record = cls(
            validation_id=validation_id,
            source_type=source_type,
            evidence_level=evidence_level,
            motor_type=motor_type,
            control_mode=control_mode,
            topology=topology,
            source_title=source_title,
            source_author_or_organization=source_author_or_organization,
            source_year=source_year,
            source_identifier=source_identifier,
            source_file=source_file,
            source_page_or_section=source_page_or_section,
            license_or_usage_note=license_or_usage_note,
            data_quality_notes=data_quality_notes,
            model_assumptions=model_assumptions,
            input_parameters=input_parameters,
            expected_outputs=expected_outputs,
            uncertainty=uncertainty,
            tolerances=tolerances,
            excluded_comparisons=excluded_comparisons,
            created_at=created_at,
            synthetic=synthetic,
            not_for_accuracy_claims=not_for_accuracy_claims,
            conversion_log=conversion_log,
        )
        record.validate_provenance_rules()
        record.validate_control_mode_rules()
        return record

    def validate_provenance_rules(self) -> None:
        allowed_levels = SOURCE_TYPE_ALLOWED_EVIDENCE_LEVELS[self.source_type]
        if self.evidence_level not in allowed_levels:
            allowed = ", ".join(level.value for level in sorted(allowed_levels, key=lambda item: item.value))
            raise ValidationRecordError(
                f"source_type={self.source_type.value} 不允许 evidence_level={self.evidence_level.value}；允许值：{allowed}。"
            )

        if self.source_type is ValidationSourceType.ANALYTICAL_REFERENCE and self.evidence_level not in {
            ValidationEvidenceLevel.LEVEL_0_INTERNAL_REGRESSION,
            ValidationEvidenceLevel.LEVEL_1_ANALYTICAL,
        }:
            raise ValidationRecordError("analytical_reference 不能被标记为实验验证或公开 benchmark。")

        if self.source_type is ValidationSourceType.BENCH_MEASUREMENT and self.evidence_level is not ValidationEvidenceLevel.LEVEL_3_CONTROLLED_MEASUREMENT and self.evidence_level is not ValidationEvidenceLevel.LEVEL_4_MULTI_SOURCE_VALIDATION:
            raise ValidationRecordError("bench_measurement 只能使用 LEVEL_3_CONTROLLED_MEASUREMENT 或 LEVEL_4_MULTI_SOURCE_VALIDATION。")

        if self.source_type is ValidationSourceType.MANUFACTURER_DATA and self.evidence_level is ValidationEvidenceLevel.LEVEL_3_CONTROLLED_MEASUREMENT:
            raise ValidationRecordError("厂家宣传参数不能被标记为台架实测证据等级。")

        if self.source_type is not ValidationSourceType.ANALYTICAL_REFERENCE and not any(
            [self.source_identifier, self.source_file, self.source_page_or_section]
        ):
            raise ValidationRecordError("外部数据必须至少提供 source_identifier、source_file 或 source_page_or_section 之一以保证可追溯。")

        if self.synthetic:
            if self.source_type is not ValidationSourceType.ANALYTICAL_REFERENCE:
                raise ValidationRecordError("synthetic 数据只能使用 analytical_reference 来源类型。")
            if self.evidence_level is not ValidationEvidenceLevel.LEVEL_1_ANALYTICAL:
                raise ValidationRecordError("synthetic 数据必须使用 LEVEL_1_ANALYTICAL。")
            if not self.not_for_accuracy_claims:
                raise ValidationRecordError("synthetic 数据必须显式标记 not_for_accuracy_claims=true。")

    def validate_control_mode_rules(self) -> None:
        waveform_field = self.input_parameters.get("back_emf_waveform")
        if waveform_field and waveform_field.is_available:
            waveform = _normalize_waveform(waveform_field.value)
            control_mode = MotorControlMode(self.control_mode)
            if control_mode is MotorControlMode.PMSM_SINUSOIDAL and waveform != "sinusoidal":
                raise ValidationRecordError("PMSM 记录只能与 sinusoidal back_emf_waveform 一起使用。")
            if control_mode is MotorControlMode.BLDC_120_DEGREE and waveform == "sinusoidal":
                raise ValidationRecordError("BLDC 120°导通记录不能使用 sinusoidal back_emf_waveform。")

        connection_field = self.input_parameters.get("winding_connection")
        if connection_field and connection_field.is_available:
            _normalize_connection(connection_field.value)

    def get_input_parameter(self, field_name: str) -> ValidationField | None:
        return self.input_parameters.get(field_name)

    def get_expected_output(self, metric_name: str) -> ValidationMetricExpectation | None:
        return self.expected_outputs.get(metric_name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "source_type": self.source_type.value,
            "evidence_level": self.evidence_level.value,
            "motor_type": self.motor_type,
            "control_mode": self.control_mode,
            "topology": self.topology,
            "source_title": self.source_title,
            "source_author_or_organization": self.source_author_or_organization,
            "source_year": self.source_year,
            "source_identifier": self.source_identifier,
            "source_file": self.source_file,
            "source_page_or_section": self.source_page_or_section,
            "license_or_usage_note": self.license_or_usage_note,
            "data_quality_notes": self.data_quality_notes,
            "model_assumptions": self.model_assumptions,
            "input_parameters": {key: value.to_dict() for key, value in self.input_parameters.items()},
            "expected_outputs": {key: value.to_dict() for key, value in self.expected_outputs.items()},
            "uncertainty": {key: value.to_dict() for key, value in self.uncertainty.items()},
            "tolerances": {key: value.to_dict() for key, value in self.tolerances.items()},
            "excluded_comparisons": self.excluded_comparisons,
            "created_at": self.created_at,
            "synthetic": self.synthetic,
            "not_for_accuracy_claims": self.not_for_accuracy_claims,
            "conversion_log": self.conversion_log,
        }


PHASE4A_VALIDATION_SCOPE = {
    "framework_goal": "建立可追溯的外部物理验证框架，不修改任何电磁公式，也不切换默认值。",
    "model_name_zh": MODEL_NAME_ZH,
    "default_topology_zh": DEFAULT_TOPOLOGY_ZH,
    "default_connection_zh": DEFAULT_CONNECTION_ZH,
}
