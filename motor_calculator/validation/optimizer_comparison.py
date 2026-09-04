"""Phase 9B Batch C2: read-only optimizer comparison between voltage bases.

The legacy `run_optimization` in `PMDC_Calculator_claude204.py` is NOT modified
or deleted. This module mirrors its scoring rule exactly and evaluates it twice,
once against the legacy required voltage and once against the corrected
single-basis value, so the two candidate paths can be compared before any
promotion decision.

Both paths use the same same-basis inverter envelope `Vdc / sqrt(2)`; the only
difference is which required-voltage quantity is compared against it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

from motor_calculator.motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params

from .design_feasibility import evaluate_design_feasibility, same_basis_available_line_rms_v


# Mirrors PMDC_Calculator_claude204.run_optimization exactly.
OPTIMIZER_TURNS_RANGE = range(15, 120, 3)
OPTIMIZER_TARGET_UTILISATION = 0.85
OPTIMIZER_TARGET_CURRENT_DENSITY = 5.5
OPTIMIZER_MAX_PARALLEL_PATHS = 10
OPTIMIZER_VOLTAGE_PENALTY = 10000.0
OPTIMIZER_SLOT_PENALTY = 5000.0
OPTIMIZER_CURRENT_DENSITY_SEVERE_PENALTY = 2000.0
OPTIMIZER_CURRENT_DENSITY_HIGH_PENALTY = 500.0
OPTIMIZER_EFFICIENCY_WEIGHT = 10.0
OPTIMIZER_VOLTAGE_UTILISATION_WEIGHT = 2.0
OPTIMIZER_RIPPLE_WEIGHT = 10.0

LEGACY_VOLTAGE_PATH = "legacy_required_voltage"
CORRECTED_VOLTAGE_PATH = "corrected_required_voltage"


@dataclass(frozen=True)
class OptimizerCandidate:
    turns: int
    parallel_paths: int
    required_voltage_v: float
    voltage_margin_percent: float
    current_density_a_per_mm2: float
    slot_occupancy: float | None
    efficiency_percent: float
    torque_ripple_percent: float
    score: float
    accepted: bool

    @property
    def rank_key(self) -> float:
        return -self.score


@dataclass(frozen=True)
class OptimizerPathResult:
    path: str
    candidates: tuple[OptimizerCandidate, ...]
    available_voltage_line_rms_v: float

    @property
    def accepted(self) -> tuple[OptimizerCandidate, ...]:
        return tuple(item for item in self.candidates if item.accepted)

    @property
    def rejected(self) -> tuple[OptimizerCandidate, ...]:
        return tuple(item for item in self.candidates if not item.accepted)

    @property
    def ranking(self) -> tuple[int, ...]:
        return tuple(
            item.turns for item in sorted(self.candidates, key=lambda entry: entry.rank_key)
        )

    @property
    def best(self) -> OptimizerCandidate | None:
        return min(self.candidates, key=lambda entry: entry.rank_key, default=None)


@dataclass(frozen=True)
class OptimizerComparison:
    legacy: OptimizerPathResult
    corrected: OptimizerPathResult

    @property
    def accepted_only_by_legacy(self) -> tuple[int, ...]:
        legacy_turns = {item.turns for item in self.legacy.accepted}
        corrected_turns = {item.turns for item in self.corrected.accepted}
        return tuple(sorted(legacy_turns - corrected_turns))

    @property
    def accepted_only_by_corrected(self) -> tuple[int, ...]:
        legacy_turns = {item.turns for item in self.legacy.accepted}
        corrected_turns = {item.turns for item in self.corrected.accepted}
        return tuple(sorted(corrected_turns - legacy_turns))

    @property
    def ranking_changed(self) -> bool:
        return self.legacy.ranking != self.corrected.ranking

    @property
    def recommended_turns_changed(self) -> bool:
        legacy_best = self.legacy.best
        corrected_best = self.corrected.best
        if legacy_best is None or corrected_best is None:
            return legacy_best is not corrected_best
        return legacy_best.turns != corrected_best.turns


def _required_voltage(result, path: str) -> float | None:
    if path == LEGACY_VOLTAGE_PATH:
        return float(result.performance.required_voltage_v)
    corrected = result.performance.required_voltage_line_rms_corrected_v
    return None if corrected is None else float(corrected)


def evaluate_optimizer_path(
    baseline_parameters: Mapping[str, Any], path: str
) -> OptimizerPathResult:
    """Replay the legacy optimizer scoring against one voltage basis."""

    if path not in {LEGACY_VOLTAGE_PATH, CORRECTED_VOLTAGE_PATH}:
        raise ValueError(f"Unsupported optimizer voltage path: {path!r}")

    baseline = dict(baseline_parameters)
    available = same_basis_available_line_rms_v(baseline["V_dc"])
    target_voltage = available * OPTIMIZER_TARGET_UTILISATION
    fill_limit = float(baseline["fill_limit"])
    conductor_area_mm2 = math.pi * (float(baseline["d_wire"]) / 2.0) ** 2

    candidates: list[OptimizerCandidate] = []
    for turns in OPTIMIZER_TURNS_RANGE:
        probe = dict(baseline)
        probe["N_ph_turns"] = turns
        probe["n_parallel"] = 1
        try:
            parsed_probe = parse_legacy_gui_params(probe)
            probe_result = LegacyGuiMotorModelBridge(parsed_probe).run_full_analysis()
        except Exception:
            continue

        estimated_current = float(probe_result.performance.phase_current_rms_a)
        parallel_paths = max(
            1,
            round(
                estimated_current / (OPTIMIZER_TARGET_CURRENT_DENSITY * conductor_area_mm2)
            ),
        )
        parallel_paths = min(parallel_paths, OPTIMIZER_MAX_PARALLEL_PATHS)

        candidate_inputs = dict(probe)
        candidate_inputs["n_parallel"] = parallel_paths
        try:
            parsed = parse_legacy_gui_params(candidate_inputs)
            result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
        except Exception:
            continue

        required = _required_voltage(result, path)
        if required is None:
            continue
        assessment = evaluate_design_feasibility(parsed, result)
        current_density = float(assessment.current_density_a_per_mm2)
        occupancy = assessment.slot_fill_factor
        margin = (available - required) / available * 100.0

        score = 0.0
        accepted = required <= available
        if not accepted:
            score -= OPTIMIZER_VOLTAGE_PENALTY
        if occupancy is not None and occupancy > fill_limit:
            score -= OPTIMIZER_SLOT_PENALTY
        if current_density > 8.0:
            score -= OPTIMIZER_CURRENT_DENSITY_SEVERE_PENALTY
        elif current_density > 6.0:
            score -= OPTIMIZER_CURRENT_DENSITY_HIGH_PENALTY
        score += float(result.performance.efficiency_percent) * OPTIMIZER_EFFICIENCY_WEIGHT
        score -= abs(target_voltage - required) * OPTIMIZER_VOLTAGE_UTILISATION_WEIGHT
        score -= (
            float(result.performance.torque_ripple_percent) * OPTIMIZER_RIPPLE_WEIGHT
        )

        candidates.append(
            OptimizerCandidate(
                turns=turns,
                parallel_paths=parallel_paths,
                required_voltage_v=required,
                voltage_margin_percent=margin,
                current_density_a_per_mm2=current_density,
                slot_occupancy=occupancy,
                efficiency_percent=float(result.performance.efficiency_percent),
                torque_ripple_percent=float(result.performance.torque_ripple_percent),
                score=score,
                accepted=accepted,
            )
        )

    return OptimizerPathResult(
        path=path,
        candidates=tuple(candidates),
        available_voltage_line_rms_v=available,
    )


def compare_optimizer_paths(
    baseline_parameters: Mapping[str, Any],
) -> OptimizerComparison:
    """Evaluate both voltage bases without touching the legacy optimizer."""

    return OptimizerComparison(
        legacy=evaluate_optimizer_path(baseline_parameters, LEGACY_VOLTAGE_PATH),
        corrected=evaluate_optimizer_path(baseline_parameters, CORRECTED_VOLTAGE_PATH),
    )


def format_optimizer_comparison_zh(comparison: OptimizerComparison) -> tuple[str, ...]:
    """Human-readable comparison report lines."""

    legacy_best = comparison.legacy.best
    corrected_best = comparison.corrected.best
    lines = [
        f"同基可用线电压 RMS: {comparison.legacy.available_voltage_line_rms_v:.4f} V",
        f"legacy 路径   : 接受 {len(comparison.legacy.accepted)} / 拒绝 {len(comparison.legacy.rejected)}",
        f"修正路径      : 接受 {len(comparison.corrected.accepted)} / 拒绝 {len(comparison.corrected.rejected)}",
        f"仅 legacy 接受的匝数: {comparison.accepted_only_by_legacy}",
        f"仅修正接受的匝数    : {comparison.accepted_only_by_corrected}",
        f"排序是否变化        : {comparison.ranking_changed}",
        f"推荐匝数是否变化    : {comparison.recommended_turns_changed}",
    ]
    for label, best in (("legacy", legacy_best), ("修正", corrected_best)):
        if best is None:
            lines.append(f"{label} 推荐: 无可行候选")
            continue
        lines.append(
            f"{label} 推荐: N={best.turns} n_par={best.parallel_paths} "
            f"V_req={best.required_voltage_v:.4f} V 裕量={best.voltage_margin_percent:.4f} % "
            f"J={best.current_density_a_per_mm2:.4f} A/mm² "
            f"槽占比={best.slot_occupancy if best.slot_occupancy is None else round(best.slot_occupancy, 4)} "
            f"效率={best.efficiency_percent:.4f} % 可行={best.accepted}"
        )
    return tuple(lines)
