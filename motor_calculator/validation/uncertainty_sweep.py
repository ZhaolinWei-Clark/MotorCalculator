"""Deterministic one-at-a-time and parameter-bound uncertainty sweeps."""

from __future__ import annotations

import itertools
import math
import random
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping

from .uncertainty_models import ParameterUncertainty, UncertaintyKind


ParameterValues = Mapping[str, float]
MetricEvaluator = Callable[[ParameterValues], float]
PhysicalValidator = Callable[[ParameterValues], str | None]


class BoundSweepMode(str, Enum):
    ONE_AT_A_TIME = "ONE_AT_A_TIME"
    FULL_CORNERS = "FULL_CORNERS"
    CAPPED_COMBINATIONS = "CAPPED_COMBINATIONS"


@dataclass(frozen=True)
class ParameterSensitivity:
    parameter_name: str
    nominal_input: float
    lower_input: float | None
    upper_input: float | None
    nominal_output: float
    lower_output: float | None
    upper_output: float | None
    absolute_output_range: float | None
    normalized_sensitivity: float | None
    status: str
    notes: tuple[str, ...]


@dataclass(frozen=True)
class DeterministicSweepResult:
    nominal_output: float
    sensitivities: tuple[ParameterSensitivity, ...]
    ranked_parameters: tuple[str, ...]
    rejected_evaluation_count: int
    rejection_reasons: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class ParameterBoundEnvelope:
    nominal_output: float
    minimum_observed_prediction: float
    maximum_observed_prediction: float
    valid_evaluation_count: int
    rejected_evaluation_count: int
    rejection_reasons: tuple[tuple[str, int], ...]
    mode: BoundSweepMode
    combinations_evaluated: int
    warnings: tuple[str, ...]


def _nominal_values(parameters: tuple[ParameterUncertainty, ...]) -> dict[str, float]:
    return {parameter.parameter_name: parameter.nominal_value for parameter in parameters}


def _evaluate(
    values: dict[str, float],
    evaluator: MetricEvaluator,
    validator: PhysicalValidator,
) -> tuple[float | None, str | None]:
    rejection = validator(values)
    if rejection is not None:
        return None, rejection
    try:
        output = float(evaluator(dict(values)))
    except (TypeError, ValueError, ArithmeticError) as exc:
        return None, f"evaluation_error:{type(exc).__name__}:{exc}"
    if not math.isfinite(output):
        return None, "evaluation_error:non_finite_output"
    return output, None


def _normalized_sensitivity(
    nominal_input: float,
    changed_input: float,
    nominal_output: float,
    changed_output: float,
) -> float | None:
    if math.isclose(nominal_input, 0.0, abs_tol=1e-15) or math.isclose(nominal_output, 0.0, abs_tol=1e-15):
        return None
    relative_input = (changed_input - nominal_input) / nominal_input
    if math.isclose(relative_input, 0.0, abs_tol=1e-15):
        return None
    relative_output = (changed_output - nominal_output) / nominal_output
    return relative_output / relative_input


def run_deterministic_parameter_sweep(
    parameters: tuple[ParameterUncertainty, ...],
    evaluator: MetricEvaluator,
    validator: PhysicalValidator,
) -> DeterministicSweepResult:
    nominal_values = _nominal_values(parameters)
    nominal_output, nominal_rejection = _evaluate(nominal_values, evaluator, validator)
    if nominal_rejection is not None or nominal_output is None:
        raise ValueError(f"nominal uncertainty case is invalid: {nominal_rejection}")

    sensitivities = []
    rejection_reasons: Counter[str] = Counter()
    for parameter in parameters:
        if not parameter.has_parameter_bounds:
            status = "exact" if parameter.uncertainty_kind is UncertaintyKind.EXACT else "unswept"
            notes = (
                "EXACT parameter remains fixed.",
            ) if status == "exact" else (
                f"{parameter.uncertainty_kind.value} has no deterministic bounds and remains nominal.",
            )
            sensitivities.append(ParameterSensitivity(
                parameter.parameter_name,
                parameter.nominal_value,
                None,
                None,
                nominal_output,
                None,
                None,
                None,
                None,
                status,
                notes,
            ))
            continue

        outputs: list[float | None] = []
        for changed_value in (float(parameter.lower_bound), float(parameter.upper_bound)):
            changed = dict(nominal_values)
            changed[parameter.parameter_name] = changed_value
            output, rejection = _evaluate(changed, evaluator, validator)
            outputs.append(output)
            if rejection is not None:
                rejection_reasons[rejection] += 1
        valid_outputs = tuple(value for value in outputs if value is not None)
        normalized = []
        for changed_input, output in zip((parameter.lower_bound, parameter.upper_bound), outputs):
            if output is not None:
                value = _normalized_sensitivity(
                    parameter.nominal_value,
                    float(changed_input),
                    nominal_output,
                    output,
                )
                if value is not None:
                    normalized.append(value)
        sensitivities.append(ParameterSensitivity(
            parameter.parameter_name,
            parameter.nominal_value,
            parameter.lower_bound,
            parameter.upper_bound,
            nominal_output,
            outputs[0],
            outputs[1],
            None if not valid_outputs else max(valid_outputs + (nominal_output,)) - min(valid_outputs + (nominal_output,)),
            None if not normalized else max(normalized, key=abs),
            "available" if len(valid_outputs) == 2 else "partially_rejected",
            ("One-at-a-time lower/upper sweep; all other parameters remain nominal.",),
        ))
    ranked = tuple(
        item.parameter_name
        for item in sorted(
            (item for item in sensitivities if item.absolute_output_range is not None),
            key=lambda item: (-float(item.absolute_output_range), item.parameter_name),
        )
    )
    return DeterministicSweepResult(
        nominal_output=nominal_output,
        sensitivities=tuple(sensitivities),
        ranked_parameters=ranked,
        rejected_evaluation_count=sum(rejection_reasons.values()),
        rejection_reasons=tuple(sorted(rejection_reasons.items())),
    )


