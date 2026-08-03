"""Continuous-time PMSM dq equations for the isolated simulation sandbox."""

from __future__ import annotations

from dataclasses import dataclass
import math

from .state import DQElectricalDerivatives, InputState, MotorState, StateDerivatives


@dataclass(frozen=True)
class PMSMDynamicParameters:
    """Lumped PMSM parameters in SI units.

    ``Rs`` is phase resistance (ohm), ``Ld`` and ``Lq`` are dq inductances
    (H), ``psi_f`` is permanent-magnet flux linkage (Wb), ``J`` is rotor and
    load inertia (kg*m^2), and ``B`` is viscous friction (N*m/(rad/s)).
    These values belong only to the dynamics sandbox and are never written to
    the production analytical model.
    """

    Rs: float
    Ld: float
    Lq: float
    psi_f: float
    pole_pairs: int
    J: float
    B: float

    def __post_init__(self) -> None:
        numeric_values = (
            ("Rs", self.Rs),
            ("Ld", self.Ld),
            ("Lq", self.Lq),
            ("psi_f", self.psi_f),
            ("J", self.J),
            ("B", self.B),
        )
        for name, value in numeric_values:
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite, got {value!r}")
        if self.Rs < 0.0:
            raise ValueError("Rs must be non-negative")
        if self.Ld <= 0.0 or self.Lq <= 0.0:
            raise ValueError("Ld and Lq must be greater than zero")
        if self.psi_f <= 0.0:
            raise ValueError("psi_f must be greater than zero")
        if isinstance(self.pole_pairs, bool) or not isinstance(self.pole_pairs, int) or self.pole_pairs <= 0:
            raise ValueError("pole_pairs must be a positive integer")
        if self.J <= 0.0:
            raise ValueError("J must be greater than zero")
        if self.B < 0.0:
            raise ValueError("B must be non-negative")


class PMSMDynamicModel:
    """Evaluate PMSM derivatives without performing time integration."""

    @staticmethod
    def compute_electromagnetic_torque(
        state: MotorState,
        parameters: PMSMDynamicParameters,
    ) -> float:
        return 1.5 * parameters.pole_pairs * (
            parameters.psi_f * state.iq
            + (parameters.Ld - parameters.Lq) * state.id * state.iq
        )

    @classmethod
    def compute_mechanical_power(
        cls,
        state: MotorState,
        parameters: PMSMDynamicParameters,
    ) -> float:
        return cls.compute_electromagnetic_torque(state, parameters) * state.omega_m

    @staticmethod
    def compute_electrical_derivatives(
        state: MotorState,
        input: InputState,
        parameters: PMSMDynamicParameters,
    ) -> DQElectricalDerivatives:
        """Evaluate only the coupled PMSM dq electrical equations."""

        omega_e = parameters.pole_pairs * state.omega_m
        did_dt = (
            input.Vd
            - parameters.Rs * state.id
            + omega_e * parameters.Lq * state.iq
        ) / parameters.Ld
        diq_dt = (
            input.Vq
            - parameters.Rs * state.iq
            - omega_e * (parameters.Ld * state.id + parameters.psi_f)
        ) / parameters.Lq
        return DQElectricalDerivatives(
            did_dt=did_dt,
            diq_dt=diq_dt,
            omega_e=omega_e,
        )

    @staticmethod
    def compute_mechanical_speed_derivative(
        state: MotorState,
        electromagnetic_torque: float,
        load_torque: float,
        parameters: PMSMDynamicParameters,
    ) -> float:
        """Evaluate the existing torque-driven mechanical speed equation."""

        if not math.isfinite(electromagnetic_torque) or not math.isfinite(load_torque):
            raise ValueError("torque inputs must be finite")
        return (
            electromagnetic_torque
            - load_torque
            - parameters.B * state.omega_m
        ) / parameters.J

    @classmethod
    def compute_derivatives(
        cls,
        state: MotorState,
        input: InputState,
        parameters: PMSMDynamicParameters,
    ) -> StateDerivatives:
        electrical_derivatives = cls.compute_electrical_derivatives(state, input, parameters)
        electromagnetic_torque = cls.compute_electromagnetic_torque(state, parameters)
        domega_dt = cls.compute_mechanical_speed_derivative(
            state=state,
            electromagnetic_torque=electromagnetic_torque,
            load_torque=input.load_torque,
            parameters=parameters,
        )

        return StateDerivatives(
            did_dt=electrical_derivatives.did_dt,
            diq_dt=electrical_derivatives.diq_dt,
            domega_dt=domega_dt,
            dtheta_dt=state.omega_m,
        )
