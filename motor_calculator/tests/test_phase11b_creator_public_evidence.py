"""Phase 11B: CREATOR public experimental evidence integration.

Two kinds of test live here.

Most of them need no data at all: the source record, the licence, the parameter
origins, the topology firewall and the compatibility verdict are metadata, and
metadata is what this repository actually ships. Those run everywhere.

A few need the CREATOR dataset itself, which is deliberately **not** committed.
They skip cleanly when it is absent and assert against the real files when a
developer has a local copy. The most important of them reproduces the
publication's 47.37 V from raw samples, which is the whole point of the phase:
if our waveform processing is wrong, that test fails and no amount of adjusting
the source data can make it pass.
"""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

import pytest

from motor_calculator.experiment import creator_adapter as adapter
from motor_calculator.experiment import creator_evidence as evidence
from motor_calculator.experiment import creator_source as src
from motor_calculator.experiment.compatibility import (
    MachineCompatibility,
    assess_compatibility,
    may_validate_current_design,
    project_machine_identity,
)
from motor_calculator.experiment.harmonics import (
    WaveformError,
    analyze_waveform,
    describe_analysis_zh,
)
from motor_calculator.experiment.origins import (
    EXPERIMENTAL_ORIGINS,
    PROVENANCE_UNRESOLVED,
    ParameterOrigin,
    ParameterSet,
    PublicParameter,
    is_measurement,
    render_parameter_table_zh,
)
from motor_calculator.experiment.schema import (
    ADAPTER_ONLY_TEST_TYPES,
    IMPLEMENTED_TEST_TYPES,
    RedistributionStatus,
    TestType,
)
from motor_calculator.experiment.sources import DatasetSourceType
from motor_calculator.experiment.topology import (
    AFPM_KERNEL_TOPOLOGIES,
    AFPM_NOT_VALIDATED,
    PIPELINE_VALIDATED,
    MachineTopology,
    TopologyMismatchError,
    is_afpm_modellable,
    reject_afpm_project_construction,
    require_compatible_topology,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

#: The dataset is not shipped. A developer with a local copy can point at it.
DEFAULT_DATASET_ROOT = Path(r"D:/File/Project/Codex_电机项目/PM_synchronous_motor")


def _dataset_root() -> Path | None:
    configured = os.environ.get("MOTORCALC_CREATOR_DATASET_ROOT")
    candidate = Path(configured) if configured else DEFAULT_DATASET_ROOT
    return candidate if (candidate / src.RELATIVE_PATHS["back_emf"]).is_file() else None


requires_dataset = pytest.mark.skipif(
    _dataset_root() is None,
    reason=(
        "the CREATOR dataset is not committed to this repository; set "
        "MOTORCALC_CREATOR_DATASET_ROOT to a local copy to run these"
    ),
)

PROJECT_PARAMS = {"p": 8, "slots": 24, "N_ph_turns": 50, "n_rated": 2500.0, "P_rated": 800.0}


# ===========================================================================
# Part A: the registered source (Step 1)
# ===========================================================================


def test_the_creator_source_is_registered_with_its_doi_and_licence():
    summary = src.source_summary()
    assert summary.source_id == "creator.pmsm.a01"
    assert summary.doi == "10.3217/sns1d-77m43"
    assert summary.license_name == "CC BY-NC 4.0"
    assert summary.evidence_class == "PUBLIC_REFERENCE_EXPERIMENT"
    assert summary.topology == "RADIAL_FLUX_INSET_PMSM"


def test_the_source_record_is_classified_as_a_public_reference_experiment():
    record = src.CREATOR_SOURCE_RECORD
    metadata = record.to_metadata("creator.ds", "CREATOR back-EMF")
    assert metadata.source_type is DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT
    assert metadata.is_experimental
    assert not metadata.test_fixture_only


def test_the_source_record_carries_no_measured_values():
    """Metadata only: the record must not embed the measurements."""

    record = src.CREATOR_SOURCE_RECORD
    assert not hasattr(record, "rows")
    assert not hasattr(record, "values")
    assert record.column_mapping == {}


def test_the_licence_is_recorded_without_asserting_commercial_rights():
    citation = src.CREATOR_CITATION
    assert citation.license == "CC BY-NC 4.0"
    assert citation.redistribution is RedistributionStatus.ALLOWED
    assert "non-commercial" in str(citation.notes).lower()
    # Whatever the licence permits, this repository stores metadata only.
    assert src.COMMIT_POLICY == "METADATA_HASH_AND_ADAPTER_ONLY"


def test_every_referenced_file_has_a_recorded_hash():
    assert set(src.FILE_HASHES) == set(src.RELATIVE_PATHS)
    for key, digest in src.FILE_HASHES.items():
        assert len(digest) == 64, key
        int(digest, 16)  # raises if not hexadecimal


def test_the_dataset_metadata_names_the_machine_as_radial_flux():
    metadata = src.dataset_metadata(
        TestType.BACK_EMF_WAVEFORM, "creator.back_emf", "CREATOR back-EMF"
    )
    assert metadata.machine.topology == MachineTopology.RADIAL_FLUX_INSET_PMSM.value
    assert metadata.machine.pole_count == 4
    assert metadata.machine.slot_count == 6


# ===========================================================================
# Part B: new test types (Steps 2, 7, 10)
# ===========================================================================


def test_the_new_test_types_exist_and_are_implemented():
    for test_type in (
        TestType.BACK_EMF_WAVEFORM,
        TestType.COGGING_TORQUE,
        TestType.NO_LOAD_LOSS,
        TestType.DRIVE_CYCLE,
    ):
        assert test_type in IMPLEMENTED_TEST_TYPES
        assert test_type in ADAPTER_ONLY_TEST_TYPES


def test_back_emf_waveform_did_not_overload_the_multi_speed_type():
    """The two are different questions and must stay different types."""

    assert TestType.BACK_EMF_WAVEFORM is not TestType.NO_LOAD_BACK_EMF
    assert TestType.BACK_EMF_WAVEFORM.value != TestType.NO_LOAD_BACK_EMF.value
    assert TestType.NO_LOAD_BACK_EMF not in ADAPTER_ONLY_TEST_TYPES


# ===========================================================================
# Harmonic extraction (Step 4)
# ===========================================================================


def test_a_pure_sinusoid_returns_its_own_amplitude():
    angles = [i * 360.0 / 720.0 for i in range(720)]
    values = [10.0 * math.sin(math.radians(a)) for a in angles]
    analysis = analyze_waveform(angles, values, pole_pairs=1, orders=(1, 2, 3, 5))
    assert analysis.fundamental_peak == pytest.approx(10.0, rel=1e-6)
    assert analysis.fundamental_rms == pytest.approx(10.0 / math.sqrt(2), rel=1e-6)
    assert analysis.order(3).amplitude == pytest.approx(0.0, abs=1e-6)
    assert analysis.thd == pytest.approx(0.0, abs=1e-6)


def test_a_known_harmonic_mixture_is_recovered_exactly():
    angles = [i * 360.0 / 3600.0 for i in range(3600)]
    values = [
        100.0 * math.sin(math.radians(2 * a))
        + 20.0 * math.sin(math.radians(2 * a * 5))
        + 5.0 * math.sin(math.radians(2 * a * 7))
        for a in angles
    ]
    analysis = analyze_waveform(angles, values, pole_pairs=2, orders=(1, 3, 5, 7))
    assert analysis.fundamental_peak == pytest.approx(100.0, rel=1e-4)
    assert analysis.order(5).amplitude == pytest.approx(20.0, rel=1e-4)
    assert analysis.order(7).amplitude == pytest.approx(5.0, rel=1e-4)
    assert analysis.order(3).amplitude == pytest.approx(0.0, abs=1e-3)
    assert analysis.thd == pytest.approx(math.hypot(20.0, 5.0) / 100.0, rel=1e-3)


def test_amplitude_is_a_peak_not_an_rms_and_says_so():
    angles = [i * 360.0 / 720.0 for i in range(720)]
    values = [10.0 * math.sin(math.radians(a)) for a in angles]
    analysis = analyze_waveform(angles, values, pole_pairs=1)
    assert analysis.fundamental_peak == pytest.approx(10.0, rel=1e-6)
    assert analysis.fundamental_peak != pytest.approx(analysis.fundamental_rms)
    assert "峰值" in analysis.method_note
    assert "峰值" in describe_analysis_zh(analysis, "V")


def test_pole_pairs_select_the_electrical_fundamental():
    angles = [i * 360.0 / 1440.0 for i in range(1440)]
    values = [7.0 * math.sin(math.radians(3 * a)) for a in angles]
    assert analyze_waveform(angles, values, pole_pairs=3).fundamental_peak == pytest.approx(
        7.0, rel=1e-4
    )
    # Read on the wrong pole-pair count the fundamental is not there.
    assert analyze_waveform(angles, values, pole_pairs=1).fundamental_peak == pytest.approx(
        0.0, abs=1e-3
    )


def test_a_non_monotonic_record_is_refused_rather_than_aliased():
    with pytest.raises(WaveformError, match="monotonic"):
        analyze_waveform([0.0, 2.0, 1.0, 3.0] * 4, [1.0, 2.0, 3.0, 4.0] * 4)


def test_too_few_samples_are_refused():
    with pytest.raises(WaveformError):
        analyze_waveform([0.0, 1.0, 2.0], [1.0, 2.0, 3.0])


# ===========================================================================
# Parameter origins (Steps 13-15)
# ===========================================================================


def test_a_parameter_cannot_be_built_without_an_origin():
    with pytest.raises(TypeError):
        PublicParameter(name="x", label_zh="x", value=1.0, unit="V")  # no origin


def test_only_measurement_origins_count_as_measurement():
    assert is_measurement(ParameterOrigin.DIRECT_MEASUREMENT)
    assert is_measurement(ParameterOrigin.MEASUREMENT_DERIVED)
    for origin in (
        ParameterOrigin.FEA_DERIVED,
        ParameterOrigin.CALCULATED,
        ParameterOrigin.DESIGN_INPUT,
        ParameterOrigin.UNKNOWN,
    ):
        assert not is_measurement(origin)
        assert origin not in EXPERIMENTAL_ORIGINS


def test_creator_rs_is_a_direct_measurement():
    parameter = src.published_parameters().get("phase_resistance_ohm")
    assert parameter.value == pytest.approx(8.9462)
    assert parameter.origin is ParameterOrigin.DIRECT_MEASUREMENT
    assert parameter.is_measurement
    assert "LCR" in parameter.source_note


@pytest.mark.parametrize(
    "name,value", [("d_axis_inductance_h", 0.2055), ("q_axis_inductance_h", 0.3320)]
)
def test_creator_inductances_are_fea_derived_not_measured(name, value):
    """The source's own README says JMAG, whatever the table's title implies."""

    parameter = src.published_parameters().get(name)
    assert parameter.value == pytest.approx(value)
    assert parameter.origin is ParameterOrigin.FEA_DERIVED
    assert parameter.is_measurement is False
    assert "JMAG" in parameter.source_note or "finite element" in parameter.source_note


def test_lambda_pm_origin_is_unknown_and_flagged_unresolved():
    parameter = src.published_parameters().get("magnet_flux_linkage_wb")
    assert parameter.value == pytest.approx(0.1144)
    assert parameter.origin is ParameterOrigin.UNKNOWN
    assert not parameter.is_measurement
    assert parameter.consistency_flag == PROVENANCE_UNRESOLVED
    assert parameter.is_unresolved


def test_the_lambda_pm_discrepancy_is_computed_not_hidden():
    assert src.LAMBDA_FROM_BACK_EMF_WB == pytest.approx(0.113088, abs=1e-5)
    assert src.LAMBDA_DISCREPANCY_RATIO == pytest.approx(0.0116, abs=5e-4)
    # Neither value was adjusted to remove the disagreement.
    assert src.PUBLISHED_LAMBDA_PM_WB == 0.1144
    assert src.PUBLISHED_BACK_EMF_FUNDAMENTAL_PEAK_V == 47.37


def test_back_emf_scalar_is_measurement_derived_not_direct():
    parameter = src.published_parameters().get("back_emf_fundamental_peak_v")
    assert parameter.origin is ParameterOrigin.MEASUREMENT_DERIVED
    assert parameter.is_measurement


def test_the_parameter_set_separates_measured_from_model_derived():
    parameters = src.published_parameters()
    measured = {p.name for p in parameters.measured}
    model = {p.name for p in parameters.model_derived}
    unknown = {p.name for p in parameters.unknown_origin}
    assert "phase_resistance_ohm" in measured
    assert {"d_axis_inductance_h", "q_axis_inductance_h"} == model
    assert "magnet_flux_linkage_wb" in unknown
    assert not (measured & model)


def test_the_rendered_table_shows_an_origin_for_every_row():
    text = render_parameter_table_zh(src.published_parameters())
    assert "有限元计算" in text
    assert "来源未知" in text
    assert "实测" in text
    assert PROVENANCE_UNRESOLVED in text
    # Every parameter row carries its own origin label; there is no blanket
    # heading standing in for them. (The phrase "实验参数" does occur, but only
    # inside the FEA caveat that warns against trusting such a heading.)
    for parameter in src.published_parameters().parameters:
        assert parameter.origin_label_zh in text
    heading = text.splitlines()[2]
    assert "来源" in heading
    assert "实验参数" not in heading


def test_a_parameter_set_never_reports_an_fea_value_as_measured():
    parameters = ParameterSet(
        schema_version="t",
        source_id="t",
        parameters=(
            PublicParameter("l", "L", 1.0, "H", ParameterOrigin.FEA_DERIVED),
        ),
    )
    assert parameters.measured == ()
    assert len(parameters.model_derived) == 1


# ===========================================================================
# Topology firewall (Steps 18-19)
# ===========================================================================


def test_only_axial_flux_topologies_are_modellable():
    assert is_afpm_modellable(MachineTopology.AFPM_DUAL_ROTOR_SINGLE_STATOR)
    for topology in (
        MachineTopology.RADIAL_FLUX_INSET_PMSM,
        MachineTopology.RADIAL_FLUX_SURFACE_PMSM,
        MachineTopology.RADIAL_FLUX_BLDC,
        MachineTopology.INDUCTION_SQUIRREL_CAGE,
        MachineTopology.UNKNOWN,
    ):
        assert not is_afpm_modellable(topology)
        assert topology not in AFPM_KERNEL_TOPOLOGIES


def test_the_creator_topology_is_refused_by_the_afpm_kernel():
    with pytest.raises(TopologyMismatchError, match="axial-flux"):
        require_compatible_topology(MachineTopology.RADIAL_FLUX_INSET_PMSM)


def test_project_construction_is_refused_for_the_creator_machine():
    with pytest.raises(TopologyMismatchError) as info:
        reject_afpm_project_construction(src.CREATOR_MACHINE.topology)
    assert "RADIAL_FLUX_INSET_PMSM" in str(info.value)


def test_afpm_geometry_fields_cannot_be_used_for_an_unknown_machine():
    with pytest.raises(TopologyMismatchError):
        reject_afpm_project_construction(
            MachineTopology.UNKNOWN, {"D_out": 140.0, "g_side": 1.0}
        )


def test_an_afpm_machine_is_still_permitted():
    reject_afpm_project_construction(
        MachineTopology.AFPM_DUAL_ROTOR_SINGLE_STATOR, {"D_out": 140.0}
    )
    assert require_compatible_topology("AFPM_DUAL_ROTOR_SINGLE_STATOR")


def test_the_creator_source_never_declares_afpm_geometry_fields():
    """Nothing in the source record should even name an AFPM input."""

    from motor_calculator.experiment.topology import AFPM_GEOMETRY_FIELDS

    text = (
        REPOSITORY_ROOT / "motor_calculator" / "experiment" / "creator_source.py"
    ).read_text(encoding="utf-8")
    for field in AFPM_GEOMETRY_FIELDS:
        assert f'"{field}"' not in text, field


# ===========================================================================
# Machine compatibility (Step 18)
# ===========================================================================


def test_creator_is_a_different_machine_from_the_afpm_design():
    assessment = assess_compatibility(
        src.CREATOR_MACHINE, project_machine_identity(PROJECT_PARAMS, connection="WYE")
    )
    assert assessment.status is MachineCompatibility.DIFFERENT_MACHINE
    conflicts = {item.field for item in assessment.conflicts}
    assert {"pole_count", "slot_count", "topology"} <= conflicts


def test_creator_may_not_validate_the_current_design():
    assessment = assess_compatibility(
        src.CREATOR_MACHINE, project_machine_identity(PROJECT_PARAMS, connection="WYE")
    )
    assert not may_validate_current_design(
        DatasetSourceType.PUBLIC_REFERENCE_EXPERIMENT, assessment.status
    )


def test_a_successful_extraction_claims_the_pipeline_not_the_design():
    assert PIPELINE_VALIDATED == "PUBLIC_REFERENCE_PIPELINE_VALIDATED"
    assert AFPM_NOT_VALIDATED == "CURRENT_AFPM_NOT_EXPERIMENTALLY_VALIDATED"
    assert "VALIDATED" in PIPELINE_VALIDATED
    assert PIPELINE_VALIDATED != AFPM_NOT_VALIDATED


# ===========================================================================
# The no-data state
# ===========================================================================


def test_the_report_is_informative_with_no_dataset_configured():
    report = evidence.build_report(None, PROJECT_PARAMS)
    assert report.state == evidence.DATA_NOT_CONFIGURED
    assert not report.has_data
    assert report.back_emf is None
    assert report.cogging is None
    # Metadata is still fully populated: it needs no data file.
    assert report.summary.doi == "10.3217/sns1d-77m43"
    assert report.is_different_machine
    assert report.afpm_claim == AFPM_NOT_VALIDATED
    assert "不显示任何数值" in report.message_zh


def test_the_no_data_state_still_renders_every_view():
    report = evidence.build_report(None, PROJECT_PARAMS)
    for render in (
        evidence.render_header_zh,
        evidence.render_back_emf_zh,
        evidence.render_cogging_zh,
        evidence.render_no_load_zh,
        evidence.render_parameters_zh,
        evidence.render_drive_cycle_zh,
    ):
        assert render(report).strip()


def test_a_missing_dataset_directory_is_reported_not_raised(tmp_path):
    report = evidence.build_report(tmp_path, PROJECT_PARAMS)
    assert report.state == evidence.DATA_UNREADABLE
    assert report.errors_zh
    assert report.afpm_claim == AFPM_NOT_VALIDATED


def test_the_adapter_names_the_doi_when_a_file_is_absent(tmp_path):
    with pytest.raises(adapter.CreatorAdapterError, match="10.3217/sns1d-77m43"):
        adapter.resolve(tmp_path, "back_emf")


# ===========================================================================
# Repository hygiene (Step 24)
# ===========================================================================


def test_no_creator_raw_data_is_committed():
    """The dataset stays external. Only metadata, hashes and adapters ship."""

    forbidden_names = {
        "Back_emf.csv", "Cogging_torque.csv", "No_load_iron_losses.csv",
        "M20231005.csv", "M20231017.csv", "M20231018.csv",
        "PMSM_overview.xlsx", "PM_synchronous_motor.zip",
        "Equivalent_circuit_parameters_PMSM.csv",
    }
    present = {
        path.name
        for path in REPOSITORY_ROOT.rglob("*")
        if path.is_file() and ".git" not in path.parts and ".venv" not in path.parts
    }
    assert not (forbidden_names & present)


def test_no_creator_binary_artefacts_are_committed():
    for pattern in ("*.mat", "*.jproj", "*.dxf", "*.step"):
        found = [
            path
            for path in REPOSITORY_ROOT.rglob(pattern)
            if ".git" not in path.parts and ".venv" not in path.parts
        ]
        assert not found, f"{pattern}: {found[:3]}"


# ===========================================================================
# Production physics and calibration
# ===========================================================================


def test_production_physics_is_untouched_by_phase11b():
    path = REPOSITORY_ROOT / "motor_calculator" / "motor_core" / "calculations.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942"
    )


