"""Traceable Phase 7G benchmark evidence projected into the existing AFPM gate."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .completeness import AFPMCompletenessGate, AFPMTargetMetric, CompletenessResult
from .electrical import AFPMInductance, BackEMFScope, BackEMFSemantics, BackEMFValueKind, WaveformFamily
from .geometry import AFPMGeometry, RadialMagnetSample
from .source_adapter import AFPMFieldRecord, AFPMFieldStatus, AdvancedAFPMCase
from .topology import AFPMTopology, AFPMTopologyType
from .torque_semantics import TorqueBoundary, TorqueSemantics
from .winding import AFPMWinding, WindingType
from .winding_network import AFPMWindingNetwork, PhaseConnection, StatorConnection


QUALITY_DIMENSIONS = (
    "topology_compatibility",
    "geometry_completeness",
    "magnet_material_completeness",
    "winding_completeness",
    "operating_point_completeness",
    "back_emf_semantic_clarity",
    "experimental_provenance",
    "fea_provenance",
    "reproducibility",
    "license_accessibility",
)


@dataclass(frozen=True)
class BenchmarkProvenance:
    source_url: str
    publication: str
    page: str
    table: str | None
    figure: str | None
    equation: str | None
    location: str


@dataclass(frozen=True)
class BenchmarkEvidenceField:
    status: AFPMFieldStatus
    value: Any
    unit: str | None
    provenance: BenchmarkProvenance
    notes: str
    derivation: str | None = None

    @property
    def is_usable(self) -> bool:
        return self.status in {AFPMFieldStatus.SOURCE_PROVIDED, AFPMFieldStatus.SAFELY_DERIVED}


@dataclass(frozen=True)
class BenchmarkEvidencePackage:
    source_id: str
    source_title: str
    source_url: str
    source_family: Mapping[str, Any]
    quality_scores: Mapping[str, int]
    fields: Mapping[str, BenchmarkEvidenceField]


def load_benchmark_evidence(path: Path) -> BenchmarkEvidencePackage:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("phase") != "7G":
        raise ValueError("benchmark evidence package must declare Phase 7G")
    scores = raw["quality_scores"]
    if set(scores) != set(QUALITY_DIMENSIONS):
        raise ValueError("quality scores must contain the ten locked dimensions")
    if any(not isinstance(value, int) or not 0 <= value <= 5 for value in scores.values()):
        raise ValueError("quality scores must be integers from 0 through 5")

    fields = {}
    for name, field in raw["fields"].items():
        status = AFPMFieldStatus(field["status"])
        value = field.get("value")
        if status in {AFPMFieldStatus.UNAVAILABLE, AFPMFieldStatus.AMBIGUOUS} and value is not None:
            raise ValueError(f"non-usable evidence field {name} must have a null value")
        if status in {AFPMFieldStatus.SOURCE_PROVIDED, AFPMFieldStatus.SAFELY_DERIVED} and value is None:
            raise ValueError(f"usable evidence field {name} requires a value")
        derivation = field.get("derivation")
        if status is AFPMFieldStatus.SAFELY_DERIVED and not derivation:
            raise ValueError(f"safely derived evidence field {name} requires derivation")
        provenance = field["provenance"]
        fields[name] = BenchmarkEvidenceField(
            status=status,
            value=value,
            unit=field.get("unit"),
            provenance=BenchmarkProvenance(
                source_url=provenance["source_url"],
                publication=provenance["publication"],
                page=provenance["page"],
                table=provenance["table"],
                figure=provenance["figure"],
                equation=provenance["equation"],
                location=provenance["location"],
            ),
            notes=field.get("notes", ""),
            derivation=derivation,
        )
    return BenchmarkEvidencePackage(
        source_id=raw["source_id"],
        source_title=raw["source_title"],
        source_url=raw["source_url"],
        source_family=MappingProxyType(raw["source_family"]),
        quality_scores=MappingProxyType(dict(scores)),
        fields=MappingProxyType(fields),
    )


def _value(package: BenchmarkEvidencePackage, name: str) -> Any | None:
    field = package.fields.get(name)
    return field.value if field is not None and field.is_usable else None


def _enum(enum_type, value: Any, default):
    try:
        return enum_type(value)
    except (TypeError, ValueError):
        return default


def project_benchmark_case(package: BenchmarkEvidencePackage) -> AdvancedAFPMCase:
    """Project source evidence without substituting defaults for missing physics."""
    topology_type = _enum(AFPMTopologyType, _value(package, "topology_type"), AFPMTopologyType.UNKNOWN)
    stator_count = int(_value(package, "stator_count") or 0)
    rotor_count = int(_value(package, "rotor_count") or 0)
    active_air_gap_count = int(_value(package, "active_air_gap_count") or 0)
    topology = AFPMTopology(
        topology_type,
        stator_count,
        rotor_count,
        active_air_gap_count,
        str(_value(package, "winding_location") or "unknown"),
        str(_value(package, "magnet_location") or "unknown"),
    )

    profile_value = _value(package, "magnet_profile_samples")
    profile = None
    if profile_value:
        profile = tuple(
            RadialMagnetSample(
                float(item["radius_m"]),
                float(item["local_magnet_arc_ratio"]),
                item.get("local_magnet_width_m"),
            )
            for item in profile_value
        )
    geometry = AFPMGeometry(
        inner_radius_m=_value(package, "inner_radius_m"),
        outer_radius_m=_value(package, "outer_radius_m"),
        air_gap_m=_value(package, "physical_air_gap_m"),
        magnet_thickness_m=_value(package, "magnet_thickness_m"),
        pole_pairs=_value(package, "pole_pairs"),
        magnet_arc_ratio=_value(package, "magnet_arc_ratio"),
        radius_dependent_magnet_profile=profile,
        stator_count=stator_count,
        rotor_count=rotor_count,
        effective_nonmagnetic_gap_m=_value(package, "effective_nonmagnetic_gap_m"),
    )

    winding_type = _enum(WindingType, _value(package, "winding_type"), WindingType.UNKNOWN)
    network = AFPMWindingNetwork(
        turns_per_coil=_value(package, "turns_per_coil"),
        coils_per_phase=_value(package, "coils_per_phase"),
        series_coils_per_branch=_value(package, "series_coils_per_branch"),
        parallel_branches=_value(package, "parallel_branches"),
        number_of_stators=stator_count,
        stator_connection=_enum(StatorConnection, _value(package, "stator_connection"), StatorConnection.UNKNOWN),
        phase_connection=_enum(PhaseConnection, _value(package, "phase_connection"), PhaseConnection.UNKNOWN),
        winding_type=winding_type,
        winding_factor=_value(package, "winding_factor"),
        pitch_factor=_value(package, "pitch_factor"),
        distribution_factor=_value(package, "distribution_factor"),
        winding_type_description=_value(package, "winding_type_description"),
    )
    winding = AFPMWinding(
        turns_per_coil=network.turns_per_coil,
        coils_per_phase=network.coils_per_phase,
        turns_per_phase=network.effective_series_turns_per_phase,
        parallel_branches=network.parallel_branches,
        connection=_value(package, "phase_connection"),
        winding_factor=network.resolve_winding_factor().value,
        pitch_factor=network.pitch_factor,
        distribution_factor=network.distribution_factor,
        winding_type=winding_type,
        stator_interconnection=_value(package, "stator_connection"),
    )

    semantics = None
    speed = _value(package, "speed_rpm")
    scope = _value(package, "back_emf_scope")
    value_kind = _value(package, "back_emf_value_kind")
    waveform = _value(package, "waveform_family")
    if None not in (speed, scope, value_kind, waveform):
        semantics = BackEMFSemantics(
            _enum(BackEMFScope, scope, BackEMFScope.PHASE),
            _enum(BackEMFValueKind, value_kind, BackEMFValueKind.WAVEFORM),
            _enum(WaveformFamily, waveform, WaveformFamily.ARBITRARY),
            float(speed),
            temperature_c=_value(package, "operating_temperature_c"),
            source_native_unit=package.fields["back_emf_reference_v"].unit,
        )
    reference_field = package.fields.get("back_emf_reference_v")
    reference_name = "back_emf_reference_v" if reference_field is not None and reference_field.is_usable else None
    source_fields = MappingProxyType({
        name: AFPMFieldRecord(
            status=field.status,
            value=field.value,
            unit=field.unit,
            source_url=field.provenance.source_url,
            page=field.provenance.page,
            location=field.provenance.location,
            note=field.notes,
            derivation=field.derivation,
        )
        for name, field in package.fields.items()
    })
    return AdvancedAFPMCase(
        case_id=f"phase7g_{package.source_id}",
        source_id=package.source_id,
        source_title=package.source_title,
        source_url=package.source_url,
        topology=topology,
        geometry=geometry,
        winding=winding,
        winding_network=network,
        back_emf_semantics=semantics,
        inductance=AFPMInductance(),
        torque_semantics=TorqueSemantics(TorqueBoundary.UNKNOWN),
        remanence_t=_value(package, "remanence_t"),
        magnet_relative_permeability=_value(package, "magnet_relative_permeability"),
        back_emf_reference_field=reference_name,
        source_fields=source_fields,
        recovered_fields=MappingProxyType({}),
        field_lineage=MappingProxyType({name: (name,) for name in package.fields}),
        adapter_notes=(
            "Phase 7G evidence projection; missing values remain None.",
            "No project defaults or generic material properties are used.",
        ),
    )


def evaluate_benchmark_evidence(package: BenchmarkEvidencePackage) -> CompletenessResult:
    return AFPMCompletenessGate().evaluate(project_benchmark_case(package), AFPMTargetMetric.BACK_EMF)
