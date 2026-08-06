# Phase 7G 定向 AFPM 基准获取报告

## 1. 结论

`AFPM_ADVANCED_BENCHMARK_STATUS = BLOCKED`

本阶段调查 13 个来源、来源族或开放模型入口，正式评分 8 个最相关候选，并为 4 个新候选建立逐字段证据包。现有 `AFPMCompletenessGate` 的结果为：

| 状态 | 数量 |
|---|---:|
| READY | 0 |
| PARTIAL | 0 |
| BLOCKED | 8 |

没有来源通过 gate，因此未运行 Advanced AFPM 求解器、未生成预测误差，也没有校准建议。最接近的是 Ferreira/IPB 2007 来源族（44/50）和 Mahmoudi 2013 TORUS 原型（42/50），两者各有 4 个 gate 缺项。

## 2. 检索方法

本阶段采用并记录了以下互补策略：

1. 回查 Phase 7F 的 Parviainen、Price、Hosseini、Abdelli 四个来源，复核论文正文、图表与来源恢复记录。
2. 检索带有 `prototype`、`measured back EMF`、`axial flux permanent magnet`、`turns per coil`、`air gap` 等组合关键词的出版物。
3. 优先访问出版社、大学机构库和开放期刊的全文，而不是二次聚合网页。
4. 检索同一机器的设计论文、原型论文、海报和机构记录，并以重复机器参数证明来源族身份。
5. 检索开放 FEMM/COMSOL/ANSYS/QuickField AFPM 个案与 OpenAFPM 项目，寻找可复现的 FEA 层基准。
6. 对每个候选按锁定的十个维度 0-5 评分，但始终以原 completeness gate 为最终决策。

未成功的检索也被保留：未找到一个同时公开给出有效非磁性气隙、径向磁体覆盖、完整绕组网络/`kw`、磁体 `Br/mur`、运行点和语义闭合实验反电势的来源；开放仿真入口多为软件示例或设计工具，而不是具有独立外部参考的完整 AFPM 基准。

## 3. 候选评分

评分列依次为：拓扑兼容、几何、磁体/材料、绕组、运行点、反电势语义、实验 provenance、FEA provenance、可复现性、许可/访问。

| 候选 | T | G | W | M | O | E | X | I | L | A | 总分 | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Ferreira/IPB 2007 DSSR 来源族 | 5 | 4 | 4 | 4 | 5 | 4 | 5 | 3 | 5 | 5 | 44 | BLOCKED |
| Mahmoudi 2013 slotted TORUS | 5 | 4 | 3 | 4 | 5 | 5 | 5 | 3 | 5 | 3 | 42 | BLOCKED |
| Parviainen 2005 原型 | 5 | 4 | 3 | 4 | 4 | 4 | 5 | 3 | 5 | 5 | 42 | BLOCKED |
| Huang 2016 concentrated AFPM | 5 | 3 | 3 | 2 | 4 | 2 | 4 | 2 | 5 | 5 | 35 | BLOCKED |
| Price 2009 coreless generator | 5 | 4 | 1 | 4 | 4 | 4 | 3 | 2 | 5 | 5 | 37 | BLOCKED |
| Abdelli 2026 DSSR prototype | 5 | 3 | 3 | 2 | 4 | 2 | 4 | 2 | 4 | 5 | 34 | BLOCKED |
| Hosseini 2008 coreless generator | 5 | 4 | 3 | 2 | 4 | 2 | 3 | 2 | 5 | 3 | 33 | BLOCKED |
| Kappatou 2016/2017 coreless 来源族 | 4 | 2 | 2 | 2 | 3 | 2 | 4 | 2 | 3 | 5 | 29 | BLOCKED |

旧四来源评分是本阶段对既有证据的排序性复核，不改变 Phase 7F 记录和 gate 结论。

## 4. 既有四来源定向复核

