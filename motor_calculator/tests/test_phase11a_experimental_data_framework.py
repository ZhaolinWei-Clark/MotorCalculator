"""Phase 11A: the experimental / public-reference data framework.

The tests that matter most here are the negative ones. It is easy to check that
a clean CSV parses; the question this phase exists to answer is whether a
simulation can ever be shown as a measurement, and whether another machine's
real data can validate this design. Those are asserted from both directions.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from motor_calculator.experiment.analysis import (
    AnalysisError,
    Connection,
    SpeedBasis,
    analyze_back_emf,
    analyze_efficiency,
    analyze_phase_resistance,
    analyze_torque_current,
    voltage_conversion,
)
from motor_calculator.experiment.columns import (
    AmbiguousColumnError,
    UnknownColumnError,
    VoltageBasis,
    resolve_header,
)
from motor_calculator.experiment.comparison import (
    NO_EXPERIMENTAL_DATA,
    OverallClaim,
    analytical_entry,
    build_overview,
    build_quantity_comparison,
    fea_entry,
    measurement_entry,
)
from motor_calculator.experiment.compatibility import (
    MachineCompatibility,
    assess_compatibility,
    may_validate_current_design,
    project_machine_identity,
)
from motor_calculator.experiment.csv_import import (
    CsvImportRejected,
    import_csv_file,
    import_csv_strict,
    import_csv_text,
)
from motor_calculator.experiment.fixtures import (
    FixtureLeakError,
    SyntheticBackEmf,
    SyntheticTorqueCurrent,
    is_production_admissible,
    require_production_admissible,
    synthetic_dataset,
    synthetic_efficiency_rows,
    synthetic_resistance_rows,
)
from motor_calculator.experiment.persistence import (
    DatasetAvailability,
    DatasetStore,
    from_preferences,
)
from motor_calculator.experiment.public_reference import (
    PHASE_11B_REQUIREMENTS,
    ExtractionMethod,
    PublicSourceRecord,
    may_commit_raw_data,
)
from motor_calculator.experiment.regression import RegressionError, fit_line
from motor_calculator.experiment.report import (
    VALIDATED_WORD,
    build_report_payload,
    export_validation_report,
    render_report_zh,
)
from motor_calculator.experiment.schema import (
    UNKNOWN,
    Citation,
    DatasetMetadata,
    MachineIdentity,
    RedistributionStatus,
    TestType,
    metadata_from_payload,
    metadata_to_payload,
)
from motor_calculator.experiment.service import ValidationDataService
from motor_calculator.experiment.sources import (
    DatasetSourceType,
    ReclassificationError,
    is_experimental,
    may_reclassify,
    require_reclassifiable,
)
from motor_calculator.experiment.templates import TEMPLATES, build_template_csv, export_template
from motor_calculator.experiment.units import UnitError, normalize, rpm_to_rad_per_s

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

AFPM = MachineIdentity(
    topology="AFPM_DUAL_ROTOR_SINGLE_STATOR",
    pole_count=16,
    slot_count=24,
    phases=3,
    connection="WYE",
    turns_per_phase=42,
    rated_speed_rpm=1800.0,
    rated_power_w=600.0,
)

PROJECT_PARAMS = {
    "p": 8, "slots": 24, "N_ph_turns": 42, "n_rated": 1800.0, "P_rated": 600.0,
}


def _metadata(
    dataset_id="ds.1",
    source_type=DatasetSourceType.USER_EXPERIMENT,
    test_type=TestType.NO_LOAD_BACK_EMF,
    machine=AFPM,
):
    return DatasetMetadata(
        dataset_id=dataset_id, title="bench run", source_type=source_type,
        test_type=test_type, machine=machine,
    )


# ===========================================================================
# Step 1-2 carryovers: File -> New, and the dashboard summary
# ===========================================================================


def test_new_project_defaults_to_auto_when_geometry_supports_it():
    from motor_calculator.winding.persistence import new_project_ui_preferences

    preferences = new_project_ui_preferences(
        slots=24, pole_pairs=8, coil_span_slots=1, manual_winding_factor=0.93
    )
    assert preferences["winding_factor_mode"] == "auto"
    assert preferences["winding.authority"] == "AUTO_FROM_GEOMETRY"
    assert preferences["coil_span_slots"] == "1"


def test_new_project_does_not_invent_a_winding_factor_without_geometry():
    from motor_calculator.winding.persistence import new_project_ui_preferences

    preferences = new_project_ui_preferences(
        slots=None, pole_pairs=None, coil_span_slots=None, manual_winding_factor=0.93
    )
    assert preferences["winding_factor_mode"] == "manual"
    assert preferences["winding.authority"] == "MANUAL_OVERRIDE"


def test_file_new_is_wired_to_the_derived_preferences():
    """The Phase 10H carryover: new_project_state needed a production consumer."""

    source = (REPOSITORY_ROOT / "motor_calculator" / "gui" / "main_window.py").read_text(
        encoding="utf-8"
    )
    body = source[source.index("    def _new_project(self)"):]
    body = body[: body.index("\n    def ")]
    assert "ui_preferences=self._new_project_ui_preferences()" in body
    assert "new_project_ui_preferences" in source


def test_loading_a_silent_project_is_still_legacy():
    """Only *creation* changed. A file that says nothing is still legacy."""

    from motor_calculator.winding.authority import WindingAuthority
    from motor_calculator.winding.persistence import from_preferences as winding_prefs

    state = winding_prefs({}, stored_manual_winding_factor=0.93)
    assert state.authority is WindingAuthority.LEGACY_MANUAL
    assert state.manual_winding_factor == 0.93


def test_dashboard_summary_reports_the_production_authority_and_fill():
    from motor_calculator.input_ux import APPLICATION_DEFAULTS
    from motor_calculator.winding.dashboard_summary import (
        build_winding_dashboard_summary,
        render_winding_dashboard_summary_zh,
    )
    from motor_calculator.winding.evaluation import evaluate_winding

    parameters = dict(APPLICATION_DEFAULTS)
    parameters["coil_span_slots"] = 1
    summary = build_winding_dashboard_summary(
        evaluate_winding(parameters, authority="AUTO_FROM_GEOMETRY")
    )
    assert summary.authority == "AUTO_FROM_GEOMETRY"
    assert summary.production_winding_factor == pytest.approx(math.sqrt(3) / 2)
    assert summary.provenance == "IDEAL_SLOT_STAR_GEOMETRY"
    rendered = render_winding_dashboard_summary_zh(summary)
    assert "生产绕组系数" in rendered and "槽利用率状态" in rendered


def test_dashboard_summary_never_shows_the_meshed_factor():
    from motor_calculator.input_ux import APPLICATION_DEFAULTS
    from motor_calculator.winding.dashboard_summary import build_winding_dashboard_summary
    from motor_calculator.winding.evaluation import evaluate_winding

    parameters = dict(APPLICATION_DEFAULTS)
    parameters["coil_span_slots"] = 1
    summary = build_winding_dashboard_summary(
        evaluate_winding(
            parameters, authority="AUTO_FROM_GEOMETRY", meshed_winding_factor=0.9557520
        )
    )
    assert summary.production_winding_factor != pytest.approx(0.9557520, rel=1e-3)
    assert summary.provenance != "MESHED_GEOMETRY_FEA_DIAGNOSTIC_ONLY"


def test_the_winding_dialog_and_the_dashboard_share_one_evaluation():
    """One computation, two views: they cannot drift apart."""

    dialog_source = (
        REPOSITORY_ROOT / "motor_calculator" / "gui" / "winding_dialog.py"
    ).read_text(encoding="utf-8")
    assert "from ..winding.evaluation import evaluate_winding" in dialog_source
    assert "compute_slot_fill" not in dialog_source


# ===========================================================================
# Part A: taxonomy and schema (Steps 3-4)
# ===========================================================================


def test_the_four_source_classes_exist():
    assert {item.value for item in DatasetSourceType} == {
        "USER_EXPERIMENT", "PUBLIC_REFERENCE_EXPERIMENT",
        "SIMULATED_REFERENCE", "METHODOLOGY_ONLY",
    }


def test_only_measurements_are_experimental():
    assert is_experimental(DatasetSourceType.USER_EXPERIMENT)
    assert is_experimental(DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT)
    assert not is_experimental(DatasetSourceType.SIMULATED_REFERENCE)
    assert not is_experimental(DatasetSourceType.METHODOLOGY_ONLY)


def test_simulation_can_never_be_relabelled_as_experiment():
    for target in (
        DatasetSourceType.USER_EXPERIMENT,
        DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT,
    ):
        assert not may_reclassify(DatasetSourceType.SIMULATED_REFERENCE, target)
        with pytest.raises(ReclassificationError):
            require_reclassifiable(DatasetSourceType.SIMULATED_REFERENCE, target)


def test_public_measurements_are_never_relabelled_as_user_experiments():
    assert not may_reclassify(
        DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT, DatasetSourceType.USER_EXPERIMENT
    )
    with pytest.raises(ReclassificationError):
        _metadata(source_type=DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT).reclassified(
            DatasetSourceType.USER_EXPERIMENT
        )


def test_weakening_a_claim_is_allowed():
    dataset = _metadata(source_type=DatasetSourceType.USER_EXPERIMENT)
    assert (
        dataset.reclassified(DatasetSourceType.SIMULATED_REFERENCE).source_type
        is DatasetSourceType.SIMULATED_REFERENCE
    )


def test_unknown_is_not_a_number_and_is_falsy():
    assert not UNKNOWN
    assert UNKNOWN == "UNKNOWN"
    assert str(UNKNOWN) == "UNKNOWN"
    assert UNKNOWN != 0


def test_metadata_requires_only_what_cannot_be_missing():
    dataset = DatasetMetadata(
        dataset_id="x", title="y",
        source_type=DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT,
        test_type=TestType.NO_LOAD_BACK_EMF,
    )
    assert dataset.operator == UNKNOWN
    assert dataset.measurement_date == UNKNOWN
    assert dataset.machine.pole_count == UNKNOWN


def test_metadata_round_trips_with_unknowns_intact():
    original = DatasetMetadata(
        dataset_id="ds", title="t",
        source_type=DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT,
        test_type=TestType.EFFICIENCY,
        machine=MachineIdentity(pole_count=16, slot_count=UNKNOWN),
        citation=Citation(doi="10.0000/x", redistribution=RedistributionStatus.NOT_ALLOWED),
    )
    restored = metadata_from_payload(json.loads(json.dumps(metadata_to_payload(original))))
    assert restored.machine.pole_count == 16
    assert restored.machine.slot_count == UNKNOWN
    assert restored.citation.doi == "10.0000/x"
    assert restored.citation.redistribution is RedistributionStatus.NOT_ALLOWED
    assert restored.source_type is original.source_type


def test_future_test_types_are_declared_but_not_implemented():
    assert TestType.INDUCTANCE in TestType
    assert not _metadata(test_type=TestType.INDUCTANCE).analysis_implemented
    assert _metadata(test_type=TestType.NO_LOAD_BACK_EMF).analysis_implemented


# ===========================================================================
# Part B: CSV import (Steps 5-7)
# ===========================================================================

CLEAN_KE_CSV = """# a bench run
speed_rpm,line_voltage_rms_v,temperature_c

