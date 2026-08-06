import json
from pathlib import Path

import pytest

from motor_calculator.advanced_afpm.benchmark_evidence import (
    evaluate_benchmark_evidence,
    load_benchmark_evidence,
    project_benchmark_case,
)
from motor_calculator.advanced_afpm.completeness import CompletenessStatus


ROOT = Path(__file__).resolve().parents[2]
PACKAGES = sorted((ROOT / "validation_data" / "source_recovery").glob("phase7g_*.json"))


def test_phase7g_packages_are_traceable_and_use_locked_scores():
    assert len(PACKAGES) == 4
    for path in PACKAGES:
        package = load_benchmark_evidence(path)
        assert len(package.quality_scores) == 10
        assert all(
            field.provenance.source_url
            and field.provenance.publication
            and field.provenance.page
            and field.provenance.location
            for field in package.fields.values()
        )


def test_phase7g_packages_run_the_unchanged_completeness_gate():
    results = [evaluate_benchmark_evidence(load_benchmark_evidence(path)) for path in PACKAGES]
    assert all(result.status is CompletenessStatus.BLOCKED for result in results)
    assert all(result.missing_fields for result in results)


def test_missing_values_are_not_replaced_by_defaults():
    package = load_benchmark_evidence(
        ROOT / "validation_data" / "source_recovery" / "phase7g_ferreira_2007_ipb_family.json"
    )
    case = project_benchmark_case(package)
    assert case.geometry.effective_nonmagnetic_gap_m is None
    assert case.geometry.magnet_arc_ratio is None
    assert case.winding_network.winding_factor is None


def test_ambiguous_field_cannot_carry_a_numeric_value(tmp_path):
    source = json.loads(PACKAGES[0].read_text(encoding="utf-8"))
    source["fields"]["effective_nonmagnetic_gap_m"]["status"] = "ambiguous"
    source["fields"]["effective_nonmagnetic_gap_m"]["value"] = 0.001
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(ValueError, match="must have a null value"):
        load_benchmark_evidence(path)


def test_evidence_projection_is_deterministic():
    package = load_benchmark_evidence(PACKAGES[0])
    first = evaluate_benchmark_evidence(package)
    second = evaluate_benchmark_evidence(package)
    assert first == second


def test_evidence_projection_does_not_mutate_json_source():
    path = PACKAGES[0]
    before = path.read_bytes()
    project_benchmark_case(load_benchmark_evidence(path))
    assert path.read_bytes() == before