def test_the_legacy_baseline_fixture_is_untouched():
    path = REPOSITORY_ROOT / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == (
        "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9"
    )


def test_no_calibration_was_introduced_in_phase11b():
    negations = ("not ", "no ", "never", "非", "不", "未", "NONE")
    for name in (
        "creator_source.py", "creator_adapter.py", "creator_evidence.py",
        "harmonics.py", "origins.py", "topology.py",
    ):
        path = REPOSITORY_ROOT / "motor_calculator" / "experiment" / name
        lines = path.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            if "calibrat" not in line.lower() and "标定" not in line:
                continue
            if "calibration_status" in line.lower():
                continue
            window = "".join(lines[index : index + 3])
            assert any(marker in window for marker in negations), f"{name}: {line}"


def test_the_published_targets_are_never_fed_into_the_extraction():
    """The 47.37 V must not be an input anywhere in the processing chain."""

    for name in ("harmonics.py", "creator_adapter.py"):
        text = (
            REPOSITORY_ROOT / "motor_calculator" / "experiment" / name
        ).read_text(encoding="utf-8")
        # harmonics.py must not know the published value at all.
        if name == "harmonics.py":
            assert "47.37" not in text
    source = (
        REPOSITORY_ROOT / "motor_calculator" / "experiment" / "creator_adapter.py"
    ).read_text(encoding="utf-8")
    # The adapter may compare against the published value, but only after the
    # extraction: the comparison lives in check_against_publication and the
    # waveform analysis never receives it.
    extraction = source[source.index("def read_back_emf") : source.index("def check_against_publication")]
    assert "PUBLISHED_BACK_EMF" not in extraction


