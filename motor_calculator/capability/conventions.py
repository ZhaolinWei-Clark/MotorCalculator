"""Phase 12: the dq convention, frozen and written down before anything uses it.

This project already contains a dq model (the dynamics sandbox), an electrical
axis convention (Phase 10G) and a same-basis voltage authority (Phase 9C). A
capability solver that invented a second Park transform, or quietly worked in
RMS where the others work in peak, would produce numbers that disagree with the
rest of the application for reasons nobody could see.

So the convention is stated here once, every capability module reads it from
here, and a cross-check test asserts that the new steady-state voltage agrees
with the Phase 9C authority on the case where both are valid.

The convention
--------------
**Park transform: amplitude-invariant.** ``dynamics/transforms.py`` is
amplitude-invariant, so a balanced set of phase currents with peak amplitude
``I`` maps to a dq vector of magnitude ``I``. Therefore:

* ``id``, ``iq`` are **peak** phase-current amplitudes, not RMS;
* ``vd``, ``vq`` are **peak** phase-voltage amplitudes, not RMS;
* the torque equation carries the ``3/2`` factor that belongs to this transform.

**Signs.** Taken from ``dynamics/pmsm_model.py`` by setting its derivatives to
zero, so the capability solver is the steady state of the model this project
already simulates:

    vd = Rs*id - omega_e*Lq*iq
    vq = Rs*iq + omega_e*(Ld*id + psi_pm)

Positive ``iq`` produces positive torque. Negative ``id`` opposes the magnet
flux, which is what makes field weakening possible.

**Speeds.** ``omega_m`` is mechanical rad/s; ``omega_e = p * omega_m`` is
electrical rad/s. Every reactance in the dq equations uses ``omega_e``; every
mechanical power uses ``omega_m``. Mixing them is a factor of ``p`` -- 8 on the
reference design -- so the two are never interchangeable and are never named
just "omega" anywhere in this package.

**Flux linkage.** ``psi_pm`` is the peak fundamental flux linkage per phase, in
Wb, such that the open-circuit peak phase back-EMF is ``omega_e * psi_pm``.

What this package does not do
-----------------------------
It adds no physics to the production kernel and modifies none. It is a new
steady-state capability model built on the parameters production already
produces, and its results are labelled as its own.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

CONVENTION_SCHEMA_VERSION = "phase12.dq_convention.v1"

#: The Park transform this project uses. Fixes peak-vs-RMS for every dq quantity.
PARK_TRANSFORM = "AMPLITUDE_INVARIANT"

#: Consequences of that choice, stated so no caller has to infer them.
CURRENT_BASIS = "PHASE_PEAK"
VOLTAGE_BASIS = "PHASE_PEAK"
TORQUE_FACTOR = 1.5

#: The basis production stores currents in. Conversion is explicit, always.
PROJECT_CURRENT_BASIS = "PHASE_RMS"
#: The basis the Phase 9C voltage authority reports in.
PROJECT_VOLTAGE_AUTHORITY_BASIS = "LINE_RMS"

SQRT2 = math.sqrt(2.0)
SQRT3 = math.sqrt(3.0)

CONVENTION_SUMMARY_ZH = (
    "Park 变换：幅值不变型（amplitude-invariant）。\n"
    "因此 id/iq 为**相电流峰值**，vd/vq 为**相电压峰值**，转矩式带 3/2 系数。\n"
    "稳态方程（取自 dynamics/pmsm_model.py 的导数置零）：\n"
    "    vd = Rs·id − ω_e·Lq·iq\n"
    "    vq = Rs·iq + ω_e·(Ld·id + ψ_pm)\n"
    "ω_e = p·ω_m。所有电抗用 ω_e，所有机械功率用 ω_m，二者相差 p 倍，绝不混用。\n"
    "ψ_pm 为每相基波磁链峰值（Wb），使开路相反电动势峰值 = ω_e·ψ_pm。\n"
    "项目存储的电流是**相有效值**，进入 dq 前必须显式乘以 √2。"
)


# ---------------------------------------------------------------------------
# Basis conversions. Every one of these is exact; none is an approximation.
# ---------------------------------------------------------------------------


def phase_rms_to_peak(value_rms: float) -> float:
    """Sinusoidal RMS to peak. Exact for a sinusoid, which dq assumes."""

    return float(value_rms) * SQRT2


def phase_peak_to_rms(value_peak: float) -> float:
    return float(value_peak) / SQRT2


def phase_peak_to_line_rms(value_peak: float) -> float:
    """Phase peak to line-to-line RMS, balanced three-phase wye.

    ``V_line_rms = sqrt(3) * V_phase_rms = sqrt(3) * V_phase_peak / sqrt(2)``.
    This is the conversion that lets the capability solver be compared against
    the Phase 9C line-RMS authority without either side being restated.
    """

    return float(value_peak) * SQRT3 / SQRT2


def line_rms_to_phase_peak(value_line_rms: float) -> float:
    return float(value_line_rms) * SQRT2 / SQRT3


def mechanical_to_electrical_rad_s(omega_m: float, pole_pairs: int) -> float:
    return float(omega_m) * int(pole_pairs)


def electrical_to_mechanical_rad_s(omega_e: float, pole_pairs: int) -> float:
    return float(omega_e) / int(pole_pairs)


def rpm_to_mechanical_rad_s(rpm: float) -> float:
    return float(rpm) * 2.0 * math.pi / 60.0


def mechanical_rad_s_to_rpm(omega_m: float) -> float:
    return float(omega_m) * 60.0 / (2.0 * math.pi)


@dataclass(frozen=True)
class BasisDeclaration:
    """What a number is, carried alongside the number itself."""

    quantity: str
    basis: str
    unit: str
    note_zh: str = ""


#: Declared bases for everything the capability solver reports. The GUI and the
#: export read these rather than hard-coding labels, so a basis cannot be
#: described one way in one place and another way somewhere else.
DECLARED_BASES: tuple[BasisDeclaration, ...] = (
    BasisDeclaration("id", CURRENT_BASIS, "A", "d 轴电流，相电流**峰值**"),
    BasisDeclaration("iq", CURRENT_BASIS, "A", "q 轴电流，相电流**峰值**"),
    BasisDeclaration("current_magnitude", CURRENT_BASIS, "A", "√(id²+iq²)，相电流峰值"),
    BasisDeclaration("vd", VOLTAGE_BASIS, "V", "d 轴电压，相电压**峰值**"),
    BasisDeclaration("vq", VOLTAGE_BASIS, "V", "q 轴电压，相电压**峰值**"),
    BasisDeclaration("voltage_magnitude", VOLTAGE_BASIS, "V", "√(vd²+vq²)，相电压峰值"),
    BasisDeclaration("psi_pm", "PHASE_PEAK_FLUX_LINKAGE", "Wb", "开路相反电动势峰值 = ω_e·ψ_pm"),
    BasisDeclaration("torque", "ELECTROMAGNETIC", "Nm", "电磁转矩，**不扣除**摩擦与风阻"),
    BasisDeclaration("mechanical_power", "ELECTROMAGNETIC", "W", "T_em·ω_m，非轴端输出功率"),
    BasisDeclaration("omega_e", "ELECTRICAL_RAD_PER_S", "rad/s", "电角速度 = p·ω_m"),
    BasisDeclaration("omega_m", "MECHANICAL_RAD_PER_S", "rad/s", "机械角速度"),
)


def render_convention_zh() -> str:
    lines = [
        f"dq 约定版本：{CONVENTION_SCHEMA_VERSION}",
        f"Park 变换：{PARK_TRANSFORM}",
        "",
        CONVENTION_SUMMARY_ZH,
        "",
        "各量基准声明：",
    ]
    for declaration in DECLARED_BASES:
        lines.append(
            f"  {declaration.quantity:<20}{declaration.basis:<28}"
            f"{declaration.unit:<6}{declaration.note_zh}"
        )
    return "\n".join(lines)
