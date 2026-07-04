# 外部数据源候选清单

更新时间：2026-07-04

## 1. 目的与边界

本文档用于 Phase 4B 的外部数据源侦察，只整理候选来源、字段完整度、导入风险和优先级，不导入任何真实外部数据文件。

本轮明确不做：

- 不修改任何 production calculation 文件
- 不切换 revised 默认链路
- 不校准任何经验系数
- 不创建 `validation_data/imported/*.json`
- 不把厂家宣传页误写成强验证证据
- 不把控制数据集误写成几何电磁 benchmark

## 2. 评分口径

- `priority score = 5`：最适合尽快转成首批 validation record
- `priority score = 4`：价值高，但需要用户补源或人工抽取
- `priority score = 3`：更适合作为 FEA / 方法 / 开源实现参考
- `priority score = 2`：价值有限，或仅能验证局部链路
- `priority score = 1`：当前不建议作为导入目标

推荐证据等级沿用 Phase 4A：

- `LEVEL_2_PUBLISHED_OR_FEA`
- `LEVEL_3_CONTROLLED_MEASUREMENT`
- `LEVEL_4_MULTI_SOURCE_VALIDATION`

## 3. 总览

| 候选 | 类型 | 电机范围 | 数据性质 | 直接导入潜力 | priority score |
|---|---|---|---|---|---:|
| CREATOR PMSM Data | published benchmark + bench measurement | PMSM | 公开数据包 + 实测 | 高 | 5 |
| CREATOR IM Data | published benchmark + bench measurement | IM | 公开数据包 + 实测 | 中 | 4 |
| Parviainen 2005 AFPM dissertation / worked examples | published worked example | AFPM PMSM | 论文/学位论文示例 | 中 | 4 |
| FEMM SPM loss tutorial | FEA example | RFPM PMSM | 教程型 FEA | 中 | 4 |
| PYLEECAN examples + FEMM coupling | open-source tool + examples | PMSM / IM / others | 仿真与代码示例 | 低到中 | 3 |
| FEMM outrunner BLDC optimization example | FEA example | outrunner BLDC | 优化示例 | 低 | 3 |
| TUMFTM Electric_Machine_Design | open-source design tool | PSM / ASM | 设计工具 + 结果文件 | 低 | 3 |
| Paderborn / Kaggle electrical-behavior dataset | university bench dataset | PMSM + inverter | 控制/系统辨识数据 | 很低 | 2 |
| Paderborn / Kaggle temperature benchmark dataset | university bench dataset | PMSM | 热状态估计数据 | 很低 | 2 |
| EMRAX public product pages | manufacturer data | AFPM BLDC/PMSM family | 厂家规格 | 很低 | 1 |
| FEniCSx PMSM model paper (exact source unresolved) | citation-only candidate | PMSM | 待补源论文 | 很低 | 1 |

## 4. 详细评估

### 4.1 CREATOR Case: Permanent Magnet Synchronous Motor Data

