"""Immutable result contracts for sandbox-only dynamic loss monitoring."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class LossModelConfig:
    """Enable individual loss monitors without changing plant equations."""

    enable_copper_loss: bool = True
    enable_iron_loss: bool = False
    enable_mechanical_loss: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("enable_copper_loss", self.enable_copper_loss),
            ("enable_iron_loss", self.enable_iron_loss),
            ("enable_mechanical_loss", self.enable_mechanical_loss),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{name} must be a bool")


@dataclass(frozen=True)
class IronLossEstimate:
    """Explicitly available or unavailable provisional iron-loss estimate."""

    loss_w: float | None
    available: bool
    provisional: bool
    method: str
    assumptions: tuple[str, ...] = ()
    warning_messages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.loss_w is not None:
            if not math.isfinite(self.loss_w) or self.loss_w < 0.0:
                raise ValueError("loss_w must be None or finite and non-negative")
        if not isinstance(self.available, bool) or not isinstance(self.provisional, bool):
            raise TypeError("available and provisional must be bool values")
        if self.available != (self.loss_w is not None):
            raise ValueError("available must agree with whether loss_w is present")
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "warning_messages", tuple(self.warning_messages))


@dataclass(frozen=True)
class LossBreakdown:
    """One sampled loss breakdown in watts."""

    copper_loss_w: float
    iron_loss_w: float | None
    mechanical_loss_w: float
    total_loss_w: float
    assumptions: tuple[str, ...] = ()
    warning_messages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("copper_loss_w", self.copper_loss_w),
            ("mechanical_loss_w", self.mechanical_loss_w),
            ("total_loss_w", self.total_loss_w),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.iron_loss_w is not None:
            if not math.isfinite(self.iron_loss_w) or self.iron_loss_w < 0.0:
                raise ValueError("iron_loss_w must be None or finite and non-negative")
        expected_total = (
            self.copper_loss_w
            + (self.iron_loss_w or 0.0)
            + self.mechanical_loss_w
        )
        if not math.isclose(
            self.total_loss_w, expected_total, rel_tol=1.0e-12, abs_tol=1.0e-12
        ):
            raise ValueError("total_loss_w must equal the sum of available losses")
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "warning_messages", tuple(self.warning_messages))
