"""Frozen model assumptions for the current refactor stage."""

from __future__ import annotations

MODEL_NAME_ZH = "三相轴向磁通永磁无刷电机 AFPM PMSM/BLDC"
DEFAULT_TOPOLOGY_ZH = "双转子、单定子、双气隙"
DEFAULT_CONNECTION_ZH = "Y 接"
DEFAULT_PHASE_COUNT = 3
DEFAULT_AIR_GAP_COUNT = 2

ASSUMPTION_SUMMARY_ZH = [
    "目标对象是三相轴向磁通永磁无刷电机，不是有刷 PMDC。",
    "默认拓扑为双转子、单定子、双气隙。",
    "默认绕组连接方式为 Y 接。",
    "pole_pairs 表示极对数，pole_count = 2 * pole_pairs 表示总极数。",
    "PMSM 模式表示正弦反电势与正弦电流。",
    "BLDC 模式表示梯形反电势与 120 度方波导通。",
    "当前阶段保留 legacy 经验公式，只补充来源状态和适用限制。",
]

EMPIRICAL_MODEL_LIMITATIONS_ZH = [
    "端部绕组长度、电感、互感、铁损、风阻、轴承损耗、齿槽转矩和转矩脉动仍为 legacy 经验模型。",
    "磁钢退磁、饱和、温升耦合、逆变器调制度、机械强度和详细槽满率尚未进入核心模型。",
]
