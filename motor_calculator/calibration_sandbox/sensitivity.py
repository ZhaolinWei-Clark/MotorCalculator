"""Read-only parameter sensitivity runner for Phase 6A."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any, Callable, Mapping, Sequence

from motor_core import MotorAnalysisEngine
from motor_core.models import AnalysisResult, MotorAnalysisInput
from motor_core.units import legacy_params_to_model_input

from .perturbation import PerturbationSpec, SensitivityTarget


class SensitivitySandboxError(ValueError):
    """Raised when a sensitivity request cannot be represented safely."""


OutputExtractor = Callable[[AnalysisResult], float | None]


@dataclass(frozen=True)
class _ParameterTargetDefinition:
    target: SensitivityTarget
    requires_integer: bool = False


@dataclass(frozen=True)
class _OutputMetricDefinition:
    output_name: str
    unit: str | None
    extractor: OutputExtractor | None
    unavailable_reason: str | None = None


@dataclass(frozen=True)
class SensitivityOutputChange:
    """One observed output change produced by a temporary perturbation."""

    output_name: str
    baseline_value: float | None
    temporary_value: float | None
    absolute_change: float | None
    relative_change_percent: float | None
    unit: str | None = None
    status: str = "available"
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SensitivityRunResult:
    """Result for one parameter and one perturbation percentage."""

    perturbation: PerturbationSpec
    affected_outputs: tuple[SensitivityOutputChange, ...]
    status: str
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "perturbation": asdict(self.perturbation),
            "affected_outputs": [item.to_dict() for item in self.affected_outputs],
            "status": self.status,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class SensitivitySummary:
    """Aggregate sandbox output for a read-only sweep."""

    tested_parameters: tuple[SensitivityTarget, ...]
    perturbation_percents: tuple[float, ...]
    output_names: tuple[str, ...]
    baseline_outputs: dict[str, float | None]
    run_results: tuple[SensitivityRunResult, ...]
    most_sensitive_parameters: dict[str, str | None]
    nonlinear_or_unstable_notes: tuple[str, ...]
    boundary_warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tested_parameters": [asdict(item) for item in self.tested_parameters],
            "perturbation_percents": list(self.perturbation_percents),
            "output_names": list(self.output_names),
            "baseline_outputs": dict(self.baseline_outputs),
            "run_results": [item.to_dict() for item in self.run_results],
            "most_sensitive_parameters": dict(self.most_sensitive_parameters),
            "nonlinear_or_unstable_notes": list(self.nonlinear_or_unstable_notes),
            "boundary_warnings": list(self.boundary_warnings),
        }


_PARAMETER_TARGETS: dict[str, _ParameterTargetDefinition] = {
    "magnet_remanence_t": _ParameterTargetDefinition(
        target=SensitivityTarget(
            parameter_name="magnet_remanence_t",
            internal_field_name="remanence_t",
            unit="T",
            available=True,
            notes="Maps to MotorAnalysisInput.remanence_t.",
        ),
    ),
    "air_gap_m": _ParameterTargetDefinition(
        target=SensitivityTarget(
            parameter_name="air_gap_m",
            internal_field_name="air_gap_per_side_m",
            unit="m",
            available=True,
            notes="Maps to the existing per-side mechanical air-gap field.",
        ),
    ),
    "magnet_thickness_m": _ParameterTargetDefinition(
        target=SensitivityTarget(
            parameter_name="magnet_thickness_m",
            internal_field_name="magnet_thickness_m",
            unit="m",
            available=True,
            notes="Maps directly to MotorAnalysisInput.magnet_thickness_m.",
        ),
    ),
    "turns_per_phase": _ParameterTargetDefinition(
        target=SensitivityTarget(
            parameter_name="turns_per_phase",
            internal_field_name="turns_per_phase",
            unit="turns",
            available=True,
            notes="Integer input; perturbations are rounded to the nearest turn.",
        ),
        requires_integer=True,
    ),
    "phase_current_a": _ParameterTargetDefinition(
        target=SensitivityTarget(
            parameter_name="phase_current_a",
            internal_field_name=None,
            unit="A",
            available=False,
            notes="The current production input model does not accept phase current as an independent input.",
        ),
    ),
    "rated_speed_rpm": _ParameterTargetDefinition(
        target=SensitivityTarget(
            parameter_name="rated_speed_rpm",
            internal_field_name="mechanical_speed_rpm",
            unit="rpm",
            available=True,
            notes="Maps to MotorAnalysisInput.mechanical_speed_rpm.",
        ),
    ),
}

_OUTPUT_METRICS: dict[str, _OutputMetricDefinition] = {
    "rated_torque_nm": _OutputMetricDefinition(
        output_name="rated_torque_nm",
        unit="Nm",
        extractor=lambda result: result.performance.rated_torque_nm,
    ),
    "back_emf_phase_peak_v": _OutputMetricDefinition(
        output_name="back_emf_phase_peak_v",
        unit="V",
        extractor=lambda result: result.electrical.back_emf_phase_peak_v,
    ),
    "back_emf_line_rms_v": _OutputMetricDefinition(
        output_name="back_emf_line_rms_v",
        unit="V",
        extractor=lambda result: result.electrical.back_emf_line_rms_v,
    ),
    "torque_constant_nm_per_a": _OutputMetricDefinition(
        output_name="torque_constant_nm_per_a",
        unit="Nm/A",
        extractor=lambda result: result.electrical.torque_constant_nm_per_phase_rms_a,
    ),
    "required_voltage_v": _OutputMetricDefinition(
        output_name="required_voltage_v",
        unit="V",
        extractor=lambda result: result.performance.required_voltage_v,
    ),
    "copper_loss_w": _OutputMetricDefinition(
        output_name="copper_loss_w",
        unit="W",
        extractor=lambda result: result.performance.copper_loss_w,
    ),
    "iron_loss_w": _OutputMetricDefinition(
        output_name="iron_loss_w",
        unit="W",
        extractor=lambda result: result.performance.core_loss_w,
    ),
    "efficiency_percent": _OutputMetricDefinition(
        output_name="efficiency_percent",
        unit="%",
        extractor=lambda result: result.performance.efficiency_percent,
    ),
}

DEFAULT_PERTURBATION_PERCENTS: tuple[float, ...] = (-5.0, -1.0, 1.0, 5.0)
DEFAULT_OUTPUT_NAMES: tuple[str, ...] = tuple(_OUTPUT_METRICS)

BOUNDARY_WARNINGS: tuple[str, ...] = (
    "Phase 6A is a read-only sensitivity sandbox.",
    "Sandbox results are not calibrated values and must not be written back to production defaults.",
    "The runner calls the existing calculation engine without modifying motor_core/calculations.py.",
)


def get_default_sensitivity_targets() -> tuple[SensitivityTarget, ...]:
    return tuple(definition.target for definition in _PARAMETER_TARGETS.values())


def run_sensitivity_case(
    baseline_input: MotorAnalysisInput | Mapping[str, Any],
    parameter_name: str,
    perturbation_percent: float,
    output_names: Sequence[str] = DEFAULT_OUTPUT_NAMES,
) -> SensitivityRunResult:
    """Run one temporary perturbation against a copied baseline input."""

    model_input = _coerce_model_input(baseline_input)
    target_definition = _get_target_definition(parameter_name)
    target = target_definition.target

    if not target.available or target.internal_field_name is None:
        return SensitivityRunResult(
            perturbation=PerturbationSpec(
                parameter_name=target.parameter_name,
                baseline_value=None,
                perturbation_percent=float(perturbation_percent),
                temporary_value=None,
                internal_field_name=target.internal_field_name,
                unit=target.unit,
                status="unavailable",
                notes=target.notes,
            ),
            affected_outputs=tuple(_unavailable_output_change(name, "input parameter unavailable") for name in output_names),
            status="unavailable",
            error_message=target.notes,
        )

    baseline_value = getattr(model_input, target.internal_field_name)
    temporary_value = _perturb_value(
        baseline_value=baseline_value,
        perturbation_percent=perturbation_percent,
        requires_integer=target_definition.requires_integer,
    )
    perturbation = PerturbationSpec(
        parameter_name=target.parameter_name,
        baseline_value=baseline_value,
        perturbation_percent=float(perturbation_percent),
        temporary_value=temporary_value,
        internal_field_name=target.internal_field_name,
        unit=target.unit,
        status="ready",
        notes=target.notes,
    )

    baseline_result = _calculate(model_input)
    temporary_input = replace(model_input, **{target.internal_field_name: temporary_value})
    temporary_result = _calculate(temporary_input)

    return SensitivityRunResult(
        perturbation=perturbation,
        affected_outputs=tuple(
            _build_output_change(output_name, baseline_result, temporary_result)
            for output_name in output_names
        ),
        status="ok",
        error_message=None,
    )


def run_sensitivity_sweep(
    baseline_input: MotorAnalysisInput | Mapping[str, Any],
    parameter_names: Sequence[str] | None = None,
    perturbation_percents: Sequence[float] = DEFAULT_PERTURBATION_PERCENTS,
    output_names: Sequence[str] = DEFAULT_OUTPUT_NAMES,
) -> SensitivitySummary:
    """Run the Phase 6A default one-parameter-at-a-time sweep."""

    selected_parameters = tuple(parameter_names or _PARAMETER_TARGETS.keys())
    selected_outputs = tuple(output_names)
    model_input = _coerce_model_input(baseline_input)
    baseline_result = _calculate(model_input)
    baseline_outputs = {
        output_name: _extract_output(output_name, baseline_result)
        for output_name in selected_outputs
    }

    results: list[SensitivityRunResult] = []
    for parameter_name in selected_parameters:
        for perturbation_percent in perturbation_percents:
            results.append(
                run_sensitivity_case(
                    model_input,
                    parameter_name=parameter_name,
                    perturbation_percent=perturbation_percent,
                    output_names=selected_outputs,
                )
            )

    return SensitivitySummary(
        tested_parameters=tuple(_get_target_definition(name).target for name in selected_parameters),
        perturbation_percents=tuple(float(value) for value in perturbation_percents),
        output_names=selected_outputs,
        baseline_outputs=baseline_outputs,
        run_results=tuple(results),
        most_sensitive_parameters=_rank_most_sensitive_parameters(results, selected_outputs),
        nonlinear_or_unstable_notes=_detect_nonlinear_or_unstable_notes(results),
        boundary_warnings=BOUNDARY_WARNINGS,
    )


def _coerce_model_input(baseline_input: MotorAnalysisInput | Mapping[str, Any]) -> MotorAnalysisInput:
    if isinstance(baseline_input, MotorAnalysisInput):
        return baseline_input
    return legacy_params_to_model_input(baseline_input)


def _get_target_definition(parameter_name: str) -> _ParameterTargetDefinition:
    try:
        return _PARAMETER_TARGETS[parameter_name]
    except KeyError as exc:
        supported = ", ".join(sorted(_PARAMETER_TARGETS))
        raise SensitivitySandboxError(
            f"Unsupported sensitivity parameter '{parameter_name}'. Supported parameters: {supported}."
        ) from exc


def _get_output_definition(output_name: str) -> _OutputMetricDefinition:
    try:
        return _OUTPUT_METRICS[output_name]
    except KeyError as exc:
        supported = ", ".join(sorted(_OUTPUT_METRICS))
        raise SensitivitySandboxError(
            f"Unsupported sensitivity output '{output_name}'. Supported outputs: {supported}."
        ) from exc


def _perturb_value(
    baseline_value: float | int,
    perturbation_percent: float,
    requires_integer: bool,
) -> float | int:
    temporary_value = float(baseline_value) * (1.0 + float(perturbation_percent) / 100.0)
    if requires_integer:
        return max(1, int(round(temporary_value)))
    return temporary_value


def _calculate(model_input: MotorAnalysisInput) -> AnalysisResult:
    return MotorAnalysisEngine(model_input).run_full_analysis()


def _build_output_change(
    output_name: str,
    baseline_result: AnalysisResult,
    temporary_result: AnalysisResult,
) -> SensitivityOutputChange:
    output_definition = _get_output_definition(output_name)
    if output_definition.extractor is None:
        return _unavailable_output_change(output_name, output_definition.unavailable_reason or "output unavailable")

    baseline_value = output_definition.extractor(baseline_result)
    temporary_value = output_definition.extractor(temporary_result)
    absolute_change = _difference(temporary_value, baseline_value)
    return SensitivityOutputChange(
        output_name=output_name,
        baseline_value=baseline_value,
        temporary_value=temporary_value,
        absolute_change=absolute_change,
        relative_change_percent=_relative_change_percent(temporary_value, baseline_value),
        unit=output_definition.unit,
        status="available" if baseline_value is not None and temporary_value is not None else "unavailable",
        notes=None if baseline_value is not None and temporary_value is not None else "AnalysisResult field returned None.",
    )


def _extract_output(output_name: str, result: AnalysisResult) -> float | None:
    output_definition = _get_output_definition(output_name)
    if output_definition.extractor is None:
        return None
    return output_definition.extractor(result)


def _unavailable_output_change(output_name: str, reason: str) -> SensitivityOutputChange:
    output_definition = _get_output_definition(output_name)
    return SensitivityOutputChange(
        output_name=output_name,
        baseline_value=None,
        temporary_value=None,
        absolute_change=None,
        relative_change_percent=None,
        unit=output_definition.unit,
        status="unavailable",
        notes=reason,
    )


def _difference(temporary_value: float | None, baseline_value: float | None) -> float | None:
    if temporary_value is None or baseline_value is None:
        return None
    return temporary_value - baseline_value


def _relative_change_percent(temporary_value: float | None, baseline_value: float | None) -> float | None:
    if temporary_value is None or baseline_value is None or baseline_value == 0:
        return None
    return (temporary_value - baseline_value) / baseline_value * 100.0


def _rank_most_sensitive_parameters(
    results: Sequence[SensitivityRunResult],
    output_names: Sequence[str],
) -> dict[str, str | None]:
    rankings: dict[str, str | None] = {}
    for output_name in output_names:
        best_parameter: str | None = None
        best_change = -math.inf
        for result in results:
            if result.status != "ok":
                continue
            for output_change in result.affected_outputs:
                if output_change.output_name != output_name:
                    continue
                if output_change.relative_change_percent is None:
                    continue
                magnitude = abs(output_change.relative_change_percent)
                if magnitude > best_change:
                    best_change = magnitude
                    best_parameter = result.perturbation.parameter_name
        rankings[output_name] = best_parameter
    return rankings


def _detect_nonlinear_or_unstable_notes(
    results: Sequence[SensitivityRunResult],
) -> tuple[str, ...]:
    notes: list[str] = []
    for result in results:
        if result.status == "unavailable":
            notes.append(f"{result.perturbation.parameter_name}: {result.error_message}")
            continue
        if result.status != "ok":
            notes.append(f"{result.perturbation.parameter_name}: run status {result.status}")
            continue
        if result.perturbation.baseline_value == result.perturbation.temporary_value:
            notes.append(
                f"{result.perturbation.parameter_name} {result.perturbation.perturbation_percent:+g}% "
                "rounded back to the baseline value."
            )
    return tuple(dict.fromkeys(notes))
