"""RC2: GUI-level winding-factor policy, provenance and project compatibility.

These exercise the real mixin methods against a headless stub, so no Tk widget
is created but the actual production code paths are covered.
"""

from __future__ import annotations

import importlib

import pytest

from helpers import build_sample_legacy_params
from motor_core import parse_legacy_gui_params
from motor_calculator.motor_core.winding_factor import (
    WINDING_FACTOR_MODE_LABELS_ZH,
    WindingFactorMode,
    WindingFactorProvenance,
)


MIXIN = importlib.import_module("gui.main_window").MotorCalculatorAppMixin


@pytest.fixture(scope="module")
def mixin():
    return MIXIN


class _Var:
    def __init__(self, value=""):
        self._value = value

    def set(self, value):
        self._value = value

    def get(self):
        return self._value


class _AppStub(MIXIN):
    """Real mixin behaviour, headless: only the widget variables are stubbed.

    `MotorCalculatorAppMixin.__init__` is deliberately not called because it
    builds Tk widgets; every method under test only touches the attributes set
    here.
    """

    def __init__(self, mixin, raw_params=None, mode=WindingFactorMode.MANUAL):
        self._mixin = mixin
        self._raw = dict(raw_params or build_sample_legacy_params())
        self._winding_factor_mode_var = _Var(WINDING_FACTOR_MODE_LABELS_ZH[mode])
        self._coil_span_slots_var = _Var("")
        self._skew_slots_var = _Var("0")
        self._winding_factor_summary_var = _Var("")
        self._winding_factor_resolution = None
        self._winding_factor_manual_provenance = WindingFactorProvenance.MANUAL_USER

    def _collect_raw_params(self):
        return dict(self._raw)

    # Bound mixin methods under test -------------------------------------
    def selected_mode(self):
        return self._mixin._selected_winding_factor_mode(self)

    def resolve(self, parsed):
        return self._mixin._resolve_winding_factor_for(self, parsed)

    def refresh(self):
        return self._mixin._refresh_winding_factor_summary(self)

    def latest(self):
        return self._mixin._latest_winding_factor_resolution(self)

    def restore(self, preferences):
        return self._mixin._restore_winding_factor_preferences(self, preferences)

    def get_params(self):
        return self._mixin._get_params(self)


def test_mode_label_round_trip(mixin):
    stub = _AppStub(mixin)
    assert stub.selected_mode() is WindingFactorMode.MANUAL

    stub._winding_factor_mode_var.set(WINDING_FACTOR_MODE_LABELS_ZH[WindingFactorMode.AUTO])
    assert stub.selected_mode() is WindingFactorMode.AUTO

    stub._winding_factor_mode_var.set("something unexpected")
    assert stub.selected_mode() is WindingFactorMode.MANUAL


def test_manual_mode_leaves_the_production_k_w_untouched(mixin):
    stub = _AppStub(mixin, build_sample_legacy_params(k_w=0.8765))
    params = stub.get_params()

    assert params["k_w"] == pytest.approx(0.8765)
    assert stub._winding_factor_resolution.provenance is WindingFactorProvenance.MANUAL_USER


def test_auto_mode_replaces_k_w_only_with_sufficient_geometry(mixin):
    stub = _AppStub(
        mixin,
        build_sample_legacy_params(slots=24, p=2, k_w=0.8765),
        mode=WindingFactorMode.AUTO,
    )

    # No coil span -> manual value preserved.
    assert stub.get_params()["k_w"] == pytest.approx(0.8765)
    assert (
        stub._winding_factor_resolution.provenance
        is WindingFactorProvenance.NOT_ENOUGH_GEOMETRY
    )

    # Explicit coil span -> derived value used.
    stub._coil_span_slots_var.set("5")
    assert stub.get_params()["k_w"] == pytest.approx(0.9330127019, abs=1e-9)
    assert stub._winding_factor_resolution.provenance is WindingFactorProvenance.AUTO_GEOMETRY


