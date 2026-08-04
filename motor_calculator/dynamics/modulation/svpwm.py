"""Deterministic SVPWM average-voltage foundation for the dynamic sandbox."""

from __future__ import annotations

import math

from ..transforms import (
    ABCPhaseValues,
    AlphaBetaValues,
    DQValues,
    clarke_transform,
    inverse_clarke_transform,
    inverse_park_transform,
    park_transform,
    wrap_electrical_angle,
)
from .modulation_results import SVPWMConfig, SVPWMResult


class SVPWMModulator:
    """Convert voltage references into bounded average inverter voltages.

    The implementation uses common-mode injection and reconstructs the
    phase-neutral average voltages from the three duty ratios. It does not
    create switching edges, carrier waveforms, or device-level losses.
    """

    @staticmethod
    def determine_sector(alpha_voltage_v: float, beta_voltage_v: float) -> int:
        """Return sectors 1..6 with exact boundaries assigned to the next sector."""

        if not math.isfinite(alpha_voltage_v) or not math.isfinite(beta_voltage_v):
            raise ValueError("alpha-beta voltage commands must be finite")
        if alpha_voltage_v == 0.0 and beta_voltage_v == 0.0:
            return 1
        angle = wrap_electrical_angle(math.atan2(beta_voltage_v, alpha_voltage_v))
        return min(int(angle / (math.pi / 3.0)) + 1, 6)

    def modulate_dq(
        self,
        vd_command_v: float,
        vq_command_v: float,
        theta_e_rad: float,
        config: SVPWMConfig,
        reconstruction_theta_e_rad: float | None = None,
    ) -> SVPWMResult:
        """Apply inverse Park, average SVPWM, and dq voltage reconstruction."""

        if not isinstance(config, SVPWMConfig):
            raise TypeError("config must be an SVPWMConfig")
        if not config.enabled:
            raise ValueError("SVPWMConfig.enabled must be true when modulation is used")
        command = inverse_park_transform(
            DQValues(d=vd_command_v, q=vq_command_v), theta_e_rad
        )
        reconstruction_angle = (
            theta_e_rad
            if reconstruction_theta_e_rad is None
            else reconstruction_theta_e_rad
        )
        return self.modulate_alpha_beta(
            command.alpha,
            command.beta,
            theta_e_rad,
            config,
            reconstruction_angle,
        )

    def modulate_alpha_beta(
        self,
        alpha_command_v: float,
        beta_command_v: float,
        controller_theta_e_rad: float,
        config: SVPWMConfig,
        reconstruction_theta_e_rad: float | None = None,
    ) -> SVPWMResult:
        """Generate duties and reconstruct the applied average voltage."""

        if not isinstance(config, SVPWMConfig):
            raise TypeError("config must be an SVPWMConfig")
        if not config.enabled:
            raise ValueError("SVPWMConfig.enabled must be true when modulation is used")
        for name, value in (
            ("alpha_command_v", alpha_command_v),
            ("beta_command_v", beta_command_v),
            ("controller_theta_e_rad", controller_theta_e_rad),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        plant_angle = (
            controller_theta_e_rad
            if reconstruction_theta_e_rad is None
            else reconstruction_theta_e_rad
        )
        if not math.isfinite(plant_angle):
            raise ValueError("reconstruction_theta_e_rad must be finite")

        requested_magnitude = math.hypot(alpha_command_v, beta_command_v)
        modulation_index = requested_magnitude / config.linear_voltage_limit_v
        alpha_applied = alpha_command_v
        beta_applied = beta_command_v
        overmodulation_active = config.allow_overmodulation and modulation_index > 1.0
        voltage_saturated = False
        warnings: list[str] = []

        if not config.allow_overmodulation and modulation_index > 1.0:
            scale = 1.0 / modulation_index
            alpha_applied *= scale
            beta_applied *= scale
            voltage_saturated = True
            warnings.append(
                "SVPWM command exceeded the Vdc/sqrt(3) linear envelope and was scaled."
            )

        phase_reference = inverse_clarke_transform(
            AlphaBetaValues(alpha=alpha_applied, beta=beta_applied)
        )
        phase_values = phase_reference.a, phase_reference.b, phase_reference.c
        phase_span = max(phase_values) - min(phase_values)
        available_span = config.duty_span * config.dc_bus_voltage_v

        if config.allow_overmodulation and phase_span > available_span:
            scale = available_span / phase_span
            alpha_applied *= scale
            beta_applied *= scale
            phase_reference = inverse_clarke_transform(
                AlphaBetaValues(alpha=alpha_applied, beta=beta_applied)
            )
            phase_values = phase_reference.a, phase_reference.b, phase_reference.c
            voltage_saturated = True
            warnings.append(
                "SVPWM overmodulation command exceeded the feasible duty hexagon and was scaled."
            )
        elif overmodulation_active:
            warnings.append(
                "SVPWM overmodulation average model is active; switching harmonics are not represented."
            )

        duty_center = 0.5 * (config.minimum_duty + config.maximum_duty)
        common_mode_v = (
            -0.5 * (max(phase_values) + min(phase_values))
            + (duty_center - 0.5) * config.dc_bus_voltage_v
        )
        duties = tuple(
            _clamp(
                0.5 + (phase_v + common_mode_v) / config.dc_bus_voltage_v,
                config.minimum_duty,
                config.maximum_duty,
            )
            for phase_v in phase_values
        )

        pole_voltages = tuple(
            (duty - 0.5) * config.dc_bus_voltage_v for duty in duties
        )
        neutral_voltage = sum(pole_voltages) / 3.0
        phase_voltages = tuple(value - neutral_voltage for value in pole_voltages)
        reconstructed = clarke_transform(ABCPhaseValues(*phase_voltages))
        controller_dq = park_transform(reconstructed, controller_theta_e_rad)
        plant_dq = park_transform(reconstructed, plant_angle)

        return SVPWMResult(
            sector=self.determine_sector(alpha_command_v, beta_command_v),
            modulation_index=modulation_index,
            duty_a=duties[0],
            duty_b=duties[1],
            duty_c=duties[2],
            phase_voltage_a_avg_v=phase_voltages[0],
            phase_voltage_b_avg_v=phase_voltages[1],
            phase_voltage_c_avg_v=phase_voltages[2],
            alpha_voltage_avg_v=reconstructed.alpha,
            beta_voltage_avg_v=reconstructed.beta,
            vd_actual_v=plant_dq.d,
            vq_actual_v=plant_dq.q,
            overmodulation_active=overmodulation_active,
            voltage_saturated=voltage_saturated,
            warning_messages=tuple(warnings),
            vd_controller_frame_v=controller_dq.d,
            vq_controller_frame_v=controller_dq.q,
        )


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)
