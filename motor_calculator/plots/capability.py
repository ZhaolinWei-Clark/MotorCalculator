"""Phase 12: the two capability figures.

These are engineering diagnostics, not decoration. The torque-speed plot exists
so a user can see where the constraint set changes; the id/iq plot exists so an
engineer can see *why* it changes -- the current circle, the voltage ellipses
shrinking with speed, and the trajectory the solver actually took between them.

Neither figure implies measurement. Both carry the model-output label in the
figure itself, so a screenshot pasted into a review still says what it is.
"""

from __future__ import annotations

import math

from ..capability.envelope import Region
from ..capability.solver import CapabilityResult
from ..capability.steady_state import voltage_magnitude

CAPABILITY_PLOT_SCHEMA_VERSION = "phase12.capability_plots.v1"

MODEL_LABEL_ZH = "稳态解析模型输出 · 未经实验验证"

#: One colour per region, used in both figures so they read together.
REGION_COLOURS = {
    Region.MTPA_CURRENT_LIMITED: "#3b7dd8",
    Region.CURRENT_AND_VOLTAGE_LIMITED: "#d98b3b",
    Region.VOLTAGE_LIMITED_FIELD_WEAKENING: "#8b5fbf",
    Region.NO_FEASIBLE_OPERATING_POINT: "#c0392b",
}


def build_torque_speed_figure(result: CapabilityResult, *, figsize=(8.4, 5.0)):
    """Maximum torque and mechanical power against speed."""

    from matplotlib.figure import Figure

    figure = Figure(figsize=figsize, dpi=100)
    axes = figure.add_subplot(111)
    power_axes = axes.twinx()

    feasible = result.feasible_points
    speeds = [point.speed_rpm for point in feasible]
    torques = [point.torque_nm for point in feasible]
    powers = [point.mechanical_power_w for point in feasible]

    axes.plot(speeds, torques, color="#2c3e50", linewidth=1.8, label="最大转矩 T (N·m)", zorder=3)
    power_axes.plot(
        speeds, powers, color="#7f8c8d", linewidth=1.4, linestyle="--",
        label="机械功率 P (W)", zorder=2,
    )

    # Region shading, driven by the solved active-constraint set.
    for index in range(len(feasible) - 1):
        axes.axvspan(
            feasible[index].speed_rpm,
            feasible[index + 1].speed_rpm,
            color=REGION_COLOURS.get(feasible[index].region, "#bdc3c7"),
            alpha=0.12,
            zorder=0,
        )

    base = result.base_speed
    if base.resolved:
        axes.axvline(base.speed_rpm, color="#c0392b", linewidth=1.2, linestyle=":", zorder=4)
        axes.annotate(
            f"基速 {base.speed_rpm:.0f} rpm",
            xy=(base.speed_rpm, max(torques) if torques else 0.0),
            xytext=(6, -14), textcoords="offset points",
            fontsize=8, color="#c0392b",
        )

    constant_power = result.constant_power
    if constant_power.exists and constant_power.start_rpm and constant_power.end_rpm:
        power_axes.axvspan(
            constant_power.start_rpm, constant_power.end_rpm,
            color="#27ae60", alpha=0.07, zorder=1,
        )
        power_axes.annotate(
            f"恒功率区 ≈ {constant_power.mean_power_w:.0f} W"
            f"（波动 {constant_power.power_spread_percent:.1f} %）",
            xy=(constant_power.start_rpm, constant_power.mean_power_w),
            xytext=(8, 8), textcoords="offset points", fontsize=8, color="#1e8449",
        )

    axes.set_xlabel("机械转速 (rpm)")
    axes.set_ylabel("转矩 (N·m)")
    power_axes.set_ylabel("机械功率 (W)")
    axes.set_title(f"转矩-转速能力包络　·　{MODEL_LABEL_ZH}", fontsize=10)
    axes.grid(True, alpha=0.25)
    axes.set_ylim(bottom=0.0)
    power_axes.set_ylim(bottom=0.0)

    handles, labels = axes.get_legend_handles_labels()
    power_handles, power_labels = power_axes.get_legend_handles_labels()
    axes.legend(handles + power_handles, labels + power_labels, loc="upper right", fontsize=8)
    figure.tight_layout()
    return figure