600,13.856,24.0
1200,27.713,24.5
1800,41.569,25.1
"""


def test_a_clean_csv_imports_with_comments_and_blank_lines_skipped():
    dataset = import_csv_text(CLEAN_KE_CSV, test_type=TestType.NO_LOAD_BACK_EMF)
    assert dataset.ok
    assert dataset.sample_count == 3
    assert dataset.rows[0].values["speed_rpm"] == 600.0


def test_missing_values_are_missing_not_zero():
    dataset = import_csv_text(
        "speed_rpm,line_voltage_rms_v,temperature_c\n600,13.8,n/a\n1200,27.7,\n",
        test_type=TestType.NO_LOAD_BACK_EMF,
    )
    assert dataset.ok
    for row in dataset.rows:
        assert "temperature_c" not in row.values
        assert "temperature_c" in row.missing
        assert row.get("temperature_c") is None


def test_malformed_numbers_are_rejected_with_a_location():
    dataset = import_csv_text(
        "speed_rpm,line_voltage_rms_v\n600,13.8\n1200,twelve\n",
        test_type=TestType.NO_LOAD_BACK_EMF,
    )
    assert not dataset.ok
    error = next(item for item in dataset.errors if item.code == "NOT_A_NUMBER")
    assert error.line == 3
    assert error.column == "line_voltage_rms_v"


def test_a_decimal_comma_is_an_error_not_a_truncation():
    dataset = import_csv_text(
        "speed_rpm,line_voltage_rms_v\n600,13,8\n", test_type=TestType.NO_LOAD_BACK_EMF
    )
    assert not dataset.ok
    assert any(item.code == "COLUMN_COUNT_MISMATCH" for item in dataset.errors)


def test_an_ambiguous_voltage_column_is_refused_with_the_alternatives():
    dataset = import_csv_text(
        "RPM,Voltage\n600,13.8\n", test_type=TestType.NO_LOAD_BACK_EMF
    )
    assert not dataset.ok
    error = next(item for item in dataset.errors if item.code == "AMBIGUOUS_COLUMN")
    assert "line_voltage_rms_v" in error.message_zh
    assert "phase_voltage_rms_v" in error.message_zh


def test_an_explicit_mapping_resolves_the_ambiguity():
    dataset = import_csv_text(
        "RPM,Voltage\n600,13.856\n1200,27.713\n",
        test_type=TestType.NO_LOAD_BACK_EMF,
        column_mapping={"Voltage": "line_voltage_rms_v"},
    )
    assert dataset.ok
    binding = next(b for b in dataset.bindings if b.canonical == "line_voltage_rms_v")
    assert binding.mapping_provenance == "EXPLICIT_MAPPING"


def test_several_header_spellings_reach_the_same_canonical_field():
    for header in ("RPM", "Speed", "Motor Speed (rpm)", "speed_rpm", "Shaft Speed"):
        assert resolve_header(header).name == "speed_rpm"


def test_an_unknown_header_is_ignored_not_guessed():
    dataset = import_csv_text(
        "speed_rpm,line_voltage_rms_v,operator_initials\n600,13.8,ZW\n",
        test_type=TestType.NO_LOAD_BACK_EMF,
    )
    assert "operator_initials" in dataset.ignored_headers
    with pytest.raises(UnknownColumnError):
        resolve_header("operator_initials")


def test_ambiguity_is_raised_rather_than_scored():
    with pytest.raises(AmbiguousColumnError):
        resolve_header("Current")


def test_a_missing_required_column_is_reported():
    dataset = import_csv_text(
        "speed_rpm,temperature_c\n600,24\n", test_type=TestType.NO_LOAD_BACK_EMF
    )
    assert not dataset.ok
    assert any(item.code == "MISSING_REQUIRED_COLUMN" for item in dataset.errors)


def test_an_empty_file_is_an_error_not_an_empty_dataset():
    dataset = import_csv_text("\n# only a comment\n", test_type=TestType.NO_LOAD_BACK_EMF)
    assert not dataset.ok
    assert dataset.errors[0].code == "EMPTY_FILE"


def test_import_is_deterministic(tmp_path):
    path = tmp_path / "run.csv"
    path.write_text(CLEAN_KE_CSV, encoding="utf-8")
    first = import_csv_file(path, test_type=TestType.NO_LOAD_BACK_EMF)
    second = import_csv_file(path, test_type=TestType.NO_LOAD_BACK_EMF)
    assert first.raw_sha256 == second.raw_sha256
    assert [row.values for row in first.rows] == [row.values for row in second.rows]


def test_the_recorded_hash_is_the_hash_of_the_bytes_read(tmp_path):
    path = tmp_path / "run.csv"
    path.write_text(CLEAN_KE_CSV, encoding="utf-8")
    dataset = import_csv_file(path, test_type=TestType.NO_LOAD_BACK_EMF)
    assert dataset.raw_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


def test_strict_import_raises_on_any_error(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("speed_rpm,line_voltage_rms_v\n600,oops\n", encoding="utf-8")
    with pytest.raises(CsvImportRejected):
        import_csv_strict(path, test_type=TestType.NO_LOAD_BACK_EMF)


# ===========================================================================
# Unit normalisation (Step 6)
# ===========================================================================


def test_units_normalise_without_losing_the_original():
    value = normalize(1800.0, "rpm")
    assert value.original_value == 1800.0 and value.original_unit == "rpm"
    torque = normalize(120.0, "mNm")
    assert torque.value == pytest.approx(0.12)
    assert torque.original_value == 120.0 and torque.original_unit == "mNm"
    assert torque.unit == "Nm"


def test_named_conversions_are_exact():
    assert normalize(50.0, "mOhm").value == pytest.approx(0.05)
    assert normalize(1500.0, "mV").value == pytest.approx(1.5)
    assert rpm_to_rad_per_s(1800.0) == pytest.approx(1800.0 * 2.0 * math.pi / 60.0)


def test_temperature_stays_celsius_and_offsets_correctly():
    assert normalize(25.0, "degC").value == 25.0
    assert normalize(298.15, "K").value == pytest.approx(25.0)
    assert normalize(77.0, "degF").value == pytest.approx(25.0)


def test_a_header_unit_suffix_is_applied(tmp_path):
    dataset = import_csv_text(
        "Motor Speed (rpm),Phase Voltage RMS (mV)\n600,8025.6\n1200,16051.2\n",
        test_type=TestType.NO_LOAD_BACK_EMF,
    )
    assert dataset.ok
    assert dataset.rows[0].values["phase_voltage_rms_v"] == pytest.approx(8.0256)
    assert dataset.rows[0].normalized["phase_voltage_rms_v"].original_unit == "mV"


def test_a_unit_of_the_wrong_quantity_is_rejected():
    with pytest.raises(UnitError):
        normalize(10.0, "rpm", expected_canonical="Nm")
    dataset = import_csv_text(
        "speed_rpm,line_voltage_rms_v (Nm)\n600,13.8\n", test_type=TestType.NO_LOAD_BACK_EMF
    )
    assert any(item.code == "BAD_UNIT" for item in dataset.errors)


def test_an_unrecognised_unit_is_an_error_not_an_assumption():
    with pytest.raises(UnitError):
        normalize(1.0, "furlongs")


# ===========================================================================
# Regression (Step 9)
# ===========================================================================


def test_a_free_intercept_recovers_an_offset():
    fit = fit_line([1.0, 2.0, 3.0, 4.0], [3.0, 5.0, 7.0, 9.0])
    assert fit.slope == pytest.approx(2.0)
    assert fit.intercept == pytest.approx(1.0)
    assert fit.r_squared == pytest.approx(1.0)
    assert not fit.intercept_forced_zero


def test_forcing_the_intercept_requires_a_reason():
    with pytest.raises(RegressionError):
        fit_line([1.0, 2.0], [2.0, 4.0], force_zero_intercept=True)
    fit = fit_line(
        [1.0, 2.0], [2.0, 4.0], force_zero_intercept=True, force_reason_zh="测试"
    )
    assert fit.intercept == 0.0 and fit.note_zh == "测试"


def test_one_point_is_a_ratio_not_a_fit():
    fit = fit_line([2.0], [4.0])
    assert fit.slope == pytest.approx(2.0)
    assert fit.r_squared is None
    assert fit.is_single_point
    assert not fit.is_well_conditioned


def test_repeated_measurements_at_one_speed_determine_no_slope():
    with pytest.raises(RegressionError):
        fit_line([1800.0, 1800.0, 1800.0], [41.0, 41.1, 40.9])


# ===========================================================================
# Ke (Steps 9-11)
# ===========================================================================


def test_ke_is_fitted_from_every_speed_point():
    rows = SyntheticBackEmf(0.12, 0.0, (600.0, 1200.0, 1800.0, 2400.0)).rows()
    result = analyze_back_emf(rows, connection=Connection.WYE)
    assert result.used_sample_count == 4
    assert result.ke_v_per_rad_s == pytest.approx(0.12 / math.sqrt(3))
    assert result.r_squared == pytest.approx(1.0)


def test_ke_does_not_collapse_to_a_single_point_when_more_exist():
    rows = SyntheticBackEmf(0.12, 0.5, (600.0, 1200.0, 1800.0)).rows()
    result = analyze_back_emf(rows, connection=Connection.WYE)
    assert not result.fit.is_single_point
    single = analyze_back_emf(rows[:1], connection=Connection.WYE)
    assert single.ke_v_per_rad_s != pytest.approx(result.ke_v_per_rad_s)


def test_a_measurement_offset_is_reported_not_absorbed_into_ke():
    rows = SyntheticBackEmf(0.12, 1.5, (600.0, 1200.0, 1800.0, 2400.0)).rows()
    result = analyze_back_emf(rows, connection=Connection.WYE)
    assert result.ke_v_per_rad_s == pytest.approx(0.12 / math.sqrt(3))
    assert result.intercept_v == pytest.approx(1.5 / math.sqrt(3))
    assert any("截距" in warning for warning in result.warnings_zh)


def test_the_intercept_is_free_unless_explicitly_forced():
    rows = SyntheticBackEmf(0.12, 1.5, (600.0, 1200.0, 1800.0)).rows()
    assert not analyze_back_emf(rows, connection=Connection.WYE).fit.intercept_forced_zero
    forced = analyze_back_emf(
        rows, connection=Connection.WYE,
        force_zero_intercept=True, force_reason_zh="用户确认零点已校准",
    )
    assert forced.fit.intercept_forced_zero
    assert forced.ke_v_per_rad_s != pytest.approx(0.12 / math.sqrt(3))


def test_line_and_phase_voltages_are_not_mixed():
    conversion = voltage_conversion(
        VoltageBasis.LINE_RMS, VoltageBasis.PHASE_RMS, connection=Connection.WYE
    )
    assert conversion.factor == pytest.approx(1.0 / math.sqrt(3))
    assert conversion.is_exact
    peak = voltage_conversion(VoltageBasis.PHASE_PEAK, VoltageBasis.PHASE_RMS)
    assert peak.factor == pytest.approx(1.0 / math.sqrt(2))
    assert not peak.is_exact
    assert "正弦" in peak.assumption_zh


def test_line_to_phase_is_refused_when_the_connection_is_unknown():
    with pytest.raises(ValueError, match="connection"):
        voltage_conversion(
            VoltageBasis.LINE_RMS, VoltageBasis.PHASE_RMS, connection=Connection.UNKNOWN
        )


def test_a_delta_connection_gives_a_different_answer_than_wye():
    rows = SyntheticBackEmf(0.12, 0.0, (600.0, 1200.0, 1800.0)).rows()
    wye = analyze_back_emf(rows, connection=Connection.WYE)
    delta = analyze_back_emf(rows, connection=Connection.DELTA)
    assert delta.ke_v_per_rad_s / wye.ke_v_per_rad_s == pytest.approx(math.sqrt(3))


def test_an_electrical_speed_basis_needs_the_pole_pairs():
    rows = SyntheticBackEmf(0.12, 0.0, (600.0, 1200.0)).rows()
    with pytest.raises(AnalysisError):
        analyze_back_emf(
            rows, connection=Connection.WYE,
            speed_basis=SpeedBasis.ELECTRICAL_RAD_PER_S,
        )
    result = analyze_back_emf(
        rows, connection=Connection.WYE,
        speed_basis=SpeedBasis.ELECTRICAL_RAD_PER_S, pole_pairs=8,
    )
    assert result.speed_basis is SpeedBasis.ELECTRICAL_RAD_PER_S
    mechanical = analyze_back_emf(rows, connection=Connection.WYE)
    assert result.ke_v_per_rad_s == pytest.approx(mechanical.ke_v_per_rad_s / 8.0)


def test_unusable_rows_are_excluded_by_name():
    from motor_calculator.experiment.csv_import import rows_from_records

    rows = rows_from_records(
        [
            {"speed_rpm": 600.0, "line_voltage_rms_v": 13.8},
            {"speed_rpm": 1200.0},
            {"line_voltage_rms_v": 27.7},
            {"speed_rpm": 1800.0, "line_voltage_rms_v": 41.5},
        ]
    )
    result = analyze_back_emf(rows, connection=Connection.WYE)
    assert result.used_sample_count == 2
    assert len(result.excluded_rows) == 2
    assert all(reason for _line, reason in result.excluded_rows)


# ===========================================================================
# Resistance (Step 12)
# ===========================================================================


def test_wye_and_delta_give_different_phase_resistances():
    rows = synthetic_resistance_rows(0.200)
    wye = analyze_phase_resistance(rows, connection=Connection.WYE)
    delta = analyze_phase_resistance(rows, connection=Connection.DELTA)
    assert wye.phase_resistance_ohm == pytest.approx(0.100)
    assert delta.phase_resistance_ohm == pytest.approx(0.300)


def test_an_unknown_connection_yields_no_phase_resistance():
    result = analyze_phase_resistance(
        synthetic_resistance_rows(0.200), connection=Connection.UNKNOWN
    )
    assert result.measured_terminal_resistance_ohm == pytest.approx(0.200)
    assert result.phase_resistance_ohm is None
    assert any("接法未知" in warning for warning in result.warnings_zh)


def test_resistance_is_never_temperature_corrected_without_being_asked():
    result = analyze_phase_resistance(
        synthetic_resistance_rows(0.200, temperature_c=80.0), connection=Connection.WYE
    )
    assert result.normalized_phase_resistance_ohm is None
    assert result.normalization_provenance == "NONE"
    assert result.measurement_temperature_c == pytest.approx(80.0)


def test_temperature_normalisation_records_its_provenance():
    result = analyze_phase_resistance(
        synthetic_resistance_rows(0.200, temperature_c=80.0),
        connection=Connection.WYE,
        normalize_to_temperature_c=20.0,
    )
    assert result.normalized_phase_resistance_ohm is not None
    assert result.normalized_phase_resistance_ohm < result.phase_resistance_ohm
    assert "EXPLICIT_REQUEST" in result.normalization_provenance


def test_normalisation_without_a_measurement_temperature_does_nothing():
    from motor_calculator.experiment.csv_import import rows_from_records

    result = analyze_phase_resistance(
        rows_from_records([{"measured_resistance_ohm": 0.2}]),
        connection=Connection.WYE,
        normalize_to_temperature_c=20.0,
    )
    assert result.normalized_phase_resistance_ohm is None
    assert "NO_MEASUREMENT_TEMPERATURE" in result.normalization_provenance


def test_resistance_can_come_from_applied_voltage_and_current():
    from motor_calculator.experiment.csv_import import rows_from_records

    result = analyze_phase_resistance(
        rows_from_records([{"applied_voltage_v": 1.0, "applied_current_a": 5.0}]),
        connection=Connection.WYE,
    )
    assert result.measured_terminal_resistance_ohm == pytest.approx(0.2)


# ===========================================================================
# Torque-current (Step 13)
# ===========================================================================


def test_a_torque_current_slope_is_not_called_kt_without_semantics():
    rows = SyntheticTorqueCurrent(0.21, 0.0, (2.0, 4.0, 6.0, 8.0)).rows()
    result = analyze_torque_current(rows)
    assert result.slope_nm_per_a == pytest.approx(0.21)
    assert not result.supports_kt_claim
    assert any("电流语义" in item for item in result.limitations_zh)


def test_declaring_the_semantics_permits_the_kt_claim():
    rows = SyntheticTorqueCurrent(0.21, 0.0, (2.0, 4.0, 6.0, 8.0)).rows()
    result = analyze_torque_current(
        rows, current_semantics_known=True, operating_point_known=True
    )
    assert result.supports_kt_claim
    assert not result.limitations_zh


def test_friction_appears_as_an_intercept_limitation():
    rows = SyntheticTorqueCurrent(0.21, 0.05, (2.0, 4.0, 6.0)).rows()
    result = analyze_torque_current(
        rows, current_semantics_known=True, operating_point_known=True
    )
    assert result.fit.intercept == pytest.approx(0.05)
    assert any("截距" in item for item in result.limitations_zh)
    assert not result.supports_kt_claim


def test_a_multi_speed_torque_sweep_says_it_crosses_operating_points():
    from motor_calculator.experiment.csv_import import rows_from_records

    result = analyze_torque_current(
        rows_from_records(
            [
                {"speed_rpm": 900.0, "phase_current_rms_a": 2.0, "torque_nm": 0.42},
                {"speed_rpm": 1800.0, "phase_current_rms_a": 4.0, "torque_nm": 0.84},
            ]
        ),
        current_semantics_known=True, operating_point_known=True,
    )
    assert any("转速" in item for item in result.limitations_zh)


# ===========================================================================
# Efficiency (Step 14)
# ===========================================================================


def test_efficiency_is_derived_from_torque_speed_and_bus_power():
    rows = synthetic_efficiency_rows(((1800.0, 3.0, 72.0, 8.5),))
    result = analyze_efficiency(rows)
    point = result.points[0]
    assert point.derived_output_power_w == pytest.approx(3.0 * rpm_to_rad_per_s(1800.0))
    assert point.derived_input_power_w == pytest.approx(612.0)
    assert point.efficiency == pytest.approx(point.derived_output_power_w / 612.0)


def test_a_measured_power_is_never_overwritten_by_a_derived_one():
    from motor_calculator.experiment.csv_import import rows_from_records

    result = analyze_efficiency(
        rows_from_records(
            [
                {
                    "speed_rpm": 1800.0, "torque_nm": 3.0,
                    "dc_bus_voltage_v": 72.0, "dc_bus_current_a": 8.5,
                    "input_power_w": 600.0,
                }
            ]
        )
    )
    point = result.points[0]
    assert point.measured_input_power_w == pytest.approx(600.0)
    assert point.input_power_source == "MEASURED"
    assert point.input_power_w == pytest.approx(600.0)


def test_a_bus_derived_efficiency_states_the_inverter_boundary():
    result = analyze_efficiency(synthetic_efficiency_rows(((1800.0, 3.0, 72.0, 8.5),)))
    assert result.includes_inverter_losses
    assert "逆变器" in result.boundary_zh


def test_an_efficiency_above_one_is_flagged_not_clipped():
    from motor_calculator.experiment.csv_import import rows_from_records

    result = analyze_efficiency(
        rows_from_records([{"speed_rpm": 1800.0, "torque_nm": 3.0,
                            "dc_bus_voltage_v": 72.0, "dc_bus_current_a": 1.0}])
    )
    assert result.points[0].efficiency > 1.0
    assert result.warnings_zh


# ===========================================================================
# Machine compatibility (Step 16)
# ===========================================================================


def test_the_same_machine_is_recognised():
    assessment = assess_compatibility(
        AFPM, project_machine_identity(PROJECT_PARAMS, connection="WYE")
    )
    assert assessment.status is MachineCompatibility.SAME_MACHINE


def test_a_different_pole_count_is_a_different_machine():
    other = MachineIdentity(
        topology="AFPM_DUAL_ROTOR_SINGLE_STATOR", pole_count=20, slot_count=24, phases=3
    )
    assessment = assess_compatibility(
        other, project_machine_identity(PROJECT_PARAMS)
    )
    assert assessment.status is MachineCompatibility.DIFFERENT_MACHINE
    assert any(item.field == "pole_count" for item in assessment.conflicts)


def test_a_different_build_of_the_same_design_is_a_compatible_reference():
    other = MachineIdentity(
        topology="AFPM_DUAL_ROTOR_SINGLE_STATOR", pole_count=16, slot_count=24,
        phases=3, connection="WYE", turns_per_phase=60,
    )
    assessment = assess_compatibility(
        other, project_machine_identity(PROJECT_PARAMS, connection="WYE")
    )
    assert assessment.status is MachineCompatibility.COMPATIBLE_REFERENCE


def test_an_unknown_machine_is_not_assumed_to_be_this_one():
    assessment = assess_compatibility(
        MachineIdentity(), project_machine_identity(PROJECT_PARAMS)
    )
    assert assessment.status is MachineCompatibility.INSUFFICIENT_METADATA
    assert assessment.status is not MachineCompatibility.SAME_MACHINE


def test_only_same_machine_experiments_may_validate_the_design():
    assert may_validate_current_design(
        DatasetSourceType.USER_EXPERIMENT, MachineCompatibility.SAME_MACHINE
    )
    assert may_validate_current_design(
        DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT, MachineCompatibility.SAME_MACHINE
    )
    assert not may_validate_current_design(
        DatasetSourceType.SIMULATED_REFERENCE, MachineCompatibility.SAME_MACHINE
    )
    for status in (
        MachineCompatibility.COMPATIBLE_REFERENCE,
        MachineCompatibility.DIFFERENT_MACHINE,
        MachineCompatibility.INSUFFICIENT_METADATA,
    ):
        assert not may_validate_current_design(DatasetSourceType.USER_EXPERIMENT, status)


# ===========================================================================
# Comparison and the evidence firewall (Steps 11, 15, 19)
# ===========================================================================


def _comparison(source_type, machine, ke=0.0693):
    dataset = _metadata(source_type=source_type, machine=machine)
    return build_quantity_comparison(
        quantity="ke_phase_rms_v_per_rad_s",
        quantity_label_zh="Ke", unit="V/(rad/s)", basis_zh="PHASE_RMS / MECHANICAL",
        analytical=analytical_entry(0.0692, "V/(rad/s)"),
        fea=fea_entry(0.0742, "V/(rad/s)"),
        measured=measurement_entry(ke, "V/(rad/s)", metadata=dataset, sample_count=4),
        dataset=dataset,
        compatibility=assess_compatibility(
            machine, project_machine_identity(PROJECT_PARAMS, connection="WYE")
        ),
    )


def test_a_same_machine_measurement_supports_an_experimental_claim():
    comparison = _comparison(DatasetSourceType.USER_EXPERIMENT, AFPM)
    assert comparison.overall_claim is OverallClaim.EXPERIMENTALLY_SUPPORTED
    assert comparison.is_affirmative


def test_a_different_machine_measurement_cannot_validate_this_design():
    other = MachineIdentity(
        topology="RADIAL_FLUX_INNER_ROTOR", pole_count=20, slot_count=24, phases=3
    )
    comparison = _comparison(DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT, other)
    assert comparison.overall_claim is OverallClaim.METHODOLOGY_REFERENCE_ONLY
    assert not comparison.is_affirmative


def test_a_tiny_residual_does_not_upgrade_a_different_machine():
    """The dangerous case: real data, perfect agreement, wrong machine."""

    other = MachineIdentity(
        topology="RADIAL_FLUX_INNER_ROTOR", pole_count=20, slot_count=24, phases=3
    )
    comparison = _comparison(DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT, other, ke=0.0692)
    residual = next(
        item for item in comparison.residuals if item.subject == "ANALYTICAL_MODEL"
        and item.reference == "MEASURED"
    )
    assert abs(residual.relative_percent) < 0.01
    assert not comparison.is_affirmative
    assert any("残差小并不改变证据类别" in item for item in comparison.limitations_zh)


def test_a_simulated_dataset_is_a_cross_check_not_a_measurement():
    comparison = _comparison(DatasetSourceType.SIMULATED_REFERENCE, AFPM)
    assert comparison.overall_claim is OverallClaim.SIMULATION_CROSS_CHECK_ONLY
    assert comparison.measured.evidence_label == "NUMERICAL_FEA"
    assert comparison.measured.evidence_label != "EXPERIMENTAL_MEASUREMENT"


def test_an_analytical_entry_cannot_claim_to_be_a_measurement():
    from motor_calculator.experiment.comparison import EvidenceEntry, EvidenceLayer

    with pytest.raises(ValueError):
        EvidenceEntry(
            layer=EvidenceLayer.ANALYTICAL_MODEL, value=1.0, unit="V",
            label_zh="x", evidence_label="EXPERIMENTAL_MEASUREMENT",
        )


def test_an_experimental_claim_cannot_be_constructed_without_the_evidence():
    dataset = _metadata(source_type=DatasetSourceType.SIMULATED_REFERENCE)
    from motor_calculator.experiment.comparison import QuantityComparison

    with pytest.raises(ValueError):
        QuantityComparison(
            schema_version="x", quantity="q", quantity_label_zh="q", unit="V",
            basis_zh="b", analytical=None, fea=None,
            measured=measurement_entry(1.0, "V", metadata=dataset),
            dataset=dataset, compatibility=None, residuals=(),
            overall_claim=OverallClaim.EXPERIMENTALLY_SUPPORTED,
            claim_label_zh="x", claim_reason_zh="x",
        )


def test_the_no_data_state_is_explicit():
    overview = build_overview((), ())
    assert overview.state == NO_EXPERIMENTAL_DATA
    assert not overview.has_experimental_data
    assert not overview.has_any_affirmative_claim
    assert "NO_EXPERIMENTAL_DATA" in overview.message_zh
    # The message must explicitly disclaim the three things a naive empty state
    # would show instead: a zero, a placeholder value, and a pass.
    assert "不显示 0" in overview.message_zh
    assert "占位测量值" in overview.message_zh
    assert "验证通过" in overview.message_zh
    assert overview.comparisons == ()


def test_simulated_datasets_alone_still_count_as_no_experimental_data():
    dataset = _metadata(source_type=DatasetSourceType.SIMULATED_REFERENCE)
    overview = build_overview((), (dataset,))
    assert overview.state == NO_EXPERIMENTAL_DATA
    assert overview.experimental_dataset_count == 0


# ===========================================================================
# Fixture firewall (Step 21)
# ===========================================================================


def test_a_fixture_is_always_simulated_and_always_flagged():
    fixture = synthetic_dataset("fx.1", test_type=TestType.NO_LOAD_BACK_EMF)
    assert fixture.source_type is DatasetSourceType.SIMULATED_REFERENCE
    assert fixture.test_fixture_only
    assert not fixture.is_experimental


def test_a_fixture_claiming_to_be_experimental_is_refused():
    with pytest.raises(ValueError, match="SIMULATED_REFERENCE"):
        DatasetMetadata(
            dataset_id="x", title="y",
            source_type=DatasetSourceType.USER_EXPERIMENT,
            test_type=TestType.NO_LOAD_BACK_EMF,
            test_fixture_only=True,
        )


def test_a_fixture_is_refused_at_the_production_boundary():
    fixture = synthetic_dataset("fx.2", test_type=TestType.NO_LOAD_BACK_EMF)
    assert not is_production_admissible(fixture)
    with pytest.raises(FixtureLeakError):
        require_production_admissible(fixture)


def test_a_fixture_never_appears_in_the_production_dataset_list(tmp_path):
    service = ValidationDataService(DatasetStore(tmp_path / "store"))
    with pytest.raises(FixtureLeakError):
        service.add_manual(
            [{"speed_rpm": 600.0, "line_voltage_rms_v": 13.8}],
            metadata=synthetic_dataset("fx.3", test_type=TestType.NO_LOAD_BACK_EMF),
        )
    assert service.production_datasets() == ()


def test_the_fixture_module_is_not_shipped_as_a_hidden_import():
    """Test fixtures have no business inside the packaged application."""

    spec = (REPOSITORY_ROOT / "packaging" / "MotorCalculator.spec").read_text(
        encoding="utf-8"
    )
    assert "motor_calculator.experiment.service" in spec
    assert "motor_calculator.experiment.fixtures" not in spec


def test_the_packaged_build_declares_every_lazily_imported_module():
    """A lazy import PyInstaller cannot see becomes an ImportError at runtime."""

    spec = (REPOSITORY_ROOT / "packaging" / "MotorCalculator.spec").read_text(
        encoding="utf-8"
    )
    for module in (
        "motor_calculator.gui.validation_data_dialog",
        "motor_calculator.winding.evaluation",
        "motor_calculator.winding.dashboard_summary",
        "motor_calculator.experiment.comparison",
        "motor_calculator.experiment.compatibility",
        "motor_calculator.experiment.report",
        "motor_calculator.experiment.templates",
    ):
        assert module in spec, module


# ===========================================================================
# Templates (Step 8)
# ===========================================================================


def test_every_implemented_test_type_has_a_template():
    for test_type in (
        TestType.NO_LOAD_BACK_EMF, TestType.PHASE_RESISTANCE,
        TestType.TORQUE_CURRENT, TestType.EFFICIENCY,
    ):
        assert test_type in TEMPLATES


def test_the_ke_template_offers_both_voltages_and_requires_neither():
    template = TEMPLATES[TestType.NO_LOAD_BACK_EMF]
    voltages = [c for c in template.columns if "voltage" in c.name]
    assert len(voltages) == 2
    assert not any(column.required for column in voltages)
    assert any(column.name == "speed_rpm" and column.required for column in template.columns)


def test_a_template_round_trips_through_the_importer(tmp_path):
    """The file we hand the user must be one our own parser accepts."""

    path = export_template(TestType.NO_LOAD_BACK_EMF, tmp_path)
    text = path.read_text(encoding="utf-8")
    filled = text + "600,13.856,,24.0\n1200,27.713,,24.5\n1800,41.569,,25.1\n"
    dataset = import_csv_text(filled, test_type=TestType.NO_LOAD_BACK_EMF)
    assert dataset.ok, [str(error) for error in dataset.errors]
    assert dataset.sample_count == 3
    assert dataset.rows[0].values["line_voltage_rms_v"] == pytest.approx(13.856)
    assert "phase_voltage_rms_v" in dataset.rows[0].missing


def test_a_template_tells_the_user_not_to_fill_missing_values_with_zero():
    assert "不要填 0" in build_template_csv(TestType.NO_LOAD_BACK_EMF)


# ===========================================================================
# Persistence (Step 22)
# ===========================================================================


def _write_ke_file(path: Path) -> Path:
    path.write_text(CLEAN_KE_CSV, encoding="utf-8")
    return path


def test_a_dataset_round_trips_through_project_preferences(tmp_path):
    service = ValidationDataService(DatasetStore(tmp_path / "store"))
    service.add_from_csv(
        _write_ke_file(tmp_path / "run.csv"),
        metadata=_metadata(),
        comparison_config={"connection": "WYE"},
    )
    preferences = service.to_preferences()

    restored = ValidationDataService(DatasetStore(tmp_path / "store"))
    restored.restore(preferences)
    assert len(restored.datasets) == 1
    item = restored.datasets[0]
    assert item.availability is DatasetAvailability.AVAILABLE
    assert len(item.rows) == 3
    assert item.metadata.machine.pole_count == 16
    assert item.reference.comparison_config["connection"] == "WYE"


def test_the_project_file_holds_a_reference_not_the_samples(tmp_path):
    service = ValidationDataService(DatasetStore(tmp_path / "store"))
    service.add_from_csv(_write_ke_file(tmp_path / "run.csv"), metadata=_metadata())
    payload = service.to_preferences()["experiment.datasets"]
    assert "41.569" not in payload
    assert "stored_relative_path" in payload
    assert len(payload) < 4000


def test_a_project_written_before_this_phase_has_no_datasets():
    references, problems = from_preferences({"input_mode": "ADVANCED"})
    assert references == () and problems == ()


def test_a_missing_data_file_is_reported_not_raised(tmp_path):
    service = ValidationDataService(DatasetStore(tmp_path / "store"))
    service.add_from_csv(_write_ke_file(tmp_path / "run.csv"), metadata=_metadata())
    preferences = service.to_preferences()

    restored = ValidationDataService(DatasetStore(tmp_path / "empty_store"))
    warnings = restored.restore(preferences)
    item = restored.datasets[0]
    assert item.availability is DatasetAvailability.MISSING
    assert item.rows == ()
    assert not item.is_usable
    assert item.metadata.title == "bench run"  # metadata survives the loss
    assert warnings


def test_an_altered_data_file_is_detected(tmp_path):
    store_root = tmp_path / "store"
    service = ValidationDataService(DatasetStore(store_root))
    loaded = service.add_from_csv(_write_ke_file(tmp_path / "run.csv"), metadata=_metadata())
    preferences = service.to_preferences()

    stored = store_root / loaded.reference.stored_relative_path
    stored.write_text(CLEAN_KE_CSV.replace("41.569", "99.999"), encoding="utf-8")

    restored = ValidationDataService(DatasetStore(store_root))
    restored.restore(preferences)
    assert restored.datasets[0].availability is DatasetAvailability.CHANGED
    assert not restored.datasets[0].is_usable


def test_manual_entry_is_stored_inline(tmp_path):
    service = ValidationDataService(DatasetStore(tmp_path / "store"))
    service.add_manual(
        [{"speed_rpm": 600.0, "line_voltage_rms_v": 13.856}],
        metadata=_metadata(dataset_id="manual.1"),
    )
    restored = ValidationDataService(DatasetStore(tmp_path / "store"))
    restored.restore(service.to_preferences())
    assert restored.datasets[0].availability is DatasetAvailability.INLINE
    assert restored.datasets[0].rows[0].values["speed_rpm"] == 600.0


def test_dataset_persistence_does_not_move_the_project_schema():
    from motor_calculator.project.schema import PROJECT_SCHEMA_VERSION

    assert PROJECT_SCHEMA_VERSION == 1


# ===========================================================================
# Report export (Step 23)
# ===========================================================================


def test_the_report_never_says_validated_for_another_machine(tmp_path):
    other = MachineIdentity(
        topology="RADIAL_FLUX_INNER_ROTOR", pole_count=20, slot_count=24, phases=3
    )
    comparison = _comparison(DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT, other)
    overview = build_overview((comparison,), (comparison.dataset,))
    payload = build_report_payload(
        overview, application_version="test", generated_at_utc="2026-09-12T00:00:00+00:00"
    )
    text = render_report_zh(payload)
    assert payload["quantities"][0]["claim"].startswith("NOT_VALIDATED")
    for occurrence in _occurrences(text, VALIDATED_WORD):
        assert text[occurrence - 4 : occurrence] == "NOT_"
    assert not payload["has_any_validated_quantity"]


def _occurrences(text: str, needle: str):
    start = 0
    while (index := text.find(needle, start)) != -1:
        yield index
        start = index + 1


def test_the_report_carries_citation_compatibility_and_limitations(tmp_path):
    dataset = DatasetMetadata(
        dataset_id="pub.1", title="published bench data",
        source_type=DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT,
        test_type=TestType.NO_LOAD_BACK_EMF,
        machine=MachineIdentity(pole_count=20, slot_count=24, phases=3,
                                topology="RADIAL_FLUX_INNER_ROTOR"),
        citation=Citation(doi="10.1234/example", year=2019,
                          redistribution=RedistributionStatus.NOT_ALLOWED),
    )
    comparison = build_quantity_comparison(
        quantity="ke_phase_rms_v_per_rad_s", quantity_label_zh="Ke",
        unit="V/(rad/s)", basis_zh="PHASE_RMS",
        analytical=analytical_entry(0.0692, "V/(rad/s)"),
        measured=measurement_entry(0.0693, "V/(rad/s)", metadata=dataset, sample_count=5),
        dataset=dataset,
        compatibility=assess_compatibility(
            dataset.machine, project_machine_identity(PROJECT_PARAMS)
        ),
    )
    overview = build_overview((comparison,), (dataset,))
    exported = export_validation_report(
        overview, tmp_path, application_version="test",
        generated_at_utc="2026-09-12T00:00:00+00:00",
    )
    payload = json.loads(exported.json_path.read_text(encoding="utf-8"))
    entry = payload["quantities"][0]
    assert entry["dataset"]["citation"]["doi"] == "10.1234/example"
    assert entry["machine_compatibility"] == "DIFFERENT_MACHINE"
    assert entry["sample_count"] == 5
    assert payload["global_limitations_zh"]
    assert payload["calibration_status"] == "NONE"
    assert exported.text_path.read_text(encoding="utf-8")


# ===========================================================================
# Public-reference architecture (Step 20)
# ===========================================================================


def test_unknown_redistribution_is_treated_as_not_permitted():
    assert not may_commit_raw_data(Citation())
    assert not may_commit_raw_data(
        Citation(redistribution=RedistributionStatus.NOT_ALLOWED)
    )
    assert may_commit_raw_data(Citation(redistribution=RedistributionStatus.ALLOWED))


def test_a_public_source_record_carries_no_measurements():
    record = PublicSourceRecord(
        schema_version="v", source_id="src.1",
        citation=Citation(doi="10.1234/x"), machine=MachineIdentity(pole_count=20),
        test_type=TestType.NO_LOAD_BACK_EMF,
        extraction_method=ExtractionMethod.FIGURE_DIGITISATION,
        location_note="Fig. 7", column_mapping={"Speed": "speed_rpm"}, column_units={},
    )
    assert not hasattr(record, "rows")
    assert not hasattr(record, "values")
    metadata = record.to_metadata("pub.1", "digitised curve")
    assert metadata.source_type is DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT
    assert "FIGURE_DIGITISATION" in metadata.data_provenance


def test_no_fabricated_literature_data_ships_with_this_phase():
    """The module prepares for literature; it contains none."""

    source = (
        REPOSITORY_ROOT / "motor_calculator" / "experiment" / "public_reference.py"
    ).read_text(encoding="utf-8")
    assert "doi" in source.lower()
    # No example DOI that looks like a real citation, and no numeric tables.
    assert "10." not in source.replace("10.1234", "")


def test_phase_11b_requirements_are_recorded():
    assert len(PHASE_11B_REQUIREMENTS) >= 5
    assert all(isinstance(item, str) and item for item in PHASE_11B_REQUIREMENTS)


# ===========================================================================
# Service-level behaviour and the GUI contract
# ===========================================================================


def test_the_service_produces_a_full_ke_comparison(tmp_path):
    service = ValidationDataService(DatasetStore(tmp_path / "store"))
    loaded = service.add_from_csv(
        _write_ke_file(tmp_path / "run.csv"),
        metadata=_metadata(),
        comparison_config={"connection": "WYE"},
    )
    comparison = service.build_back_emf_comparison(
        loaded,
        project_parameters=PROJECT_PARAMS,
        analytical_ke_v_per_rad_s=0.0692,
        fea_ke_v_per_rad_s=0.0742,
        connection=Connection.WYE,
        project_connection="WYE",
    )
    assert comparison is not None
    assert comparison.overall_claim is OverallClaim.EXPERIMENTALLY_SUPPORTED
    assert len(comparison.residuals) == 3
    assert comparison.measured.sample_count == 3


def test_an_unimplemented_test_type_is_held_but_not_analysed(tmp_path):
    service = ValidationDataService(DatasetStore(tmp_path / "store"))
    path = tmp_path / "ind.csv"
    path.write_text("speed_rpm,torque_nm\n1800,3.0\n", encoding="utf-8")
    loaded = service.add_from_csv(
        path, metadata=_metadata(dataset_id="ind.1", test_type=TestType.INDUCTANCE)
    )
    assert service.analyze(loaded) is None
    assert loaded in service.datasets


def test_a_dataset_with_import_errors_does_not_participate(tmp_path):
    service = ValidationDataService(DatasetStore(tmp_path / "store"))
    path = tmp_path / "bad.csv"
    path.write_text("speed_rpm,line_voltage_rms_v\n600,oops\n", encoding="utf-8")
    loaded = service.add_from_csv(path, metadata=_metadata(dataset_id="bad.1"))
    assert loaded.import_errors
    assert not loaded.is_usable
    assert service.analyze(loaded) is None


def test_the_overview_is_empty_and_says_so_for_a_new_session(tmp_path):
    service = ValidationDataService(DatasetStore(tmp_path / "store"))
    overview = service.build_overview()
    assert overview.state == NO_EXPERIMENTAL_DATA
    assert overview.dataset_count == 0


# ===========================================================================
# No calibration, no physics mutation
# ===========================================================================


def test_production_physics_is_untouched_by_phase11a():
    path = REPOSITORY_ROOT / "motor_calculator" / "motor_core" / "calculations.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942"
    )


def test_the_legacy_baseline_fixture_is_untouched():
    path = REPOSITORY_ROOT / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"
    )


def test_no_calibration_was_introduced():
    from motor_calculator.fea.comparison import AUTO_CALIBRATION_ENABLED
    from motor_calculator.fea.diagnostics import CALIBRATION_STATUS

    assert AUTO_CALIBRATION_ENABLED is False
    assert CALIBRATION_STATUS == "NONE"

    package = REPOSITORY_ROOT / "motor_calculator" / "experiment"
    negations = ("not ", "no ", "never", "非", "不", "未", "NONE")
    for path in sorted(package.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if "calibrat" not in line.lower() and "标定" not in line:
                continue
            # Naming the calibration_status field or constant is fine: its
            # value is asserted to be NONE above, and it exists precisely to
            # deny calibration.
            if "calibration_status" in line.lower():
                continue
            # The negation may sit on the continuation of a wrapped string, so
            # the guard looks at the statement, not at one physical line.
            window = "".join(lines[index : index + 3])
            assert any(marker in window for marker in negations), f"{path.name}: {line}"


def test_no_fitted_coefficient_enters_a_comparison():
    """Every conversion is an exact ratio or a named definition, never a fit."""

    from motor_calculator.experiment.units import UNIT_DEFINITIONS

    for definition in UNIT_DEFINITIONS:
        assert definition.provenance.startswith(
            ("IDENTITY", "EXACT_SI_PREFIX", "EXACT_DEFINITION")
        )


def test_the_analytical_value_is_never_adjusted_toward_the_measurement():
    comparison = _comparison(DatasetSourceType.USER_EXPERIMENT, AFPM, ke=0.0800)
    assert comparison.analytical.value == pytest.approx(0.0692)
    payload = build_report_payload(
        build_overview((comparison,), (comparison.dataset,)),
        application_version="test", generated_at_utc="2026-09-12T00:00:00+00:00",
    )
    assert payload["quantities"][0]["analytical_value"] == pytest.approx(0.0692)
    assert "corrected" not in json.dumps(payload).lower()