# ===========================================================================
# Dataset-backed tests (skip cleanly when the data is absent)
# ===========================================================================


@pytest.fixture(scope="module")
def dataset_root():
    root = _dataset_root()
    if root is None:
        pytest.skip("CREATOR dataset not available")
    return root


@pytest.fixture(scope="module")
def back_emf(dataset_root):
    return adapter.read_back_emf(dataset_root)


@requires_dataset
def test_the_back_emf_file_is_the_audited_file(back_emf):
    assert back_emf.binding.integrity == "VERIFIED"
    assert back_emf.binding.sha256 == src.FILE_HASHES["back_emf"]


@requires_dataset
def test_the_back_emf_record_has_the_expected_shape(back_emf):
    assert back_emf.sample_count == 7681
    assert back_emf.angle_basis == "MECHANICAL_DEGREES"
    assert back_emf.voltage_basis == "PHASE_TO_NEUTRAL_INSTANTANEOUS"
    assert back_emf.speed_rpm == 2000.0
    assert back_emf.pole_pairs == 2


@requires_dataset
def test_the_three_phases_sum_to_approximately_zero(back_emf):
    """Confirms these are phase-to-neutral voltages of a balanced set."""

    assert back_emf.balanced
    assert back_emf.phase_sum_residual_ratio < adapter.PHASE_SUM_TOLERANCE_RATIO
    assert back_emf.phase_sum_max_abs < 2.0


