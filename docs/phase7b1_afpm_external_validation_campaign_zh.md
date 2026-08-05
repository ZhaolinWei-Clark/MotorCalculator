# Phase 7B.1 外部 AFPM 逐指标验证活动

## 目标与边界

本阶段不再要求一篇论文同时覆盖所有 geometry、winding、material 与 output 字段，而是按 metric 建立独立证据链。每一行都必须保留来源、页码、表/图、operating point、波形/连接/电流语义、证据类型与不确定性。

本活动不修改 `motor_core/calculations.py`、`legacy_baseline.json`、任何生产公式、默认参数、GUI、动态模型或控制器；不拟合参数，不引入修正系数，不用图像数字化或缺失字段推断来制造可比行。

## 状态定义

- `DIRECT`：来源量与模型量的物理语义、单位和 operating point 可直接对应。
- `SAFE_TRANSFORM`：只需已批准且可追踪的 SI、正弦 RMS/peak 或已知 Y 接 phase/line 换算。
- `APPROXIMATE`：来源存在近似或读图成分；可观察趋势，但不能产生 accuracy PASS 声明。
- `BLOCKED`：来源有值，但拓扑、绕组、波形、quantity scope 或模型输入不兼容。
- `UNAVAILABLE`：来源没有该值或无法取得数值全文；不得用 0 或估算值代替。

## 来源质量排序

| 顺位 | 来源 | 全文状态 | AFPM 拓扑 | 可用证据 | 本阶段判断 |
|---:|---|---|---|---|---|
| 1 | Parviainen 2005 dissertation | LUT 元数据与公开全文可取得 | 单转子/双定子，双定子电气并联 | 完整原型参数、额定点、E、R、Ld/Lq、效率 | 额定轴端 P-speed-torque 可 DIRECT；电磁量因拓扑/语义 BLOCKED |
| 2 | Hosseini et al. 2008 | 公开全文可取得 | 双转子/单无铁芯定子 | geometry、Br、空载/负载电压、效率、同步电抗 | 拓扑接近；绕组连接、波形和生产输入仍不完整 |
| 3 | Price et al. 2009 | 期刊整期 PDF 可取得 | 双转子/单无铁芯定子 | 37 V back-EMF peak、12.6 Nm shaft torque | topology 接近，但 Br、漏磁、winding factor 与 current basis 不足 |
| 4 | Abdelli et al. 2026 | 开放全文页面可读 | 双定子/单转子、18 槽 12 极 | 现代样机 geometry、back-EMF/torque 曲线、FEA | topology 不同且关键结果仅图示 |
| 5 | Bumby et al. 2004 | 仓储元数据和摘要可读，数值全文未取得 | slotless AFPM generators | 摘要声明 EMF 约 5%、L 约 10% | 不能用摘要百分比代替机器级参考值，UNAVAILABLE |

## 分指标来源质量评级

评级只针对该 metric，不构成来源的全局好坏排序。

| 来源 | back-EMF | torque | resistance | inductance | loss/efficiency | thermal |
|---|---|---|---|---|---|---|
| Abdelli 2026 | 中：有 measured/FEA 曲线但无数值表，且 DSSR | 中：有 torque-current 曲线但不读图 | 无：未报告 | 无：未报告 | 低：只有特定 FEA 分项 | 低：有冷却条件但无可映射温升验证行 |
| Price 2009 | 高证据/低可比：37 V phase peak 明确，production inputs 不足 | 高证据/低可比：12.6 Nm 明确，current basis 不足 | 无 | 无 | 无 | 无 |
| Parviainen 2005 | 高证据/阻塞：211 V phase RMS，DSSR 并联定子 | 高：额定轴端 P-speed-torque 可 DIRECT；torque-current 仍阻塞 | 高证据/阻塞：per-stator 3.7 ohm | 高证据/阻塞：Ld/Lq 不折叠 | 高证据/阻塞：89.2% 与 loss/cooling 映射不足 | 中：温度条件可见但无 production thermal 对应量 |
| Bumby 2004 | 潜在高、当前无：摘要称有 measurement | 无 | 无 | 潜在高、当前无：摘要称有 measurement | 无 | 无 |
| Hosseini 2008 | 高证据/阻塞：空载和负载 Vpp 表完整，波形有谐波 | 无明确 torque 点 | 无 | 中证据/阻塞：Xsd/Xsq 不是 scalar L | 高证据/阻塞：78.1% operating-point 映射不足 | 无 |