def build_id_iq_figure(result: CapabilityResult, *, figsize=(7.0, 6.4), ellipse_count: int = 5):
    """The dq plane: current circle, voltage ellipses, MTPA and FW trajectories."""

    from matplotlib.figure import Figure

    figure = Figure(figsize=figsize, dpi=100)
    axes = figure.add_subplot(111)

    parameters = result.parameters
    imax = result.current_limit.peak_a
    vmax = result.voltage_limit.phase_peak_v

    # Current-limit circle.
    angles = [2.0 * math.pi * index / 360.0 for index in range(361)]
    axes.plot(
        [imax * math.cos(a) for a in angles],
        [imax * math.sin(a) for a in angles],
        color="#2980b9", linewidth=1.6, label=f"电流圆 |I| = {imax:.2f} A（峰值）",
    )

    # Voltage-limit ellipses at a spread of speeds. Drawn by evaluating the
    # constraint on a grid rather than by an analytic ellipse, so the curve
    # shown is the constraint the solver actually used, Rs included.
    feasible = result.feasible_points
    if feasible:
        speeds = [
            feasible[0].omega_e_rad_s
            + (feasible[-1].omega_e_rad_s - feasible[0].omega_e_rad_s) * index / (ellipse_count - 1)
            for index in range(ellipse_count)
        ]
        span = imax * 1.35
        for order, omega_e in enumerate(speeds):
            if omega_e <= 0.0:
                continue
            contour_id: list[float] = []
            contour_iq: list[float] = []
            steps = 240
            for index in range(steps + 1):
                id_a = -span + 2.0 * span * index / steps
                # Solve |V|^2 = Vmax^2 for iq, the same quadratic the solver uses.
                A = parameters.Rs * id_a
                B = -omega_e * parameters.Lq
                C = omega_e * (parameters.Ld * id_a + parameters.psi_pm)
                D = parameters.Rs
                a = B * B + D * D
                b = 2.0 * (A * B + C * D)
                c = A * A + C * C - vmax * vmax
                discriminant = b * b - 4.0 * a * c
                if a <= 0.0 or discriminant < 0.0:
                    continue
                root = math.sqrt(discriminant)
                contour_id.append(id_a)
                contour_iq.append((-b + root) / (2.0 * a))
            if contour_id:
                shade = 0.25 + 0.6 * order / max(ellipse_count - 1, 1)
                axes.plot(
                    contour_id, contour_iq,
                    color=(0.55, 0.2, 0.55), alpha=shade, linewidth=1.0,
                    label=(
                        f"电压椭圆（ω_e = {omega_e:.0f} rad/s）"
                        if order in (0, ellipse_count - 1)
                        else None
                    ),
                )

    # MTPA locus.
    axes.plot(
        [point.id_a for point in result.mtpa_locus],
        [point.iq_a for point in result.mtpa_locus],
        color="#27ae60", linewidth=2.0, label="MTPA 轨迹",
    )

    # The trajectory the solver took across the envelope.
    axes.plot(
        [point.id_a for point in feasible],
        [point.iq_a for point in feasible],
        color="#e67e22", linewidth=1.8, marker="o", markersize=2.6,
        label="弱磁轨迹（包络工作点）",
    )

    # The characteristic current, which is where the trajectory converges.
    characteristic = -parameters.characteristic_current_a
    axes.axvline(
        characteristic, color="#7f8c8d", linestyle=":", linewidth=1.1,
        label=f"特征电流 −ψ/Ld = {characteristic:.2f} A",
    )

    axes.axhline(0.0, color="#95a5a6", linewidth=0.8)
    axes.axvline(0.0, color="#95a5a6", linewidth=0.8)
    axes.set_xlabel("id (A, 相电流峰值)")
    axes.set_ylabel("iq (A, 相电流峰值)")
    axes.set_title(f"dq 电流平面能力图　·　{MODEL_LABEL_ZH}", fontsize=10)
    axes.grid(True, alpha=0.25)
    axes.set_xlim(-imax * 1.25, imax * 0.35)
    axes.set_ylim(-imax * 0.1, imax * 1.2)
    axes.set_aspect("equal", adjustable="box")
    axes.legend(loc="upper left", fontsize=7.5)
    figure.tight_layout()
    return figure