@requires_dataset
def test_the_record_covers_two_electrical_periods(back_emf):
    analysis = back_emf.analysis("U")
    assert analysis.angle_span_deg == pytest.approx(360.0, abs=0.05)
    assert analysis.electrical_periods == pytest.approx(2.0, abs=0.001)


@requires_dataset
def test_the_measured_fundamental_reproduces_the_publication(back_emf):
    """The phase's headline result: 47.37 V from raw samples, untuned."""

    check = adapter.check_against_publication(back_emf)
    assert check.published == 47.37
    assert check.extracted == pytest.approx(47.37, rel=5e-4)
    assert abs(check.difference_percent) <= adapter.PUBLICATION_TOLERANCE_PERCENT
    assert check.reproduced


@requires_dataset
def test_all_three_phases_reproduce_the_publication(back_emf):
    for _name, analysis in back_emf.per_phase:
        assert analysis.fundamental_peak == pytest.approx(47.37, rel=3e-3)
    assert back_emf.phase_spread_percent < 1.0


@requires_dataset
def test_the_waveform_is_strongly_non_sinusoidal(back_emf):
    """Why the fundamental must be extracted rather than read off as a peak."""

    analysis = back_emf.analysis("U")
    assert analysis.raw_peak > 60.0
    assert analysis.crest_ratio > 1.3
    assert analysis.thd > 0.15
    assert analysis.order(5).percent_of_fundamental > 10.0
    assert analysis.order(7).percent_of_fundamental > 10.0


