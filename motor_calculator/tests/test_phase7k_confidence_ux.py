from __future__ import annotations

import inspect
import json
from dataclasses import replace
from pathlib import Path

import pytest

from motor_calculator.gui.feedback_dialog import (
    EVIDENCE_TYPE_LABELS,
    format_feedback_submission_result,
)
from motor_calculator.gui.main_window import MotorCalculatorAppMixin
from motor_calculator.validation.confidence_summary import (
    UncertaintyDimensionStatus,
    build_unavailable_confidence_summary,
    export_confidence_summary,
    load_validation_summary_safely,
    render_confidence_summary_json,
    render_confidence_summary_text,
)
from motor_calculator.validation.feedback_models import (
    EvidenceQuality,
    ExternalValidationCoverage,
    FeedbackModelIdentity,
    FeedbackOperatingPoint,
    FeedbackSubmission,
    MetricSemantics,
    ValidationEvidenceType,
)
from motor_calculator.validation.feedback_service import submit_feedback
from motor_calculator.validation.phase7i_uncertainty_report import run_phase7i_demonstration
from motor_calculator.validation.phase7k_confidence_demo import run_phase7k_confidence_demo
from motor_calculator.validation.uncertainty_form import UncertaintyInputRow
from motor_calculator.validation.uncertainty_models import (
    ParameterUncertainty,
    ResultConfidence,
    UncertaintyKind,
    load_uncertainty_specification,
)


ROOT = Path(__file__).resolve().parents[2]
SPEC_PATH = ROOT / "validation_data" / "uncertainty" / "phase7i_afpm_back_emf_uncertainty.json"


@pytest.fixture(scope="module")
def phase7k_demo(tmp_path_factory):
    return run_phase7k_confidence_demo(
        ROOT, tmp_path_factory.mktemp("phase7k") / "feedback_records.jsonl"
    )


def _blocked_submission() -> FeedbackSubmission:
    predicted = MetricSemantics("phase", "rms", "sinusoidal", "not_applicable", "not_applicable")
    reference = MetricSemantics("line", "peak", "unknown", "not_applicable", "not_applicable")
    return FeedbackSubmission(
        metric_name="back_emf_phase_rms_v",
        predicted_value=33.0,
        reference_value=31.8,
        predicted_unit="V",
        reference_unit="V",
        predicted_semantics=predicted,
        reference_semantics=reference,
        operating_point=FeedbackOperatingPoint(1000.0),
        evidence_type=ValidationEvidenceType.OTHER,
        model_identity=FeedbackModelIdentity(
            calculator_version="test",
            model_version="test",
            model_track="sandbox",
            topology="SSDR",
            software_version="test",
            git_commit=None,
            model_family="test",
            calculation_mode="static",
            origin="sandbox",
            formula_version="test",
        ),
        full_input_snapshot={"topology": "SSDR", "winding_connection": "Y"},
        notes="test blocked semantics",
    )


def test_confidence_summary_combines_phase7i_and_phase7j_without_changing_values(phase7k_demo):
    summary = phase7k_demo.confidence_summary
    assert summary.nominal_value == pytest.approx(33.329273055309)
    assert summary.parameter_bound_min == pytest.approx(28.466740070843)
    assert summary.parameter_bound_max == pytest.approx(38.757257393917)
    assert summary.p10 == pytest.approx(32.150112537558)
    assert summary.p50 == pytest.approx(33.340057815664)
    assert summary.p90 == pytest.approx(34.534283497564)
    assert summary.confidence_level is ResultConfidence.LOW
    assert summary.external_validation_coverage is ExternalValidationCoverage.VERY_LIMITED
    assert summary.compatible_validation_records == 1
    assert summary.high_quality_validation_records == 0


def test_confidence_explanation_states_reasons_not_a_mysterious_score(phase7k_demo):
    summary = phase7k_demo.confidence_summary
    reasons = " ".join(summary.confidence_reasons).lower()
    assert "external validation" in reasons
    assert "model-form uncertainty" in reasons
    assert "well converged" in reasons
    assert "score" not in reasons


def test_missing_uncertainty_degrades_to_explicit_unavailable_message():
    summary = build_unavailable_confidence_summary(
        metric_name="rated_torque_nm", nominal_value=4.2, unit="Nm"
    )
    text = render_confidence_summary_text(summary)
    assert summary.confidence_level is ResultConfidence.INSUFFICIENT
    assert summary.parameter_uncertainty_status is UncertaintyDimensionStatus.UNAVAILABLE
    assert "Estimated parameter-driven range: unavailable" in text
    assert "Uncertainty estimate not available" in text


def test_accuracy_wording_policy_avoids_unsupported_claims(phase7k_demo):
    text = render_confidence_summary_text(phase7k_demo.confidence_summary).lower()
    for unsupported in (
        "95% accurate",
        "guaranteed accuracy",
        "actual error ±",
        "exact result",
        "validated to",
        "accuracy score",
    ):
        assert unsupported not in text
    assert "nominal prediction" in text
    assert "parameter-driven range" in text
    assert "model-form uncertainty" in text


