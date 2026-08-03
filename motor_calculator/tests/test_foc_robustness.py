"""Anti-windup and dq decoupling checks for the Phase 6J foundation."""

from __future__ import annotations

import math

import pytest

from dynamics import (
    DCBusConfig,
    DQCurrentController,
    DQVoltageCommand,
    FOCReference,
    FOCRunner,
    FOCRunnerConfig,
    FOCStepInput,
    PIController,
    PMSMDynamicParameters,
    compute_pmsm_dq_decoupling_feedforward,
)


def _parameters() -> PMSMDynamicParameters:
    return PMSMDynamicParameters(
        Rs=1.0,
        Ld=0.01,
        Lq=0.02,
        psi_f=0.1,
        pole_pairs=2,
        J=1.0,
        B=0.0,
    )


def _zero_current_input(*, omega_m_rad_s: float = 0.0) -> FOCStepInput:
    return FOCStepInput(
        phase_current_a=0.0,
        phase_current_b=0.0,
        phase_current_c=0.0,
        theta_m_rad=0.0,
        omega_m_rad_s=omega_m_rad_s,
        load_torque_nm=0.0,
    )


def test_pi_without_anti_windup_preserves_previous_behavior():
    controller = PIController(kp=2.0, ki=3.0)

    first_output = controller.compute(error=1.0, dt=0.1)
    controller.apply_anti_windup(
        commanded_output=first_output,
        applied_output=0.0,
        dt=0.1,
    )
    second_output = controller.compute(error=-0.5, dt=0.2)

    assert controller.anti_windup_enabled is False
    assert first_output == pytest.approx(2.3)
    assert controller.integral_state == pytest.approx(0.0)
    assert second_output == pytest.approx(-1.0)


def test_back_calculation_reduces_integrator_accumulation_during_saturation():
    baseline = PIController(kp=0.0, ki=1.0)
    robust = PIController(kp=0.0, ki=1.0, anti_windup_gain=5.0)

    for _ in range(20):
        baseline_output = baseline.compute(error=10.0, dt=0.01)
        baseline.apply_anti_windup(baseline_output, applied_output=0.0, dt=0.01)
        robust_output = robust.compute(error=10.0, dt=0.01)
        robust.apply_anti_windup(robust_output, applied_output=0.0, dt=0.01)

    assert robust.anti_windup_enabled is True
    assert abs(robust.integral_state) < abs(baseline.integral_state)


def test_anti_windup_controller_reset_clears_corrected_integral():
    controller = PIController(kp=1.0, ki=1.0, anti_windup_gain=2.0)
    output = controller.compute(error=3.0, dt=0.1)
    controller.apply_anti_windup(output, applied_output=0.0, dt=0.1)

    controller.reset()

    assert controller.integral_state == 0.0


class _RecordingDQController(DQCurrentController):
    def __init__(self) -> None:
        super().__init__(kp=100.0, ki=0.0, anti_windup_gain=1.0)
        self.last_saturation_feedback = None

    def track_applied_voltage(
        self,
        command: DQVoltageCommand,
        vd_actual_v: float,
        vq_actual_v: float,
        dt: float,
    ):
        feedback = super().track_applied_voltage(
            command,
            vd_actual_v,
            vq_actual_v,
            dt,
        )
        self.last_saturation_feedback = feedback
        return feedback


def test_foc_runner_passes_inverter_saturation_feedback_to_controller():
    controller = _RecordingDQController()
    runner = FOCRunner(
        controller=controller,
        motor_parameters=_parameters(),
        config=FOCRunnerConfig(
            pole_pairs=2,
            control_time_step_s=0.001,
            use_inverter_limit=True,
        ),
        inverter_config=DCBusConfig(nominal_voltage_v=24.0),
    )

    output = runner.step(
        reference=FOCReference(id_ref_a=0.0, iq_ref_a=1.0),
        step_input=_zero_current_input(),
    )
    feedback = controller.last_saturation_feedback

    assert feedback is not None
    assert feedback.raw_voltage_command == output.raw_voltage_command
    assert feedback.saturated_voltage_command == output.saturated_voltage_command
    assert feedback.saturation_error == output.saturation_error
    assert feedback.saturation_active is True
    assert output.saturation_active is True
    assert feedback.saturation_error.vq_command_v == pytest.approx(
        output.vq_actual_v - output.vq_command_v
    )


def test_pmsm_dq_decoupling_terms_match_analytical_equations():
    feedforward = compute_pmsm_dq_decoupling_feedforward(
        omega_e_rad_s=100.0,
        id_a=2.0,
        iq_a=3.0,
        motor_parameters=_parameters(),
    )

    assert feedforward.vd_ff_v == pytest.approx(-6.0)
    assert feedforward.vq_ff_v == pytest.approx(12.0)


def test_disabled_decoupling_returns_zero_feedforward():
    feedforward = compute_pmsm_dq_decoupling_feedforward(
        omega_e_rad_s=100.0,
        id_a=2.0,
        iq_a=3.0,
        motor_parameters=_parameters(),
        enabled=False,
    )

    assert feedforward.vd_ff_v == 0.0
    assert feedforward.vq_ff_v == 0.0


def test_foc_runner_adds_optional_decoupling_to_pi_voltage():
    alpha = 2.0
    beta = 3.0
    phase_b = -0.5 * alpha + 0.5 * math.sqrt(3.0) * beta
    phase_c = -0.5 * alpha - 0.5 * math.sqrt(3.0) * beta
    runner = FOCRunner(
        controller=DQCurrentController(kp=0.0, ki=0.0),
        motor_parameters=_parameters(),
        config=FOCRunnerConfig(
            pole_pairs=2,
            control_time_step_s=0.001,
            use_inverter_limit=False,
            use_decoupling_feedforward=True,
        ),
    )

    output = runner.step(
        reference=FOCReference(id_ref_a=2.0, iq_ref_a=3.0),
        step_input=FOCStepInput(
            phase_current_a=alpha,
            phase_current_b=phase_b,
            phase_current_c=phase_c,
            theta_m_rad=0.0,
            omega_m_rad_s=50.0,
            load_torque_nm=0.0,
        ),
    )

    assert output.vd_command_v == pytest.approx(-6.0)
    assert output.vq_command_v == pytest.approx(12.0)


def test_existing_foc_runner_defaults_still_use_pi_only():
    runner = FOCRunner(
        controller=DQCurrentController(kp=5.0, ki=100.0),
        motor_parameters=_parameters(),
        config=FOCRunnerConfig(
            pole_pairs=2,
            control_time_step_s=0.001,
            use_inverter_limit=False,
        ),
    )

    output = runner.step(
        reference=FOCReference(id_ref_a=0.0, iq_ref_a=1.0),
        step_input=_zero_current_input(omega_m_rad_s=50.0),
    )

    assert output.vd_command_v == pytest.approx(0.0)
    assert output.vq_command_v == pytest.approx(5.1)
    assert output.saturation_active is False