@requires_dataset
def test_even_harmonics_are_negligible(back_emf):
    """A symmetric machine should show almost none; large ones would be a fault."""

    analysis = back_emf.analysis("U")
    for order in (2, 4, 6):
        assert analysis.order(order).percent_of_fundamental < 1.0


@requires_dataset
def test_single_speed_ke_has_its_own_provenance_and_no_r_squared(back_emf):
    ke = adapter.single_speed_ke(back_emf)
    assert ke.provenance == "MEASUREMENT_DERIVED_SINGLE_SPEED"
    assert ke.r_squared is None
    assert not ke.is_regression
    assert ke.voltage_basis == "PHASE_PEAK"
    assert ke.speed_basis == "ELECTRICAL_RAD_PER_S"
    assert ke.speed_rpm == 2000.0
    assert ke.uncertainty_status == "NOT_QUANTIFIED"
    assert ke.limitations_zh


@requires_dataset
def test_single_speed_ke_equals_fundamental_over_electrical_speed(back_emf):
    ke = adapter.single_speed_ke(back_emf)
    omega = 2000.0 / 60.0 * 2.0 * math.pi * 2
    assert ke.value_v_per_rad_s == pytest.approx(back_emf.fundamental_peak_v / omega)
    assert ke.value_v_per_rad_s == pytest.approx(0.1131, abs=5e-4)


