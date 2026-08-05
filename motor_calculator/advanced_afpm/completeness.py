"""Metric-specific completeness checks with no implicit substitutions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .source_adapter import AdvancedAFPMCase
from .topology import AFPMTopologyType


class AFPMTargetMetric(str, Enum):
    BACK_EMF = "back_emf"
    TORQUE = "torque"
    RESISTANCE = "resistance"
    INDUCTANCE = "inductance"
    EFFICIENCY = "efficiency"


class CompletenessStatus(str, Enum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class CompletenessResult:
    target_metric: AFPMTargetMetric
    status: CompletenessStatus
    missing_fields: tuple[str, ...]
    available_fields: tuple[str, ...]
    notes: tuple[str, ...]


class AFPMCompletenessGate:
    def evaluate(self, case: AdvancedAFPMCase, target_metric: AFPMTargetMetric | str) -> CompletenessResult:
        metric = AFPMTargetMetric(target_metric)
        if metric is AFPMTargetMetric.BACK_EMF:
            return self._back_emf(case)
        if metric is AFPMTargetMetric.INDUCTANCE:
            has_reference = case.inductance.scalar_phase_h is not None or (
                case.inductance.ld_h is not None and case.inductance.lq_h is not None
            )
            return self._unsupported_metric(metric, has_reference, "inductance_physics_path")
        reference_names = {
            AFPMTargetMetric.TORQUE: ("average_shaft_torque_nm", "torque_numeric_nm"),
            AFPMTargetMetric.RESISTANCE: ("phase_dc_resistance_ohm",),
            AFPMTargetMetric.EFFICIENCY: ("efficiency_percent",),
        }[metric]
        has_reference = any(
            field is not None and field.is_usable
            for field in (case.source_field(name) for name in reference_names)
        )
        physics = {
            AFPMTargetMetric.TORQUE: "torque_current_physics_path",
            AFPMTargetMetric.RESISTANCE: "resistance_geometry_and_temperature_path",
            AFPMTargetMetric.EFFICIENCY: "loss_and_power_boundary_path",
        }[metric]
        return self._unsupported_metric(metric, has_reference, physics)

    @staticmethod
    def _unsupported_metric(
        metric: AFPMTargetMetric,
        has_reference: bool,
        physics_path: str,
    ) -> CompletenessResult:
        missing = (physics_path,) if has_reference else ("external_reference", physics_path)
        return CompletenessResult(
            metric,
            CompletenessStatus.PARTIAL if has_reference else CompletenessStatus.BLOCKED,
            missing,
            ("external_reference",) if has_reference else (),
            ("Phase 7E implements only radial-slice back-EMF physics.",),
        )

    @staticmethod
    def _back_emf(case: AdvancedAFPMCase) -> CompletenessResult:
        network = case.winding_network
        effective_turns = (
            network.effective_series_turns_per_phase
            if network is not None
            else case.winding.turns_per_phase
        )
        winding_factor = (
            network.resolve_winding_factor().value
            if network is not None
            else case.winding.winding_factor
        )
        checks = {
            "topology": case.topology.topology_type is not AFPMTopologyType.UNKNOWN,
            "geometry.inner_radius_m": case.geometry.inner_radius_m is not None,
            "geometry.outer_radius_m": case.geometry.outer_radius_m is not None,
            "geometry.effective_nonmagnetic_gap_m": case.geometry.effective_nonmagnetic_gap_m is not None,
            "geometry.magnet_thickness_m": case.geometry.magnet_thickness_m is not None,
            "geometry.pole_pairs": case.geometry.pole_pairs is not None,
            "geometry.magnet_coverage": (
                case.geometry.magnet_arc_ratio is not None
                or bool(case.geometry.radius_dependent_magnet_profile)
            ),
            "material.remanence_t": case.remanence_t is not None,
            "material.magnet_relative_permeability": case.magnet_relative_permeability is not None,
            "winding_network.effective_series_turns_per_phase": effective_turns is not None,
            "winding_network.winding_factor": winding_factor is not None,
            "back_emf.semantics": case.back_emf_semantics is not None,
            "back_emf.external_reference": (
                case.back_emf_reference_field is not None
                and case.source_field(case.back_emf_reference_field) is not None
                and case.source_field(case.back_emf_reference_field).is_usable
            ),
        }
        if case.topology.topology_type is AFPMTopologyType.DSSR:
            checks["winding_network.stator_connection"] = (
                network is not None and network.stator_connection.value in {"series", "parallel"}
            )
        missing = tuple(name for name, present in checks.items() if not present)
        available = tuple(name for name, present in checks.items() if present)
        return CompletenessResult(
            AFPMTargetMetric.BACK_EMF,
            CompletenessStatus.READY if not missing else CompletenessStatus.BLOCKED,
            missing,
            available,
            ("No missing value is replaced by a project or production default.",),
        )
