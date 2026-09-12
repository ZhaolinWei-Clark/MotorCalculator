"""Phase 10H.1: startup preset authority and legacy reproducibility."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from motor_calculator.input_ux import APPLICATION_DEFAULTS
from motor_calculator.motor_core.calculations import LegacyGuiMotorModelBridge
from motor_calculator.motor_core.validation import parse_legacy_gui_params
from motor_calculator.presets.models import apply_preset
from motor_calculator.validation.design_feasibility import evaluate_design_feasibility
from motor_calculator.winding.authority import (
    WindingAuthority,
    resolve_production_winding_factor,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PRESET_FILE = REPOSITORY_ROOT / "motor_calculator" / "presets" / "data" / "presets.json"

V1 = "design.manufacturability_start.v1"
V2 = "design.manufacturability_start.v2"
V3 = "design.manufacturability_start.v3"

GEOMETRY_KW = math.sqrt(3.0) / 2.0
LEGACY_KW = 0.93


def _records():
    payload = json.loads(PRESET_FILE.read_text(encoding="utf-8"))
    return {record["preset_id"]: record for record in payload["presets"]}


def _registry():
    from motor_calculator.presets.loader import load_preset_file

    return {preset.preset_id: preset for preset in load_preset_file(PRESET_FILE)}


# ---------------------------------------------------------------------------
# The preset set
# ---------------------------------------------------------------------------


def test_all_three_starting_examples_exist():
    records = _records()
    for preset_id in (V1, V2, V3):
        assert preset_id in records


def test_v3_declares_auto_and_supplies_the_coil_span():
    record = _records()[V3]
    assert record["winding_authority"] == "AUTO_FROM_GEOMETRY"
    assert record["coil_span_slots"] == 1


def test_the_legacy_examples_declare_legacy_manual():
    for preset_id in (V1, V2):
        assert _records()[preset_id]["winding_authority"] == "LEGACY_MANUAL"


def test_v3_is_the_same_machine_as_v2():
    """Only the winding-factor authority differs; no input value moved."""

    records = _records()
    assert records[V3]["values"] == records[V2]["values"]


def test_no_legacy_preset_input_value_was_changed():
    """Declaring authority must not have touched any number."""

    records = _records()
    assert records[V2]["values"] == {
        "V_dc": 72.0, "P_rated": 600.0, "n_rated": 1800.0,
        "N_ph_turns": 42, "d_wire": 1.2, "n_parallel": 3,
        "slot_type": "半闭口槽", "coreless": False,
    }
    assert "k_w" not in records[V2]["values"]
    assert "k_w" not in records[V1]["values"]


def test_the_gui_points_at_v3_and_keeps_the_legacy_ids():
    source = (
        REPOSITORY_ROOT / "motor_calculator" / "gui" / "main_window.py"
    ).read_text(encoding="utf-8")
    assert f'STARTUP_EXAMPLE_PRESET_ID = "{V3}"' in source
    assert f'LEGACY_STARTUP_EXAMPLE_PRESET_ID = "{V1}"' in source
    assert f'LEGACY_MANUAL_STARTUP_EXAMPLE_PRESET_ID = "{V2}"' in source


def test_a_preset_declaring_auto_without_a_coil_span_is_rejected():
    from motor_calculator.presets.loader import PresetLoadError, load_preset_file

    payload = json.loads(PRESET_FILE.read_text(encoding="utf-8"))
    for record in payload["presets"]:
        if record["preset_id"] == V3:
            record.pop("coil_span_slots")
    import tempfile

    broken = Path(tempfile.mkdtemp()) / "presets.json"
    broken.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(PresetLoadError, match="coil_span_slots"):
        load_preset_file(broken)


def test_presets_without_an_authority_declaration_still_load():
    """Every pre-10H.1 preset says nothing about authority and must be fine."""

    registry = _registry()
    silent = [p for p in registry.values() if p.winding_authority is None]
    assert silent, "most presets should still declare nothing"
    for preset in silent:
        assert preset.preset_id not in (V1, V2, V3)


# ---------------------------------------------------------------------------
# Resolved authority and the quantified impact
# ---------------------------------------------------------------------------


def _analysis(kw: float):
    parameters = dict(APPLICATION_DEFAULTS)
    parameters.update(_records()[V3]["values"])
    parameters["k_w"] = kw
    bridge = LegacyGuiMotorModelBridge(parse_legacy_gui_params(parameters))
    result = bridge.run_full_analysis()
    feasibility = evaluate_design_feasibility(parameters, result)
    omega = bridge.input_data.mechanical_speed_rpm * 2.0 * math.pi / 60.0
    return {
        "ke": result.electrical.back_emf_phase_rms_v / omega,
        "kt": result.electrical.legacy_torque_constant_nm_per_phase_rms_a,
        "voltage": result.performance.required_voltage_line_rms_v,
        "margin": feasibility.voltage_margin_percent,
        "density": feasibility.current_density_a_per_mm2,
        "has_error": feasibility.has_error,
        "issues": len(feasibility.issues),
    }


def test_v3_resolves_to_the_geometry_winding_factor():
    record = _records()[V3]
    resolved = resolve_production_winding_factor(
        authority=WindingAuthority(record["winding_authority"]),
        manual_value=APPLICATION_DEFAULTS["k_w"],
        slots=APPLICATION_DEFAULTS["slots"],
        pole_pairs=APPLICATION_DEFAULTS["p"],
        coil_span_slots=record["coil_span_slots"],
    )
    assert resolved.value == pytest.approx(GEOMETRY_KW)
    assert resolved.authority is WindingAuthority.AUTO_FROM_GEOMETRY
    assert resolved.provenance == "IDEAL_SLOT_STAR_GEOMETRY"
    assert resolved.value != pytest.approx(LEGACY_KW)


def test_v2_still_reproduces_the_historical_manual_value():
    """Legacy reproducibility, checked headlessly so no GUI state is disturbed."""

    resolved = resolve_production_winding_factor(
        authority=WindingAuthority(_records()[V2]["winding_authority"]),
        manual_value=APPLICATION_DEFAULTS["k_w"],
        slots=APPLICATION_DEFAULTS["slots"],
        pole_pairs=APPLICATION_DEFAULTS["p"],
        coil_span_slots=1,
    )
    assert resolved.value == LEGACY_KW  # exact
    assert resolved.authority is WindingAuthority.LEGACY_MANUAL
    assert resolved.provenance == "LEGACY_PROJECT"


def test_v2_reproduces_its_published_observations():
    """The RC3/RC4 startup numbers must still be obtainable."""

    legacy = _analysis(LEGACY_KW)
    assert legacy["voltage"] == pytest.approx(41.095139, abs=1e-4)
    assert legacy["margin"] == pytest.approx(19.281524, abs=1e-4)
    assert legacy["density"] == pytest.approx(4.209820, abs=1e-4)


def test_the_startup_change_impact_is_exactly_what_was_documented():
    legacy, geometry = _analysis(LEGACY_KW), _analysis(GEOMETRY_KW)
    assert geometry["ke"] / legacy["ke"] - 1.0 == pytest.approx(-0.06879, abs=1e-4)
    assert geometry["kt"] / legacy["kt"] - 1.0 == pytest.approx(-0.06879, abs=1e-4)
    assert geometry["voltage"] / legacy["voltage"] - 1.0 == pytest.approx(0.01953, abs=1e-4)
    assert geometry["margin"] == pytest.approx(17.704960, abs=1e-4)
    assert geometry["density"] == pytest.approx(4.520806, abs=1e-4)


def test_the_new_startup_design_remains_feasible():
    geometry = _analysis(GEOMETRY_KW)
    assert geometry["has_error"] is False
    # and the issue count does not grow relative to the legacy basis.
    assert geometry["issues"] <= _analysis(LEGACY_KW)["issues"]


def test_the_startup_preset_never_resolves_to_the_meshed_value():
    from motor_calculator.fea.meshed_winding import meshed_winding_factor_for_case
    from motor_calculator.fea.models import FEAValidationTarget
    from motor_calculator.fea.reference_cases import build_self_consistent_reference_case

    meshed = meshed_winding_factor_for_case(
        build_self_consistent_reference_case(FEAValidationTarget.NO_LOAD_BACK_EMF)
    ).value
    record = _records()[V3]
    resolved = resolve_production_winding_factor(
        authority=WindingAuthority(record["winding_authority"]),
        manual_value=None,
        slots=APPLICATION_DEFAULTS["slots"],
        pole_pairs=APPLICATION_DEFAULTS["p"],
        coil_span_slots=record["coil_span_slots"],
    )
    assert resolved.value != pytest.approx(meshed, rel=1e-3)
    assert resolved.value == pytest.approx(GEOMETRY_KW)


# ---------------------------------------------------------------------------
# Reset semantics
# ---------------------------------------------------------------------------


def test_reset_to_defaults_also_resets_the_winding_authority():
    """Otherwise 'reset to defaults' does not give you the defaults."""

    source = (
        REPOSITORY_ROOT / "motor_calculator" / "gui" / "main_window.py"
    ).read_text(encoding="utf-8")
    reset_body = source[source.index("def reset_defaults"):]
    reset_body = reset_body[: reset_body.index("\n    def ")]
    assert "_winding_factor_mode_var" in reset_body
    assert "WindingFactorMode.MANUAL" in reset_body


# ---------------------------------------------------------------------------
# Protected physics and calibration
# ---------------------------------------------------------------------------


def test_application_defaults_are_still_frozen():
    assert APPLICATION_DEFAULTS["k_w"] == LEGACY_KW
    assert APPLICATION_DEFAULTS["slots"] == 24
    assert APPLICATION_DEFAULTS["p"] == 8


def test_production_physics_is_untouched_by_phase10h1():
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

    assert AUTO_CALIBRATION_ENABLED is False
    # Presets may mention calibration only to deny it. Every occurrence must sit
    # in a string that also carries a negation, the same rule the FEA bridge
    # guard applies to its own modules.
    negations = ("not ", "no ", "never", "非", "不", "未")
    for record in _records().values():
        for text in list(record.get("notes", ())) + list(record.get("assumptions", ())):
            lowered = str(text).lower()
            if "calibrat" not in lowered:
                continue
            assert any(marker in lowered for marker in negations), (
                f"{record['preset_id']}: {text}"
            )