| 来源 | 本轮检索范围 | 恢复结果 | 仍然主导的缺项 |
|---|---|---|---|
| Price 2009 | 主论文、引用链、同作者/机构线索、原型图表 | Phase 7F 已恢复 6 极对、108 有效串联匝/相、Y 接和径向磁体宽度；本轮未找到同机来源给出的数值 `Br`、`mur` 或来源等价 `kw` | `Br`、`mur`、`kw` |
| Parviainen 2005 | 博士论文原型章节、公式章节、表格与绕组说明 | 未发现把原型线圈跨度闭合为数值 `kw` 的补充表；未用通用分布绕组因子替代 | 原型等价 `kw`，以及其余既有 gate 缺项 |
| Hosseini 2008 | 全文、表格、绕组图、变量定义 | “50 conductors per coil”仍不能安全等同于匝数；相内串并联、Y/Delta、数值 `kw` 未恢复 | 匝数语义、相网络、相连接、`kw` |
| Abdelli 2026 | 开放全文、设计表、原型制造段、图注 | 设计 27 匝与原型 48 匝差异继续分开；定子间连接和相连接未找到明确说明 | 有效相串联匝数、定子连接、相连接、`kw` |

Price 2009 是本轮既有来源的最高优先级，但检索没有合法恢复其三项关键缺值。结论为“证据仍缺失”，而不是用 NdFeB 通用属性或集中绕组经验值填入。

## 5. 新来源证据

### 5.1 Ferreira/IPB 2007 DSSR 来源族

