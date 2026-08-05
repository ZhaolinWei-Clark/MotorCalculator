"""Explicit AFPM topology descriptions for the sandbox model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AFPMTopologyType(str, Enum):
    SSDR = "single_stator_double_rotor"
    DSSR = "double_stator_single_rotor"
    SINGLE_SIDED = "single_stator_single_rotor"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AFPMTopology:
    topology_type: AFPMTopologyType
    stator_count: int
    rotor_count: int
    active_air_gap_count: int
    winding_location: str
    magnet_location: str

    def __post_init__(self) -> None:
        counts = (self.stator_count, self.rotor_count, self.active_air_gap_count)
        if any(value < 0 for value in counts):
            raise ValueError("topology counts cannot be negative")
        if self.topology_type is not AFPMTopologyType.UNKNOWN and any(value == 0 for value in counts):
            raise ValueError("known AFPM topology counts must be positive")
        if not self.winding_location or not self.magnet_location:
            raise ValueError("winding and magnet locations must be explicit")
