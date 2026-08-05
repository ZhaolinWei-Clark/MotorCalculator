from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from advanced_afpm import (
    AFPMTopology,
    AFPMTopologyType,
    StatorConnection,
    RadialSliceBackEMFModel,
    RadialSliceInputError,
    build_synthetic_radial_reference_case,
    convergence_study,
    load_advanced_afpm_cases,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_radial_integration_is_deterministic() -> None:
    case = build_synthetic_radial_reference_case()
    model = RadialSliceBackEMFModel()

    assert model.compute(case, slice_count=100) == model.compute(case, slice_count=100)


def test_radial_integration_converges_across_required_resolutions() -> None:
    points = convergence_study(build_synthetic_radial_reference_case(), (10, 50, 100, 500))

    assert tuple(point.slice_count for point in points) == (10, 50, 100, 500)
    assert points[-1].phase_fundamental_rms_v == pytest.approx(28.889356302566522)
    assert points[-1].relative_difference_from_previous_percent < 0.001
    assert abs(points[-1].phase_fundamental_rms_v - points[-2].phase_fundamental_rms_v) < 0.0001


def test_radius_dependent_profile_differs_from_mean_radius_approximation() -> None:
    case = build_synthetic_radial_reference_case()
    model = RadialSliceBackEMFModel()
    radial = model.compute(case, slice_count=500)
    mean = model.compute_mean_radius(case)
    relative = (radial.phase_fundamental_rms_v - mean.phase_fundamental_rms_v) / mean.phase_fundamental_rms_v * 100.0

    assert radial.phase_fundamental_rms_v > mean.phase_fundamental_rms_v
    assert relative == pytest.approx(1.068364102564149, rel=1e-9)


def test_dssr_series_and_parallel_stator_voltage_aggregation_is_explicit() -> None:
    base = build_synthetic_radial_reference_case()
    topology = AFPMTopology(
        AFPMTopologyType.DSSR, 2, 1, 2,
        "one winding on each outer stator", "both central rotor faces",
    )
    geometry = replace(base.geometry, stator_count=2, rotor_count=1)
    parallel = replace(
        base,
        topology=topology,
        geometry=geometry,
        winding=replace(base.winding, stator_interconnection="two stators electrically parallel"),
        winding_network=replace(
            base.winding_network,
            number_of_stators=2,
            stator_connection=StatorConnection.PARALLEL,
        ),
    )
    series = replace(
        parallel,
        winding=replace(parallel.winding, stator_interconnection="two stators electrically series"),
        winding_network=replace(parallel.winding_network, stator_connection=StatorConnection.SERIES),
    )
    model = RadialSliceBackEMFModel()

    parallel_result = model.compute(parallel, slice_count=100)
    series_result = model.compute(series, slice_count=100)

    assert parallel_result.voltage_aggregation_multiplier == 1.0
    assert series_result.voltage_aggregation_multiplier == 2.0
    assert series_result.phase_fundamental_rms_v == pytest.approx(2.0 * parallel_result.phase_fundamental_rms_v)


def test_external_case_with_missing_fields_is_rejected_not_filled() -> None:
    cases = load_advanced_afpm_cases(REPO_ROOT / "validation_data" / "reconstructed_cases")
    price = next(case for case in cases if case.source_id.startswith("price"))

    with pytest.raises(RadialSliceInputError) as exc_info:
        RadialSliceBackEMFModel().compute(price)

    assert "material.remanence_t" in exc_info.value.missing_fields
    assert "material.magnet_relative_permeability" in exc_info.value.missing_fields
    assert "winding_network.winding_factor" in exc_info.value.missing_fields


def test_radial_sandbox_does_not_modify_production_or_legacy_baseline() -> None:
    calculations = REPO_ROOT / "motor_calculator" / "motor_core" / "calculations.py"
    legacy = REPO_ROOT / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json"
    before = (_sha256(calculations), _sha256(legacy))

    RadialSliceBackEMFModel().compute(build_synthetic_radial_reference_case(), slice_count=100)

    assert (_sha256(calculations), _sha256(legacy)) == before
    assert before[1] == "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"
