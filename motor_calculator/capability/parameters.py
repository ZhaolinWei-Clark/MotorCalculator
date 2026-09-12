"""Phase 12: one bridge from production quantities to capability parameters.

The failure this module exists to prevent is deriving ``psi_pm`` two different
ways in two different places. Production exposes both a phase-peak back-EMF
constant and a phase-RMS back-EMF, and both can yield ``psi_pm``:

    psi_pm = Ke_phase_peak_per_mechanical_rad_s / p
    psi_pm = sqrt(2) * E_phase_rms / omega_e

These agree exactly -- verified to full double precision on the reference design
-- because they are the same quantity expressed twice. That they agree is not a
reason to keep both: it is a reason to pick one, use it everywhere, and record
the other as a cross-check. :func:`bridge_from_analysis` is the only place in
this package that reads a production result.

Saliency is not invented. Production carries a single synchronous inductance,
so ``Ld = Lq = Ls`` with provenance ``ISOTROPIC_ASSUMPTION``. A user who knows
their machine is salient may supply Ld and Lq explicitly, and the provenance
changes to say so. Nothing here manufactures a saliency ratio.

Which inductance is the one subtlety worth stating twice. The dq equations need
the **synchronous** inductance ``L_s = L_ph - M``, not the self inductance.
Production's field names invert the intuition -- ``phase_inductance_h`` is the
self inductance and ``line_inductance_h`` is the synchronous one -- which is why
Phase 9C added ``phase_synchronous_inductance_h`` as an unambiguous alias, and
why this bridge reads that alias. Reading the self inductance instead
understates the reactance by the mutual coupling, 15 % on the reference design.

Where semantics are insufficient the bridge returns ``UNRESOLVED`` rather than
substituting a value.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from .conventions import (
    CONVENTION_SCHEMA_VERSION,
    phase_rms_to_peak,
    rpm_to_mechanical_rad_s,
)

PARAMETERS_SCHEMA_VERSION = "phase12.capability_parameters.v1"


class MachineType(str, Enum):
    """How the dq inductances relate. Decided from the values, not assumed."""

    #: Ld == Lq to within tolerance. Reluctance torque is identically zero.
    NON_SALIENT = "NON_SALIENT"
    #: Lq > Ld, the usual interior-PM case. Negative id adds reluctance torque.
    SALIENT_IPM = "SALIENT_IPM"
    #: Ld > Lq. Unusual, but the solver does not assume it away.
    INVERSE_SALIENT = "INVERSE_SALIENT"


MACHINE_TYPE_LABELS_ZH = {
    MachineType.NON_SALIENT: "非凸极（Ld = Lq）",
    MachineType.SALIENT_IPM: "凸极（Lq > Ld）",
    MachineType.INVERSE_SALIENT: "反凸极（Ld > Lq）",
}

#: Below this the machine is treated as non-salient and MTPA reduces to id = 0.
#: Not a physical constant: it is the point below which the saliency term is
#: numerically meaningless next to the magnet term.
SALIENCY_TOLERANCE_H = 1.0e-12

UNRESOLVED = "UNRESOLVED"


class CapabilityParameterError(ValueError):
    """The production result does not carry what the solver needs."""


@dataclass(frozen=True)
class ParameterProvenance:
    """Where one capability parameter came from, and on what basis."""

    name: str
    value: float | None
    unit: str
    source: str
    basis: str
    conversion: str
    provenance: str
    note_zh: str = ""

    @property
    def is_resolved(self) -> bool:
        return self.value is not None and self.provenance != UNRESOLVED


@dataclass(frozen=True)
class CapabilityParameters:
    """Everything the capability solver needs, with every basis nailed down."""

    schema_version: str
    convention_version: str
    #: Phase resistance, ohm, at the temperature production computed it at.
    Rs: float
    #: d-axis inductance, H.
    Ld: float
    #: q-axis inductance, H.
    Lq: float
    #: Peak fundamental flux linkage per phase, Wb.
    psi_pm: float
    pole_pairs: int
    #: Winding temperature the resistance belongs to, degC, or None if unknown.
    resistance_temperature_c: float | None
    provenance: tuple[ParameterProvenance, ...]
    machine_type: MachineType
    warnings_zh: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("Rs", "Ld", "Lq", "psi_pm"):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise CapabilityParameterError(f"{name} must be finite, got {value!r}")
        if self.Ld <= 0.0 or self.Lq <= 0.0:
            raise CapabilityParameterError("Ld and Lq must be positive")
        if self.psi_pm <= 0.0:
            raise CapabilityParameterError("psi_pm must be positive")
        if self.Rs < 0.0:
            raise CapabilityParameterError("Rs must be non-negative")
        if int(self.pole_pairs) <= 0:
            raise CapabilityParameterError("pole_pairs must be positive")

    @property
    def saliency_h(self) -> float:
        """``Lq - Ld``. Positive for a normal interior-PM machine."""

        return self.Lq - self.Ld

    @property
    def is_salient(self) -> bool:
        return abs(self.saliency_h) > SALIENCY_TOLERANCE_H

    @property
    def saliency_ratio(self) -> float:
        return self.Lq / self.Ld

    @property
    def characteristic_current_a(self) -> float:
        """``psi_pm / Ld``: the current that would cancel the magnet flux.

        A machine whose current limit reaches this value can in principle be
        driven to unbounded speed; one whose limit falls short cannot. It is
        reported because it explains the shape of the envelope better than any
        single speed number does.
        """

        return self.psi_pm / self.Ld

    def get(self, name: str) -> ParameterProvenance | None:
        for item in self.provenance:
            if item.name == name:
                return item
        return None


def _classify(Ld: float, Lq: float) -> MachineType:
    if abs(Lq - Ld) <= SALIENCY_TOLERANCE_H:
        return MachineType.NON_SALIENT
    return MachineType.SALIENT_IPM if Lq > Ld else MachineType.INVERSE_SALIENT


def bridge_from_analysis(
    result: Any,
    parameters: Mapping[str, Any] | None = None,
    *,
    d_axis_inductance_h: float | None = None,
    q_axis_inductance_h: float | None = None,
) -> CapabilityParameters:
    """Build capability parameters from a production analysis result.

    The only place this package reads production. Everything downstream takes
    the returned object, so there is exactly one definition of each parameter.
    """

    electrical = getattr(result, "electrical", None)
    performance = getattr(result, "performance", None)
    if electrical is None or performance is None:
        raise CapabilityParameterError(
            "a production AnalysisResult with electrical and performance "
            "sections is required"
        )
    parameters = dict(parameters or {})

    pole_pairs = parameters.get("p")
    if pole_pairs is None:
        raise CapabilityParameterError("pole-pair count p is required")
    pole_pairs = int(pole_pairs)

    # --- psi_pm ---------------------------------------------------------
    ke_peak_per_mech = getattr(
        electrical, "revised_back_emf_constant_phase_peak_v_per_rad_s", None
    )
    back_emf_phase_rms = getattr(electrical, "back_emf_phase_rms_v", None)
    speed_rpm = getattr(performance, "mechanical_speed_rpm", None)

    psi_pm = None
    psi_source = UNRESOLVED
    psi_conversion = ""
    cross_check_note = ""
    if ke_peak_per_mech and math.isfinite(ke_peak_per_mech) and ke_peak_per_mech > 0:
        psi_pm = float(ke_peak_per_mech) / pole_pairs
        psi_source = "electrical.revised_back_emf_constant_phase_peak_v_per_rad_s"
        psi_conversion = "psi_pm = Ke_phase_peak_per_mechanical_rad_s / p"
        # Cross-check against the independent RMS route, without using it.
        if back_emf_phase_rms and speed_rpm:
            omega_e = rpm_to_mechanical_rad_s(float(speed_rpm)) * pole_pairs
            if omega_e > 0:
                alternative = phase_rms_to_peak(float(back_emf_phase_rms)) / omega_e
                deviation = abs(alternative / psi_pm - 1.0) if psi_pm else float("inf")
                cross_check_note = (
                    f"交叉核对：√2·E_phase_rms/ω_e = {alternative:.12g} Wb，"
                    f"与所用值相差 {deviation * 100.0:.3g} %。"
                    "两条路径是同一个量的两种写法，此处只采用其中一条作为唯一来源。"
                )

    if psi_pm is None:
        raise CapabilityParameterError(
            "psi_pm is UNRESOLVED: the production result carries no usable "
            "phase-peak back-EMF constant. The capability solver will not "
            "invent a flux linkage."
        )

    # --- Rs -------------------------------------------------------------
    Rs = getattr(electrical, "phase_resistance_ohm", None)
    if Rs is None or not math.isfinite(Rs) or Rs < 0:
        raise CapabilityParameterError("phase resistance is UNRESOLVED")
    Rs = float(Rs)
    temperature = parameters.get("Temp_coil")
    temperature = float(temperature) if temperature is not None else None

    # --- Ld / Lq --------------------------------------------------------
    # The dq equations need the SYNCHRONOUS inductance L_s = L_ph - M, not the
    # self inductance. Production names these confusingly for historical
    # reasons -- `phase_inductance_h` is the self inductance and
    # `line_inductance_h` is the synchronous one, despite its name -- which is
    # exactly why Phase 9C added `phase_synchronous_inductance_h` as an
    # unambiguous alias. That alias is what this bridge reads.
    #
    # Using the self inductance here understates the reactance by the mutual
    # coupling (15 % on the reference design) and made the Phase 9C voltage
    # cross-check fail by 6.86 % before it was corrected.
    warnings: list[str] = []
    synchronous = getattr(electrical, "phase_synchronous_inductance_h", None)
    if synchronous is None:
        synchronous = getattr(electrical, "line_inductance_h", None)
    if d_axis_inductance_h is not None and q_axis_inductance_h is not None:
        Ld, Lq = float(d_axis_inductance_h), float(q_axis_inductance_h)
        inductance_provenance = "USER_SUPPLIED_SALIENT"
        inductance_note = "用户显式提供 Ld 与 Lq；未作各向同性假设。"
    elif synchronous and math.isfinite(synchronous) and synchronous > 0:
        Ld = Lq = float(synchronous)
        inductance_provenance = "ISOTROPIC_ASSUMPTION"
        inductance_note = (
            "取自生产模型的**每相同步电感** L_s = L_ph − M"
            "（字段名为 line_inductance_h，但其含义是每相同步电感，"
            "Phase 9C 已为此加了明确别名 phase_synchronous_inductance_h）。"
            "生产模型只提供这一个同步电感，因此取 Ld = Lq = Ls。"
            "这是**工程假设**，不是测量结果：本软件不会凭空制造凸极性。"
            "若实际机器为凸极结构，磁阻转矩与弱磁能力都会被低估。"
        )
        warnings.append(inductance_note)
    else:
        raise CapabilityParameterError("Ld/Lq are UNRESOLVED: no usable inductance")

    provenance = (
        ParameterProvenance(
            name="psi_pm",
            value=psi_pm,
            unit="Wb",
            source=psi_source,
            basis="PHASE_PEAK_FLUX_LINKAGE",
            conversion=psi_conversion,
            provenance="PRODUCTION_DERIVED",
            note_zh=cross_check_note,
        ),
        ParameterProvenance(
            name="Rs",
            value=Rs,
            unit="Ohm",
            source="electrical.phase_resistance_ohm",
            basis="PER_PHASE",
            conversion="identity",
            provenance="PRODUCTION_DERIVED",
            note_zh=(
                f"生产模型在绕组温度 {temperature:.1f} °C 下计算。"
                "本求解器**不做任何额外温度修正**。"
                if temperature is not None
                else "绕组温度未知；本求解器不做任何温度修正。"
            ),
        ),
        ParameterProvenance(
            name="Ld",
            value=Ld,
            unit="H",
            source=(
                "user" if inductance_provenance == "USER_SUPPLIED_SALIENT"
                else "electrical.phase_synchronous_inductance_h (= L_ph - M)"
            ),
            basis="PER_PHASE_SYNCHRONOUS",
            conversion="identity" if inductance_provenance == "USER_SUPPLIED_SALIENT" else "Ld = Ls = L_ph - M",
            provenance=inductance_provenance,
            note_zh=inductance_note,
        ),
        ParameterProvenance(
            name="Lq",
            value=Lq,
            unit="H",
            source=(
                "user" if inductance_provenance == "USER_SUPPLIED_SALIENT"
                else "electrical.phase_synchronous_inductance_h (= L_ph - M)"
            ),
            basis="PER_PHASE_SYNCHRONOUS",
            conversion="identity" if inductance_provenance == "USER_SUPPLIED_SALIENT" else "Lq = Ls = L_ph - M",
            provenance=inductance_provenance,
            note_zh=inductance_note,
        ),
    )

    return CapabilityParameters(
        schema_version=PARAMETERS_SCHEMA_VERSION,
        convention_version=CONVENTION_SCHEMA_VERSION,
        Rs=Rs,
        Ld=Ld,
        Lq=Lq,
        psi_pm=psi_pm,
        pole_pairs=pole_pairs,
        resistance_temperature_c=temperature,
        provenance=provenance,
        machine_type=_classify(Ld, Lq),
        warnings_zh=tuple(warnings),
    )


def render_provenance_zh(parameters: CapabilityParameters) -> str:
    lines = [
        f"机器类型：{MACHINE_TYPE_LABELS_ZH[parameters.machine_type]}",
        f"极对数 p = {parameters.pole_pairs}",
        f"凸极比 Lq/Ld = {parameters.saliency_ratio:.6f}",
        f"特征电流 ψ_pm/Ld = {parameters.characteristic_current_a:.4f} A（峰值）",
        "",
    ]
    for item in parameters.provenance:
        lines.extend(
            [
                f"{item.name} = {item.value:.10g} {item.unit}",
                f"    来源    ：{item.source}",
                f"    基准    ：{item.basis}",
                f"    换算    ：{item.conversion}",
                f"    溯源标记：{item.provenance}",
            ]
        )
        if item.note_zh:
            lines.append(f"    说明    ：{item.note_zh}")
        lines.append("")
    return "\n".join(lines)
