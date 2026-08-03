"""Deterministic Phase 6B sandbox examples; values are not calibrated."""

from __future__ import annotations

from dataclasses import dataclass

from .pmsm_model import PMSMDynamicModel, PMSMDynamicParameters
from .simulation_results import SimulationResult
from .simulation_runner import SimulationRunner
from .state import InputState, MotorState


@dataclass(frozen=True)
class SteadyStateVerification:
    result: SimulationResult
    final_domega_dt: float
    final_torque_error: float


def example_parameters() -> PMSMDynamicParameters:
    """Return transparent synthetic parameters for demonstrations only."""

    return PMSMDynamicParameters(
        Rs=0.5,
        Ld=0.005,
        Lq=0.005,
        psi_f=0.1,
        pole_pairs=4,
        J=0.01,
        B=0.002,
    )


def run_startup_example() -> SimulationResult:
    return SimulationRunner().run(
        initial_state=MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0),
        motor_parameters=example_parameters(),
        input_profile=InputState(Vd=0.0, Vq=24.0, load_torque=0.0),
        simulation_time=1.0,
        time_step=0.0001,
    )


def run_load_step_example() -> SimulationResult:
    def load_step(time_s: float) -> InputState:
        return InputState(Vd=0.0, Vq=24.0, load_torque=0.0 if time_s < 1.0 else 1.0)

    return SimulationRunner().run(
        initial_state=MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0),
        motor_parameters=example_parameters(),
        input_profile=load_step,
        simulation_time=2.0,
        time_step=0.0001,
    )


def run_steady_state_verification_example() -> SteadyStateVerification:
    parameters = example_parameters()
    final_input = InputState(Vd=0.0, Vq=24.0, load_torque=1.0)
    result = SimulationRunner().run(
        initial_state=MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0),
        motor_parameters=parameters,
        input_profile=final_input,
        simulation_time=5.0,
        time_step=0.0001,
    )
    final_derivatives = PMSMDynamicModel.compute_derivatives(result.final_state, final_input, parameters)
    final_torque = PMSMDynamicModel.compute_electromagnetic_torque(result.final_state, parameters)
    opposing_torque = final_input.load_torque + parameters.B * result.final_state.omega_m
    return SteadyStateVerification(
        result=result,
        final_domega_dt=final_derivatives.domega_dt,
        final_torque_error=final_torque - opposing_torque,
    )


def _print_example_summary() -> None:
    startup = run_startup_example()
    load_step = run_load_step_example()
    steady = run_steady_state_verification_example()
    before_load_index = load_step.time.index(1.0)

    print(f"startup final speed: {startup.speed[-1]:.6f} rad/s")
    print(f"load-step speed at 1 s: {load_step.speed[before_load_index]:.6f} rad/s")
    print(f"load-step final speed: {load_step.speed[-1]:.6f} rad/s")
    print(f"load-step final iq: {load_step.iq[-1]:.6f} A")
    print(f"steady final torque: {steady.result.torque[-1]:.6f} N*m")
    print(f"steady final domega/dt: {steady.final_domega_dt:.9f} rad/s^2")
    print(f"steady torque-balance error: {steady.final_torque_error:.9f} N*m")


if __name__ == "__main__":
    _print_example_summary()
