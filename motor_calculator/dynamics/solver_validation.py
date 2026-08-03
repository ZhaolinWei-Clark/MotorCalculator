"""Numerical validation helpers for the Phase 6C dynamics sandbox."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import math

from .examples import example_parameters
from .integrators import EulerIntegrator, RK4Integrator
from .pmsm_model import PMSMDynamicModel
from .simulation_results import SimulationResult
from .simulation_runner import SimulationRunner
from .state import InputState, MotorState

CONVERGENCE_TIME_STEPS = (1.0e-2, 1.0e-3, 1.0e-4)
CONVERGENCE_SIMULATION_TIME = 0.2


@dataclass(frozen=True)
class SolverConvergenceRecord:
    solver_name: str
    time_step: float
    final_speed: float
    final_torque: float
    final_id: float
    final_iq: float
    final_current_magnitude: float
    speed_relative_error: float
    torque_relative_error: float
    current_relative_error: float
    status: str


@dataclass(frozen=True)
class SteadyStateConsistency:
    final_speed: float
    dynamic_torque: float
    steady_state_torque: float
    torque_relative_error: float
    final_domega_dt: float


@dataclass(frozen=True)
class PowerTrendRecord:
    time: float
    electrical_power: float
    mechanical_power: float
    raw_power_difference: float


def _relative_error(value: float, reference: float) -> float:
    return abs(value - reference) / max(abs(reference), 1.0e-15)


def _run_convergence_case(solver_name: str, time_step: float) -> tuple[str, float, SimulationResult]:
    integrator = EulerIntegrator() if solver_name == "Euler" else RK4Integrator()
    result = SimulationRunner(integrator=integrator).run(
        initial_state=MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0),
        motor_parameters=example_parameters(),
        input_profile=InputState(Vd=0.0, Vq=24.0, load_torque=0.5),
        simulation_time=CONVERGENCE_SIMULATION_TIME,
        time_step=time_step,
    )
    return solver_name, time_step, result


@lru_cache(maxsize=1)
def run_solver_convergence_analysis() -> tuple[SolverConvergenceRecord, ...]:
    raw_results = tuple(
        _run_convergence_case(solver_name, time_step)
        for solver_name in ("Euler", "RK4")
        for time_step in CONVERGENCE_TIME_STEPS
    )
    reference_result = next(
        result
        for solver_name, time_step, result in raw_results
        if solver_name == "RK4" and time_step == min(CONVERGENCE_TIME_STEPS)
    )
    reference_current = math.hypot(reference_result.id[-1], reference_result.iq[-1])

    records = []
    for solver_name, time_step, result in raw_results:
        current_magnitude = math.hypot(result.id[-1], result.iq[-1])
        speed_error = _relative_error(result.speed[-1], reference_result.speed[-1])
        torque_error = _relative_error(result.torque[-1], reference_result.torque[-1])
        current_error = _relative_error(current_magnitude, reference_current)
        maximum_error = max(speed_error, torque_error, current_error)
        records.append(
            SolverConvergenceRecord(
                solver_name=solver_name,
                time_step=time_step,
                final_speed=result.speed[-1],
                final_torque=result.torque[-1],
                final_id=result.id[-1],
                final_iq=result.iq[-1],
                final_current_magnitude=current_magnitude,
                speed_relative_error=speed_error,
                torque_relative_error=torque_error,
                current_relative_error=current_error,
                status="unstable" if maximum_error > 1.0 else "finite",
            )
        )
    return tuple(records)


@lru_cache(maxsize=1)
def _run_steady_state_case() -> tuple[SimulationResult, InputState]:
    input_state = InputState(Vd=0.0, Vq=24.0, load_torque=1.0)
    result = SimulationRunner(integrator=RK4Integrator()).run(
        initial_state=MotorState(id=0.0, iq=0.0, omega_m=0.0, theta=0.0),
        motor_parameters=example_parameters(),
        input_profile=input_state,
        simulation_time=5.0,
        time_step=1.0e-3,
    )
    return result, input_state


def calculate_steady_state_consistency() -> SteadyStateConsistency:
    result, input_state = _run_steady_state_case()
    parameters = example_parameters()
    derivatives = PMSMDynamicModel.compute_derivatives(result.final_state, input_state, parameters)
    steady_state_torque = input_state.load_torque + parameters.B * result.speed[-1]
    return SteadyStateConsistency(
        final_speed=result.speed[-1],
        dynamic_torque=result.torque[-1],
        steady_state_torque=steady_state_torque,
        torque_relative_error=_relative_error(result.torque[-1], steady_state_torque),
        final_domega_dt=derivatives.domega_dt,
    )


def collect_power_balance_trend() -> tuple[PowerTrendRecord, ...]:
    result, _ = _run_steady_state_case()
    records = []
    for requested_time in (0.01, 0.1, 0.5, 1.0, 5.0):
        index = min(range(len(result.time)), key=lambda item: abs(result.time[item] - requested_time))
        electrical_power = result.electrical_power[index]
        mechanical_power = result.mechanical_power[index]
        records.append(
            PowerTrendRecord(
                time=result.time[index],
                electrical_power=electrical_power,
                mechanical_power=mechanical_power,
                raw_power_difference=electrical_power - mechanical_power,
            )
        )
    return tuple(records)


def print_validation_summary() -> None:
    for record in run_solver_convergence_analysis():
        print(
            record.solver_name,
            f"dt={record.time_step:.0e}",
            f"speed={record.final_speed:.12g}",
            f"torque={record.final_torque:.12g}",
            f"current={record.final_current_magnitude:.12g}",
            f"speed_error={record.speed_relative_error:.6e}",
            f"torque_error={record.torque_relative_error:.6e}",
            f"current_error={record.current_relative_error:.6e}",
            f"status={record.status}",
        )
    steady = calculate_steady_state_consistency()
    print(
        "steady",
        f"speed={steady.final_speed:.12g}",
        f"dynamic_torque={steady.dynamic_torque:.12g}",
        f"relationship_torque={steady.steady_state_torque:.12g}",
        f"relative_error={steady.torque_relative_error:.6e}",
        f"domega_dt={steady.final_domega_dt:.6e}",
    )
    for record in collect_power_balance_trend():
        print(
            "power",
            f"time={record.time:.2f}",
            f"electrical={record.electrical_power:.12g}",
            f"mechanical={record.mechanical_power:.12g}",
            f"raw_difference={record.raw_power_difference:.12g}",
        )


if __name__ == "__main__":
    print_validation_summary()
