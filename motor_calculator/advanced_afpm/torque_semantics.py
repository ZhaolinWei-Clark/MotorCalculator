"""Torque boundary declarations for source-native AFPM evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


class TorqueBoundary(str, Enum):
    ELECTROMAGNETIC = "electromagnetic"
    SHAFT = "shaft"
    LOAD = "load"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TorqueSemantics:
    source_boundary: TorqueBoundary
    mechanical_loss_torque_nm: float | None = None

    def __post_init__(self) -> None:
        value = self.mechanical_loss_torque_nm
        if value is not None and (not math.isfinite(value) or value < 0.0):
            raise ValueError("mechanical_loss_torque_nm must be finite and non-negative")
