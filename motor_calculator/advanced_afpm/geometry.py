"""Geometry representations for radius-aware AFPM sandbox calculations."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RadialMagnetSample:
    radius_m: float
    local_magnet_arc_ratio: float
    local_magnet_width_m: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.radius_m) or self.radius_m <= 0.0:
            raise ValueError("radius_m must be finite and positive")
        if not math.isfinite(self.local_magnet_arc_ratio) or not 0.0 <= self.local_magnet_arc_ratio <= 1.0:
            raise ValueError("local_magnet_arc_ratio must be within [0, 1]")
        if self.local_magnet_width_m is not None:
            if not math.isfinite(self.local_magnet_width_m) or self.local_magnet_width_m <= 0.0:
                raise ValueError("local_magnet_width_m must be finite and positive when provided")


@dataclass(frozen=True)
class AFPMGeometry:
    inner_radius_m: float | None
    outer_radius_m: float | None
    air_gap_m: float | None
    magnet_thickness_m: float | None
    pole_pairs: int | None
    magnet_arc_ratio: float | None
    radius_dependent_magnet_profile: tuple[RadialMagnetSample, ...] | None
    stator_count: int
    rotor_count: int
    effective_nonmagnetic_gap_m: float | None = None

    def __post_init__(self) -> None:
        for name in (
            "inner_radius_m",
            "outer_radius_m",
            "air_gap_m",
            "magnet_thickness_m",
            "effective_nonmagnetic_gap_m",
        ):
            value = getattr(self, name)
            if value is not None and (not math.isfinite(value) or value <= 0.0):
                raise ValueError(f"{name} must be finite and positive when provided")
        if self.inner_radius_m is not None and self.outer_radius_m is not None:
            if self.outer_radius_m <= self.inner_radius_m:
                raise ValueError("outer_radius_m must exceed inner_radius_m")
        if self.pole_pairs is not None and self.pole_pairs <= 0:
            raise ValueError("pole_pairs must be positive when provided")
        if self.magnet_arc_ratio is not None:
            if not math.isfinite(self.magnet_arc_ratio) or not 0.0 <= self.magnet_arc_ratio <= 1.0:
                raise ValueError("magnet_arc_ratio must be within [0, 1]")
        if self.stator_count < 0 or self.rotor_count < 0:
            raise ValueError("stator_count and rotor_count cannot be negative")
        profile = self.radius_dependent_magnet_profile
        if profile:
            radii = tuple(sample.radius_m for sample in profile)
            if tuple(sorted(radii)) != radii or len(set(radii)) != len(radii):
                raise ValueError("radial magnet samples must have strictly increasing radii")
            if self.inner_radius_m is not None and radii[0] > self.inner_radius_m:
                raise ValueError("radial profile must cover the inner radius")
            if self.outer_radius_m is not None and radii[-1] < self.outer_radius_m:
                raise ValueError("radial profile must cover the outer radius")

    def magnet_coverage_at(self, radius_m: float) -> float:
        """Return explicit scalar coverage or linearly interpolated source samples."""
        profile = self.radius_dependent_magnet_profile
        if not profile:
            if self.magnet_arc_ratio is None:
                raise ValueError("magnet coverage is unavailable")
            return self.magnet_arc_ratio
        if radius_m <= profile[0].radius_m:
            return profile[0].local_magnet_arc_ratio
        if radius_m >= profile[-1].radius_m:
            return profile[-1].local_magnet_arc_ratio
        for left, right in zip(profile, profile[1:]):
            if left.radius_m <= radius_m <= right.radius_m:
                fraction = (radius_m - left.radius_m) / (right.radius_m - left.radius_m)
                return left.local_magnet_arc_ratio + fraction * (
                    right.local_magnet_arc_ratio - left.local_magnet_arc_ratio
                )
        raise RuntimeError("radial profile interpolation failed")
