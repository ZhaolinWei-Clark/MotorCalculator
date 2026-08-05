from __future__ import annotations

import pytest

from advanced_afpm import (
    AFPMGeometry,
    AFPMInductance,
    AFPMTopology,
    AFPMTopologyType,
    AFPMWinding,
    RadialMagnetSample,
    TorqueBoundary,
    TorqueSemantics,
    WindingType,
)


def test_explicit_topology_schema_distinguishes_afpm_arrangements() -> None:
    ssdr = AFPMTopology(AFPMTopologyType.SSDR, 1, 2, 2, "central stator", "two rotor faces")
    dssr = AFPMTopology(AFPMTopologyType.DSSR, 2, 1, 2, "outer stators", "central rotor faces")
    single = AFPMTopology(AFPMTopologyType.SINGLE_SIDED, 1, 1, 1, "stator", "rotor face")

    assert (ssdr.stator_count, ssdr.rotor_count) == (1, 2)
    assert (dssr.stator_count, dssr.rotor_count) == (2, 1)
    assert single.active_air_gap_count == 1


def test_radial_profile_interpolates_only_from_explicit_samples() -> None:
    geometry = AFPMGeometry(
        0.05, 0.10, 0.001, 0.005, 5, None,
        (RadialMagnetSample(0.05, 0.4), RadialMagnetSample(0.10, 0.8)),
        1, 2, 0.012,
    )

    assert geometry.magnet_coverage_at(0.075) == pytest.approx(0.6)


def test_missing_magnet_coverage_is_rejected_instead_of_inferred() -> None:
    geometry = AFPMGeometry(0.05, 0.10, 0.001, 0.005, 5, None, None, 1, 2, 0.012)

    with pytest.raises(ValueError, match="coverage is unavailable"):
        geometry.magnet_coverage_at(0.075)


def test_winding_factor_remains_optional_and_is_not_derived() -> None:
    winding = AFPMWinding(36, 3, 108, None, "Y", None, None, None, WindingType.UNKNOWN)

    assert winding.turns_per_phase == 108
    assert winding.winding_factor is None
    assert winding.parallel_branches is None


def test_ld_lq_and_torque_boundaries_remain_distinct() -> None:
    inductance = AFPMInductance(ld_h=0.055, lq_h=0.060)
    torque = TorqueSemantics(TorqueBoundary.SHAFT)

    assert inductance.scalar_phase_h is None
    assert inductance.ld_h != inductance.lq_h
    assert torque.source_boundary is TorqueBoundary.SHAFT
    assert torque.mechanical_loss_torque_nm is None
