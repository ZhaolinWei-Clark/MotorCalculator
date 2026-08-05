# Phase 7B：兼容 AFPM 静态 benchmark 复核与映射矩阵

## 1. 决策与边界

`AFPM_STATIC_BENCHMARK_STATUS = BLOCKED`

本轮没有候选同时满足：默认双转子、单定子、双气隙 AFPM 拓扑兼容，production 静态模型所需输入可从来源直接取得或安全转换，且至少一个外部输出具有明确工况和电气语义。因此本阶段按门槛停止在来源审计，不创建 `validation_data/imported/afpm_static_primary_record.json`，不运行 production prediction，也不生成误差行。

本结论不表示候选论文质量不足，只表示它们尚不能在**不猜测缺失字段**的前提下驱动当前模型并形成直接比较。

## 2. 候选复核

| 候选 | topology / evidence | 关键可用字段 | 关键缺口 | access / reuse | 决策 |
|---|---|---|---|---|---|
| [Parviainen 2005 dissertation](https://lutpub.lut.fi/handle/10024/31185) | AFPM；重点原型为一转子、两定子，5 kW、300 rpm；论文含 analytical、FEA 和 prototype study | AFPM 设计方法、额定点和多类设计数据 | 原型为 DSSR，不是默认 SSDR；不能做径向/轴向或 DSSR/SSDR 参数变换 | LUT 稳定元数据/全文入口；本轮未确认可再分发许可 | `BLOCKED`：topology mismatch |
| [Price et al. 2008](https://www.researchgate.net/publication/255661627_Design_and_Testing_of_a_Permanent_Magnet_Axial_Flux_Wind_Power_Generator) | 双转子、单定子、ironless/coreless、三相 Y；analytical + prototype measurement | 9 coils、36 turns/coil、磁体和主要半径/轴向尺寸、600 rpm 相反电势峰值、500 rpm torque/current operating point | `Br`、完整绕组/导线几何、若干 production required inputs 不可得；公开副本的再分发许可未确认 | 可在线阅读；仅记录 citation 和字段 provenance，不复制全文 | `BLOCKED`：material/input completeness |
| [Kowal et al. 2010](https://doi.org/10.1109/TMAG.2009.2032145) | 单定子、双转子、16 poles、15 teeth、三相集中绕组；FEA + prototype measurement | `Br=1.26 T`、90 turns/tooth、5 series coils/phase、2000 rpm、5.78 A；有 torque/back-EMF figures | 关键尺寸和健康输出主要在图中；T-shaped magnets、铁心与 production geometry 语义不完整；温度/电压语义不足 | IEEE DOI 可追溯；再分发受出版方条款约束 | `BLOCKED`：geometry/output extraction |
| [Si et al. 2022](https://eprints.whiterose.ac.uk/id/eprint/189185/) | 双转子、单定子、slotless，三相 Y，特殊 ED-TW；3D-FEA + prototype | 12 pole pairs、36 coils、51 turns/coil、612 turns/phase、1 mm gap、8 mm magnet、内外径、400 rpm/10 A RMS、phase/line back EMF | 只给出 N48SH grade，未给数值 `Br`；ED-TW 不能按普通绕组解释；健康输出主要为 FEA，测量定义不覆盖全部字段 | White Rose author manuscript；页面明确 further copying may not be permitted | `BLOCKED`：material + winding abstraction |
| [Shahnazari et al. 2026](https://www.nature.com/articles/s41598-026-50884-6) | 单定子、双转子、coreless，三相，24 poles；3D-FEA + experiment | 390 W、40 V phase、3000 rpm、12 pole pairs、25x10x3 mm magnets、60/35 mm radii、8 mm stator、1 mm gap/side、50 turns/coil、`Br=1.2 T` | winding connection、导线/线圈截面和 turns-per-phase 语义未给；健康 phase voltage 只在图中；相 EMF 明确非正弦，不能做 RMS/peak/line/phase 推断 | CC BY-NC-ND 4.0；可非商业共享原文但不可分发改编材料 | `BLOCKED`：winding + numeric output semantics |

候选优先级更新：Parviainen 全文现已可追溯，但其主要原型拓扑不兼容。Shahnazari 2026 是当前最接近默认 SSDR coreless 拓扑、且材料字段最完整的**补源候选**；它仍不是已批准 primary benchmark。

## 3. 最近候选的字段映射

下表以 Shahnazari 2026 健康机为最近候选。分类只说明来源字段映射状态，不代表已经足以运行模型。

| Target field | Source evidence | Classification | Mapping / blocker |
|---|---|---|---|
| topology | single-stator dual-rotor, coreless, two air gaps | `DIRECT` | 与默认大类兼容 |
| `pole_pairs` | 12 | `DIRECT` | source Table 2 |
| `rated_speed_rpm` | 3000 rpm | `DIRECT` | source Table 2；另有 600 rpm healthy generator experiment |
| `air_gap_m` | 1 mm one side | `TRANSFORM` | `1 mm * 1e-3 = 0.001 m`；保留 per-side 语义 |
| `magnet_thickness_m` | 25x10x3 mm magnet dimensions | `TRANSFORM` | 仅在明确 3 mm 为 axial height 后可映射为 0.003 m；论文正文的 `h_m` 支持该方向，但仍保留 provenance |
| magnet plan dimensions | rectangular 25x10 mm | `TRANSFORM` | mm 到 m；production 的 width/length 方向需要图形语义，不能仅按数字顺序猜测 |
| `magnet_remanence_t` | 1.2 T | `DIRECT` | source Table 2 |
| active diameters | stator outer/inner radius 60/35 mm | `TRANSFORM` | 可安全转换为 outer/inner diameter 0.120/0.070 m |
| `turns_per_phase` | 50 turns/coil；18 coils total | `BLOCKED` | 相内串并联与 connection 未明确；不能从 coil count 自动推导 |
| `winding_connection` | three-phase only | `UNAVAILABLE` | 不假设 Y/Delta |
| winding geometry | trapezoid, single-layer, 18 coils | `BLOCKED` | 无足够的 coil side、wire diameter、parallel paths 等 production inputs |
| `phase_resistance_ohm` | not reported | `UNAVAILABLE` | 不从 load resistance 或 current density推断 |
| `phase_inductance_h` / `Ld`,`Lq` | not reported | `UNAVAILABLE` | 不从 coreless topology 推断为零 |
| current | current density 23.8 A/mm2 | `BLOCKED` | conductor area unavailable，不能换算 phase current |
| back EMF / phase voltage | healthy experiment at 600 rpm and 10 ohm/phase load, waveform figure | `BLOCKED` | 图中没有可追溯表格数值；loaded phase voltage 不是自动等同 no-load back EMF |
| `Ke` | not reported | `UNAVAILABLE` | 不能从未数值化、非正弦 waveform 推导 |
| torque | healthy/full-load curves and eccentricity table | `BLOCKED` | 没有与完整 healthy electrical operating point 成套的可直接导入值 |
| `Kt` | not reported | `UNAVAILABLE` | current basis unavailable，不推导 |
| losses | efficiency results under fault studies | `BLOCKED` | healthy loss breakdown 与相同 operating point 不完整 |
| efficiency | rated/fault analysis discussed | `BLOCKED` | 输入/输出功率和健康工况数据未形成可直接导入成套记录 |
| operating temperature | not reported | `UNAVAILABLE` | 不采用默认温度替代来源温度 |

## 4. 允许的 normalization

本轮只批准并记录以下变换；由于 primary benchmark 未锁定，它们没有被用于生成 comparison row：

| Transformation | Formula | Safety condition |
|---|---|---|
| rpm to rad/s | `omega = rpm * 2*pi/60` | speed basis 明确为 mechanical |
| rad/s to rpm | `rpm = omega * 60/(2*pi)` | 同上 |
| mm to m | `m = mm * 1e-3` | dimension direction/meaning 已明确 |
| radius to diameter | `D = 2*r` | source 明确给 radius |
| sinusoidal phase RMS to phase peak | `V_peak = sqrt(2)*V_phase_rms` | waveform 明确为 sinusoidal 和 fundamental/total basis 已知 |
| sinusoidal Y phase RMS to line RMS | `V_line_rms = sqrt(3)*V_phase_rms` | Y connection 与 sinusoidal phase sequence 均明确 |

禁止的 normalization：DSSR 到 SSDR、radial 到 axial、未知 connection 的 phase/line 换算、非正弦波形的 RMS/peak 换算、`Ld/Lq` 到 scalar inductance、current density 到 phase current、magnet grade 到 `Br`、未知 current basis 到 `Kt`。

## 5. Primary selection result

本轮**没有选择 primary static AFPM benchmark**。这是 threshold failure，不是候选排名。因而：

- imported source records created：0；
- externally directly comparable rows：0；
- production model invocations：0；
- guessed/default-substituted source fields：0；
- `validation_data/reports/phase7b_afpm_static_comparison_zh.md`：不生成。

解除阻断的最短路径是取得 Shahnazari/Hosseini 原始设计资料或作者补充数据，至少确认 phase connection、每相串并联匝数、导线/线圈几何、健康 no-load back-EMF 数值与 peak/RMS/phase/line 定义。若无法取得，应继续寻找字段完整的公开 SSDR AFPM benchmark，而不是降低门槛。