同一机器身份由重复的 DSSR 拓扑、65/90 mm 半径、N30SH 磁体、24 匝/线圈、每定子 60 线圈和 600 rpm 原型参数闭合。机构库全文给出两定子串联、Y 接、600 rpm 下相对中性点 80.6 V RMS 的实验值；相关海报给出 `Br=1.12 T`。来源同时报告显著三次谐波，因此该 80.6 V 是总 RMS，不能与当前基波 RMS 求解器直接比较。[IPB 论文](https://bibliotecadigital.ipb.pt/bitstreams/c12b3d6d-93c0-4078-8c4b-5b8ce84c1281/download)、[同机资料](https://bibliotecadigital.ipb.pt/bitstreams/30bba33f-d119-4caa-8f1b-604f3d919dd3/download)、[同机海报](https://bibliotecadigital.ipb.pt/bitstreams/4189f3ec-c4a0-4e2a-a88e-fff6270288d0/content)

现有 gate 缺项：

1. `geometry.effective_nonmagnetic_gap_m`
2. `geometry.magnet_coverage`
3. `winding_network.effective_series_turns_per_phase`
4. `winding_network.winding_factor`

首个缺项为有效非磁性气隙。来源只给物理气隙；不得把 slotted-machine 的物理间隙直接改名为有效间隙。磁体为商用圆柱体，来源的 0.617 只在平均半径定义，不能代表整个径向区间。

### 5.2 Mahmoudi 2013 slotted TORUS

该 1 kW、4 极、30 槽原型的几何、18 匝/线圈、180 匝/相、Y 接、`Br=1.3 T` 与 1500/750 rpm 实测反电势均较清晰。1500 rpm 实测为 52.0 V phase RMS，THD 2.6%。[IET 原始论文页面](https://ietresearch.onlinelibrary.wiley.com/doi/10.1049/iet-epa.2012.0377)

现有 gate 缺项：

1. `geometry.effective_nonmagnetic_gap_m`
2. `geometry.magnet_coverage`
3. `material.magnet_relative_permeability`
4. `winding_network.winding_factor`

来源的 118 度标签未被强行解释为当前求解器的局部磁体覆盖率，磁体 `mur` 也未用通用 NdFeB 数值补齐。

### 5.3 Huang 2016 concentrated AFPM

开放论文给出 SSDR、6 极/9 槽、45/70 mm 半径、3 mm 气隙、`Br=1.03 T` 和实验反电势系数，但未闭合磁体厚度、覆盖率、绕组匝数/因子及该系数的完整比较语义。[MDPI 原始论文](https://www.mdpi.com/1996-1073/9/11/892)

gate 缺项共 8 项：有效气隙、磁体厚度、磁体覆盖、`mur`、有效串联匝数、绕组因子、反电势语义和外部标量参考。

### 5.4 Kappatou 2016/2017 coreless 来源族

该来源族有设计与原型测试价值，但本轮没有恢复出足以证明同一运行点并完整投影到 gate 的标量集合。为避免从相关设计或图形中误拼字段，证据包保守保留大量 `unavailable`。[设计论文](https://www.scirp.org/pdf/JEMAA_2016111615243457.pdf)、[实验论文](https://www.mdpi.com/1996-1073/10/9/1269)

## 6. 字段可用性摘要

| 候选 | 磁体材料 | 绕组因子 | 外部反电势 |
|---|---|---|---|
| Ferreira/IPB | `Br`、来源模型 `mur` 可用 | 不可用 | 80.6 V phase-neutral total RMS 可用，但含显著三次谐波 |
| Mahmoudi | `Br` 可用，`mur` 不可用 | 不可用 | 52.0 V phase RMS、THD 2.6% 可用 |
| Huang | `Br` 可用，`mur` 只有定性描述 | 不可用 | 系数存在，但当前标量语义未闭合 |
| Kappatou | 本轮未锁定完整数值 | 不可用 | 有实验波形证据，但本轮未恢复语义闭合标量 |
| Price | 数值 `Br`、`mur` 不可用 | 不可用 | 相峰值参考可用 |
| Parviainen | 部分材料可用 | 原型等价 `kw` 歧义 | 相 RMS 参考可用 |
| Hosseini | 部分材料可用 | 不可用 | source-native waveform 可用 |
| Abdelli | 部分材料可用 | 不可用 | 图形/数值语义未完全闭合 |

非正弦来源未因转换不安全而从候选池删除；它们保留 `arbitrary`/source-native 语义，供未来谐波路径评估，但 Phase 7G 不新增谐波求解器。

## 7. 其他调查对象

除 8 个正式评分候选外，还筛查了：Yazdi 2020 coreless AFPM、Gulec 2014 slotted AFPM、2014 Halbach ironless AFPM、2025 ironless sizing/experimental paper，以及 OpenAFPM/公开 FEA 示例入口。它们在本轮未形成比前四个新候选更完整的 gate 输入包：有的只给实验波形而缺少完整机器输入，有的给设计工具而无独立实验参考，有的关键全文字段尚不能合法、可复现地恢复。[OpenAFPM 项目](https://rurerg.net/open-source-platform/software/openafpm/)

## 8. 证据包与可复现 gate

新增来源包：

- `validation_data/source_recovery/phase7g_ferreira_2007_ipb_family.json`
- `validation_data/source_recovery/phase7g_mahmoudi_2013_torus.json`
- `validation_data/source_recovery/phase7g_huang_2016_eccentricity.json`
- `validation_data/source_recovery/phase7g_kappatou_2017_coreless.json`

每个值包含 `status`、`value`、`unit`、来源 URL、publication、page、table、figure、equation、位置和说明。来源未给出的 table/figure/equation 以显式 `null` 保存；`safely_derived` 额外要求推导式；`unavailable` 与 `ambiguous` 必须保持 `null`。

验证侧模块 `benchmark_evidence.py` 只执行两项工作：无默认替换地投影为不可变 `AdvancedAFPMCase`，并调用未修改的 `AFPMCompletenessGate`。评分不参与 gate。

## 9. 第一个模型误差

未观察到合法的 Advanced AFPM 外部模型误差。所有候选均在求解前被 gate 阻断，因此不存在 predicted/reference、绝对误差或相对误差。把未运行模型写成“0% 误差”是不成立的。

## 10. 决策

1. 是否有 AFPM benchmark 变为 READY：**否**。
2. 是否获得首个合法 AFPM 电磁外部比较：**否**。
3. 外部误差：**不存在可报告误差**，因为 gate 在求解前阻断全部候选。
4. 主导缺项：有效非磁性气隙、可表示整个半径的磁体覆盖、来源等价 `kw`/完整相串联网络；部分来源还缺 `mur` 或基波语义闭合参考。
5. 下一步选择：优先 **D. additional benchmark acquisition**，定向索取 Ferreira/IPB 或 Mahmoudi 同机补充资料；若无法获得，再选择 **E. controlled FEA benchmark generation**，并严格标记 `FEA_REFERENCE`。当前证据不足以优先进入 A、B 或 C。

## 11. 后续获取清单

不建议进入模型修正或校准。下一步应针对 Ferreira/IPB 或 Mahmoudi 原型获取以下一手补充材料：

- 明确的有效气隙/Carter 修正定义，或足够的槽几何以在独立验证层计算它；
- 可映射到整个有效半径的磁体几何；
- 完整相绕组网络与来源等价的基波 `kw`；
- 对 Ferreira/IPB，基波 RMS 的测量/FFT 分量，而不是仅有含三次谐波的总 RMS；
- 对 Mahmoudi，来源采用的磁体回线相对磁导率。

在这些字段恢复之前，`BLOCKED` 是证据上正确的结果。
