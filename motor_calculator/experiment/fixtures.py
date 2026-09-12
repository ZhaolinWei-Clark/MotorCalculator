"""Phase 11A: synthetic datasets for tests, and the firewall around them.

The test suite needs measurement-shaped data. The application must never show
that data as a measurement. Those two requirements are in direct tension, and
the tension is resolved structurally rather than by naming convention:

* every fixture is built by :func:`synthetic_dataset`, which is the only
  constructor here;
* it hard-codes ``source_type=SIMULATED_REFERENCE`` -- the caller cannot choose,
  and :class:`DatasetMetadata` independently refuses a fixture that claims any
  other class;
* it sets ``test_fixture_only=True``, and :func:`is_production_admissible`
  refuses such a dataset at the boundary of the production store;
* the values are generated from a stated closed-form expression, so a test can
  assert an exact expected result rather than a tolerance around noise.

A fixture that reached the production UI would be the single worst outcome of
this phase: a plausible-looking measurement that never happened. So the check is
made twice, in two different modules, and tested from both directions.
"""

from __future__ import annotations

from dataclasses import dataclass

from .csv_import import MeasurementRow, rows_from_records
from .schema import DatasetMetadata, MachineIdentity, TestType
from .sources import DatasetSourceType

FIXTURE_SCHEMA_VERSION = "phase11a.experiment.fixture.v1"

#: Stamped into every fixture's provenance and title so it is visible in any
#: view that shows either.
FIXTURE_PROVENANCE = "SYNTHETIC_FIXTURE"
FIXTURE_TITLE_PREFIX = "[TEST FIXTURE — NOT A MEASUREMENT]"


class FixtureLeakError(RuntimeError):
    """A test fixture reached a production surface."""


def synthetic_dataset(
    dataset_id: str,
    *,
    test_type: TestType,
    title: str = "synthetic fixture",
    machine: MachineIdentity | None = None,
) -> DatasetMetadata:
    """A fixture's metadata. Always simulated, always flagged.

    There is deliberately no ``source_type`` parameter.
    """

    return DatasetMetadata(
        dataset_id=dataset_id,
        title=f"{FIXTURE_TITLE_PREFIX} {title}",
        source_type=DatasetSourceType.SIMULATED_REFERENCE,
        test_type=test_type,
        machine=machine or MachineIdentity(),
        data_provenance=FIXTURE_PROVENANCE,
        test_fixture_only=True,
        notes=(
            "合成测试数据，由解析表达式生成，用于自动化测试。"
            "不是实验数据，不得作为任何验证证据出现在生产界面中。"
        ),
    )


def is_production_admissible(dataset: DatasetMetadata) -> bool:
    """Whether a dataset may appear in the production UI at all."""

    return not dataset.test_fixture_only


def require_production_admissible(dataset: DatasetMetadata) -> DatasetMetadata:
    """The boundary guard. Called wherever a dataset enters production."""

    if not is_production_admissible(dataset):
        raise FixtureLeakError(
            f"dataset {dataset.dataset_id!r} is marked TEST_FIXTURE_ONLY and must "
            "never be presented as evidence in the application"
        )
    return dataset


# ---------------------------------------------------------------------------
# Generators. Each states its closed form so a test can assert exactly.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SyntheticBackEmf:
    """``V_line_rms = ke_line_per_rad_s * omega_mech + offset``, exactly."""

    ke_line_rms_v_per_rad_s: float
    offset_v: float
    speeds_rpm: tuple[float, ...]

    def rows(self) -> tuple[MeasurementRow, ...]:
        from .units import rpm_to_rad_per_s

        return rows_from_records(
            [
                {
                    "speed_rpm": speed,
                    "line_voltage_rms_v": (
                        self.ke_line_rms_v_per_rad_s * rpm_to_rad_per_s(speed)
                        + self.offset_v
                    ),
                    "temperature_c": 25.0,
                }
                for speed in self.speeds_rpm
            ]
        )


@dataclass(frozen=True)
class SyntheticTorqueCurrent:
    """``T = kt * I + friction``, exactly."""

    kt_nm_per_a: float
    friction_nm: float
    currents_a: tuple[float, ...]
    speed_rpm: float = 1800.0

    def rows(self) -> tuple[MeasurementRow, ...]:
        return rows_from_records(
            [
                {
                    "speed_rpm": self.speed_rpm,
                    "phase_current_rms_a": current,
                    "torque_nm": self.kt_nm_per_a * current + self.friction_nm,
                }
                for current in self.currents_a
            ]
        )


def synthetic_resistance_rows(
    terminal_ohm: float, temperature_c: float = 25.0, repeats: int = 3
) -> tuple[MeasurementRow, ...]:
    """Repeated identical terminal-resistance readings."""

    return rows_from_records(
        [
            {"measured_resistance_ohm": terminal_ohm, "temperature_c": temperature_c}
            for _ in range(repeats)
        ]
    )


def synthetic_efficiency_rows(
    points: tuple[tuple[float, float, float, float], ...]
) -> tuple[MeasurementRow, ...]:
    """``(speed_rpm, torque_nm, dc_bus_voltage_v, dc_bus_current_a)`` points."""

    return rows_from_records(
        [
            {
                "speed_rpm": speed,
                "torque_nm": torque,
                "dc_bus_voltage_v": voltage,
                "dc_bus_current_a": current,
            }
            for speed, torque, voltage, current in points
        ]
    )
