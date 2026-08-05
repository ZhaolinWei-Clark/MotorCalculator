"""Electrical quantity semantics for advanced AFPM source cases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


class BackEMFScope(str, Enum):
    PHASE = "phase"
    LINE = "line"


class BackEMFValueKind(str, Enum):
    PEAK = "peak"
    RMS = "rms"
    FUNDAMENTAL_RMS = "fundamental_rms"
    WAVEFORM = "waveform"


class WaveformFamily(str, Enum):
    SINUSOIDAL = "sinusoidal"
    TRAPEZOIDAL = "trapezoidal"
    FLATTENED = "flattened"
    ARBITRARY = "arbitrary"


@dataclass(frozen=True)
class BackEMFSemantics:
    scope: BackEMFScope
    value_kind: BackEMFValueKind
    waveform_family: WaveformFamily
    speed_rpm: float
    temperature_c: float | None = None
    source_native_unit: str | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.speed_rpm) or self.speed_rpm <= 0.0:
            raise ValueError("speed_rpm must be finite and positive")
        if self.temperature_c is not None and not math.isfinite(self.temperature_c):
            raise ValueError("temperature_c must be finite when provided")


@dataclass(frozen=True)
class AFPMInductance:
    scalar_phase_h: float | None = None
    ld_h: float | None = None
    lq_h: float | None = None

    def __post_init__(self) -> None:
        for name in ("scalar_phase_h", "ld_h", "lq_h"):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0.0):
                raise ValueError(f"{name} must be finite and positive when provided")
