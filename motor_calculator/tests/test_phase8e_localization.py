"""Phase 8E localization boundaries and stable-key coverage."""

from __future__ import annotations

import hashlib
from pathlib import Path

from motor_calculator.i18n import (
    DEFAULT_LOCALE,
    available_locales,
    get_locale,
    input_label,
    input_tooltip,
    preset_name,
    semantic_label,
    semantic_value,
    set_locale,
    tr,
)
from motor_calculator.i18n import strings_en_US, strings_zh_CN
from motor_calculator.input_ux.metadata import INPUT_DEFINITIONS
from motor_calculator.presets import default_preset_registry
from motor_calculator.validation.uncertainty_models import UncertaintyKind


ROOT = Path(__file__).resolve().parents[2]


def test_default_locale_is_simplified_chinese() -> None:
    set_locale(DEFAULT_LOCALE)
    assert DEFAULT_LOCALE == "zh_CN"
    assert get_locale() == "zh_CN"
    assert set(available_locales()) == {"zh_CN", "en_US"}


def test_chinese_resource_has_every_stable_string_key() -> None:
    assert set(strings_en_US.STRINGS) <= set(strings_zh_CN.STRINGS)
    assert all(strings_zh_CN.STRINGS[key].strip() for key in strings_en_US.STRINGS)


def test_critical_gui_keys_resolve_to_nonempty_chinese() -> None:
    set_locale("zh_CN")
    keys = (
        "app.title", "menu.file", "menu.open", "guided.basic", "guided.advanced",
        "confidence.tab", "feedback.add_title", "uncertainty.title", "recovery.title",
        "analysis.error_title", "runtime.startup_failed",
    )
    assert all(tr(key).strip() for key in keys)
    assert tr("app.title") == "电机电磁计算器"
    assert tr("confidence.tab") == "置信度与验证"


def test_every_uncertainty_kind_has_a_localized_label() -> None:
    assert all(tr(f"uncertainty.kind.{kind.value.lower()}").strip() for kind in UncertaintyKind)


def test_feedback_semantics_are_localized_without_changing_internal_values() -> None:
    for value in ("phase", "rms", "sinusoidal", "shaft", "not_applicable"):
        assert semantic_label(value) != value
        assert semantic_value(semantic_label(value)) == value


def test_engineering_abbreviations_and_units_are_preserved() -> None:
    combined = "\n".join(strings_zh_CN.STRINGS.values()) + "\n" + "\n".join(
        strings_zh_CN.PRESET_NAMES.values()
    )
    for abbreviation in ("PMSM", "BLDC", "AFPM", "SSDR", "DSSR", "RMS", "Ke", "Kt"):
        assert abbreviation in combined
    for unit in ("rpm", "rad/s", "V", "A", "T"):
        assert unit in combined or any(unit in value for value in strings_zh_CN.INPUT_TOOLTIPS.values())


def test_all_engineering_inputs_have_chinese_label_and_tooltip() -> None:
    set_locale("zh_CN")
    for field in INPUT_DEFINITIONS:
        assert input_label(field).strip()
        assert input_tooltip(field).strip()


def test_every_preset_has_a_localized_display_name() -> None:
    registry = default_preset_registry()
    for preset in registry.presets:
        localized = preset_name(preset.preset_id, preset.display_name)
        assert localized.strip()
        assert localized != preset.display_name


def test_protected_calculation_and_legacy_baseline_hashes() -> None:
    expected = {
        ROOT / "motor_calculator" / "motor_core" / "calculations.py":
            "1609b2ee96ec93fa56a0af68ca4fe3eaea368807d70aa0e2078e7e18c72c1a14",
        ROOT / "motor_calculator" / "tests" / "fixtures" / "legacy_baseline.json":
            "15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9",
    }
    for path, digest in expected.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest


def test_runtime_source_has_no_absolute_repository_dependency() -> None:
    old_root = "C:\\Users\\10099\\Documents\\Codex\\2026-07-03\\agents-md-docs-project-status-zh\\repo"
    runtime_files = (
        ROOT / "motor_calculator" / "runtime" / "paths.py",
        ROOT / "motor_calculator" / "gui" / "main_window.py",
        ROOT / "packaging" / "MotorCalculator.spec",
    )
    assert all(old_root not in path.read_text(encoding="utf-8") for path in runtime_files)


def test_gui_smoke_checks_confidence_actions_remain_visible() -> None:
    source = (ROOT / "motor_calculator" / "runtime" / "gui_smoke.py").read_text(encoding="utf-8")
    assert '"confidence_actions_visible"' in source
    assert "_widget_fits_window(" in source
    assert "app.confidence_panel.actions" in source


def test_temperature_selector_displays_degree_symbol_without_changing_internal_token() -> None:
    source = (ROOT / "motor_calculator" / "gui" / "guided_input_panel.py").read_text(encoding="utf-8")
    assert '("°C", "K")' in source
    assert '"degC" if value == "°C" else value' in source
