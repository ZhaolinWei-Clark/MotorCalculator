"""Immutable state and input records for the Phase 6B dynamics sandbox."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


@dataclass(frozen=True)
class MotorState:
    """PMSM dq state in SI units.

    ``id`` and ``iq`` are amperes, ``omega_m`` is mechanical rad/s, and
    ``theta`` is the unwrapped mechanical rotor angle in radians.
    """

    id: float
    iq: float
    omega_m: float
    theta: float

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("iq", self.iq),
            ("omega_m", self.omega_m),
            ("theta", self.theta),
        ):
            _require_finite(name, value)


@dataclass(frozen=True)
class InputState:
    """Instantaneous dq voltage and mechanical load input in SI units."""

    Vd: float
    Vq: float
    load_torque: float

    def __post_init__(self) -> None:
        for name, value in (
            ("Vd", self.Vd),
            ("Vq", self.Vq),
            ("load_torque", self.load_torque),
        ):
            _require_finite(name, value)


@dataclass(frozen=True)
class DQElectricalDerivatives:
    """Electrical dq derivatives and electrical speed in SI units."""

    did_dt: float
    diq_dt: float
    omega_e: float

    def __post_init__(self) -> None:
        for name, value in (
            ("did_dt", self.did_dt),
            ("diq_dt", self.diq_dt),
            ("omega_e", self.omega_e),
        ):
            _require_finite(name, value)


@dataclass(frozen=True)
class StateDerivatives:
    """Time derivatives corresponding to :class:`MotorState`."""

    did_dt: float
    diq_dt: float
    domega_dt: float
    dtheta_dt: float

    def __post_init__(self) -> None:
        for name, value in (
            ("did_dt", self.did_dt),
            ("diq_dt", self.diq_dt),
            ("domega_dt", self.domega_dt),
            ("dtheta_dt", self.dtheta_dt),
        ):
            _require_finite(name, value)
