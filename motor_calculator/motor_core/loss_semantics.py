"""Single source of truth for what the legacy loss terms actually mean.

Phase 9B Batch A carries no formula change. Its whole purpose is to stop two
loss outputs from reading as validated predictions:

* the conductor eddy-current term is an experimental scalar-field approximation
* the "core loss" term is a rated-point empirical lump, not a stator-core-loss
  model, and it is not separated from rotor back-iron and magnet losses

This module is GUI-independent and contains no equations. It exists so that the
dashboard, the detailed report, the machine-readable export and the capability
matrix all quote exactly the same limitation text.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Machine-readable status codes
# ---------------------------------------------------------------------------

EDDY_LOSS_MODEL_STATUS = "EXPERIMENTAL_SCALAR_AIRGAP_FIELD"
CORE_LOSS_MODEL_STATUS = "EMPIRICAL_LUMPED_RATED_POINT"


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

EDDY_LOSS_LABEL_ZH = "导体涡流损耗（实验性）"
CORE_LOSS_LABEL_ZH = "集总磁性损耗（额定点经验）"


# ---------------------------------------------------------------------------
# Limitation statements
# ---------------------------------------------------------------------------

EDDY_LOSS_LIMITATION_ZH = (
    "实验性近似：使用单一气隙峰值磁密标量，并将其施加于包含端部绕组在内的"
    "全部铜体积；未解析导体局部磁场分布、端部磁场衰减、电枢反应磁场、"
    "邻近效应与线股位置。该项在中高速工况下可能主导效率估计。"
)

CORE_LOSS_LIMITATION_ZH = (
    "额定点经验集总项：按额定输出功率的固定比例取值，与转速和磁密完全解耦，"
    "不是经过验证的定子铁芯损耗预测。无铁芯（coreless）拓扑下定子无铁，但"
    "转子背铁与磁钢仍为铁磁/导电材料，其损耗既未建模也未与该项分离，"
    "因此该项不得被解读为可置零。"
)


# ---------------------------------------------------------------------------
# Derivation strings for the audited output inventory
# ---------------------------------------------------------------------------

EDDY_LOSS_DERIVATION = (
    "scalar air-gap peak flux density applied to the whole copper volume; "
    "no local, end-region, armature-reaction or proximity field resolution"
)

CORE_LOSS_DERIVATION = (
    "empirical lumped fraction of rated output power; independent of speed and "
    "flux density; rotor back-iron and magnet losses are not separated"
)

EDDY_LOSS_CONFIDENCE = "EXPERIMENTAL/scalar-field-approximation"
CORE_LOSS_CONFIDENCE = "EMPIRICAL_LUMPED/not-a-validated-core-loss-model"


def loss_limitation_report_lines_zh() -> tuple[str, ...]:
    """Detailed-report lines quoting both limitations verbatim."""

    return (
        "   损耗模型边界说明",
        f"     · {EDDY_LOSS_LABEL_ZH}（{EDDY_LOSS_MODEL_STATUS}）",
        f"       {EDDY_LOSS_LIMITATION_ZH}",
        f"     · {CORE_LOSS_LABEL_ZH}（{CORE_LOSS_MODEL_STATUS}）",
        f"       {CORE_LOSS_LIMITATION_ZH}",
    )


def loss_model_status_payload() -> dict[str, str]:
    """Machine-readable status fields for exports."""

    return {
        "eddy_loss_model_status": EDDY_LOSS_MODEL_STATUS,
        "eddy_loss_limitation_zh": EDDY_LOSS_LIMITATION_ZH,
        "core_loss_model_status": CORE_LOSS_MODEL_STATUS,
        "core_loss_limitation_zh": CORE_LOSS_LIMITATION_ZH,
    }