- `name`: CREATOR Case: Permanent Magnet Synchronous Motor Data
- `source_type`: `published_benchmark` + `bench_measurement`
- `URL or citation`:
  - TU Graz dataset DOI: [10.3217/sns1d-77m43](https://doi.org/10.3217/sns1d-77m43)
  - Paper: [CREATOR Case: PMSM and IM Electric Machine Data for Validation and Benchmarking of Simulation and Modeling Approaches](https://arxiv.org/abs/2501.15921)
- `license / usage note`: CC BY-NC 4.0 on the TU Graz repository dataset page
- `access status`: `open`
- `motor type`: PMSM
- `topology`: 研究用 PMSM；精确拓扑需查看数据包 PDF / ZIP
- `control mode`: 需要从数据包细化；已知含 steady-state 与 drive-cycle measurement
- `whether it is PMSM, BLDC, AFPM, RFPM, IM, or other`: PMSM；是否 AFPM/RFPM 待人工抽取确认
- `available input fields`: 几何参数、材料参数、电参数、绕组方案、等效电路参数、驱动循环输入
- `available output fields`: no-load / equivalent-circuit / drive-cycle measurement、输入/输出功率、损耗类结果
- `whether geometry is complete`: 是
- `whether material data is complete`: 是
- `whether winding data is complete`: 是
- `whether speed/current/voltage conditions are complete`: 是
- `whether outputs include torque`: 是
- `whether outputs include back EMF`: 需要人工确认具体字段名
- `whether outputs include Ke`: 需要人工确认
- `whether outputs include Kt`: 需要人工确认
- `whether outputs include efficiency`: 是，可由输入/输出功率直接或间接得到
- `whether outputs include copper loss`: 需要人工确认是否分项给出
- `whether outputs include iron loss`: 需要人工确认是否分项给出
- `whether outputs include temperature`: 当前侦察未确认
- `whether data is experimental, FEA, analytical, synthetic, or manufacturer spec`: 以公开设计数据 + 台架测量为主
- `whether it is directly importable into Phase 4A schema`: 基本可以，但仍需要人工抽取字段并填写 comparability / exclusions
- `missing fields`: 当前侦察阶段尚未逐页确认 back EMF / Ke / Kt / 温度 / 拓扑字段名
- `risks`:
  - 很可能不是 AFPM
  - 需要人工从 ZIP/PDF 提取字段
  - 许可为非商用，后续共享导入文件时要保留来源说明
- `recommended evidence level`: `LEVEL_3_CONTROLLED_MEASUREMENT`
- `priority score from 1 to 5`: `5`
- `recommended next action`: 作为 Phase 4C 首选，先做一条 PMSM validation record 的手工抽取模板

### 4.2 CREATOR Case: Induction Motor Data

- `name`: CREATOR Case: Induction Motor Data
- `source_type`: `published_benchmark` + `bench_measurement`
- `URL or citation`:
  - Paper: [CREATOR Case: PMSM and IM Electric Machine Data for Validation and Benchmarking of Simulation and Modeling Approaches](https://arxiv.org/abs/2501.15921)
  - Dataset DOI is cited inside the paper and should be used during Phase 4C import
- `license / usage note`: 预计与 PMSM 数据包同类；导入前仍需在实际数据页核对
- `access status`: `open`, but exact IM repository page still needs manual follow-up
- `motor type`: IM
- `topology`: IM；精确结构需看数据包
- `control mode`: 需从数据包细化
- `whether it is PMSM, BLDC, AFPM, RFPM, IM, or other`: IM
- `available input fields`: 几何、材料、电参数、绕组、等效电路、驱动循环输入
- `available output fields`: no-load / locked-rotor / equivalent-circuit / drive-cycle measurement
- `whether geometry is complete`: 是
- `whether material data is complete`: 是
- `whether winding data is complete`: 是
- `whether speed/current/voltage conditions are complete`: 是
- `whether outputs include torque`: 是
- `whether outputs include back EMF`: 不适用
- `whether outputs include Ke`: 不适用
- `whether outputs include Kt`: 不适用
- `whether outputs include efficiency`: 是
- `whether outputs include copper loss`: 需要人工确认是否分项给出
- `whether outputs include iron loss`: 需要人工确认是否分项给出
- `whether outputs include temperature`: 当前侦察未确认
- `whether data is experimental, FEA, analytical, synthetic, or manufacturer spec`: 公开设计数据 + 台架测量
- `whether it is directly importable into Phase 4A schema`: 可以，但与当前 AFPM PMSM/BLDC 生产链相关性较低
- `missing fields`: 与项目目标电机类型不匹配；PM 相关字段不适用
- `risks`:
  - 不是本项目目标机型
  - 适合验证 schema 和 comparability gate，不适合直接证明 AFPM/PMSM/BLDC 物理准确度
- `recommended evidence level`: `LEVEL_3_CONTROLLED_MEASUREMENT`
- `priority score from 1 to 5`: `4`
- `recommended next action`: 作为 schema 压测用候选保留，优先级低于 CREATOR PMSM

### 4.3 Parviainen 2005 AFPM dissertation / worked examples

- `name`: Asko Parviainen, *Design of axial-flux permanent-magnet low-speed machines and performance comparison between radial-flux and axial-flux machines* (2005)
- `source_type`: `published_benchmark` / `analytical_or_fea_worked_example`
- `URL or citation`: title cited by multiple public references; this scouting pass did not confirm a stable full-text URL
- `license / usage note`: `needs_user_supplied_source`
- `access status`: `needs_user_supplied_source`
- `motor type`: AFPM PMSM
- `topology`: 高相关 AFPM；预计包含单/双转子比较
- `control mode`: likely steady-state design example; exact operating assumptions need source
- `whether it is PMSM, BLDC, AFPM, RFPM, IM, or other`: AFPM PMSM
- `available input fields`: likely geometry / winding / pole count / material and rated-point design data, but not verified in this pass
- `available output fields`: likely torque / efficiency / power-density style outputs, but not verified in this pass
- `whether geometry is complete`: `needs_user_supplied_source`
- `whether material data is complete`: `needs_user_supplied_source`
- `whether winding data is complete`: `needs_user_supplied_source`
- `whether speed/current/voltage conditions are complete`: `needs_user_supplied_source`
- `whether outputs include torque`: `needs_user_supplied_source`
- `whether outputs include back EMF`: `needs_user_supplied_source`
- `whether outputs include Ke`: `needs_user_supplied_source`
- `whether outputs include Kt`: `needs_user_supplied_source`
- `whether outputs include efficiency`: `needs_user_supplied_source`
- `whether outputs include copper loss`: `needs_user_supplied_source`
- `whether outputs include iron loss`: `needs_user_supplied_source`
- `whether outputs include temperature`: `needs_user_supplied_source`
- `whether data is experimental, FEA, analytical, synthetic, or manufacturer spec`: likely analytical + FEA + design example, exact mix unconfirmed
- `whether it is directly importable into Phase 4A schema`: 暂不能判断
- `missing fields`: 需要用户提供论文或可访问全文
- `risks`:
  - 当前只有 citation，没有完成字段级确认
  - 即便有 worked example，也未必是实验 benchmark
- `recommended evidence level`: 暂按 `LEVEL_2_PUBLISHED_OR_FEA` 预估
- `priority score from 1 to 5`: `4`
- `recommended next action`: 如果用户能提供全文，这是最值得优先补源的 AFPM 文献候选之一

### 4.4 FEMM example: Rotating Losses in a Surface Mount Permanent Magnet Motor

- `name`: FEMM example: Rotating Losses in a Surface Mount Permanent Magnet Motor
- `source_type`: `fea_simulation`
- `URL or citation`: [FEMM SPMLoss example](https://www.femm.info/wiki/SPMLoss)
- `license / usage note`: 官方公开教程页面；导入时应保留原始教程链接与作者
- `access status`: `open`
- `motor type`: surface-mount PMSM
- `topology`: RFPM, concentrated winding
- `control mode`: sinusoidal / field-oriented style operating假设
- `whether it is PMSM, BLDC, AFPM, RFPM, IM, or other`: PMSM, RFPM
- `available input fields`: 转子内外径、定子尺寸、气隙、叠长、磁材、硅钢、导线规格、匝数、绕组节距
- `available output fields`: core loss / magnet loss / winding loss / waveform distortion discussion
- `whether geometry is complete`: 是
- `whether material data is complete`: 是
- `whether winding data is complete`: 是
- `whether speed/current/voltage conditions are complete`: 部分完整
- `whether outputs include torque`: 不作为主输出给出
- `whether outputs include back EMF`: 有波形与 THD 讨论，但仍需人工抽图/抽值
- `whether outputs include Ke`: 否
- `whether outputs include Kt`: 否
- `whether outputs include efficiency`: 否
- `whether outputs include copper loss`: 部分有
- `whether outputs include iron loss`: 是
- `whether outputs include temperature`: 否
- `whether data is experimental, FEA, analytical, synthetic, or manufacturer spec`: FEA tutorial
- `whether it is directly importable into Phase 4A schema`: 可以转为 `fea_simulation` 记录，但必须明确它不是实验验证
- `missing fields`: 额定点定义、统一的 torque / efficiency / Ke / Kt 输出
- `risks`:
  - 非 AFPM
  - 教程导向，目标不是 benchmark packaging
  - 结果强依赖 FEMM workflow
- `recommended evidence level`: `LEVEL_2_PUBLISHED_OR_FEA`
- `priority score from 1 to 5`: `4`
- `recommended next action`: 如果用户希望先打通 FEA 类记录导入流程，可作为第一条 FEA-only 样例

### 4.5 PYLEECAN open-source examples and FEMM-coupled workflows

- `name`: PYLEECAN / Eomys open-source machine design and simulation framework
- `source_type`: `fea_simulation` / `synthetic_example` / `open_source_tool`
- `URL or citation`:
  - GitHub: [Eomys/pyleecan](https://github.com/Eomys/pyleecan)
- `license / usage note`: Apache-2.0
- `access status`: `open`
- `motor type`: PMSM / IM / DFIM / WRSM / SRM / SynRM 等
- `topology`: 以二维 RFPM 拓扑为主；项目主页未显示 AFPM 是现成标准拓扑
- `control mode`: 依具体 example 而定
- `whether it is PMSM, BLDC, AFPM, RFPM, IM, or other`: mostly RFPM PMSM/IM family
- `available input fields`: 几何、材料、槽型、磁钢、绕组、仿真设置
- `available output fields`: 磁场、损耗、等效电路、参数扫频等，取决于 example
- `whether geometry is complete`: 是
- `whether material data is complete`: 是
- `whether winding data is complete`: 是
- `whether speed/current/voltage conditions are complete`: 部分完整
- `whether outputs include torque`: 是，取决于 example
- `whether outputs include back EMF`: 是，取决于 example
- `whether outputs include Ke`: 通常需要后处理
- `whether outputs include Kt`: 通常需要后处理
- `whether outputs include efficiency`: 取决于 model / example
- `whether outputs include copper loss`: 是
- `whether outputs include iron loss`: 是
- `whether outputs include temperature`: 取决于 coupling
- `whether data is experimental, FEA, analytical, synthetic, or manufacturer spec`: 主要是 FEA / simulation-generated examples
- `whether it is directly importable into Phase 4A schema`: 不能当作强 external benchmark；仅能当 FEA reference 或 synthetic/derived record
- `missing fields`: 原始实验 provenance、统一 benchmark 输出包
- `risks`:
  - 这是工具，不是单一标准 benchmark
  - 例子很多，但每个例子的证据等级和字段完整度不同
  - 不应把 PYLEECAN 运行结果误写成真实外部实验
- `recommended evidence level`: `LEVEL_2_PUBLISHED_OR_FEA`
- `priority score from 1 to 5`: `3`
- `recommended next action`: 若后续要导入 FEA examples，应先锁定一个具体 tutorial case 再单独抽字段

### 4.6 FEMM example: Optimization of an Outrunner BLDC Motor

- `name`: FEMM random optimization / outrunner BLDC motor example
- `source_type`: `fea_simulation`
- `URL or citation`: [FEMM RandomOptimization example](https://www.femm.info/wiki/RandomOptimization)
- `license / usage note`: 官方公开教程页面；应保留教程出处
- `access status`: `open`
- `motor type`: outrunner BLDC
- `topology`: RFPM outrunner BLDC
- `control mode`: torque target + current density constraint; exact electrical semantics are tutorial-defined
- `whether it is PMSM, BLDC, AFPM, RFPM, IM, or other`: BLDC, RFPM
- `available input fields`: candidate geometry variables, target torque, current density
- `available output fields`: optimized geometry / torque per unit length / size tradeoff
- `whether geometry is complete`: 部分完整
- `whether material data is complete`: 部分完整
- `whether winding data is complete`: 部分完整
- `whether speed/current/voltage conditions are complete`: 不完整
- `whether outputs include torque`: 是
- `whether outputs include back EMF`: 否
- `whether outputs include Ke`: 否
- `whether outputs include Kt`: 否
- `whether outputs include efficiency`: 否
- `whether outputs include copper loss`: 间接约束，不是完整输出
- `whether outputs include iron loss`: 否
- `whether outputs include temperature`: 否
- `whether data is experimental, FEA, analytical, synthetic, or manufacturer spec`: FEA + optimization tutorial
- `whether it is directly importable into Phase 4A schema`: 不适合作为首批 validation record
- `missing fields`: 电压条件、材料完整度、统一测试工况、损耗与热链
- `risks`:
  - 更像设计优化演示，不像验证 benchmark
  - 与本项目目标 AFPM 有拓扑不匹配
- `recommended evidence level`: `LEVEL_2_PUBLISHED_OR_FEA`
- `priority score from 1 to 5`: `3`
- `recommended next action`: 只保留作 BLDC FEA 方法参考，不作为首批导入目标

### 4.7 Paderborn / Kaggle electrical-behavior dataset

- `name`: Paderborn / Wallscheid / Böcker electrical-behavior PMSM dataset
- `source_type`: `bench_measurement` with public dataset mirror on Kaggle
- `URL or citation`:
  - Paper I: [Data Set Description: Identifying the Physics Behind an Electric Motor -- Data-Driven Learning of the Electrical Behavior (Part I)](https://arxiv.org/abs/2003.07273)
  - Paper II: [Data Set Description: Identifying the Physics Behind an Electric Motor -- Data-Driven Learning of the Electrical Behavior (Part II)](https://arxiv.org/abs/2003.06268)
- `license / usage note`: 需要在实际 Kaggle dataset 页面核对
- `access status`: paper `open`; dataset distribution channel requires manual follow-up
- `motor type`: PMSM + inverter system
- `topology`: 未在本轮侦察中确认
- `control mode`: 强控制导向 / MPC / system identification
- `whether it is PMSM, BLDC, AFPM, RFPM, IM, or other`: PMSM system dataset
- `available input fields`: 高时间分辨率控制相关变量；精确字段清单需查数据页
- `available output fields`: 动态电行为相关目标；精确字段清单需查数据页
- `whether geometry is complete`: 否
- `whether material data is complete`: 否
- `whether winding data is complete`: 否
- `whether speed/current/voltage conditions are complete`: 是，且动态范围大
- `whether outputs include torque`: 需要人工确认
- `whether outputs include back EMF`: 否，至少当前公开摘要未说明
- `whether outputs include Ke`: 否
- `whether outputs include Kt`: 否
- `whether outputs include efficiency`: 否
- `whether outputs include copper loss`: 否
- `whether outputs include iron loss`: 否
- `whether outputs include temperature`: 否
- `whether data is experimental, FEA, analytical, synthetic, or manufacturer spec`: 台架测量
- `whether it is directly importable into Phase 4A schema`: 不适合作为本项目电磁几何 benchmark 的首批记录
- `missing fields`: 几何、材料、绕组、磁钢、Back EMF / Ke / Kt
- `risks`:
  - 容易被误判成“电机 benchmark”，实际上更偏控制 / 系统辨识
  - 无法完整验证电磁模型
- `recommended evidence level`: `LEVEL_3_CONTROLLED_MEASUREMENT`
- `priority score from 1 to 5`: `2`
- `recommended next action`: 若后续单独做控制/辨识验证可再跟进；当前不建议优先导入

### 4.8 Paderborn / Kaggle PMSM temperature benchmark dataset

- `name`: Paderborn / Wallscheid thermal-state PMSM benchmark dataset
- `source_type`: `bench_measurement` with public benchmark reuse in later papers
- `URL or citation`:
  - [Data-Driven Permanent Magnet Temperature Estimation in Synchronous Motors with Supervised Machine Learning](https://arxiv.org/abs/2001.06246)
  - [Global Attention-based Encoder-Decoder LSTM Model for Temperature Prediction of Permanent Magnet Synchronous Motors](https://arxiv.org/abs/2208.00293)
- `license / usage note`: actual dataset page still needs manual follow-up
- `access status`: paper `open`; dataset distribution channel unresolved in this pass
- `motor type`: PMSM
- `topology`: 未在本轮侦察中确认
- `control mode`: control / thermal estimation context
- `whether it is PMSM, BLDC, AFPM, RFPM, IM, or other`: PMSM
- `available input fields`: external measurable electrical quantities + operating conditions
- `available output fields`: stator winding / tooth / yoke / magnet temperatures
- `whether geometry is complete`: 否
- `whether material data is complete`: 否
- `whether winding data is complete`: 否
- `whether speed/current/voltage conditions are complete`: 是
- `whether outputs include torque`: 需要人工确认
- `whether outputs include back EMF`: 否
- `whether outputs include Ke`: 否
- `whether outputs include Kt`: 否
- `whether outputs include efficiency`: 否
- `whether outputs include copper loss`: 否
- `whether outputs include iron loss`: 否
- `whether outputs include temperature`: 是
- `whether data is experimental, FEA, analytical, synthetic, or manufacturer spec`: 台架测量
- `whether it is directly importable into Phase 4A schema`: 仅适合作 future thermal-only weak validation，不适合当前电磁几何 validation 主线
- `missing fields`: 几何、材料、绕组、loss breakdown、back EMF family
- `risks`:
  - 与当前 legacy thermal model 的字段链仍未对齐
  - 不能反向证明电磁计算链正确
- `recommended evidence level`: `LEVEL_3_CONTROLLED_MEASUREMENT`
- `priority score from 1 to 5`: `2`
- `recommended next action`: 暂列保留项；只有在未来单独批准 thermal validation 时再推进

### 4.9 TUMFTM Electric_Machine_Design

- `name`: TUMFTM / Electric_Machine_Design
- `source_type`: `open_source_tool`
- `URL or citation`: [TUMFTM/Electric_Machine_Design](https://github.com/TUMFTM/Electric_Machine_Design)
- `license / usage note`: 当前仓库首页未看到明确开源 license，后续使用前需核对
- `access status`: `open`
- `motor type`: PSM / ASM
- `topology`: 设计工具层面通用，非单一 benchmark machine
- `control mode`: 效率图与设计工具假设
- `whether it is PMSM, BLDC, AFPM, RFPM, IM, or other`: PSM / IM family
- `available input fields`: nominal power, speed, voltage, pole pairs, power factor, phases, conductor material, winding connection, cooling, magnet pattern
- `available output fields`: calculated machine parameters and efficiency diagrams
- `whether geometry is complete`: 部分完整，由工具生成
- `whether material data is complete`: 部分完整
- `whether winding data is complete`: 部分完整
- `whether speed/current/voltage conditions are complete`: 部分完整
- `whether outputs include torque`: 间接可得
- `whether outputs include back EMF`: 当前仓库首页未明确
- `whether outputs include Ke`: 未明确
- `whether outputs include Kt`: 未明确
- `whether outputs include efficiency`: 是
- `whether outputs include copper loss`: 取决于输出 Excel，当前未逐项确认
- `whether outputs include iron loss`: 取决于输出 Excel，当前未逐项确认
- `whether outputs include temperature`: 未明确
- `whether data is experimental, FEA, analytical, synthetic, or manufacturer spec`: 工具输出 + literature-based approximations
- `whether it is directly importable into Phase 4A schema`: 不建议直接导入为真实 validation data
- `missing fields`: 原始实验记录、统一外部 expected、明确 license
- `risks`:
  - 更像设计工具，而不是外部 benchmark 数据源
  - README 写明部分参数来自 literature approximations
- `recommended evidence level`: 若真要导入，只能按 `LEVEL_2_PUBLISHED_OR_FEA` 或更低保守处理
- `priority score from 1 to 5`: `3`
- `recommended next action`: 作为结构和字段参考，不作为首批导入数据

### 4.10 EMRAX public product pages

- `name`: EMRAX public product family pages
- `source_type`: `manufacturer_data`
- `URL or citation`: [EMRAX official site](https://emrax.com/)
- `license / usage note`: 厂家公开网页；仅可作弱参考
- `access status`: `open`
- `motor type`: axial flux e-motors
- `topology`: AFPM
- `control mode`: 未公开完整定义
- `whether it is PMSM, BLDC, AFPM, RFPM, IM, or other`: AFPM family
- `available input fields`: 产品级功率、扭矩、部分电压等级、效率宣传值
- `available output fields`: 产品级 peak/continuous specs
- `whether geometry is complete`: 否
- `whether material data is complete`: 否
- `whether winding data is complete`: 否
- `whether speed/current/voltage conditions are complete`: 部分完整
- `whether outputs include torque`: 是
- `whether outputs include back EMF`: 否
- `whether outputs include Ke`: 否
- `whether outputs include Kt`: 否
- `whether outputs include efficiency`: 是，产品级
- `whether outputs include copper loss`: 否
- `whether outputs include iron loss`: 否
- `whether outputs include temperature`: 否
- `whether data is experimental, FEA, analytical, synthetic, or manufacturer spec`: manufacturer spec
- `whether it is directly importable into Phase 4A schema`: 不建议
- `missing fields`: 几何、材料、绕组、相/线语义、RMS/peak语义、loss breakdown、test conditions
- `risks`:
  - 厂家规格不能当控制台架验证
  - 语义边界和测试条件不够完整
- `recommended evidence level`: 至多 `LEVEL_2_PUBLISHED_OR_FEA` 风格弱参考；不能升格为 `LEVEL_3`
- `priority score from 1 to 5`: `1`
- `recommended next action`: 仅保留作 AFPM 市售规格参考，不导入 validation_data

### 4.11 FEniCSx PMSM model paper (exact source unresolved in this scouting pass)

- `name`: FEniCSx PMSM model paper / example (exact citation unresolved)
- `source_type`: `published_paper_candidate`
- `URL or citation`: `needs_user_supplied_source`
- `license / usage note`: `needs_user_supplied_source`
- `access status`: `needs_user_supplied_source`
- `motor type`: PMSM
- `topology`: unresolved
- `control mode`: unresolved
- `whether it is PMSM, BLDC, AFPM, RFPM, IM, or other`: PMSM candidate
- `available input fields`: unresolved
- `available output fields`: unresolved
- `whether geometry is complete`: `needs_user_supplied_source`
- `whether material data is complete`: `needs_user_supplied_source`
- `whether winding data is complete`: `needs_user_supplied_source`
- `whether speed/current/voltage conditions are complete`: `needs_user_supplied_source`
- `whether outputs include torque`: `needs_user_supplied_source`
- `whether outputs include back EMF`: `needs_user_supplied_source`
- `whether outputs include Ke`: `needs_user_supplied_source`
- `whether outputs include Kt`: `needs_user_supplied_source`
- `whether outputs include efficiency`: `needs_user_supplied_source`
- `whether outputs include copper loss`: `needs_user_supplied_source`
- `whether outputs include iron loss`: `needs_user_supplied_source`
- `whether outputs include temperature`: `needs_user_supplied_source`
- `whether data is experimental, FEA, analytical, synthetic, or manufacturer spec`: likely FEA paper, but not confirmed
- `whether it is directly importable into Phase 4A schema`: 当前不能判断
- `missing fields`: 全部需要用户补源或提供精确 citation
- `risks`:
  - 本轮未找到可确认的精确来源
  - 不能凭记忆编造字段
- `recommended evidence level`: 待定；若后续确认是公开 FEA 论文，预期是 `LEVEL_2_PUBLISHED_OR_FEA`
- `priority score from 1 to 5`: `1`
- `recommended next action`: 需要用户提供具体 paper / DOI / PDF 后再评估

## 5. 当前结论

当前最适合进入 Phase 4C 首个真实 validation record 导入的候选仍然是：

1. CREATOR PMSM Data
2. Parviainen 2005 AFPM 文献（前提是用户提供全文）
3. FEMM SPM loss tutorial（如果用户允许首条记录是 FEA-only，而不是实验 benchmark）

当前最容易被误判、因此必须谨慎的候选是：

- Paderborn/Kaggle 控制或温度数据集
- EMRAX 等厂家产品页
- TUMFTM / PYLEECAN 这类“工具输出”而不是“外部实测 benchmark”的来源