def test_switching_back_to_manual_restores_the_exact_original_value(mixin):
    stub = _AppStub(
        mixin,
        build_sample_legacy_params(slots=24, p=2, k_w=0.8765),
        mode=WindingFactorMode.AUTO,
    )
    stub._coil_span_slots_var.set("5")
    assert stub.get_params()["k_w"] != pytest.approx(0.8765)

    stub._winding_factor_mode_var.set(WINDING_FACTOR_MODE_LABELS_ZH[WindingFactorMode.MANUAL])
    assert stub.get_params()["k_w"] == pytest.approx(0.8765)


def test_project_without_rc2_metadata_is_marked_legacy_and_kept_manual(mixin):
    """A .motorproj saved before RC2 must never look model-derived."""

    stub = _AppStub(mixin, build_sample_legacy_params(k_w=0.93))
    stub.restore({"input_mode": "ADVANCED", "length_unit": "mm"})  # pre-RC2 payload

    assert stub._winding_factor_manual_provenance is WindingFactorProvenance.LEGACY_PROJECT
    assert stub.selected_mode() is WindingFactorMode.MANUAL
    assert stub._coil_span_slots_var.get() == ""
    resolution = stub.latest()
    assert resolution.provenance is WindingFactorProvenance.LEGACY_PROJECT
    assert resolution.value == pytest.approx(0.93)
    assert stub.get_params()["k_w"] == pytest.approx(0.93)


def test_project_with_rc2_metadata_restores_auto_mode(mixin):
    stub = _AppStub(mixin, build_sample_legacy_params(slots=24, p=2, k_w=0.93))
    stub.restore(
        {
            "winding_factor_mode": "auto",
            "coil_span_slots": "5",
            "skew_slots": "0",
        }
    )

    assert stub.selected_mode() is WindingFactorMode.AUTO
    assert stub._coil_span_slots_var.get() == "5"
    assert stub._winding_factor_manual_provenance is WindingFactorProvenance.MANUAL_USER
    assert stub.get_params()["k_w"] == pytest.approx(0.9330127019, abs=1e-9)


def test_unknown_stored_mode_degrades_to_manual(mixin):
    stub = _AppStub(mixin, build_sample_legacy_params(k_w=0.93))
    stub.restore({"winding_factor_mode": "telepathy", "coil_span_slots": "5"})

    assert stub.selected_mode() is WindingFactorMode.MANUAL
    assert stub.get_params()["k_w"] == pytest.approx(0.93)


def test_preset_provenance_is_reported_when_a_preset_supplied_k_w(mixin):
    stub = _AppStub(mixin, build_sample_legacy_params(k_w=0.93))
    stub._winding_factor_manual_provenance = WindingFactorProvenance.PRESET

    resolution = stub.resolve(parse_legacy_gui_params(stub._collect_raw_params()))
    assert resolution.provenance is WindingFactorProvenance.PRESET
    assert resolution.provenance_label_zh == "预设提供"


def test_summary_caption_is_populated_and_mentions_provenance(mixin):
    stub = _AppStub(mixin, build_sample_legacy_params(slots=24, p=2), mode=WindingFactorMode.AUTO)
    stub._coil_span_slots_var.set("5")
    stub.refresh()

    caption = stub._winding_factor_summary_var.get()
    assert "自动计算" in caption
    assert "k_d" in caption and "k_p" in caption and "k_s" in caption


def test_invalid_inputs_do_not_raise_from_the_summary_refresh(mixin):
    stub = _AppStub(mixin, build_sample_legacy_params())
    stub._raw["p"] = "not-a-number"
    stub.refresh()

    assert "无效" in stub._winding_factor_summary_var.get()


def test_get_params_is_safe_before_the_winding_factor_ux_exists(mixin):
    """`_get_params` runs during legacy construction, before the panel exists."""

    class _Bare:
        def _collect_raw_params(self):
            return build_sample_legacy_params(k_w=0.91)

    params = mixin._get_params(_Bare())
    assert params["k_w"] == pytest.approx(0.91)
