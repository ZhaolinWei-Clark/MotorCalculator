"""Structured dashboard and plot records for traceable result UX."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class AvailabilityStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_RUN = "NOT_RUN"
    INVALID = "INVALID"


class DashboardStatus(str, Enum):
    NORMAL = "NORMAL"
    INFO = "INFO"
    REVIEW = "REVIEW"
    WARNING = "WARNING"
    SEVERE = "SEVERE"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT = "INSUFFICIENT"


STATUS_LABELS_ZH: Mapping[DashboardStatus, str] = {
    DashboardStatus.NORMAL: "正常",
    DashboardStatus.INFO: "提示",
    DashboardStatus.REVIEW: "建议检查",
    DashboardStatus.WARNING: "警告",
    DashboardStatus.SEVERE: "严重设计风险",
    DashboardStatus.UNAVAILABLE: "不可用",
    DashboardStatus.INSUFFICIENT: "信息不足",
}


@dataclass(frozen=True)
class DashboardMetric:
    key: str
    label_zh: str
    value: float | None
    display_value: str
    unit: str
    status: DashboardStatus
    interpretation_zh: str
    availability: AvailabilityStatus = AvailabilityStatus.AVAILABLE
    source: str = ""

    @property
    def status_label_zh(self) -> str:
        return STATUS_LABELS_ZH[self.status]


@dataclass(frozen=True)
class AvailabilityItem:
    key: str
    label_zh: str
    status: AvailabilityStatus
    reason_zh: str


@dataclass(frozen=True)
class DesignStatusSummary:
    headline_zh: str
    severe_count: int
    warning_count: int
    review_count: int
    insufficient_count: int
    contributors_zh: tuple[str, ...]


@dataclass(frozen=True)
class DashboardData:
    primary_metrics: tuple[DashboardMetric, ...]
    feasibility_metrics: tuple[DashboardMetric, ...]
    electromagnetic_metrics: tuple[DashboardMetric, ...]
    loss_metrics: tuple[DashboardMetric, ...]
    availability_items: tuple[AvailabilityItem, ...]
    design_status: DesignStatusSummary
    result_label_zh: str = "当前成功计算"
    # Phase 9C: legacy mixed-basis values are kept for compatibility/debugging
    # but must not sit beside the primary KPIs as if equally authoritative.
    legacy_diagnostic_metrics: tuple[DashboardMetric, ...] = ()

    @property
    def metric_by_key(self) -> Mapping[str, DashboardMetric]:
        return {
            metric.key: metric
            for section in (
                self.primary_metrics,
                self.feasibility_metrics,
                self.electromagnetic_metrics,
                self.loss_metrics,
                self.legacy_diagnostic_metrics,
            )
            for metric in section
        }


@dataclass(frozen=True)
class SpeedSweepPoint:
    speed_rpm: float
    torque_nm: float | None
    output_power_w: float | None
    # Phase 9C authoritative values (corrected single-basis, PMSM only).
    required_voltage_line_rms_v: float | None
    available_voltage_line_rms_v: float | None
    voltage_margin_percent: float | None
    efficiency_percent: float | None
    current_density_a_per_mm2: float | None
    availability: AvailabilityStatus
    feasibility_status: DashboardStatus
    message_zh: str = ""
    # Legacy mixed-basis reference, retained for optional comparison only.
    legacy_required_voltage_line_rms_v: float | None = None
    legacy_voltage_margin_percent: float | None = None


@dataclass(frozen=True)
class SpeedSweepResult:
    points: tuple[SpeedSweepPoint, ...]
    control_mode: str
    source_label_zh: str
    input_hash: str
    elapsed_seconds: float

    @property
    def valid_points(self) -> tuple[SpeedSweepPoint, ...]:
        return tuple(
            point for point in self.points if point.availability is AvailabilityStatus.AVAILABLE
        )


@dataclass(frozen=True)
class PlotSeries:
    key: str
    label_zh: str
    x_values: tuple[float, ...]
    y_values: tuple[float | None, ...]
    x_label_zh: str
    y_label_zh: str
    unit: str
    availability: AvailabilityStatus
    unavailable_reason_zh: str = ""
    source_label_zh: str = ""
    # Phase 9C: legacy comparison curves exist but are not drawn by default.
    default_visible: bool = True


@dataclass(frozen=True)
class DynamicPlotData:
    series: tuple[PlotSeries, ...]
    source_status: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class UncertaintyPlotData:
    availability: AvailabilityStatus
    metric_name: str
    unit: str
    nominal_value: float | None
    lower_value: float | None
    upper_value: float | None
    p10: float | None
    p50: float | None
    p90: float | None
    dominant_parameters: tuple[str, ...]
    reason_zh: str


@dataclass(frozen=True)
class SensitivityPlotData:
    parameter_name: str
    output_name: str
    perturbation_percent: tuple[float, ...]
    output_values: tuple[float | None, ...]
    unit: str
    availability: AvailabilityStatus
    reason_zh: str = ""


@dataclass(frozen=True)
class SnapshotAssessment:
    status: AvailabilityStatus
    is_current: bool
    message_zh: str
    result: Mapping[str, Any] | None
