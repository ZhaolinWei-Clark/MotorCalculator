"""Phase 10F: what each torque quantity in this project actually means.

Phase 10C and 10D were both derailed by two numbers sharing a symbol. Torque is
worse than the winding factor was, because the project holds at least six
quantities that are all called "torque" and only some of them are outputs of a
physical model at all.

The specific trap this module exists to close: the production model's
``rated_torque_nm`` is ``P_rated / omega_mech``. It is a **shaft** torque derived
from a rated-power *input*; it is not computed from the magnetic circuit and it
does not move when the magnetic design changes. FEMM reports **electromagnetic**
torque from a Maxwell stress integral. Comparing those two directly would report
the difference between an assumption and a measurement, and would look like a
model residual.

The same-basis electromagnetic torque is available from values the production
model already publishes, and is defined here rather than invented in a script:

    T_em = Kt_rms * I_phase_rms = 3 * E_phase_rms * I_phase_rms / omega_mech

which is the power balance ``P_em = 3 * E * I`` for a sinusoidal PMSM at
``id = 0``. Nothing in this module changes a production value.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

TORQUE_SEMANTICS_SCHEMA_VERSION = "phase10f.torque_semantics.v1"


class TorqueSource:
    """Where a torque number comes from."""

    ANALYTICAL_MODEL = "ANALYTICAL_MODEL"
    DERIVED_FROM_INPUT = "DERIVED_FROM_INPUT"
    NUMERICAL_FEA = "NUMERICAL_FEA"
    EMPIRICAL_INPUT = "EMPIRICAL_INPUT"
    NO_ANALYTICAL_MODEL = "NO_ANALYTICAL_MODEL"


@dataclass(frozen=True)
class TorqueQuantity:
    """One named torque, with everything needed to know what it may be compared to."""

    name: str
    label_zh: str
    definition_zh: str
    equation: str
    unit: str
    load_condition: str
    source: str
    includes_losses: bool
    #: Quantities sharing a basis may be compared directly. Anything else needs
    #: an explicit reconciliation before a residual means anything.
    basis: str

    def comparable_with(self, other: "TorqueQuantity") -> bool:
        return self.basis == other.basis


#: The electromagnetic basis: torque developed by the air-gap field, before any
#: mechanical or stray loss is removed.
BASIS_ELECTROMAGNETIC = "ELECTROMAGNETIC_AIRGAP"
#: The shaft basis: what leaves the machine after losses.
BASIS_SHAFT = "SHAFT_OUTPUT"
#: A ratio of rated torque supplied by the user, not a torque model at all.
BASIS_EMPIRICAL_RATIO = "EMPIRICAL_RATIO_OF_RATED"


TORQUE_MAP: tuple[TorqueQuantity, ...] = (
    TorqueQuantity(
        name="rated_torque_nm",
        label_zh="额定转矩",
        definition_zh="由额定输出功率与机械转速直接得到的轴端转矩，不来自磁路模型",
        equation="T = P_rated / omega_mech",
        unit="newton_metre",
        load_condition="rated operating point, by definition",
        source=TorqueSource.DERIVED_FROM_INPUT,
        includes_losses=True,
        basis=BASIS_SHAFT,
    ),
    TorqueQuantity(
        name="average_torque_nm",
        label_zh="平均转矩（生产输出）",
        definition_zh="生产模型直接返回 rated_torque_nm，并非对磁场求平均得到",
        equation="T_avg = T_rated = P_rated / omega_mech",
        unit="newton_metre",
        load_condition="rated operating point",
        source=TorqueSource.DERIVED_FROM_INPUT,
        includes_losses=True,
        basis=BASIS_SHAFT,
    ),
    TorqueQuantity(
        name="electromagnetic_torque_same_basis_nm",
        label_zh="电磁转矩（同基准）",
        definition_zh="由反电动势与相电流经功率平衡得到的气隙电磁转矩，与 FEMM 同基准",
        equation="T_em = 3 * E_phase_rms * I_phase_rms / omega_mech",
        unit="newton_metre",
        load_condition="id = 0, iq = I_phase_rms, sinusoidal PMSM",
        source=TorqueSource.ANALYTICAL_MODEL,
        includes_losses=False,
        basis=BASIS_ELECTROMAGNETIC,
    ),
    TorqueQuantity(
        name="femm_block_integral_torque_nm",
        label_zh="FEMM 电磁转矩",
        definition_zh="对转子块做加权 Maxwell 应力积分得到的周向力乘以平均半径",
        equation="T = F_x * r_mean,  F_x = mo_blockintegral(18) over rotor groups",
        unit="newton_metre",
        load_condition="as excited in the solved case",
        source=TorqueSource.NUMERICAL_FEA,
        includes_losses=False,
        basis=BASIS_ELECTROMAGNETIC,
    ),
    TorqueQuantity(
        name="torque_ripple_percent",
        label_zh="转矩脉动（生产输出）",
        definition_zh="由用户输入的 6 次与 12 次脉动系数合成，不是磁场计算结果",
        equation="T(theta) = T_rated * (1 + k6 cos(6 theta_e) + k12 cos(12 theta_e))",
        unit="percent",
        load_condition="rated operating point",
        source=TorqueSource.EMPIRICAL_INPUT,
        includes_losses=True,
        basis=BASIS_EMPIRICAL_RATIO,
    ),
    TorqueQuantity(
        name="cogging_torque_peak_nm",
        label_zh="齿槽转矩峰值（生产输出）",
        definition_zh="用户输入的齿槽系数乘以额定转矩与一个形状因子；无铁芯时结构性为零",
        equation="T_cog_peak = shape_factor * k_cogging * T_rated,  = 0 if coreless",
        unit="newton_metre",
        load_condition="zero stator current, PM excitation only",
        source=TorqueSource.EMPIRICAL_INPUT,
        includes_losses=False,
        basis=BASIS_EMPIRICAL_RATIO,
    ),
)

TORQUE_BY_NAME = {quantity.name: quantity for quantity in TORQUE_MAP}


def same_basis_electromagnetic_torque_nm(
    *,
    back_emf_phase_rms_v: float,
    phase_current_rms_a: float,
    mechanical_angular_speed_rad_s: float,
    phases: int = 3,
) -> float:
    """Analytical electromagnetic torque on the basis FEMM reports.

    Power balance for a sinusoidal machine at ``id = 0``: all of ``m * E * I``
    crosses the air gap as electromagnetic power, so ``T = m E I / omega_mech``.
    No loss term is subtracted, because the FEMM block integral does not
    subtract one either.

    This is a restatement of quantities the production model already publishes.
    It does not modify, replace or correct any of them.
    """

    for name, value in (
        ("back_emf_phase_rms_v", back_emf_phase_rms_v),
        ("phase_current_rms_a", phase_current_rms_a),
        ("mechanical_angular_speed_rad_s", mechanical_angular_speed_rad_s),
    ):
        if not math.isfinite(value) or value < 0.0:
            raise ValueError(f"{name} must be finite and non-negative")
    if mechanical_angular_speed_rad_s == 0.0:
        raise ValueError("mechanical_angular_speed_rad_s must be non-zero")
    if phases < 1:
        raise ValueError("phases must be at least 1")
    return (
        phases
        * back_emf_phase_rms_v
        * phase_current_rms_a
        / mechanical_angular_speed_rad_s
    )


def assert_same_basis(left: str, right: str) -> None:
    """Raise unless two named torque quantities share a basis.

    Used as a guard at comparison sites so a basis error becomes an exception
    rather than a plausible-looking residual.
    """

    try:
        a, b = TORQUE_BY_NAME[left], TORQUE_BY_NAME[right]
    except KeyError as error:
        raise ValueError(f"unknown torque quantity: {error.args[0]!r}") from error
    if not a.comparable_with(b):
        raise ValueError(
            f"{left!r} is on the {a.basis} basis and {right!r} is on the "
            f"{b.basis} basis; comparing them would report the difference "
            "between two definitions, not a model residual"
        )
