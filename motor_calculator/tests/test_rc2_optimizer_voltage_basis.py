"""RC2 Step 17: behavioural regression for the legacy optimizer voltage basis.

`run_optimization` still resolves to the legacy implementation at runtime (the
mixin does not override it), so its constraint is genuinely user-facing. These
tests drive the real legacy method through a minimal headless stub.
"""

from __future__ import annotations

import importlib
import math

import pytest

from motor_core import LegacyGuiMotorModelBridge, parse_legacy_gui_params
from motor_calculator.validation.design_feasibility import (
    evaluate_design_feasibility,
    feasible_starting_inputs,
    same_basis_available_line_rms_v,
)


def _legacy_module():
    return importlib.import_module("gui.main_window")._load_legacy_module()


def _application_default_inputs():
    from motor_calculator.input_ux.metadata import APPLICATION_DEFAULTS

    return dict(APPLICATION_DEFAULTS)


class _StringVar:
    def __init__(self, value=""):
        self._value = value

    def set(self, value):
        self._value = value

    def get(self):
        return self._value


class _TextWidget:
    def __init__(self):
        self.buffer = []

    def delete(self, *_args, **_kwargs):
        self.buffer.clear()

    def insert(self, _index, text):
        self.buffer.append(text)

    def see(self, *_args, **_kwargs):
        pass

    @property
    def text(self):
        return "".join(self.buffer)


class _Root:
    def update(self):
        pass


class _OptimizerHarness:
    """Minimal object satisfying everything `run_optimization` touches."""

    def __init__(self, parsed_params):
        self._parsed_params = dict(parsed_params)
        self.root = _Root()
        self.result_text = _TextWidget()
        self.vars = {
            "N_ph_turns": _StringVar(str(parsed_params["N_ph_turns"])),
            "n_parallel": _StringVar(str(parsed_params["n_parallel"])),
        }
        self.calc_results = None

    def _get_params(self):
        return dict(self._parsed_params)

    def _display_report(self):
        pass

    def _plot_performance_curves(self):
        pass

    def _plot_back_emf(self):
        pass

    def _plot_torque(self):
        pass

    def _plot_flux_distribution(self):
        pass

    def _draw_geometry(self):
        pass


def _run_legacy_optimizer(raw_inputs):
    module = _legacy_module()
    module.PMDCMotorModel = LegacyGuiMotorModelBridge
    harness = _OptimizerHarness(parse_legacy_gui_params(raw_inputs))
    module.MotorCalculatorApp.run_optimization(harness)
    return harness


@pytest.fixture(scope="module")
def slotted_starting_inputs():
    raw = feasible_starting_inputs(_application_default_inputs())
    return raw


def test_same_basis_envelope_helper_is_exact():
    for dc in (24.0, 48.0, 72.0, 400.0):
        assert math.isclose(
            same_basis_available_line_rms_v(dc), dc / math.sqrt(2.0), rel_tol=1e-15
        )


def test_optimizer_recommends_a_same_basis_feasible_design(slotted_starting_inputs):
    harness = _run_legacy_optimizer(slotted_starting_inputs)

    assert harness.calc_results is not None, harness.result_text.text
    recommended = dict(harness._get_params())
    recommended["N_ph_turns"] = int(harness.vars["N_ph_turns"].get())
    recommended["n_parallel"] = int(harness.vars["n_parallel"].get())

    parsed = parse_legacy_gui_params(recommended)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    assessment = evaluate_design_feasibility(parsed, result)

    assert assessment.voltage_margin_percent is not None
    assert assessment.voltage_margin_percent >= 0.0, (
        "the optimizer must not recommend a design that exceeds the linear "
        f"SVPWM line-RMS envelope; margin={assessment.voltage_margin_percent:.4f}% "
        f"required={result.performance.required_voltage_v:.4f} V "
        f"available={assessment.available_voltage_line_rms_v:.4f} V"
    )


def test_optimizer_recommendation_would_be_rejected_under_the_legacy_basis(
    slotted_starting_inputs,
):
    """The correction is behavioural, not cosmetic: the legacy raw-Vdc basis
    would have accepted a strictly higher turns count."""

    harness = _run_legacy_optimizer(slotted_starting_inputs)
    recommended_turns = int(harness.vars["N_ph_turns"].get())

    dc_bus = float(slotted_starting_inputs["V_dc"])
    envelope = same_basis_available_line_rms_v(dc_bus)

    legacy_accepted = []
    same_basis_accepted = []
    for turns in range(15, 120, 3):
        candidate = dict(slotted_starting_inputs)
        candidate["N_ph_turns"] = turns
        parsed = parse_legacy_gui_params(candidate)
        required = float(
            LegacyGuiMotorModelBridge(parsed).run_full_analysis().performance.required_voltage_v
        )
        if required <= dc_bus:
            legacy_accepted.append(turns)
        if required <= envelope:
            same_basis_accepted.append(turns)

    assert same_basis_accepted, "at least one candidate must satisfy the envelope"
    assert max(legacy_accepted) > max(same_basis_accepted), (
        "the legacy basis is expected to admit higher turns counts than the "
        f"same-basis envelope. legacy_max={max(legacy_accepted)} "
        f"same_basis_max={max(same_basis_accepted)}"
    )
    assert recommended_turns <= max(same_basis_accepted)


def test_optimizer_summary_uses_modern_labels(slotted_starting_inputs):
    harness = _run_legacy_optimizer(slotted_starting_inputs)
    text = harness.result_text.text

    assert "同基电压裕量" in text
    assert "近似裸铜槽占比" in text
    # Legacy values may remain, but only as explicitly marked compatibility values.
    assert "兼容值 legacy 直流母线差额" in text
    assert "Legacy 线性绕组占比" in text
    assert "所需线电压 RMS" in text
    for line in text.splitlines():
        if line.strip().startswith("• 电压裕量") or line.strip().startswith("• 填充系数"):
            pytest.fail(f"legacy metric exposed under a modern-sounding label: {line!r}")


def test_optimizer_slot_penalty_uses_modern_occupancy_when_geometry_exists(
    slotted_starting_inputs,
):
    """With slot geometry present the optimizer must judge occupancy on the
    Phase 8G metric, which is bounded, rather than on the unbounded proxy."""

    harness = _run_legacy_optimizer(slotted_starting_inputs)
    recommended = dict(harness._get_params())
    recommended["N_ph_turns"] = int(harness.vars["N_ph_turns"].get())
    recommended["n_parallel"] = int(harness.vars["n_parallel"].get())

    parsed = parse_legacy_gui_params(recommended)
    result = LegacyGuiMotorModelBridge(parsed).run_full_analysis()
    assessment = evaluate_design_feasibility(parsed, result)

    assert assessment.slot_fill_factor is not None
    assert assessment.slot_fill_factor <= float(parsed["fill_limit"])
    # The legacy proxy would have failed the same limit for every candidate.
    assert float(result.performance.fill_factor) > float(parsed["fill_limit"])
