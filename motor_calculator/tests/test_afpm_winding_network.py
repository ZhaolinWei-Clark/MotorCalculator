from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from advanced_afpm import (
    AFPMWindingNetwork,
    PhaseConnection,
    RadialSliceBackEMFModel,
    RadialSliceInputError,
    StatorConnection,
    WindingFactorMethod,
    WindingType,
    build_synthetic_radial_reference_case,
    load_advanced_afpm_cases,
)
from advanced_afpm.source_recovery import (
    RecoveryFieldStatus,
    load_phase7f_source_recovery,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = REPO_ROOT / "validation_data" / "reconstructed_cases"
RECOVERY_PATH = REPO_ROOT / "validation_data" / "source_recovery" / "phase7f_winding_recovery.json"


def _network(**overrides) -> AFPMWindingNetwork:
    values = {
        "turns_per_coil": 20,
        "coils_per_phase": 3,
        "series_coils_per_branch": 3,
        "parallel_branches": 1,
        "number_of_stators": 1,
        "stator_connection": StatorConnection.INDEPENDENT,
        "phase_connection": PhaseConnection.Y,
        "winding_type": WindingType.CONCENTRATED,
        "winding_factor": 0.92,
        "pitch_factor": None,
        "distribution_factor": None,
    }
    values.update(overrides)
    return AFPMWindingNetwork(**values)


def test_series_coils_add_effective_turns() -> None:
    assert _network().effective_series_turns_per_phase == 60


def test_parallel_branches_do_not_multiply_effective_turns_or_emf() -> None:
    two_branches = _network(coils_per_phase=6, series_coils_per_branch=3, parallel_branches=2)
    one_branch = _network(coils_per_phase=3, series_coils_per_branch=3, parallel_branches=1)

    assert two_branches.effective_series_turns_per_phase == one_branch.effective_series_turns_per_phase == 60


def test_two_identical_stators_in_series_double_terminal_emf() -> None:
    result = _network(number_of_stators=2, stator_connection=StatorConnection.SERIES).combine_identical_stator_phase_emf(12.0)

    assert result.terminal_phase_emf_v == 24.0


def test_two_identical_stators_in_parallel_preserve_terminal_emf() -> None:
    result = _network(number_of_stators=2, stator_connection=StatorConnection.PARALLEL).combine_identical_stator_phase_emf(12.0)

    assert result.terminal_phase_emf_v == 12.0


def test_independent_stators_have_no_combined_terminal_emf() -> None:
    result = _network(number_of_stators=2, stator_connection=StatorConnection.INDEPENDENT).combine_identical_stator_phase_emf(12.0)

    assert result.terminal_phase_emf_v is None
    assert result.independent_stator_phase_emfs_v == (12.0, 12.0)


def test_y_delta_and_unknown_phase_semantics_remain_explicit() -> None:
    assert _network(phase_connection=PhaseConnection.Y).phase_rms_to_line_rms(10.0) == pytest.approx(10.0 * 3.0**0.5)
    assert _network(phase_connection=PhaseConnection.DELTA).phase_rms_to_line_rms(10.0) == 10.0
    assert _network(phase_connection=PhaseConnection.UNKNOWN).phase_rms_to_line_rms(10.0) is None


def test_winding_factor_uses_direct_kw_before_component_factors() -> None:
    resolution = _network(winding_factor=0.91, pitch_factor=0.8, distribution_factor=0.7).resolve_winding_factor()

    assert resolution.value == 0.91
    assert resolution.method is WindingFactorMethod.DIRECT


def test_winding_factor_is_safely_derived_only_when_kp_and_kd_are_known() -> None:
    derived = _network(winding_factor=None, pitch_factor=0.95, distribution_factor=0.9).resolve_winding_factor()
    blocked = _network(winding_factor=None, pitch_factor=0.95, distribution_factor=None).resolve_winding_factor()

    assert derived.value == pytest.approx(0.855)
    assert derived.method is WindingFactorMethod.DERIVED_KP_KD
    assert blocked.value is None
    assert blocked.method is WindingFactorMethod.UNAVAILABLE


def test_unknown_winding_factor_blocks_radial_prediction_without_default() -> None:
    case = build_synthetic_radial_reference_case()
    network = replace(case.winding_network, winding_factor=None, pitch_factor=None, distribution_factor=None)

    with pytest.raises(RadialSliceInputError) as exc_info:
        RadialSliceBackEMFModel().compute(case, winding_network=network)

    assert "winding_network.winding_factor" in exc_info.value.missing_fields


def test_recovered_source_networks_preserve_known_and_unknown_fields() -> None:
    cases = {case.source_id: case for case in load_advanced_afpm_cases(CASE_DIR)}
    price = cases["price_2009_coreless_afpm_generator"].winding_network
    parviainen = cases["parviainen_2005_afpm_prototype"].winding_network
    hosseini = cases["hosseini_2008_coreless_afpm_generator"].winding_network

    assert price.effective_series_turns_per_phase == 108
    assert price.phase_connection is PhaseConnection.Y
    assert price.resolve_winding_factor().value is None
    assert parviainen.effective_series_turns_per_phase == 840
    assert parviainen.stator_connection is StatorConnection.PARALLEL
    assert hosseini.coils_per_phase == 6
    assert hosseini.effective_series_turns_per_phase is None


def test_source_recovery_preserves_field_provenance_and_derivations() -> None:
    recovered = load_phase7f_source_recovery(RECOVERY_PATH)

    for fields in recovered.values():
        for field in fields.values():
            assert field.source_url
            assert field.page
            assert field.location
            assert field.note
            if field.status is RecoveryFieldStatus.SAFELY_DERIVED:
                assert field.derivation


def test_unavailable_price_material_is_not_replaced_by_a_default() -> None:
    cases = {case.source_id: case for case in load_advanced_afpm_cases(CASE_DIR)}
    price = cases["price_2009_coreless_afpm_generator"]

    assert price.remanence_t is None
    assert price.magnet_relative_permeability is None
    assert price.recovered_fields["remanence_t"].status is RecoveryFieldStatus.UNAVAILABLE


def test_explicit_network_radial_solver_remains_deterministic() -> None:
    case = build_synthetic_radial_reference_case()
    model = RadialSliceBackEMFModel()

    assert model.compute(case, winding_network=case.winding_network) == model.compute(
        case,
        winding_network=case.winding_network,
    )
