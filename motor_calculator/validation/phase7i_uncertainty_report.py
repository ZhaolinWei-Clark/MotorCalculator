"""Run and render the frozen Phase 7I AFPM back-EMF demonstration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .afpm_uncertainty import (
    controlled_reference_nominal_values,
    evaluate_controlled_back_emf_phase_rms_v,
    numerical_integration_uncertainty_percent,
    validate_physical_parameter_values,
)
from .fea_reference import load_fea_reference_definition
from .monte_carlo import MonteCarloResult, run_monte_carlo
from .uncertainty_models import (
    AccuracyEnvelopeResult,
    ModelFormUncertaintyStatus,
    ResultConfidence,
    UncertaintyKind,
    UncertaintySpecification,
    classify_result_confidence,
    load_uncertainty_specification,
)
from .uncertainty_sweep import (
    BoundSweepMode,
    DeterministicSweepResult,
    ParameterBoundEnvelope,
    run_deterministic_parameter_sweep,
    run_parameter_bound_envelope,
)


@dataclass(frozen=True)
class Phase7IUncertaintyDemonstration:
    specification: UncertaintySpecification
    deterministic_sweep: DeterministicSweepResult
    bound_envelope: ParameterBoundEnvelope
    monte_carlo: MonteCarloResult
    accuracy_envelope: AccuracyEnvelopeResult


def run_phase7i_demonstration(
    repository_root: Path,
    *,
    monte_carlo_sample_count: int = 5000,
    random_seed: int = 20260701,
    specification_override: UncertaintySpecification | None = None,
) -> Phase7IUncertaintyDemonstration:
    root = Path(repository_root)
    reference = load_fea_reference_definition(
        root / "validation_data" / "fea_reference" / "phase7h_controlled_ssdr_machine.json"
    )
    specification = specification_override or load_uncertainty_specification(
        root / "validation_data" / "uncertainty" / "phase7i_afpm_back_emf_uncertainty.json"
    )
    reference_nominal = controlled_reference_nominal_values(reference)
    for parameter in specification.parameters:
        if parameter.parameter_name not in reference_nominal:
            raise ValueError(f"uncertainty parameter is not supported by controlled AFPM adapter: {parameter.parameter_name}")
        if specification_override is None and parameter.nominal_value != reference_nominal[parameter.parameter_name]:
            raise ValueError(f"uncertainty nominal does not match frozen reference: {parameter.parameter_name}")

    evaluator = lambda values: evaluate_controlled_back_emf_phase_rms_v(reference, values)
    sweep = run_deterministic_parameter_sweep(
        specification.parameters, evaluator, validate_physical_parameter_values
    )
    bounded_parameter_count = sum(
        parameter.has_parameter_bounds for parameter in specification.parameters
    )
    bound_mode = (
        BoundSweepMode.FULL_CORNERS
        if 3 ** bounded_parameter_count <= 5000
        else BoundSweepMode.CAPPED_COMBINATIONS
    )
    bound = run_parameter_bound_envelope(
        specification.parameters,
        evaluator,
        validate_physical_parameter_values,
        mode=bound_mode,
        max_combinations=5000,
    )
    monte_carlo = run_monte_carlo(
        specification.parameters,
        evaluator,
        validate_physical_parameter_values,
        sample_count=monte_carlo_sample_count,
        random_seed=random_seed,
    )
    numerical = numerical_integration_uncertainty_percent(
        reference, specification.nominal_values()
    )
    unknown_count = sum(
        parameter.uncertainty_kind is UncertaintyKind.UNKNOWN
        for parameter in specification.parameters
    )
    confidence = classify_result_confidence(
        nominal_available=True,
        topology_supported=True,
        unknown_parameter_count=unknown_count,
        numerical_convergence_available=True,
        external_validation_status=specification.external_validation_status,
        model_form_status=specification.model_form_uncertainty_status,
    )
    warnings = tuple(dict.fromkeys(
        bound.warnings
        + monte_carlo.warnings
        + (
            "External AFPM electromagnetic validation coverage remains limited.",
            "The envelope quantifies parameter movement only; it is not the true model error range.",
        )
    ))
    accuracy = AccuracyEnvelopeResult(
        metric_name="back_emf_phase_fundamental_rms_v",
        nominal_value=sweep.nominal_output,
        unit="V",
        parameter_bound_min=bound.minimum_observed_prediction,
        parameter_bound_max=bound.maximum_observed_prediction,
        monte_carlo_available=True,
        p10=monte_carlo.p10,
        p50=monte_carlo.p50,
        p90=monte_carlo.p90,
        standard_deviation=monte_carlo.standard_deviation,
        dominant_uncertainty_parameters=sweep.ranked_parameters[:5],
        numerical_uncertainty=numerical,
        model_form_uncertainty_status=ModelFormUncertaintyStatus.UNQUANTIFIED,
        external_validation_status=specification.external_validation_status,
        confidence_level=confidence,
        warnings=warnings,
        assumptions=specification.assumptions,
    )
    return Phase7IUncertaintyDemonstration(specification, sweep, bound, monte_carlo, accuracy)


def render_phase7i_report(result: Phase7IUncertaintyDemonstration) -> str:
    envelope = result.accuracy_envelope
    monte_carlo = result.monte_carlo
    lines = [
        "# Phase 7I AFPM 反电势不确定性包络",
        "",
        "## 1. 边界声明",
        "",
        f"假设标签：`{result.specification.assumption_label}`。本报告仅回答显式参数变化会让模型预测移动多少。它不是实际误差保证，不包含 model-form error，也不是实验或 FEA 验证。",
        "",
        "## 2. 核心结果",
        "",
        f"- 指标：`{envelope.metric_name}`",
        f"- nominal prediction：{envelope.nominal_value:.6f} V",
        f"- parameter-bound envelope：{envelope.parameter_bound_min:.6f} - {envelope.parameter_bound_max:.6f} V",
        f"- Monte Carlo P10 / P50 / P90：{envelope.p10:.6f} / {envelope.p50:.6f} / {envelope.p90:.6f} V",
        f"- Monte Carlo standard deviation：{envelope.standard_deviation:.6f} V",
        f"- confidence：`{envelope.confidence_level.value}`",
        f"- model-form uncertainty：`{envelope.model_form_uncertainty_status.value}`",
        f"- external validation coverage：`{envelope.external_validation_status}`",
        "",
        "## 3. 参数定义",
        "",
        "| 参数 | Kind | Nominal | Bounds / PDF | Provenance |",
        "|---|---|---:|---|---|",
    ]
    for parameter in result.specification.parameters:
        if parameter.uncertainty_kind is UncertaintyKind.NORMAL:
            declaration = f"mean={parameter.mean:g}, sigma={parameter.standard_deviation:g}, bounds=[{parameter.lower_bound:g}, {parameter.upper_bound:g}]"
        elif parameter.has_parameter_bounds:
            declaration = f"[{parameter.lower_bound:g}, {parameter.upper_bound:g}]"
        else:
            declaration = "no variation / no declared distribution"
        lines.append(
            f"| {parameter.parameter_name} | {parameter.uncertainty_kind.value} | "
            f"{parameter.nominal_value:g} {parameter.unit} | {declaration} | {parameter.provenance} |"
        )
    lines.extend((
        "",
        "`RANGE` 不参与 Monte Carlo；`UNKNOWN` 保持 nominal 并产生警告。所有非 exact 数值均为项目演示假设，不是通用制造公差。",
        "",
        "## 4. One-at-a-time sensitivity",
        "",
        "| Rank | 参数 | Output low | Output nominal | Output high | Absolute range | Normalized sensitivity |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ))
    sensitivity_by_name = {
        item.parameter_name: item for item in result.deterministic_sweep.sensitivities
    }
    for rank, name in enumerate(result.deterministic_sweep.ranked_parameters, start=1):
        item = sensitivity_by_name[name]
        normalized = "UNAVAILABLE" if item.normalized_sensitivity is None else f"{item.normalized_sensitivity:.6f}"
        lines.append(
            f"| {rank} | {name} | {item.lower_output:.6f} | {item.nominal_output:.6f} | "
            f"{item.upper_output:.6f} | {item.absolute_output_range:.6f} | {normalized} |"
        )
    lines.extend((
        "",
        "## 5. Parameter-bound envelope",
        "",
        f"模式：`{result.bound_envelope.mode.value}`；评估 {result.bound_envelope.combinations_evaluated} 个 lower/nominal/upper 组合，"
        f"有效 {result.bound_envelope.valid_evaluation_count}，拒绝 {result.bound_envelope.rejected_evaluation_count}。",
        "",
        f"观察到的 minimum / maximum：{envelope.parameter_bound_min:.6f} / {envelope.parameter_bound_max:.6f} V。该区间必须称为 parameter-bound prediction envelope，不能称为 confidence interval。",
        "",
        "## 6. Monte Carlo",
        "",
        f"seed={monte_carlo.random_seed}，requested={monte_carlo.requested_sample_count}，valid={monte_carlo.valid_sample_count}，rejected={monte_carlo.failed_sample_count}。",
        "",
        f"P05/P10/P50/P90/P95 = {monte_carlo.p05:.6f} / {monte_carlo.p10:.6f} / {monte_carlo.p50:.6f} / {monte_carlo.p90:.6f} / {monte_carlo.p95:.6f} V。",
        "",
        "这些是 declared demonstration distributions 下的 sample percentiles，不是 90% 或 95% 真实置信区间。",
        "",
        "Correlation-based variance association（不是 Sobol index）：",
        "",
        "| 参数 | Normalized r-squared association |",
        "|---|---:|",
    ))
    for estimate in monte_carlo.variance_association_estimates:
        lines.append(f"| {estimate.parameter_name} | {estimate.normalized_r_squared_percent:.3f}% |")
    lines.extend((
        "",
        "## 7. Numerical 与 model-form uncertainty",
        "",
        f"100-to-500 radial-slice numerical difference：{envelope.numerical_uncertainty:.12f}%。当前常数 magnet coverage 下 midpoint radial integral 对线性半径项给出相同结果；这不代表物理模型无误差。",
        "",
        "Model-form uncertainty 保持 `UNQUANTIFIED`，未进入 sweep 或 Monte Carlo。未量化项包括 leakage、fringing、简化磁路、未建模 saturation、线圈/磁体三维几何和 topology abstraction。",
        "",
        "## 8. Confidence 与 readiness",
        "",
        f"结果为 `{envelope.confidence_level.value}`：拓扑和数值积分路径可执行，但外部 AFPM 电磁验证 coverage limited，存在 UNKNOWN 参数，且 model-form error 未量化。因此不允许 HIGH。",
        "",
        "框架的数据结构已可供未来 GUI 只读展示，但 Phase 7I 不接入 GUI。建议 Phase 7J 仅实现 optional user validation feedback，并继续把用户观测、参数 uncertainty 与 model-form discrepancy 分开。",
        "",
        "## 9. Phase 6A 对比",
        "",
        "Phase 6A 提供 production input 上的局部百分比工程敏感性；Phase 7I 新增显式 uncertainty kinds、非概率边界包络、带 seed 的 Monte Carlo、percentile、拒绝原因以及外部验证/模型形式 readiness 语境。两者都不写回 production，也不执行 calibration。",
        "",
        "## 10. Warnings",
        "",
    ))
    lines.extend(f"- {warning}" for warning in envelope.warnings)
    return "\n".join(lines) + "\n"


def write_phase7i_report(result: Phase7IUncertaintyDemonstration, path: Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_phase7i_report(result), encoding="utf-8")
    return destination