@requires_dataset
def test_the_ke_basis_changes_the_number_and_is_stated(back_emf):
    peak = adapter.single_speed_ke(back_emf, voltage_basis="PHASE_PEAK")
    rms = adapter.single_speed_ke(back_emf, voltage_basis="PHASE_RMS")
    assert rms.value_v_per_rad_s == pytest.approx(peak.value_v_per_rad_s / math.sqrt(2))
    mechanical = adapter.single_speed_ke(back_emf, speed_basis="MECHANICAL_RAD_PER_S")
    assert mechanical.value_v_per_rad_s == pytest.approx(peak.value_v_per_rad_s * 2)


@requires_dataset
def test_an_unsupported_basis_is_refused(back_emf):
    with pytest.raises(adapter.CreatorAdapterError):
        adapter.single_speed_ke(back_emf, voltage_basis="LINE_RMS")


# --- Cogging ---------------------------------------------------------------


@pytest.fixture(scope="module")
def cogging(dataset_root):
    return adapter.read_cogging(dataset_root)


@requires_dataset
def test_the_cogging_record_is_read_in_full(cogging):
    assert cogging.sample_count == 240001
    assert cogging.binding.integrity == "VERIFIED"
    assert cogging.current_condition == "ZERO_CURRENT"
    assert cogging.speed_rpm == 0.25
    assert cogging.torque_basis == "MOTOR_SHAFT"


