import csv
import hashlib
import math
from dataclasses import asdict
from pathlib import Path

import pytest

from motor_calculator.validation.fea_import import (
    ExternalFEAImportAdapter,
    FEAImportedMeshMetadata,
    analyze_periodic_waveform,
    sha256_file,
)
from motor_calculator.validation.fea_reference import (
    EvidenceClassification,
    FEADimensionality,
    FEAExecutionStatus,
    FEAFidelityTier,
    FEAMeshConvergencePoint,
    FEASolverMetadata,
    assess_mesh_convergence,
    load_fea_reference_definition,
)


ROOT = Path(__file__).resolve().parents[2]
REFERENCE_PATH = ROOT / "validation_data" / "fea_reference" / "phase7h_controlled_ssdr_machine.json"


def _metadata() -> FEASolverMetadata:
    return FEASolverMetadata(
        solver="ANSYS Maxwell 3D external",
        solver_version="2025 R2",
        model_version="phase7h-controlled-ssdr-v1",
        dimensionality=FEADimensionality.THREE_D,
        fidelity_tier=FEAFidelityTier.FEA_TIER_1,
        automation_path="external solve and CSV export",
    )


def _mesh_metadata() -> FEAImportedMeshMetadata:
    return FEAImportedMeshMetadata(
        mesh_name="fine",
        element_count=120000,
        node_count=25000,
        minimum_element_quality=0.31,
        solver_mesh_notes="3D tetrahedral mesh with local air-gap refinement",
    )


def _reference():
    return load_fea_reference_definition(REFERENCE_PATH)


def _write_sine_csv(path: Path, count: int = 72) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            (
                "rotor_angle_deg",
                "time_s",
                "flux_linkage_phase_a_wb_turn",
                "back_emf_phase_a_v",
                "torque_nm",
            )
        )
        for index in range(count):
            angle = 72.0 * index / count
            phase = 2.0 * math.pi * index / count
            writer.writerow((angle, 0.012 * index / count, 0.02 * math.cos(phase), 10.0 * math.sin(phase), ""))


def test_controlled_fea_reference_schema_is_fully_specified_and_blocked():
    reference = load_fea_reference_definition(REFERENCE_PATH)
    assert reference.execution_status is FEAExecutionStatus.BLOCKED_BY_SOLVER_AVAILABILITY
    assert reference.provenance.reference_label == "CONTROLLED_FEA_REFERENCE"
    assert reference.geometry.topology == "single_stator_double_rotor_coreless"
    assert reference.winding.effective_series_turns_per_phase == 100
    assert reference.winding.phase_assignment_by_coil[:6] == ("A+", "C-", "B+", "A-", "C+", "B-")
    assert reference.winding.analytical_projection_winding_factor == pytest.approx(0.9330127019)
    assert reference.materials.ferromagnetic_core_present is False
    assert len(reference.mesh_plan.levels) == 3


def test_evidence_classifications_remain_distinct():
    assert len({classification.value for classification in EvidenceClassification}) == 4
    assert EvidenceClassification.INDEPENDENT_FEA_REFERENCE is not EvidenceClassification.EXPERIMENTAL_MEASUREMENT


def test_reference_modules_do_not_reuse_analytical_afpm_implementation():
    validation_dir = ROOT / "motor_calculator" / "validation"
    source = "\n".join(
        (validation_dir / name).read_text(encoding="utf-8")
        for name in ("fea_reference.py", "fea_import.py")
    )
    assert "radial_slice_back_emf" not in source
    assert "advanced_afpm" not in source
    assert "motor_core.calculations" not in source


def test_waveform_rms_peak_and_fundamental_are_calculated_from_samples():
    values = tuple(10.0 * math.sin(2.0 * math.pi * index / 360) for index in range(360))
    metrics = analyze_periodic_waveform(values)
    assert metrics.phase_rms_v == pytest.approx(10.0 / math.sqrt(2.0), rel=1e-12)
    assert metrics.phase_peak_v == pytest.approx(10.0)
    assert metrics.phase_fundamental_rms_v == pytest.approx(10.0 / math.sqrt(2.0), rel=1e-12)
    assert metrics.dc_component_v == pytest.approx(0.0, abs=1e-12)


