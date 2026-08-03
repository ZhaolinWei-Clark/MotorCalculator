"""Reusable stateful PI controller for sandbox control experiments."""

from __future__ import annotations

import math


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


class PIController:
    """A PI controller with optional back-calculation anti-windup."""

    def __init__(
        self,
        kp: float,
        ki: float,
        anti_windup_gain: float = 0.0,
    ) -> None:
        _require_finite("kp", kp)
        _require_finite("ki", ki)
        _require_finite("anti_windup_gain", anti_windup_gain)
        if kp < 0.0 or ki < 0.0 or anti_windup_gain < 0.0:
            raise ValueError("kp, ki, and anti_windup_gain must be non-negative")
        self.kp = kp
        self.ki = ki
        self.anti_windup_gain = anti_windup_gain
        self._integral_state = 0.0

    @property
    def integral_state(self) -> float:
        return self._integral_state

    @property
    def anti_windup_enabled(self) -> bool:
        """Report whether inverter tracking alters the integral state."""

        return self.anti_windup_gain > 0.0

    def compute(self, error: float, dt: float) -> float:
        """Advance the integral once and return the PI correction."""

        _require_finite("error", error)
        _require_finite("dt", dt)
        if dt <= 0.0:
            raise ValueError("dt must be greater than zero")

        self._integral_state += error * dt
        return self.kp * error + self.ki * self._integral_state

    def update(self, error: float, dt: float) -> float:
        """Alias for :meth:`compute` for control-loop terminology."""

        return self.compute(error, dt)

    def reset(self) -> None:
        self._integral_state = 0.0

    def apply_anti_windup(
        self,
        commanded_output: float,
        applied_output: float,
        dt: float,
    ) -> None:
        """Apply ``Kaw * (u_sat - u)`` after the error integration update."""

        _require_finite("commanded_output", commanded_output)
        _require_finite("applied_output", applied_output)
        _require_finite("dt", dt)
        if dt <= 0.0:
            raise ValueError("dt must be greater than zero")
        self._integral_state += (
            self.anti_windup_gain
            * (applied_output - commanded_output)
            * dt
        )