def _parameter_points(parameter: ParameterUncertainty) -> tuple[float, ...]:
    if not parameter.has_parameter_bounds:
        return (parameter.nominal_value,)
    return tuple(dict.fromkeys((
        float(parameter.lower_bound),
        parameter.nominal_value,
        float(parameter.upper_bound),
    )))


def _candidate_combinations(
    parameters: tuple[ParameterUncertainty, ...],
    mode: BoundSweepMode,
    max_combinations: int,
    seed: int,
) -> tuple[tuple[float, ...], ...]:
    points = tuple(_parameter_points(parameter) for parameter in parameters)
    nominal = tuple(parameter.nominal_value for parameter in parameters)
    if mode is BoundSweepMode.ONE_AT_A_TIME:
        combinations = [nominal]
        for index, parameter_points in enumerate(points):
            for point in parameter_points:
                candidate = list(nominal)
                candidate[index] = point
                combinations.append(tuple(candidate))
        return tuple(dict.fromkeys(combinations))

    total = math.prod(len(values) for values in points)
    if mode is BoundSweepMode.FULL_CORNERS:
        if total > max_combinations:
            raise ValueError(
                f"full-corner sweep requires {total} combinations, exceeding cap {max_combinations}"
            )
        return tuple(itertools.product(*points))

    if max_combinations < 3:
        raise ValueError("capped combinations require max_combinations >= 3")
    if total <= max_combinations:
        return tuple(itertools.product(*points))
    rng = random.Random(seed)
    selected = {nominal, tuple(values[0] for values in points), tuple(values[-1] for values in points)}
    while len(selected) < max_combinations:
        selected.add(tuple(rng.choice(values) for values in points))
    return tuple(sorted(selected))


def run_parameter_bound_envelope(
    parameters: tuple[ParameterUncertainty, ...],
    evaluator: MetricEvaluator,
    validator: PhysicalValidator,
    *,
    mode: BoundSweepMode = BoundSweepMode.FULL_CORNERS,
    max_combinations: int = 10000,
    seed: int = 0,
) -> ParameterBoundEnvelope:
    nominal_values = _nominal_values(parameters)
    nominal_output, nominal_rejection = _evaluate(nominal_values, evaluator, validator)
    if nominal_rejection is not None or nominal_output is None:
        raise ValueError(f"nominal uncertainty case is invalid: {nominal_rejection}")
    combinations = _candidate_combinations(parameters, mode, max_combinations, seed)
    outputs = []
    reasons: Counter[str] = Counter()
    names = tuple(parameter.parameter_name for parameter in parameters)
    for combination in combinations:
        values = dict(zip(names, combination))
        output, rejection = _evaluate(values, evaluator, validator)
        if output is None:
            reasons[rejection or "unknown_rejection"] += 1
        else:
            outputs.append(output)
    if not outputs:
        raise ValueError("all parameter-bound evaluations were rejected")
    warnings = [
        "This is a parameter-bound envelope, not a confidence interval.",
        "Model-form uncertainty is not included.",
    ]
    unknown = tuple(
        parameter.parameter_name
        for parameter in parameters
        if parameter.uncertainty_kind is UncertaintyKind.UNKNOWN
    )
    if unknown:
        warnings.append(f"UNKNOWN parameters held nominal: {', '.join(unknown)}.")
    return ParameterBoundEnvelope(
        nominal_output=nominal_output,
        minimum_observed_prediction=min(outputs),
        maximum_observed_prediction=max(outputs),
        valid_evaluation_count=len(outputs),
        rejected_evaluation_count=sum(reasons.values()),
        rejection_reasons=tuple(sorted(reasons.items())),
        mode=mode,
        combinations_evaluated=len(combinations),
        warnings=tuple(warnings),
    )
