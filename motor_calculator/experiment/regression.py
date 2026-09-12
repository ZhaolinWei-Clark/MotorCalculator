"""Phase 11A: ordinary least squares, stated plainly.

Deliberately not a fit library. This is the one regression the framework needs --
a straight line through measured points -- implemented so that every number it
reports can be checked by hand, and so that it refuses rather than extrapolates
when the data does not support a fit.

Two decisions worth naming.

**The intercept is free by default.** Forcing ``E = k*w`` through the origin is
the textbook form of a back-EMF constant, and forcing it is also the fastest way
to hide a real measurement problem: an offset from a probe, a residual field, an
instrument zero. Fitting the intercept and *reporting* it lets the user see that
offset. Forcing it is available, is a separate argument, and records that it was
forced.

**A single point is not a fit.** With one sample the slope is ``y/x``, R-squared
is undefined, and there is no evidence about linearity at all. That case returns
a result that says so, rather than an R-squared of 1.0, which would be the most
misleading number this module could produce.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

REGRESSION_SCHEMA_VERSION = "phase11a.experiment.regression.v1"


class RegressionError(ValueError):
    """The data cannot support a fit at all."""


@dataclass(frozen=True)
class LinearFit:
    """A straight-line fit and everything needed to judge it."""

    schema_version: str
    slope: float
    intercept: float
    #: ``None`` when undefined: a single point, or zero variance in ``y``.
    r_squared: float | None
    sample_count: int
    x_min: float
    x_max: float
    #: Sample standard deviation of the residuals, ``None`` below 3 points.
    residual_std: float | None
    max_abs_residual: float
    #: Residual as a fraction of the fitted value, worst case. ``None`` when any
    #: fitted value is zero.
    max_abs_relative_residual: float | None
    intercept_forced_zero: bool
    #: True when the fit rests on one point and is therefore a ratio, not a fit.
    is_single_point: bool
    residuals: tuple[float, ...]
    note_zh: str = ""

    @property
    def x_span(self) -> float:
        return self.x_max - self.x_min

    @property
    def is_well_conditioned(self) -> bool:
        """Enough points, over enough range, to mean anything."""

        return (
            self.sample_count >= 3
            and self.x_span > 0.0
            and self.x_max != 0.0
            and abs(self.x_span / self.x_max) >= 0.1
        )


def fit_line(
    x_values,
    y_values,
    *,
    force_zero_intercept: bool = False,
    force_reason_zh: str = "",
) -> LinearFit:
    """Least-squares straight line through the measured points.

    ``force_zero_intercept`` must be an explicit choice by the caller and, when
    used, a reason is recorded with the result.
    """

    xs = [float(value) for value in x_values]
    ys = [float(value) for value in y_values]
    if len(xs) != len(ys):
        raise RegressionError("x and y must have the same number of samples")
    if not xs:
        raise RegressionError("no samples to fit")
    if any(not math.isfinite(value) for value in (*xs, *ys)):
        raise RegressionError("every sample must be finite")
    if force_zero_intercept and not force_reason_zh:
        raise RegressionError(
            "forcing the intercept through zero requires a stated reason; it "
            "changes the reported constant and can conceal a measurement offset"
        )

    count = len(xs)

    if count == 1:
        if xs[0] == 0.0:
            raise RegressionError("a single sample at x = 0 determines no slope")
        slope = ys[0] / xs[0]
        return LinearFit(
            schema_version=REGRESSION_SCHEMA_VERSION,
            slope=slope, intercept=0.0, r_squared=None, sample_count=1,
            x_min=xs[0], x_max=xs[0], residual_std=None,
            max_abs_residual=0.0, max_abs_relative_residual=0.0,
            intercept_forced_zero=True, is_single_point=True, residuals=(0.0,),
            note_zh=(
                "只有一个测点：该结果是 y/x 的比值，不是回归。"
                "没有关于线性度的任何证据，R² 不适用。"
            ),
        )

    if force_zero_intercept:
        denominator = sum(value * value for value in xs)
        if denominator == 0.0:
            raise RegressionError("every x is zero; no slope is determined")
        slope = sum(x * y for x, y in zip(xs, ys)) / denominator
        intercept = 0.0
    else:
        mean_x = sum(xs) / count
        mean_y = sum(ys) / count
        sxx = sum((x - mean_x) ** 2 for x in xs)
        if sxx == 0.0:
            raise RegressionError(
                "every sample is at the same x; a slope cannot be determined "
                "from repeated measurements at one operating point"
            )
        sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        slope = sxy / sxx
        intercept = mean_y - slope * mean_x

    fitted = [slope * x + intercept for x in xs]
    residuals = [y - f for y, f in zip(ys, fitted)]
    ss_res = sum(value * value for value in residuals)
    mean_y = sum(ys) / count
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    r_squared = None if ss_tot == 0.0 else 1.0 - ss_res / ss_tot

    degrees = count - (1 if force_zero_intercept else 2)
    residual_std = math.sqrt(ss_res / degrees) if degrees >= 1 else None

    relatives = [
        abs(residual / value) for residual, value in zip(residuals, fitted) if value != 0.0
    ]
    note = force_reason_zh if force_zero_intercept else ""

    return LinearFit(
        schema_version=REGRESSION_SCHEMA_VERSION,
        slope=slope,
        intercept=intercept,
        r_squared=r_squared,
        sample_count=count,
        x_min=min(xs),
        x_max=max(xs),
        residual_std=residual_std,
        max_abs_residual=max(abs(value) for value in residuals),
        max_abs_relative_residual=max(relatives) if relatives else None,
        intercept_forced_zero=force_zero_intercept,
        is_single_point=False,
        residuals=tuple(residuals),
        note_zh=note,
    )


def describe_fit_zh(fit: LinearFit, *, slope_unit: str = "", intercept_unit: str = "") -> str:
    """A short human description. Says what is unknown rather than omitting it."""

    lines = [
        f"斜率 = {fit.slope:.6g}{(' ' + slope_unit) if slope_unit else ''}",
        f"截距 = {fit.intercept:.6g}{(' ' + intercept_unit) if intercept_unit else ''}"
        + ("（已强制为 0）" if fit.intercept_forced_zero else ""),
        f"样本数 = {fit.sample_count}",
        f"自变量范围 = {fit.x_min:.6g} … {fit.x_max:.6g}",
        "R² = 不适用" if fit.r_squared is None else f"R² = {fit.r_squared:.6f}",
    ]
    if fit.residual_std is not None:
        lines.append(f"残差标准差 = {fit.residual_std:.6g}")
    lines.append(f"最大绝对残差 = {fit.max_abs_residual:.6g}")
    if fit.max_abs_relative_residual is not None:
        lines.append(f"最大相对残差 = {fit.max_abs_relative_residual * 100.0:.3f} %")
    if not fit.is_well_conditioned:
        lines.append(
            "注意：测点数量或自变量跨度不足，该拟合不足以支撑关于线性度的结论。"
        )
    if fit.note_zh:
        lines.append(fit.note_zh)
    return "\n".join(lines)