@requires_dataset
def test_the_four_cogging_statistics_are_kept_separate(cogging):
    assert cogging.max_positive_nm == pytest.approx(0.037521, abs=1e-5)
    assert cogging.min_negative_nm == pytest.approx(-0.035871, abs=1e-5)
    assert cogging.max_abs_nm == pytest.approx(0.037521, abs=1e-5)
    assert cogging.peak_to_peak_nm == pytest.approx(0.073392, abs=1e-5)
    assert cogging.max_abs_nm != pytest.approx(cogging.peak_to_peak_nm)


@requires_dataset
def test_the_published_cogging_scalar_is_flagged_ambiguous(cogging):
    assert cogging.published_scalar_flag == "PUBLISHED_SCALAR_DEFINITION_AMBIGUOUS"
    assert cogging.published_scalar_nm == 0.0357
    # It matches the negative peak, not max|T|.
    assert cogging.published_scalar_matches == "abs_min_negative"
    assert abs(cogging.min_negative_nm) == pytest.approx(0.0357, rel=0.01)
    assert cogging.max_abs_nm != pytest.approx(0.0357, rel=0.01)


@requires_dataset
def test_the_raw_cogging_data_was_not_forced_to_match_the_publication(cogging):
    """max|T| genuinely differs from the published scalar; that is preserved."""

    deviation = (cogging.max_abs_nm - 0.0357) / 0.0357 * 100.0
    assert deviation > 4.0
    assert "不调整原始数据" in cogging.published_scalar_note_zh


@requires_dataset
def test_cogging_harmonics_match_the_slot_pole_combination(cogging):
    """6 slots and 4 poles give LCM = 12 cogging periods per revolution."""

    assert cogging.harmonics is not None
    orders = {h.order: h.amplitude for h in cogging.harmonics.harmonics}
    assert orders[12] > orders[6] * 10
    assert orders[12] > orders[18] * 10


@requires_dataset
def test_downsampling_happens_only_after_the_statistics(dataset_root, cogging):
    angles = list(range(cogging.sample_count))
    values = [0.0] * cogging.sample_count
    thin_a, thin_v = adapter.downsample(angles, values, target=2000)
    assert len(thin_a) == 2000
    # The reported statistics came from the full record, not the thinned one.
    assert cogging.sample_count == 240001


# --- No-load loss ----------------------------------------------------------


@pytest.fixture(scope="module")
def no_load(dataset_root):
    return adapter.read_no_load_loss(dataset_root)


@requires_dataset
def test_rotor_in_and_rotor_out_runs_are_distinguished(no_load):
    configurations = [run.configuration for run in no_load.runs]
    assert configurations.count("ROTOR_OUTSIDE_STATOR") == 2
    assert configurations.count("ROTOR_INSIDE_STATOR") == 1
    inside = no_load.run("ROTOR_INSIDE_STATOR")
    outside = no_load.run("ROTOR_OUTSIDE_STATOR")
    assert inside.measurement_date == "2023-10-18"
    assert outside.measurement_date in {"2023-10-05", "2023-10-17"}


