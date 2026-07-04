"""Comparability checks and structured error metrics for validation records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, Mapping

from .assumptions import DEFAULT_CONNECTION_ZH, DEFAULT_TOPOLOGY_ZH
from .electrical_semantics import MotorControlMode, normalize_motor_control_mode
from .models import AnalysisResult
from .validation_loader import convert_value_between_units
from .validation_records import (
    ValidationComparabilityStatus,
    ValidationMetricExpectation,
    ValidationRecord,
)


@dataclass(frozen=True)
class MetricPredictionDefinition:
    canonical_unit: str
    quantity_scope: str
    value_kind: str
    current_basis: str | None
    extractor: Callable[[AnalysisResult, str], float | None]


@dataclass(frozen=True)
class ValidationMetricResult:
    metric_name: str
    expected_value: float | None
    predicted_legacy_value: float | None
    predicted_revised_value: float | None
    unit: str | None
    absolute_error_legacy: float | None
    relative_error_legacy: float | None
    absolute_error_revised: float | None
    relative_error_revised: float | None
    uncertainty_band: Dict[str, float | str | None]
    within_tolerance_legacy: bool | None
    within_tolerance_revised: bool | None
    comparability_status: ValidationComparabilityStatus
    exclusion_reason: str | None
    conversion_log: list[str]

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["comparability_status"] = self.comparability_status.value
        return payload


@dataclass(frozen=True)
class ValidationReport:
    validation_id: str
    source_type: str
    evidence_level: str
    synthetic: bool
    not_for_accuracy_claims: bool
    metric_results: list[ValidationMetricResult]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "source_type": self.source_type,
            "evidence_level": self.evidence_level,
            "synthetic": self.synthetic,
            "not_for_accuracy_claims": self.not_for_accuracy_claims,
            "metric_results": [item.to_dict() for item in self.metric_results],
        }


METRIC_PREDICTIONS: Dict[str, Dict[str, MetricPredictionDefinition]] = {
    "rated_torque_nm": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="Nm",
            quantity_scope="shaft",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: result.performance.legacy_rated_torque_nm,
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="Nm",
            quantity_scope="shaft",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: result.performance.revised_rated_torque_nm,
        ),
    },
    "back_emf_phase_peak_v": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="V",
            quantity_scope="phase",
            value_kind="peak",
            current_basis=None,
            extractor=lambda result, _: result.electrical.back_emf_phase_peak_v,
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="V",
            quantity_scope="phase",
            value_kind="peak",
            current_basis=None,
            extractor=lambda result, _: result.electrical.back_emf_phase_peak_v,
        ),
    },
    "back_emf_phase_rms_v": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="V",
            quantity_scope="phase",
            value_kind="rms",
            current_basis=None,
            extractor=lambda result, _: result.electrical.back_emf_phase_rms_v,
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="V",
            quantity_scope="phase",
            value_kind="rms",
            current_basis=None,
            extractor=lambda result, _: (
                result.electrical.back_emf_phase_rms_v
                if result.electrical.control_mode is MotorControlMode.PMSM_SINUSOIDAL
                else result.electrical.revised_bldc_phase_rms_back_emf_v
            ),
        ),
    },
    "back_emf_line_rms_v": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="V",
            quantity_scope="line",
            value_kind="rms",
            current_basis=None,
            extractor=lambda result, _: result.electrical.back_emf_line_rms_v,
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="V",
            quantity_scope="line",
            value_kind="rms",
            current_basis=None,
            extractor=lambda result, _: (
                result.electrical.back_emf_line_rms_v
                if result.electrical.control_mode is MotorControlMode.PMSM_SINUSOIDAL
                else result.electrical.revised_bldc_line_to_line_rms_back_emf_v
            ),
        ),
    },
    "back_emf_constant_line_rms_v_per_krpm": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="V/krpm",
            quantity_scope="line",
            value_kind="rms",
            current_basis=None,
            extractor=lambda result, _: result.electrical.legacy_back_emf_constant_line_rms_v_per_krpm,
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="V/krpm",
            quantity_scope="line",
            value_kind="rms",
            current_basis=None,
            extractor=lambda result, _: (
                result.electrical.revised_back_emf_constant_line_rms_v_per_krpm
                if result.electrical.control_mode is MotorControlMode.PMSM_SINUSOIDAL
                else result.electrical.revised_bldc_back_emf_constant_line_rms_v_per_krpm
            ),
        ),
    },
    "torque_constant_nm_per_a": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="Nm/A",
            quantity_scope="phase",
            value_kind="rms",
            current_basis="phase_rms",
            extractor=lambda result, current_basis: (
                result.electrical.legacy_torque_constant_nm_per_phase_rms_a if current_basis == "phase_rms" else None
            ),
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="Nm/A",
            quantity_scope="phase",
            value_kind="rms",
            current_basis="phase_rms",
            extractor=lambda result, current_basis: _extract_revised_torque_constant(result, current_basis),
        ),
    },
    "phase_resistance_ohm": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="ohm",
            quantity_scope="phase",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: result.electrical.phase_resistance_ohm,
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="ohm",
            quantity_scope="phase",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: None,
        ),
    },
    "phase_inductance_h": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="H",
            quantity_scope="phase",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: result.electrical.phase_inductance_h,
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="H",
            quantity_scope="phase",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: None,
        ),
    },
    "rated_current_a": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="A",
            quantity_scope="phase",
            value_kind="rms",
            current_basis="phase_rms",
            extractor=lambda result, current_basis: (
                result.performance.phase_current_rms_a if current_basis == "phase_rms" else None
            ),
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="A",
            quantity_scope="phase",
            value_kind="rms",
            current_basis="phase_rms",
            extractor=lambda result, _: None,
        ),
    },
    "copper_loss_w": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="W",
            quantity_scope="phase",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: result.performance.copper_loss_w,
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="W",
            quantity_scope="phase",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: None,
        ),
    },
    "iron_loss_w": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="W",
            quantity_scope="core",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: result.performance.core_loss_w,
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="W",
            quantity_scope="core",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: None,
        ),
    },
    "mechanical_loss_w": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="W",
            quantity_scope="mechanical",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: result.performance.mechanical_loss_w,
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="W",
            quantity_scope="mechanical",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: None,
        ),
    },
    "efficiency": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="%",
            quantity_scope="system",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: result.performance.efficiency_percent,
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="%",
            quantity_scope="system",
            value_kind="average",
            current_basis=None,
            extractor=lambda result, _: None,
        ),
    },
    "required_voltage_v": {
        "legacy": MetricPredictionDefinition(
            canonical_unit="V",
            quantity_scope="line",
            value_kind="rms",
            current_basis=None,
            extractor=lambda result, _: result.performance.required_voltage_v,
        ),
        "revised": MetricPredictionDefinition(
            canonical_unit="V",
            quantity_scope="line",
            value_kind="rms",
            current_basis=None,
            extractor=lambda result, _: None,
        ),
    },
}


def _extract_revised_torque_constant(result: AnalysisResult, current_basis: str | None) -> float | None:
    if result.electrical.control_mode is MotorControlMode.PMSM_SINUSOIDAL:
        if current_basis == "phase_rms":
            return result.electrical.revised_torque_constant_nm_per_phase_rms_a
        if current_basis == "phase_peak":
            return result.electrical.revised_torque_constant_nm_per_phase_peak_a
        return None

    if current_basis == "phase_rms":
        return result.electrical.revised_bldc_torque_constant_nm_per_phase_rms_a
    if current_basis == "conduction":
        return result.electrical.revised_bldc_torque_constant_nm_per_conduction_a
    return None


def compare_validation_record(
    record: ValidationRecord,
    legacy_result: AnalysisResult,
    revised_result: AnalysisResult,
) -> ValidationReport:
    metric_results = [
        _compare_metric(record, metric_name, metric_expectation, legacy_result, revised_result)
        for metric_name, metric_expectation in record.expected_outputs.items()
    ]
    return ValidationReport(
        validation_id=record.validation_id,
        source_type=record.source_type.value,
        evidence_level=record.evidence_level.value,
        synthetic=record.synthetic,
        not_for_accuracy_claims=record.not_for_accuracy_claims,
        metric_results=metric_results,
    )


def _compare_metric(
    record: ValidationRecord,
    metric_name: str,
    expectation: ValidationMetricExpectation,
    legacy_result: AnalysisResult,
    revised_result: AnalysisResult,
) -> ValidationMetricResult:
    conversion_log: list[str] = []
    excluded_reason = record.excluded_comparisons.get(metric_name)
    if excluded_reason:
        return ValidationMetricResult(
            metric_name=metric_name,
            expected_value=expectation.value,
            predicted_legacy_value=None,
            predicted_revised_value=None,
            unit=expectation.unit,
            absolute_error_legacy=None,
            relative_error_legacy=None,
            absolute_error_revised=None,
            relative_error_revised=None,
            uncertainty_band=_build_uncertainty_band(record, metric_name),
            within_tolerance_legacy=None,
            within_tolerance_revised=None,
            comparability_status=ValidationComparabilityStatus.NOT_AVAILABLE,
            exclusion_reason=excluded_reason,
            conversion_log=conversion_log,
        )

    comparability_status, exclusion_reason = _determine_comparability(record, expectation, legacy_result)
    if comparability_status is not ValidationComparabilityStatus.DIRECTLY_COMPARABLE:
        return ValidationMetricResult(
            metric_name=metric_name,
            expected_value=expectation.value if expectation.is_available else None,
            predicted_legacy_value=None,
            predicted_revised_value=None,
            unit=expectation.unit,
            absolute_error_legacy=None,
            relative_error_legacy=None,
            absolute_error_revised=None,
            relative_error_revised=None,
            uncertainty_band=_build_uncertainty_band(record, metric_name),
            within_tolerance_legacy=None,
            within_tolerance_revised=None,
            comparability_status=comparability_status,
            exclusion_reason=exclusion_reason,
            conversion_log=conversion_log,
        )

    expected_value = float(expectation.value)
    metric_definitions = METRIC_PREDICTIONS[metric_name]
    legacy_definition = metric_definitions["legacy"]
    revised_definition = metric_definitions["revised"]
    current_basis = expectation.current_basis
    canonical_unit = legacy_definition.canonical_unit
    if expectation.unit != canonical_unit:
        expected_value, log_message = convert_value_between_units(expected_value, expectation.unit or "", canonical_unit)
        conversion_log.append(log_message)

    legacy_value = legacy_definition.extractor(legacy_result, current_basis)
    revised_value = revised_definition.extractor(revised_result, current_basis)

    absolute_error_legacy, relative_error_legacy = _compute_error_pair(expected_value, legacy_value)
    absolute_error_revised, relative_error_revised = _compute_error_pair(expected_value, revised_value)

    return ValidationMetricResult(
        metric_name=metric_name,
        expected_value=expected_value,
        predicted_legacy_value=legacy_value,
        predicted_revised_value=revised_value,
        unit=canonical_unit,
        absolute_error_legacy=absolute_error_legacy,
        relative_error_legacy=relative_error_legacy,
        absolute_error_revised=absolute_error_revised,
        relative_error_revised=relative_error_revised,
        uncertainty_band=_build_uncertainty_band(record, metric_name),
        within_tolerance_legacy=_within_tolerance(record, metric_name, absolute_error_legacy, relative_error_legacy),
        within_tolerance_revised=_within_tolerance(record, metric_name, absolute_error_revised, relative_error_revised),
        comparability_status=ValidationComparabilityStatus.DIRECTLY_COMPARABLE,
        exclusion_reason=None,
        conversion_log=conversion_log,
    )


def _determine_comparability(
    record: ValidationRecord,
    expectation: ValidationMetricExpectation,
    result: AnalysisResult,
) -> tuple[ValidationComparabilityStatus, str | None]:
    if not expectation.is_available:
        return ValidationComparabilityStatus.NOT_AVAILABLE, "expected output 当前不可用。"

    record_mode = normalize_motor_control_mode(record.control_mode)
    result_mode = normalize_motor_control_mode(result.electrical.control_mode)
    if record_mode is not result_mode:
        return ValidationComparabilityStatus.CONTROL_STRATEGY_MISMATCH, "control_mode 与计算结果不一致。"

    if _normalize_topology(record.topology) != _normalize_topology(DEFAULT_TOPOLOGY_ZH):
        return ValidationComparabilityStatus.TOPOLOGY_MISMATCH, "当前记录拓扑与项目默认拓扑不一致。"

    connection_field = record.get_input_parameter("winding_connection")
    if connection_field and connection_field.is_available and str(connection_field.value).strip() != "Y":
        return ValidationComparabilityStatus.SEMANTICS_MISMATCH, "当前项目默认 Y 接，不允许直接比较 Delta 连接数据。"

    waveform_field = record.get_input_parameter("back_emf_waveform")
    if waveform_field and waveform_field.is_available:
        waveform = str(waveform_field.value).strip().lower()
        if record_mode is MotorControlMode.PMSM_SINUSOIDAL and waveform != "sinusoidal":
            return ValidationComparabilityStatus.WAVEFORM_MISMATCH, "PMSM 结果只能与 sinusoidal 波形数据比较。"
        if record_mode is MotorControlMode.BLDC_120_DEGREE and waveform == "sinusoidal":
            return ValidationComparabilityStatus.WAVEFORM_MISMATCH, "BLDC 结果不能与 sinusoidal 波形数据比较。"

    metric_definitions = METRIC_PREDICTIONS[expectation.metric_name]
    legacy_definition = metric_definitions["legacy"]
    if expectation.quantity_scope and expectation.quantity_scope != legacy_definition.quantity_scope:
        return ValidationComparabilityStatus.SEMANTICS_MISMATCH, "phase/line 或系统量纲语义不一致。"
    if expectation.value_kind and expectation.value_kind != legacy_definition.value_kind:
        return ValidationComparabilityStatus.SEMANTICS_MISMATCH, "RMS/peak/flat-top 等数值语义不一致。"
    if legacy_definition.current_basis and not expectation.current_basis:
        return ValidationComparabilityStatus.INSUFFICIENT_INPUT_DATA, "缺少 current_basis，无法判断 A 的电流基准。"
    if expectation.current_basis and legacy_definition.current_basis and expectation.current_basis != legacy_definition.current_basis:
        if expectation.metric_name == "torque_constant_nm_per_a":
            if record_mode is MotorControlMode.PMSM_SINUSOIDAL and expectation.current_basis == "phase_peak":
                return ValidationComparabilityStatus.DIRECTLY_COMPARABLE, None
            if record_mode is MotorControlMode.BLDC_120_DEGREE and expectation.current_basis == "conduction":
                return ValidationComparabilityStatus.DIRECTLY_COMPARABLE, None
        return ValidationComparabilityStatus.SEMANTICS_MISMATCH, "电流基准不一致，不能直接比较。"

    return ValidationComparabilityStatus.DIRECTLY_COMPARABLE, None


def _normalize_topology(raw_value: str) -> str:
    return raw_value.replace("，", ",").replace(" ", "").lower()


def _compute_error_pair(expected_value: float, predicted_value: float | None) -> tuple[float | None, float | None]:
    if predicted_value is None:
        return None, None
    absolute_error = predicted_value - expected_value
    if expected_value == 0:
        return absolute_error, None
    return absolute_error, absolute_error / expected_value


def _build_uncertainty_band(record: ValidationRecord, metric_name: str) -> Dict[str, float | str | None]:
    uncertainty = record.uncertainty.get(metric_name)
    if uncertainty is None:
        return {"absolute": None, "relative": None, "coverage_factor": None, "notes": None}
    return {
        "absolute": uncertainty.absolute,
        "relative": uncertainty.relative,
        "coverage_factor": uncertainty.coverage_factor,
        "notes": uncertainty.notes,
    }


def _within_tolerance(
    record: ValidationRecord,
    metric_name: str,
    absolute_error: float | None,
    relative_error: float | None,
) -> bool | None:
    tolerance = record.tolerances.get(metric_name)
    if tolerance is None or absolute_error is None:
        return None

    if tolerance.absolute is not None and abs(absolute_error) > tolerance.absolute:
        return False
    if tolerance.relative is not None:
        if relative_error is None:
            return None
        if abs(relative_error) > tolerance.relative:
            return False
    return True
