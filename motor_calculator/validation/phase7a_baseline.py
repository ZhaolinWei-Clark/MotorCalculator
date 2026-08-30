"""Reproducible, read-only Phase 7A pre-calibration baseline."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from motor_calculator.motor_core.bldc_ke_kt_models import (
    calculate_bldc_average_electromagnetic_power_w,
    calculate_bldc_line_to_line_back_emf_rms_from_phase_flat_top_v,
    calculate_bldc_phase_back_emf_rms_from_flat_top_v,
    calculate_bldc_phase_current_rms_from_conduction_current,
)
from motor_calculator.motor_core.electrical_semantics import MotorControlMode
from motor_calculator.motor_core.pmsm_ke_kt_models import (
    calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed,
    derive_revised_pmsm_torque_constants_from_power_balance,
)

from .accuracy_metrics import AccuracyMetrics, compute_accuracy_metrics


class ValidationStatus(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    INTERNAL_ONLY = "INTERNAL_ONLY"


class BaselineOutcome(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    BLOCKED = "blocked"
    INTERNAL_PASS = "internal_pass"


@dataclass(frozen=True)
class TargetLock:
    model_track: str
    metric: str
    status: ValidationStatus
    reason: str


TARGET_LOCKS = (
    TargetLock("A/B", "back_emf_phase_peak_v", ValidationStatus.PARTIAL, "CREATOR provides the quantity, but radial-to-AFPM topology compatibility is absent."),
    TargetLock("A", "back_emf_phase_rms_v", ValidationStatus.INTERNAL_ONLY, "Only PMSM analytical semantics cases are directly usable."),
    TargetLock("A/C", "back_emf_line_rms_v", ValidationStatus.INTERNAL_ONLY, "Only PMSM/BLDC analytical waveform cases are directly usable."),
    TargetLock("A/C", "Ke", ValidationStatus.INTERNAL_ONLY, "Definitions and unit conversions are internally verified; no compatible external value is imported."),
    TargetLock("A/C", "Kt", ValidationStatus.INTERNAL_ONLY, "Power-balance derivations are internally verified; no compatible external value is imported."),
    TargetLock("A/B", "rated_torque_nm", ValidationStatus.PARTIAL, "CREATOR provides torque for a radial PMSM, not the AFPM production topology."),
    TargetLock("A/B", "phase_resistance_ohm", ValidationStatus.PARTIAL, "CREATOR provides phase resistance, but geometry and winding mapping are incompatible with Track B."),
    TargetLock("A", "inductance", ValidationStatus.PARTIAL, "CREATOR reports Ld/Lq, but the imported schema intentionally does not collapse them to phase inductance."),
    TargetLock("D", "steady-state current", ValidationStatus.INTERNAL_ONLY, "Dynamic equations have numerical checks but no external current trace."),
    TargetLock("D", "steady-state speed", ValidationStatus.INTERNAL_ONLY, "Solver convergence and torque balance are internal only."),
    TargetLock("D", "torque balance", ValidationStatus.INTERNAL_ONLY, "Mechanical equilibrium is checked analytically, not against measurement."),
    TargetLock("D", "startup response", ValidationStatus.BLOCKED, "No compatible voltage, load, inertia, and measured time-series dataset is imported."),
    TargetLock("D", "load-step response", ValidationStatus.BLOCKED, "No synchronized load-step and current/speed/torque trace is imported."),
    TargetLock("E", "copper_loss_w", ValidationStatus.INTERNAL_ONLY, "The algebraic loss monitor is tested without an external operating-point benchmark."),
    TargetLock("E", "iron_loss_w", ValidationStatus.BLOCKED, "No defensible source and matched operating point are available."),
    TargetLock("E", "efficiency", ValidationStatus.BLOCKED, "No matched input/output power operating point is imported."),
    TargetLock("E", "winding_temperature_c", ValidationStatus.BLOCKED, "No thermal history, cooling condition, and measurement-location dataset is imported."),
)


@dataclass(frozen=True)
class AccuracyBaselineRow:
    benchmark: str
    model_track: str
    metric: str
    operating_point: str
    unit: str
    metrics: AccuracyMetrics
    tolerance: str
    outcome: BaselineOutcome
    notes: str


@dataclass(frozen=True)
class Phase7ABaselineResult:
    rows: tuple[AccuracyBaselineRow, ...]
    target_locks: tuple[TargetLock, ...]

    @property
    def outcome_counts(self) -> dict[str, int]:
        counts = Counter(row.outcome.value for row in self.rows)
        return {key: counts.get(key, 0) for key in BaselineOutcome._value2member_map_}

    @property
    def target_status_counts(self) -> dict[str, int]:
        counts = Counter(target.status.value for target in self.target_locks)
        return {key: counts.get(key, 0) for key in ValidationStatus._value2member_map_}


def _repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def _internal_outcome(metrics: AccuracyMetrics) -> BaselineOutcome:
    if metrics.relative_error is None:
        return BaselineOutcome.WARNING
    return BaselineOutcome.INTERNAL_PASS if abs(metrics.relative_error) <= 1e-9 else BaselineOutcome.FAIL


def _internal_row(
    *, benchmark: str, model_track: str, metric: str, operating_point: str,
    prediction: float, reference: float, unit: str, notes: str,
) -> AccuracyBaselineRow:
    metrics = compute_accuracy_metrics(prediction, reference)
    return AccuracyBaselineRow(
        benchmark=benchmark,
        model_track=model_track,
        metric=metric,
        operating_point=operating_point,
        unit=unit,
        metrics=metrics,
        tolerance="absolute(relative error) <= 1e-9 (internal algebraic consistency)",
        outcome=_internal_outcome(metrics),
        notes=notes,
    )


def _creator_rows(repo_root: Path) -> list[AccuracyBaselineRow]:
    path = repo_root / "validation_data" / "imported" / "creator_pmsm_initial_record.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    topology = str(record["topology"])
    operating_point = "2000 rpm; source-specific conditions"
    rows: list[AccuracyBaselineRow] = []
    for metric_name, expected in record["expected_outputs"].items():
        reference = expected.get("value") if expected.get("status") in {"provided", "inferred"} else None
        reason = (
            f"Topology mismatch ({topology}); CREATOR radial PMSM is not routed through the AFPM production model."
            if reference is not None
            else f"Source field unavailable: {expected.get('notes', 'no source value') }"
        )
        rows.append(
            AccuracyBaselineRow(
                benchmark=record["validation_id"],
                model_track="A/B boundary",
                metric=metric_name,
                operating_point=operating_point,
                unit=expected.get("unit") or "-",
                metrics=compute_accuracy_metrics(None, reference),
                tolerance="not applied: comparison blocked",
                outcome=BaselineOutcome.BLOCKED,
                notes=reason,
            )
        )
    return rows


def _pmsm_reference_rows(repo_root: Path) -> list[AccuracyBaselineRow]:
    path = repo_root / "motor_calculator" / "tests" / "fixtures" / "pmsm_reference_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    rows: list[AccuracyBaselineRow] = []
    for case in cases:
        ke_values = calculate_revised_pmsm_back_emf_constants_from_phase_rms_and_angular_speed(
            back_emf_phase_rms_v=case["back_emf_phase_rms_v"],
            mechanical_speed_rpm=case["mechanical_speed_rpm"],
            mechanical_angular_speed_rad_s=case["mechanical_angular_speed_rad_s"],
            control_mode=MotorControlMode.PMSM_SINUSOIDAL,
        )
        kt_values = derive_revised_pmsm_torque_constants_from_power_balance(
            revised_back_emf_constant_phase_peak_v_per_rad_s=ke_values[0],
            revised_back_emf_constant_phase_rms_v_per_rad_s=ke_values[1],
            control_mode=MotorControlMode.PMSM_SINUSOIDAL,
        )
        operating_point = f"{case['mechanical_speed_rpm']:.12g} rpm"
        rows.extend((
            _internal_row(
                benchmark=case["case_id"], model_track="A", metric="Ke_line_rms_v_per_krpm",
                operating_point=operating_point, prediction=ke_values[3],
                reference=case["expected_ke_line_rms_v_per_krpm"], unit="V/krpm",
                notes="Internal analytical reference only; not external accuracy evidence.",
            ),
            _internal_row(
                benchmark=case["case_id"], model_track="A", metric="Kt_phase_rms_nm_per_a",
                operating_point=operating_point, prediction=kt_values[1],
                reference=case["expected_kt_phase_rms_nm_per_a"], unit="Nm/A",
                notes="Internal power-balance reference only; not external accuracy evidence.",
            ),
        ))
    return rows


def _bldc_reference_rows(repo_root: Path) -> list[AccuracyBaselineRow]:
    path = repo_root / "motor_calculator" / "tests" / "fixtures" / "bldc_reference_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    rows: list[AccuracyBaselineRow] = []
    for case in cases:
        emf = case["phase_flat_top_back_emf_v"]
        current = case["conduction_current_a"]
        mode = MotorControlMode.BLDC_120_DEGREE
        values = (
            ("phase_back_emf_rms_v", calculate_bldc_phase_back_emf_rms_from_flat_top_v(emf, mode), case["expected_phase_back_emf_rms_v"], "V"),
            ("line_back_emf_rms_v", calculate_bldc_line_to_line_back_emf_rms_from_phase_flat_top_v(emf, mode), case["expected_line_back_emf_rms_v"], "V"),
            ("phase_current_rms_a", calculate_bldc_phase_current_rms_from_conduction_current(current, mode), case["expected_phase_current_rms_a"], "A"),
            ("electromagnetic_power_w", calculate_bldc_average_electromagnetic_power_w(emf, current, mode), case["expected_average_electromagnetic_power_w"], "W"),
        )
        for metric, prediction, reference, unit in values:
            rows.append(_internal_row(
                benchmark=case["case_id"], model_track="C", metric=metric,
                operating_point=f"{case['mechanical_speed_rpm']:.12g} rpm",
                prediction=prediction, reference=reference, unit=unit,
                notes="Internal ideal 120-degree analytical reference only; not external accuracy evidence.",
            ))
    return rows


def build_phase7a_baseline(repo_root: Path | None = None) -> Phase7ABaselineResult:
    root = Path(repo_root) if repo_root is not None else _repo_root_from_module()
    rows = _creator_rows(root) + _pmsm_reference_rows(root) + _bldc_reference_rows(root)
    return Phase7ABaselineResult(rows=tuple(rows), target_locks=TARGET_LOCKS)


def _format_number(value: float | None) -> str:
    return "unavailable" if value is None else f"{value:.12g}"


def render_phase7a_report(result: Phase7ABaselineResult) -> str:
    external_rows = [row for row in result.rows if row.benchmark == "creator_pmsm_initial_record"]
    internal_rows = [row for row in result.rows if row.outcome is BaselineOutcome.INTERNAL_PASS]
    lines = [
        "# Phase 7A 预校准精度基线",
        "",
        "## 边界声明",
        "",
        "本报告只读取既有外部记录与分析夹具，不修改参数、公式、默认值、GUI 或 production calculation chain。",
        "CREATOR 为径向磁通 PMSM，禁止用其数值误差声称 AFPM 默认模型精度。内部分析用例只证明代数/语义一致性。",
        "",
        "## 基线结论",
        "",
        f"- 外部记录行：{len(external_rows)}；可直接比较：0；blocked：{len(external_rows)}。",
        f"- 内部一致性通过：{len(internal_rows)}；这些结果不属于外部 accuracy validation。",
        "- 当前没有可归因于模型误差的外部 tolerance failure；原因是缺少兼容 benchmark，而不是模型已通过精度验证。",
        "",
        "## 比较明细",
        "",
        "| benchmark | track | metric | operating point | predicted | reference | unit | absolute error | relative error % | tolerance | outcome | blocker / notes |",
        "|---|---|---|---|---:|---:|---|---:|---:|---|---|---|",
    ]
    for row in result.rows:
        relative_percent = None if row.metrics.relative_error is None else 100.0 * row.metrics.relative_error
        safe_notes = row.notes.replace("|", "/")
        lines.append(
            f"| {row.benchmark} | {row.model_track} | {row.metric} | {row.operating_point} | "
            f"{_format_number(row.metrics.prediction)} | {_format_number(row.metrics.reference)} | {row.unit} | "
            f"{_format_number(row.metrics.absolute_error)} | {_format_number(relative_percent)} | {row.tolerance} | "
            f"{row.outcome.value} | {safe_notes} |"
        )
    lines.extend((
        "",
        "## Target 状态计数",
        "",
        *(f"- {status}: {count}" for status, count in result.target_status_counts.items()),
        "",
        "## 禁止用途",
        "",
        "不得将本报告中的内部分析结果解释为实测精度，不得从 blocked 行推导校准值，也不得据此写回 production 参数。",
        "",
    ))
    return "\n".join(lines)


def run_phase7a_accuracy_baseline(
    *, repo_root: Path | None = None, report_path: Path | None = None, write_report: bool = True,
) -> Phase7ABaselineResult:
    root = Path(repo_root) if repo_root is not None else _repo_root_from_module()
    result = build_phase7a_baseline(root)
    if write_report:
        destination = report_path or root / "validation_data" / "reports" / "phase7a_accuracy_baseline_zh.md"
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_phase7a_report(result), encoding="utf-8")
    return result