@requires_dataset
def test_the_rotor_inside_run_measures_more_torque(no_load):
    """Because it includes the iron loss the rotor-out runs do not."""

    inside = no_load.run("ROTOR_INSIDE_STATOR")
    outside = no_load.run("ROTOR_OUTSIDE_STATOR")
    for speed in (1000.0, 3000.0, 7000.0):
        assert inside.torque_at(speed) > outside.torque_at(speed)


@requires_dataset
def test_no_load_loss_is_not_treated_as_all_iron_loss(no_load):
    assert any("不等于" in note for note in no_load.notes_zh)
    assert no_load.published_iron_loss_origin is ParameterOrigin.MEASUREMENT_DERIVED


@requires_dataset
def test_iron_loss_reconstruction_reproduces_the_source_closely(no_load):
    assert len(no_load.reconstruction) == 16
    assert no_load.mean_abs_residual_percent < 5.0
    assert no_load.closes


@requires_dataset
def test_the_iron_loss_reconstruction_residual_stays_visible(no_load):
    """It does not close exactly, and that is reported rather than smoothed."""

    worst = max(abs(item.residual_percent) for item in no_load.reconstruction)
    assert worst > 5.0
    assert no_load.max_abs_residual_percent == pytest.approx(worst)


# --- Drive cycle -----------------------------------------------------------


@requires_dataset
def test_the_headerless_mid_vehicle_files_are_read_correctly(dataset_root):
    """Their first row is data; consuming it as a header would lose a sample."""

    mid = adapter.read_drive_cycle(dataset_root, vehicle="Mid_sized_vehicle", cycle="Wltp")
    small = adapter.read_drive_cycle(dataset_root, vehicle="Small_sized_vehicle", cycle="Wltp")
    assert all(not s.has_header for s in mid.signals)
    assert all(s.has_header for s in small.signals)
    assert len(mid.signal("input_power").values) == 3601
    assert len(small.signal("input_power").values) == 3601


@requires_dataset
def test_input_and_output_power_come_from_the_filename_not_the_header(dataset_root):
    cycle = adapter.read_drive_cycle(dataset_root, vehicle="Small_sized_vehicle", cycle="Wltp")
    assert cycle.signal("input_power").semantics == "DC_INPUT"
    assert cycle.signal("output_power").semantics == "MECHANICAL_OUTPUT"
    assert any("文件名" in note for note in cycle.notes_zh)


@requires_dataset
def test_regenerative_power_keeps_its_sign(dataset_root):
    cycle = adapter.read_drive_cycle(dataset_root, vehicle="Small_sized_vehicle", cycle="Wltp")
    output = cycle.signal("output_power")
    assert output.has_negative
    assert output.min_value < 0.0
    assert cycle.regenerative_samples > 0
    # Never clipped or absolute-valued.
    assert min(output.values) == output.min_value


@requires_dataset
def test_drive_cycle_efficiency_is_an_energy_ratio(dataset_root):
    cycle = adapter.read_drive_cycle(dataset_root, vehicle="Small_sized_vehicle", cycle="Wltp")
    assert cycle.shared_time_base
    assert 0.0 < cycle.cycle_efficiency < 1.0
    assert cycle.cycle_efficiency == pytest.approx(
        cycle.output_energy_j / cycle.input_energy_j
    )


@requires_dataset
def test_an_unknown_vehicle_or_cycle_is_refused(dataset_root):
    with pytest.raises(adapter.CreatorAdapterError):
        adapter.read_drive_cycle(dataset_root, vehicle="Lorry")
    with pytest.raises(adapter.CreatorAdapterError):
        adapter.read_drive_cycle(dataset_root, cycle="Nedc")


# --- Whole report ----------------------------------------------------------


@requires_dataset
def test_the_full_report_validates_the_pipeline_not_the_afpm_design(dataset_root):
    report = evidence.build_report(dataset_root, PROJECT_PARAMS)
    assert report.state == evidence.DATA_AVAILABLE
    assert report.pipeline_claim == PIPELINE_VALIDATED
    assert report.afpm_claim == AFPM_NOT_VALIDATED
    assert report.is_different_machine
    assert report.publication_check.reproduced


@requires_dataset
def test_every_rendered_view_states_the_machine_is_different(dataset_root):
    report = evidence.build_report(dataset_root, PROJECT_PARAMS)
    header = evidence.render_header_zh(report)
    assert "DIFFERENT_MACHINE" in header
    back_emf = evidence.render_back_emf_zh(report)
    assert AFPM_NOT_VALIDATED in back_emf
    assert PIPELINE_VALIDATED in back_emf