def test_confidence_export_is_deterministic_and_local(phase7k_demo, tmp_path: Path):
    summary = phase7k_demo.confidence_summary
    first = export_confidence_summary(summary, tmp_path / "summary.json", format_name="json")
    second_text = render_confidence_summary_json(summary)
    assert first.read_text(encoding="utf-8") == second_text
    payload = json.loads(second_text)
    assert payload["confidence_level"] == "LOW"
    assert payload["external_validation_coverage"] == "VERY_LIMITED"


def test_corrupt_feedback_store_does_not_block_confidence_summary(tmp_path: Path):
    store = tmp_path / "feedback_records.jsonl"
    store.write_text("not-json\n", encoding="utf-8")
    summary, warning = load_validation_summary_safely(store)
    assert summary.total_records == 0
    assert summary.validation_coverage is ExternalValidationCoverage.NONE
    assert warning is not None
    assert "database is unavailable" in warning


@pytest.mark.parametrize(
    ("kind", "extra"),
    (
        (UncertaintyKind.EXACT, {}),
        (UncertaintyKind.RANGE, {"lower_bound": "0.9", "upper_bound": "1.1"}),
        (UncertaintyKind.NORMAL, {"mean": "1.0", "standard_deviation": "0.02"}),
        (UncertaintyKind.UNIFORM, {"lower_bound": "0.9", "upper_bound": "1.1"}),
        (UncertaintyKind.UNKNOWN, {}),
    ),
)
def test_uncertainty_input_form_supports_all_explicit_kinds(kind, extra):
    row = UncertaintyInputRow(
        parameter_name="test_parameter",
        unit="-",
        nominal_value="1.0",
        uncertainty_kind=kind.value,
        **extra,
    )
    assert row.to_parameter_uncertainty().uncertainty_kind is kind


def test_uncertainty_form_never_invents_missing_distribution_parameters():
    row = UncertaintyInputRow(
        parameter_name="Br",
        unit="T",
        nominal_value="1.2",
        uncertainty_kind="NORMAL",
    )
    with pytest.raises(ValueError, match="invalid uncertainty declaration"):
        row.to_parameter_uncertainty()


def test_user_specification_override_changes_only_controlled_sandbox_prediction():
    before = SPEC_PATH.read_bytes()
    base = load_uncertainty_specification(SPEC_PATH)
    remanence = ParameterUncertainty(
        parameter_name="magnet_remanence_t",
        nominal_value=1.1,
        unit="T",
        uncertainty_kind=UncertaintyKind.EXACT,
        lower_bound=None,
        upper_bound=None,
        mean=None,
        standard_deviation=None,
        provenance="test-only explicit local override",
        confidence="test",
        notes=("sandbox only",),
    )
    override = replace(base, parameters=(remanence,) + base.parameters[1:])
    result = run_phase7i_demonstration(
        ROOT,
        monte_carlo_sample_count=30,
        random_seed=5,
        specification_override=override,
    )
    assert result.accuracy_envelope.nominal_value < 33.329273055309
    assert SPEC_PATH.read_bytes() == before


def test_blocked_feedback_display_never_shows_fake_error(tmp_path: Path):
    record = submit_feedback(_blocked_submission(), tmp_path / "feedback.jsonl").record
    display = format_feedback_submission_result(record)
    assert "可比性：暂不可比" in display
    assert "数值误差：未计算" in display
    assert "APE:" not in display
    assert record.signed_error is None


def test_evidence_type_ux_covers_all_backend_types():
    assert set(EVIDENCE_TYPE_LABELS.values()) == set(ValidationEvidenceType)
    assert any("实体电机测试" in label for label in EVIDENCE_TYPE_LABELS)
    assert any("场求解器" in label for label in EVIDENCE_TYPE_LABELS)


def test_synthetic_demo_is_unverified_and_only_very_limited_coverage(phase7k_demo):
    assert phase7k_demo.feedback_record.evidence_quality is EvidenceQuality.UNVERIFIED
    assert phase7k_demo.confidence_summary.external_validation_coverage is ExternalValidationCoverage.VERY_LIMITED
    assert phase7k_demo.feedback_record.absolute_percentage_error == pytest.approx(4.809034765122)


def test_normal_analysis_source_has_no_mandatory_uncertainty_run():
    source = inspect.getsource(MotorCalculatorAppMixin.run_analysis)
    assert "run_phase7i_demonstration" not in source
    assert "_estimate_controlled_reference_uncertainty" not in source


def test_confidence_panel_uses_tkinter_only_and_has_no_network_or_calibration_action():
    paths = (
        ROOT / "motor_calculator" / "gui" / "confidence_panel.py",
        ROOT / "motor_calculator" / "gui" / "feedback_dialog.py",
        ROOT / "motor_calculator" / "gui" / "uncertainty_dialog.py",
        ROOT / "motor_calculator" / "validation" / "confidence_summary.py",
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths).lower()
    assert "matplotlib" not in source
    assert "import requests" not in source
    assert "import urllib" not in source
    assert "import socket" not in source
    assert "apply_calibration" not in source
    assert "correction_factor" not in source
