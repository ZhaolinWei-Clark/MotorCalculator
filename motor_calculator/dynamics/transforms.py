"""Amplitude-invariant coordinate transforms for future FOC work."""

from __future__ import annotations

from dataclasses import dataclass
import math


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite, got {value!r}")


@dataclass(frozen=True)
class ABCPhaseValues:
    """Three-phase values in the stationary abc coordinate system."""

    a: float
    b: float
    c: float

    def __post_init__(self) -> None:
        for name, value in (("a", self.a), ("b", self.b), ("c", self.c)):
            _require_finite(name, value)


@dataclass(frozen=True)
class AlphaBetaValues:
    """Two-axis values in the stationary alpha-beta coordinate system."""

    alpha: float
    beta: float

    def __post_init__(self) -> None:
        _require_finite("alpha", self.alpha)
        _require_finite("beta", self.beta)


@dataclass(frozen=True)
class DQValues:
    """Two-axis values in the rotating dq coordinate system."""

    d: float
    q: float

    def __post_init__(self) -> None:
        _require_finite("d", self.d)
        _require_finite("q", self.q)


def clarke_transform(abc: ABCPhaseValues) -> AlphaBetaValues:
    """Apply the balanced, amplitude-invariant abc to alpha-beta transform.

    This Phase 6H convention assumes ``a + b + c = 0``. The zero-sequence
    component is intentionally ignored rather than represented.
    """

    if not isinstance(abc, ABCPhaseValues):
        raise TypeError("abc must be an ABCPhaseValues instance")
    return AlphaBetaValues(
        alpha=abc.a,
        beta=(abc.a + 2.0 * abc.b) / math.sqrt(3.0),
    )


def inverse_clarke_transform(alpha_beta: AlphaBetaValues) -> ABCPhaseValues:
    """Apply the amplitude-invariant alpha-beta to balanced abc transform."""

    if not isinstance(alpha_beta, AlphaBetaValues):
        raise TypeError("alpha_beta must be an AlphaBetaValues instance")
    half_alpha = 0.5 * alpha_beta.alpha
    beta_component = 0.5 * math.sqrt(3.0) * alpha_beta.beta
    return ABCPhaseValues(
        a=alpha_beta.alpha,
        b=-half_alpha + beta_component,
        c=-half_alpha - beta_component,
    )


def park_transform(alpha_beta: AlphaBetaValues, theta_e_rad: float) -> DQValues:
    """Rotate stationary alpha-beta values into the electrical dq frame."""

    if not isinstance(alpha_beta, AlphaBetaValues):
        raise TypeError("alpha_beta must be an AlphaBetaValues instance")
    _require_finite("theta_e_rad", theta_e_rad)
    cosine = math.cos(theta_e_rad)
    sine = math.sin(theta_e_rad)
    return DQValues(
        d=alpha_beta.alpha * cosine + alpha_beta.beta * sine,
        q=-alpha_beta.alpha * sine + alpha_beta.beta * cosine,
    )


def inverse_park_transform(dq: DQValues, theta_e_rad: float) -> AlphaBetaValues:
    """Rotate electrical dq values back into the stationary alpha-beta frame."""

    if not isinstance(dq, DQValues):
        raise TypeError("dq must be a DQValues instance")
    _require_finite("theta_e_rad", theta_e_rad)
    cosine = math.cos(theta_e_rad)
    sine = math.sin(theta_e_rad)
    return AlphaBetaValues(
        alpha=dq.d * cosine - dq.q * sine,
        beta=dq.d * sine + dq.q * cosine,
    )


def wrap_electrical_angle(theta_e_rad: float) -> float:
    """Wrap a finite electrical angle into the half-open interval [0, 2*pi)."""

    _require_finite("theta_e_rad", theta_e_rad)
    return theta_e_rad % math.tau


def electrical_angle(theta_m_rad: float, pole_pairs: int) -> float:
    """Map an unwrapped mechanical angle to its unwrapped electrical angle."""

    _require_finite("theta_m_rad", theta_m_rad)
    if isinstance(pole_pairs, bool) or not isinstance(pole_pairs, int) or pole_pairs <= 0:
        raise ValueError("pole_pairs must be a positive integer")
    theta_e_rad = pole_pairs * theta_m_rad
    _require_finite("electrical angle", theta_e_rad)
    return theta_e_rad
