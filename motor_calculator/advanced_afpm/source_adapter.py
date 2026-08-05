"""Adapters from Phase 7C records into immutable advanced AFPM cases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from validation.reconstructed_cases import ReconstructedAFPMCase, load_reconstructed_case

from .electrical import (
    AFPMInductance,
    BackEMFScope,
    BackEMFSemantics,
    BackEMFValueKind,
    WaveformFamily,
)
from .geometry import AFPMGeometry
from .topology import AFPMTopology, AFPMTopologyType
from .torque_semantics import TorqueBoundary, TorqueSemantics
from .winding import AFPMWinding, WindingType


class AFPMFieldStatus(str, Enum):
    SOURCE_PROVIDED = "source_provided"
    SAFELY_DERIVED = "safely_derived"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class AFPMFieldRecord:
    status: AFPMFieldStatus
    value: Any
    unit: str | None
    source_url: str
    page: str
    location: str
    note: str
    derivation: str | None = None

    @property
    def is_usable(self) -> bool:
        return self.status in {AFPMFieldStatus.SOURCE_PROVIDED, AFPMFieldStatus.SAFELY_DERIVED}


@dataclass(frozen=True)
class AdvancedAFPMCase:
    case_id: str
    source_id: str
    source_title: str
    source_url: str
    topology: AFPMTopology
    geometry: AFPMGeometry
    winding: AFPMWinding
    back_emf_semantics: BackEMFSemantics | None
    inductance: AFPMInductance
    torque_semantics: TorqueSemantics
    remanence_t: float | None
    magnet_relative_permeability: float | None
    back_emf_reference_field: str | None
    source_fields: Mapping[str, AFPMFieldRecord]
    field_lineage: Mapping[str, tuple[str, ...]]
    adapter_notes: tuple[str, ...]

    def source_field(self, name: str) -> AFPMFieldRecord | None:
        return self.source_fields.get(name)


def _usable(case: ReconstructedAFPMCase, name: str) -> Any | None:
    field = case.fields.get(name)
    return field.value if field is not None and field.is_usable else None


def _copy_fields(case: ReconstructedAFPMCase) -> Mapping[str, AFPMFieldRecord]:
    copied = {
        name: AFPMFieldRecord(
            status=AFPMFieldStatus(field.status.value),
            value=field.value,
            unit=field.unit,
            source_url=field.provenance.source_url,
            page=field.provenance.page,
            location=field.provenance.location,
            note=field.provenance.note,
            derivation=field.derivation,
        )
        for name, field in case.fields.items()
    }
    return MappingProxyType(copied)


def _topology(case: ReconstructedAFPMCase) -> AFPMTopology:
    if case.source_id in {"price_2009_coreless_afpm_generator", "hosseini_2008_coreless_afpm_generator"}:
        return AFPMTopology(
            AFPMTopologyType.SSDR, 1, 2, 2,
            "central stator winding", "inward faces of both rotors",
        )
    if case.source_id in {"parviainen_2005_afpm_prototype", "abdelli_2026_dssr_afpm"}:
        return AFPMTopology(
            AFPMTopologyType.DSSR, 2, 1, 2,
            "one winding system on each outer stator", "both faces of central rotor",
        )
    return AFPMTopology(AFPMTopologyType.UNKNOWN, 0, 0, 0, "unknown", "unknown")


def _speed(case: ReconstructedAFPMCase) -> float | None:
    for name in (
        "mechanical_speed_rpm",
        "mechanical_speed_rpm_back_emf",
        "mechanical_speed_rpm_validation",
    ):
        value = _usable(case, name)
        if value is not None:
            return float(value)
    return None


def _geometry(case: ReconstructedAFPMCase, topology: AFPMTopology) -> AFPMGeometry:
    outer_diameter = _usable(case, "outer_diameter_m")
    inner_diameter = _usable(case, "inner_diameter_m")
    air_gap = next(
        (value for value in (
            _usable(case, "air_gap_per_side_m"),
            _usable(case, "air_gap_per_stator_m"),
            _usable(case, "air_gap_m"),
        ) if value is not None),
        None,
    )
    effective_gap = _usable(case, "effective_air_gap_length_m")
    if case.source_id == "hosseini_2008_coreless_afpm_generator":
        coil_height = _usable(case, "coil_height_m")
        if coil_height is not None and air_gap is not None:
            effective_gap = float(coil_height) + 2.0 * float(air_gap)
    return AFPMGeometry(
        inner_radius_m=None if inner_diameter is None else float(inner_diameter) / 2.0,
        outer_radius_m=None if outer_diameter is None else float(outer_diameter) / 2.0,
        air_gap_m=None if air_gap is None else float(air_gap),
        magnet_thickness_m=_usable(case, "magnet_thickness_m"),
        pole_pairs=_usable(case, "pole_pairs"),
        magnet_arc_ratio=_usable(case, "pole_arc_coefficient"),
        radius_dependent_magnet_profile=None,
        stator_count=topology.stator_count,
        rotor_count=topology.rotor_count,
        effective_nonmagnetic_gap_m=effective_gap,
    )


def _winding(case: ReconstructedAFPMCase) -> AFPMWinding:
    turns_per_coil = next((value for value in (
        _usable(case, "turns_per_coil"),
        _usable(case, "prototype_turns_per_coil"),
    ) if value is not None), None)
    turns_per_phase = next((value for value in (
        _usable(case, "turns_per_phase"),
        _usable(case, "turns_per_phase_per_stator"),
    ) if value is not None), None)
    connection = next((value for value in (
        _usable(case, "winding_connection"),
        _usable(case, "winding_connection_per_stator"),
    ) if value is not None), None)
    parallel_branches = None
    stator_interconnection = _usable(case, "stator_interconnection")
    if case.source_id == "parviainen_2005_afpm_prototype":
        parallel_branches = 2
    coils_per_phase = 3 if case.source_id == "price_2009_coreless_afpm_generator" else None
    return AFPMWinding(
        turns_per_coil=turns_per_coil,
        coils_per_phase=coils_per_phase,
        turns_per_phase=turns_per_phase,
        parallel_branches=parallel_branches,
        connection=connection,
        winding_factor=_usable(case, "winding_factor"),
        pitch_factor=None,
        distribution_factor=None,
        winding_type=WindingType.UNKNOWN,
        stator_interconnection=stator_interconnection,
    )


def _back_emf(case: ReconstructedAFPMCase) -> tuple[BackEMFSemantics | None, str | None]:
    speed = _speed(case)
    if speed is None:
        return None, None
    if case.source_id == "parviainen_2005_afpm_prototype":
        return BackEMFSemantics(
            BackEMFScope.PHASE, BackEMFValueKind.RMS, WaveformFamily.FLATTENED,
            speed, source_native_unit="V phase RMS",
        ), "back_emf_phase_rms_v"
    if case.source_id == "price_2009_coreless_afpm_generator":
        return BackEMFSemantics(
            BackEMFScope.PHASE, BackEMFValueKind.PEAK, WaveformFamily.SINUSOIDAL,
            speed, source_native_unit="V phase peak",
        ), "back_emf_phase_peak_v"
    if case.source_id == "hosseini_2008_coreless_afpm_generator":
        return BackEMFSemantics(
            BackEMFScope.PHASE, BackEMFValueKind.WAVEFORM, WaveformFamily.ARBITRARY,
            speed, source_native_unit="V phase peak-to-peak",
        ), "back_emf_no_load_peak_to_peak_v"
    if case.source_id == "abdelli_2026_dssr_afpm":
        return BackEMFSemantics(
            BackEMFScope.PHASE, BackEMFValueKind.WAVEFORM, WaveformFamily.ARBITRARY,
            speed, source_native_unit="graph only",
        ), "back_emf_numeric_v"
    return None, None


def _inductance(case: ReconstructedAFPMCase) -> AFPMInductance:
    return AFPMInductance(
        ld_h=next((value for value in (
            _usable(case, "Ld_h"), _usable(case, "Ld_from_Xsd_h"),
        ) if value is not None), None),
        lq_h=next((value for value in (
            _usable(case, "Lq_h"), _usable(case, "Lq_from_Xsq_h"),
        ) if value is not None), None),
    )


def _field_lineage(case: ReconstructedAFPMCase) -> Mapping[str, tuple[str, ...]]:
    speed_field = next((name for name in (
        "mechanical_speed_rpm", "mechanical_speed_rpm_back_emf", "mechanical_speed_rpm_validation",
    ) if _usable(case, name) is not None), "$topology")
    air_gap_field = next((name for name in (
        "air_gap_per_side_m", "air_gap_per_stator_m", "air_gap_m",
    ) if _usable(case, name) is not None), "$topology")
    effective_gap_sources: tuple[str, ...] = ()
    if _usable(case, "effective_air_gap_length_m") is not None:
        effective_gap_sources = ("effective_air_gap_length_m",)
    elif case.source_id == "hosseini_2008_coreless_afpm_generator":
        effective_gap_sources = ("coil_height_m", "air_gap_per_side_m")
    turns_field = next((name for name in (
        "turns_per_phase", "turns_per_phase_per_stator",
    ) if _usable(case, name) is not None), "$topology")
    connection_field = next((name for name in (
        "winding_connection", "winding_connection_per_stator",
    ) if _usable(case, name) is not None), "$topology")
    reference_field = _back_emf(case)[1]
    lineage = {
        "topology": ("$topology",),
        "geometry.inner_radius_m": ("inner_diameter_m",),
        "geometry.outer_radius_m": ("outer_diameter_m",),
        "geometry.air_gap_m": (air_gap_field,),
        "geometry.effective_nonmagnetic_gap_m": effective_gap_sources,
        "geometry.magnet_thickness_m": ("magnet_thickness_m",),
        "geometry.pole_pairs": ("pole_pairs",),
        "geometry.magnet_arc_ratio": ("pole_arc_coefficient",),
        "winding.turns_per_phase": (turns_field,),
        "winding.connection": (connection_field,),
        "winding.winding_factor": ("winding_factor",),
        "back_emf.semantics": (speed_field,) + (() if reference_field is None else (reference_field,)),
        "material.remanence_t": ("remanence_t",),
        "material.magnet_relative_permeability": (
            ("magnet_relative_permeability",)
            if "magnet_relative_permeability" in case.fields
            else ()
        ),
        "inductance.ld_h": tuple(name for name in ("Ld_h", "Ld_from_Xsd_h") if _usable(case, name) is not None),
        "inductance.lq_h": tuple(name for name in ("Lq_h", "Lq_from_Xsq_h") if _usable(case, name) is not None),
        "torque.source_boundary": (
            ("average_shaft_torque_nm",)
            if case.source_id == "price_2009_coreless_afpm_generator"
            else ("$topology",)
        ),
    }
    return MappingProxyType(lineage)


def adapt_reconstructed_case(case: ReconstructedAFPMCase) -> AdvancedAFPMCase:
    topology = _topology(case)
    semantics, reference_field = _back_emf(case)
    torque_boundary = (
        TorqueBoundary.SHAFT
        if case.source_id == "price_2009_coreless_afpm_generator"
        else TorqueBoundary.UNKNOWN
    )
    return AdvancedAFPMCase(
        case_id=case.case_id,
        source_id=case.source_id,
        source_title=case.source_title,
        source_url=case.source_url,
        topology=topology,
        geometry=_geometry(case, topology),
        winding=_winding(case),
        back_emf_semantics=semantics,
        inductance=_inductance(case),
        torque_semantics=TorqueSemantics(torque_boundary),
        remanence_t=_usable(case, "remanence_t"),
        magnet_relative_permeability=_usable(case, "magnet_relative_permeability"),
        back_emf_reference_field=reference_field,
        source_fields=_copy_fields(case),
        field_lineage=_field_lineage(case),
        adapter_notes=(
            "No production defaults are applied.",
            "Radius conversion uses source diameter divided by two.",
            "No scalar magnet coverage is inferred from a shape description.",
        ),
    )


def load_advanced_afpm_cases(case_directory: Path) -> tuple[AdvancedAFPMCase, ...]:
    return tuple(
        adapt_reconstructed_case(load_reconstructed_case(path))
        for path in sorted(Path(case_directory).glob("*_case.json"))
    )
