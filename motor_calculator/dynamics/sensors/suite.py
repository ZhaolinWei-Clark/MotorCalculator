"""Composition of independent current, position, and speed sensors."""

from __future__ import annotations

from dataclasses import dataclass
import random

from ..transforms import ABCPhaseValues
from .current_sensor import CurrentSensor, CurrentSensorConfig
from .measurement import SensorMeasurement
from .position_sensor import PositionMeasurement, PositionSensor, PositionSensorConfig
from .speed_sensor import SpeedSensor, SpeedSensorConfig


@dataclass(frozen=True)
class SensorSuiteConfig:
    """Optional per-channel models; omitted channels remain ideal."""

    phase_current_a_sensor: CurrentSensorConfig | None = None
    phase_current_b_sensor: CurrentSensorConfig | None = None
    phase_current_c_sensor: CurrentSensorConfig | None = None
    position_sensor: PositionSensorConfig | None = None
    speed_sensor: SpeedSensorConfig | None = None

    def __post_init__(self) -> None:
        for name, value, expected_type in (
            ("phase_current_a_sensor", self.phase_current_a_sensor, CurrentSensorConfig),
            ("phase_current_b_sensor", self.phase_current_b_sensor, CurrentSensorConfig),
            ("phase_current_c_sensor", self.phase_current_c_sensor, CurrentSensorConfig),
            ("position_sensor", self.position_sensor, PositionSensorConfig),
            ("speed_sensor", self.speed_sensor, SpeedSensorConfig),
        ):
            if value is not None and not isinstance(value, expected_type):
                raise TypeError(f"{name} must be None or {expected_type.__name__}")

    @property
    def enabled(self) -> bool:
        configs = (
            self.phase_current_a_sensor,
            self.phase_current_b_sensor,
            self.phase_current_c_sensor,
            self.position_sensor,
            self.speed_sensor,
        )
        return any(config is not None and config.enabled for config in configs)


@dataclass(frozen=True)
class SensorSuiteMeasurement:
    """All feedback values from one controller sampling instant."""

    phase_current_a: SensorMeasurement
    phase_current_b: SensorMeasurement
    phase_current_c: SensorMeasurement
    position: PositionMeasurement
    speed: SensorMeasurement
    warning_messages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "warning_messages", tuple(self.warning_messages))

    @property
    def measured_phase_currents(self) -> ABCPhaseValues:
        return ABCPhaseValues(
            a=self.phase_current_a.measured_value,
            b=self.phase_current_b.measured_value,
            c=self.phase_current_c.measured_value,
        )


class SensorSuite:
    """Own sensor instances and an optional caller-supplied random generator."""

    def __init__(
        self,
        config: SensorSuiteConfig | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.config = config or SensorSuiteConfig()
        self._rng = rng
        self._phase_a = CurrentSensor(self.config.phase_current_a_sensor)
        self._phase_b = CurrentSensor(self.config.phase_current_b_sensor)
        self._phase_c = CurrentSensor(self.config.phase_current_c_sensor)
        self._position = PositionSensor(self.config.position_sensor)
        self._speed = SpeedSensor(self.config.speed_sensor)

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    def measure(
        self,
        true_phase_currents: ABCPhaseValues,
        true_position_rad: float,
        true_speed_rad_s: float,
        pole_pairs: int,
    ) -> SensorSuiteMeasurement:
        phase_a = self._phase_a.measure(true_phase_currents.a, self._rng)
        phase_b = self._phase_b.measure(true_phase_currents.b, self._rng)
        phase_c = self._phase_c.measure(true_phase_currents.c, self._rng)
        position = self._position.measure(true_position_rad, pole_pairs, self._rng)
        speed = self._speed.measure(true_speed_rad_s, self._rng)
        warnings = tuple(
            dict.fromkeys(
                (
                    *phase_a.warning_messages,
                    *phase_b.warning_messages,
                    *phase_c.warning_messages,
                    *position.warning_messages,
                    *speed.warning_messages,
                )
            )
        )
        return SensorSuiteMeasurement(
            phase_current_a=phase_a,
            phase_current_b=phase_b,
            phase_current_c=phase_c,
            position=position,
            speed=speed,
            warning_messages=warnings,
        )
