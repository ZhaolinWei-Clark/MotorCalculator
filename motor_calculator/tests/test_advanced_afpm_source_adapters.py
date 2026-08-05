from __future__ import annotations

from pathlib import Path

from advanced_afpm import AFPMFieldStatus, AFPMTopologyType, TorqueBoundary, load_advanced_afpm_cases
from validation.reconstructed_cases import load_reconstructed_case


REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_DIR = REPO_ROOT / "validation_data" / "reconstructed_cases"


def _cases():
    return {case.source_id: case for case in load_advanced_afpm_cases(CASE_DIR)}


def test_all_four_reconstructed_sources_are_adapted_with_full_field_provenance() -> None:
    cases = _cases()

    assert len(cases) == 4
    for advanced in cases.values():
        reconstructed_path = next(
            path for path in CASE_DIR.glob("*_case.json")
            if load_reconstructed_case(path).source_id == advanced.source_id
        )
        reconstructed = load_reconstructed_case(reconstructed_path)
        assert set(advanced.source_fields) == set(reconstructed.fields)
        for name, field in advanced.source_fields.items():
            original = reconstructed.fields[name]
            assert field.status.value == original.status.value
            assert field.value == original.value
            assert field.source_url == original.provenance.source_url
            assert field.page == original.provenance.page
            assert field.location == original.provenance.location


def test_adapter_field_lineage_references_only_source_fields_or_source_metadata() -> None:
    for case in _cases().values():
        for source_names in case.field_lineage.values():
            assert all(name == "$topology" or name in case.source_fields for name in source_names)


def test_missing_inputs_stay_missing_without_production_defaults() -> None:
    cases = _cases()
    price = cases["price_2009_coreless_afpm_generator"]
    hosseini = cases["hosseini_2008_coreless_afpm_generator"]
    abdelli = cases["abdelli_2026_dssr_afpm"]

    assert price.remanence_t is None
    assert price.geometry.pole_pairs == 6
    assert price.geometry.magnet_arc_ratio is None
    assert price.geometry.radius_dependent_magnet_profile is not None
    assert price.recovered_fields["pole_pairs"].status.value == "safely_derived"
    assert hosseini.winding.turns_per_phase is None
    assert hosseini.winding.connection is None
    assert abdelli.winding.turns_per_phase is None
    assert abdelli.source_fields["turns_per_phase"].status is AFPMFieldStatus.AMBIGUOUS


def test_topology_inductance_and_torque_semantics_are_preserved() -> None:
    cases = _cases()
    parviainen = cases["parviainen_2005_afpm_prototype"]
    hosseini = cases["hosseini_2008_coreless_afpm_generator"]
    price = cases["price_2009_coreless_afpm_generator"]

    assert parviainen.topology.topology_type is AFPMTopologyType.DSSR
    assert parviainen.inductance.ld_h == 0.055
    assert parviainen.inductance.lq_h == 0.060
    assert hosseini.inductance.scalar_phase_h is None
    assert hosseini.inductance.ld_h == hosseini.inductance.lq_h
    assert price.torque_semantics.source_boundary is TorqueBoundary.SHAFT
    assert price.torque_semantics.mechanical_loss_torque_nm is None