## Partial Geometry Mapping

`MISSING` 与 `AMBIGUOUS` 字段绝不由 production defaults 补齐。

| source | topology | active diameters | air gap | magnet thickness | Br | turns/winding | connection | winding factor | leakage semantics |
|---|---|---|---|---|---|---|---|---|---|
| Abdelli 2026 | `TOPOLOGY_DEPENDENT` DSSR | `DIRECT` 245/140 mm | `DIRECT` 1 mm | `DIRECT` 10 mm | `MISSING` numeric Br | `AMBIGUOUS` design vs prototype turns | `MISSING` | `MISSING` | `MISSING` |
| Price 2009 | `DIRECT` SSDR/coreless class | `DIRECT` ro/ri | `AMBIGUOUS` paper `lg` quantity vs project per-gap | `DIRECT` | `MISSING` | `DIRECT` 36 turns/coil, 3 series coils/phase | `DIRECT` Y | `MISSING` | `MISSING` |
| Parviainen 2005 | `TOPOLOGY_DEPENDENT` DSSR | `DIRECT` 328/197 mm | `DIRECT` 1.5 mm per stator | `DIRECT` 4 mm | `DIRECT` 1.05 T at 100 C | `DIRECT` 840 series turns/phase | `TOPOLOGY_DEPENDENT` star stators in parallel | `SAFE_TRANSFORM` only if source formula semantics are adopted, not approved here | `TOPOLOGY_DEPENDENT` |
| Bumby 2004 | `AMBIGUOUS` without numeric full text | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` | `MISSING` |
| Hosseini 2008 | `DIRECT` SSDR/coreless class | `DIRECT` 60/35 mm radii | `DIRECT` 1 mm each side | `DIRECT` 3 mm | `DIRECT` 1.2 T | `AMBIGUOUS` 50 conductors/coil without full phase series mapping | `MISSING` | `MISSING` | source uses `kfb=1.5`, not safely identical to production leakage factor |

## 已批准换算

验证代码仅支持显式的：

- `rpm -> rad/s`：乘以 `2*pi/60`。
- 正弦 phase RMS -> phase peak：乘以 `sqrt(2)`。
- 已知 Y 接且正弦的 phase RMS -> line RMS：乘以 `sqrt(3)`。

未知波形、未知连接、peak-to-peak harmonic waveform、未知 current basis、`Ld/Lq -> scalar L`、reactance -> production inductance 均拒绝自动换算。

## 首批结果

- 共 21 个逐指标证据行：`DIRECT=1`、`SAFE_TRANSFORM=0`、`APPROXIMATE=0`、`BLOCKED=14`、`UNAVAILABLE=6`。
- Parviainen 原型机表 3.1 给出 5 kW、300 rpm、159 Nm。既有 strict-SI 关系预测 `159.154943091895 Nm`，绝对误差 `0.154943091895 Nm`，APE `0.0974484855%`，按 Phase 7A torque tolerance 为 `PASS`。
- 该行只验证额定轴端 `T=P/omega` 的单位和数值一致性；它不验证 air-gap magnetic circuit、back-EMF、Ke/Kt 或 torque-current 模型。
- 其余数据没有被丢弃：来源值和 provenance 均保留，但在缺少安全模型桥时不计算误差。

## 是否进入 Phase 7C

建议只进入“逐指标证据扩充与 blocker 消除”的 Phase 7C，不建议进入参数校准。优先目标是取得同一 SSDR 样机的明确 series turns/phase、Y/Delta、Br 温度点、winding factor/leakage 语义，以及可表格化的 no-load back-EMF；在此之前不得把当前 PASS 扩展为 AFPM 模型整体 accuracy 结论。
