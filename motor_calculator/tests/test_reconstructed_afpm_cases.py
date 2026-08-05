from __future__ import annotations

from pathlib import Path

import pytest

from validation.reconstructed_cases import (
    MissingReconstructedInputError,
    ReconstructedFieldStatus,
    load_reconstructed_case,
    normalize_copper_resistance_temperature,
    require_reconstructed_inputs,
    synchronous_reactance_to_inductance_h,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = REPO_ROOT / "validation_data" / "reconstructed_cases"


def _case(name: str):
    return load_reconstructed_case(CASE_DIR / name)


def test_all_reconstructed_cases_load_with_field_level_provenance() -> None:
    cases = tuple(_case(name) for name in (
        "abdelli_2026_case.json",
        "hosseini_2008_case.json",
        "parviainen_2005_case.json",
        "price_2009_case.json",
    ))

    assert len(cases) == 4
    assert all(case.fields for case in cases)
    for case in cases:
        for field in case.fields.values():
            assert field.provenance.source_url.startswith("http")
            assert field.provenance.page
            assert field.provenance.location
            assert field.provenance.note


def test_no_silent_default_substitution_for_price_back_emf() -> None:
    case = _case("price_2009_case.json")
    required = (
        "mechanical_speed_rpm_back_emf", "pole_pairs", "outer_diameter_m",
        "inner_diameter_m", "air_gap_per_side_m", "magnet_thickness_m",
        "remanence_t", "magnet_relative_permeability", "turns_per_phase",
        "pole_arc_coefficient", "leakage_factor", "winding_factor",
    )

    with pytest.raises(MissingReconstructedInputError) as exc_info:
        require_reconstructed_inputs(case, required)

    assert set(exc_info.value.missing_fields) == {
        "pole_pairs", "air_gap_per_side_m", "remanence_t",
        "magnet_relative_permeability", "pole_arc_coefficient",
        "leakage_factor", "winding_factor",
    }
    assert case.fields["remanence_t"].value is None
    with pytest.raises(TypeError):
        case.fields["remanence_t"] = case.fields["turns_per_phase"]


def test_safe_copper_resistance_temperature_transform() -> None:
    transformed = normalize_copper_resistance_temperature(1.0, 20.0, 100.0)

    assert transformed.value == pytest.approx(1.3144)
    assert transformed.comparability == "SAFE_TRANSFORM"
    assert "alpha" in transformed.derivation


def test_hosseini_reactances_transform_to_separate_dq_inductances() -> None:
    transformed = synchronous_reactance_to_inductance_h(2.1, 300.0)
    case = _case("hosseini_2008_case.json")

    assert transformed.value == pytest.approx(0.0011140846016432675)
    assert case.fields["Ld_from_Xsd_h"].value == pytest.approx(transformed.value)
    assert case.fields["Lq_from_Xsq_h"].value == pytest.approx(transformed.value)
    assert "not scalar phase inductance" in transformed.derivation


def test_ambiguous_current_basis_is_not_usable() -> None:
    case = _case("hosseini_2008_case.json")

    assert case.fields["phase_current_a"].status is ReconstructedFieldStatus.AMBIGUOUS
    with pytest.raises(MissingReconstructedInputError):
        case.usable_value("phase_current_a")
