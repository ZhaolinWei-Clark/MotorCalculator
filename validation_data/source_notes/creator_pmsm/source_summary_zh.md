# CREATOR PMSM 数据源摘要

更新时间：2026-07-04

## 1. 数据源介绍

本轮 Phase 4C 选择的首条真实外部 validation source 候选是：

- 数据集标题：`CREATOR Case: Permanent Magnet Synchronous Motor Data`
- 数据集 DOI：`10.3217/sns1d-77m43`
- 数据集仓库页：`https://repository.tugraz.at/records/sns1d-77m43`
- 数据集发布方：`Graz University of Technology`
- 数据集创建者：
  - `Pawan Kumar Dhakal`
  - `Kourosh Heidarikani`
  - `Annette Muetze`
  - `Roland Seebacher`
- 已核验的关联机构：
  - `Graz University of Technology`
  - `Electric Drives and Power Electronic Systems Institute (EALS), TU Graz`
- 数据集发布时间：`2024-11-04`
- 当前访问日期：`2026-07-04`

已核验的配套论文信息：

- 标题：`CREATOR Case: PMSM and IM Electric Machine Data for Validation and Benchmarking of Simulation and Modeling Approaches`
- 作者：
  - `Annette Mütze`
  - `Kourosh Heidarikani`
  - `Pawan Kumar Dhakal`
  - `Roland Seebacher`
  - `Sebastian Schöps`
- arXiv：`2501.15921`
- 关联 DOI：`10.1108/COMPEL-11-2024-0462`
- 论文年份：`2025`

## 2. 为什么选择它作为第一条真实 validation source

- 这是当前已侦察来源里最完整、最可追溯、最接近“真实外部 validation record”的公开 PMSM 数据集。
- 仓库页已明确给出持久化 DOI、发布机构、创建者、许可信息和文件清单。
- 配套论文和仓库描述都明确说明该数据集同时包含设计参数和实验测量结果。
- 该来源是 `PMSM`，与当前项目的 `PMSM` 路径有直接相关性，但并不自动等价于本项目默认拓扑或默认控制语义。

## 3. 已核验的文件清单

以下文件已通过仓库页文件列表核验，但本轮未下载到仓库：

| 文件名 | 大小 | 格式 | 预期用途 | 本轮是否下载 |
|---|---:|---|---|---|
| `README.md` | `892 B` | Markdown | 快速说明、许可提示、ZIP 内容概览 | 否 |
| `CREATOR_Machine_Data_2024-11-04.pdf` | `2.1 MB` | PDF | 数据包用户手册/字段导航 | 否 |
| `PM_synchronous_motor.zip` | `12.6 MB` | ZIP | PMSM 主数据包，预计包含设计参数与测量结果 | 否 |

说明：

- 本轮没有下载 `PDF` 或 `ZIP`，因为你已要求不要直接下载较大原始文件，且尚未对这两个文件的本地保存做单独批准。
- `README.md` 虽然较小，但本轮也未写入仓库，只通过仓库预览页进行人工核验。

## 4. 已核验的数据能力

以下能力已经从仓库描述、README 预览和配套论文摘要/正文说明中被核验为“存在于数据包中”：

- 包含设计参数：`是`
- 包含实验结果：`是`
- 包含材料数据：`是`
- 包含绕组数据：`是`
- 包含几何数据：`是`
- 包含低频等效参数：`是`
- 包含 drive-cycle 测量结果：`是`

这些结论仅表示“来源宣称并说明这些类别存在”，不表示本轮已经完成逐字段抽取。

## 5. 它能验证哪些指标

在完成 ZIP/PDF 的人工抽取与字段语义核验后，它有潜力验证：

- `PMSM` 路径下的部分反电势相关量
- `PMSM` 路径下的部分转矩相关量
- 低频等效参数对应的部分 `phase_resistance_ohm` / `phase_inductance_h`
- 部分稳态和 drive-cycle 下的 `torque_nm`
- 部分 `copper_loss_w` / `iron_loss_w` / `mechanical_loss_w` / `efficiency`

前提是：

- 字段必须能定位到具体文件和具体表/页/节；
- `phase/line`、`RMS/peak`、`current_basis`、`control_mode`、`topology` 等语义必须明确；
- 只能比较 `directly_comparable` 字段。

## 6. 它不能验证哪些指标

当前这份来源本身不能直接证明：

- 本项目全部模型都已被验证
- 本项目 `BLDC` 路径已被验证
- 本项目 `AFPM` 拓扑已被验证
- `required_voltage_v` 已被真实外部数据验证
- 损耗、电感、槽满率、退磁、温升模型已经获得充分 external validation
- revised 结果应自动替换 legacy 默认链路

## 7. 与当前项目 PMSM / BLDC / AFPM 模型的关系

- 它是 `PMSM` 数据源，不是 `BLDC` 数据源。
- 它当前只能作为 `PMSM` validation 候选，不能外推到 `BLDC revised Ke/Kt`。
- 现阶段尚未从原始文件中确认其拓扑是否与本项目默认 `双转子、单定子、双气隙 AFPM` 一致，因此不能把它自动视为 `AFPM` benchmark。
- 在拓扑未核验前，它更安全地应被视为“PMSM 外部数据源候选”，而不是“本项目 AFPM 默认拓扑的直接 benchmark”。

## 8. 需要人工核验的关键字段

以下关键信息尚未在本轮从原始文件逐项抽取，因此必须标记为待人工核验：

- `control_mode` 是否可安全落为 `PMSM_SINUSOIDAL`
- `topology` 的原文定义
- 具体的 `pole_pairs`
- 额定参数表中的速度、电压、电流、功率
- 低频等效参数表中的相电阻、相电感或等效参数定义
- 反电势量的 `phase/line` 与 `RMS/peak` 语义
- `torque_constant_nm_per_a` 所使用的 `current_basis`
- 各类损耗数据在源文件中的具体字段名和单位

## 9. 授权和引用注意事项

- 仓库页与 README 预览均显示许可为 `CC BY-NC 4.0`。
- 这意味着本轮只能记录为“已核验为非商业 Creative Commons 许可”，不能写成“可商业自由使用”。
- 当前浏览到的仓库 HTML 没有直接展开一条现成的格式化 citation 文本，因此以下数据集引用只能记为“基于仓库元数据整理的工作用 citation 草案”，不能伪装成仓库导出的正式引文：

```text
Dhakal, Pawan Kumar; Heidarikani, Kourosh; Muetze, Annette; Seebacher, Roland.
CREATOR Case: Permanent Magnet Synchronous Motor Data.
Graz University of Technology, published 2024-11-04.
DOI: 10.3217/sns1d-77m43.
```

- 配套论文可作为来源说明和字段导航参考，但不能替代对 ZIP/PDF 原始数据文件的字段级核验。

## 10. 不得外推的边界

- 不得把该数据源写成 `BLDC` 数据。
- 不得把该数据源写成 `AFPM` benchmark，除非原始文件明确给出并完成核验。
- 不得把该数据源的局部一致性扩展为“本项目全部模型准确”。
- 不得把该数据源用于自动校准公式、系数或默认值。
- 不得据此修改 production calculation chain。