def test_harmonic_waveform_total_rms_is_not_replaced_by_sinusoidal_conversion():
    values = tuple(
        10.0 * math.sin(2.0 * math.pi * index / 360)
        + 3.0 * math.sin(6.0 * math.pi * index / 360)
        for index in range(360)
    )
    metrics = analyze_periodic_waveform(values)
    assert metrics.phase_rms_v == pytest.approx(math.sqrt((10.0**2 + 3.0**2) / 2.0), rel=1e-12)
    assert metrics.phase_fundamental_rms_v == pytest.approx(10.0 / math.sqrt(2.0), rel=1e-12)
    assert metrics.phase_rms_v != pytest.approx(metrics.phase_peak_v / math.sqrt(2.0), rel=1e-3)


def test_external_import_preserves_solver_metadata_and_source_hash(tmp_path):
    path = tmp_path / "maxwell_export.csv"
    _write_sine_csv(path)
    imported = ExternalFEAImportAdapter().import_csv(path, _metadata(), _mesh_metadata(), _reference())
    assert imported.reference_id == "phase7h_controlled_coreless_ssdr_v1"
    assert imported.solver_metadata == _metadata()
    assert imported.mesh_metadata == _mesh_metadata()
    assert imported.evidence_classification is EvidenceClassification.INDEPENDENT_FEA_REFERENCE
    assert imported.source_file_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert imported.source_file_sha256 == sha256_file(path)
    assert imported.waveform_metrics.phase_rms_v == pytest.approx(10.0 / math.sqrt(2.0))


def test_external_import_is_deterministic(tmp_path):
    path = tmp_path / "comsol_export.csv"
    _write_sine_csv(path)
    adapter = ExternalFEAImportAdapter()
    assert adapter.import_csv(path, _metadata(), _mesh_metadata(), _reference()) == adapter.import_csv(
        path, _metadata(), _mesh_metadata(), _reference()
    )


def test_external_import_rejects_nonuniform_samples_before_dft(tmp_path):
    path = tmp_path / "nonuniform.csv"
    _write_sine_csv(path)
    rows = list(csv.reader(path.read_text(encoding="utf-8").splitlines()))
    rows[5][1] = str(float(rows[5][1]) + 1e-4)
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerows(rows)
    with pytest.raises(ValueError, match="uniformly spaced"):
        ExternalFEAImportAdapter().import_csv(path, _metadata(), _mesh_metadata(), _reference())


def test_mesh_convergence_accepts_only_when_every_refinement_change_passes():
    points = (
        FEAMeshConvergencePoint("coarse", 10000, 10.00, 0.0200),
        FEAMeshConvergencePoint("medium", 40000, 10.05, 0.0201),
        FEAMeshConvergencePoint("fine", 120000, 10.08, 0.02016),
    )
    result = assess_mesh_convergence(points, tolerance_percent=1.0)
    assert result.accepted is True
    assert result.maximum_successive_change_percent < 1.0


def test_mesh_convergence_rejects_a_large_coarse_to_medium_change():
    points = (
        FEAMeshConvergencePoint("coarse", 10000, 8.0, 0.016),
        FEAMeshConvergencePoint("medium", 40000, 10.0, 0.020),
        FEAMeshConvergencePoint("fine", 120000, 10.02, 0.02004),
    )
    result = assess_mesh_convergence(points, tolerance_percent=1.0)
    assert result.accepted is False
    assert result.maximum_successive_change_percent > 1.0


def test_import_does_not_mutate_controlled_reference_parameters(tmp_path):
    reference = load_fea_reference_definition(REFERENCE_PATH)
    before = asdict(reference)
    path = tmp_path / "external.csv"
    _write_sine_csv(path)
    ExternalFEAImportAdapter().import_csv(path, _metadata(), _mesh_metadata(), reference)
    assert asdict(reference) == before
