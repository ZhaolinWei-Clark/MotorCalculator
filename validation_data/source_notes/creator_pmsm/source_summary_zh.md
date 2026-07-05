# CREATOR PMSM 数据源摘要

更新时间：2026-07-04

## 1. 数据源介绍

- 数据集标题：`CREATOR Case: Permanent Magnet Synchronous Motor Data`
- 机构：`Graz University of Technology`
- 作者：`Pawan Kumar Dhakal`、`Kourosh Heidarikani`、`Annette Muetze`、`Roland Seebacher`
- 仓库页：`https://repository.tugraz.at/records/sns1d-77m43`
- DOI：`10.3217/sns1d-77m43`
- 发布日期：`2024-11-04`
- 访问日期：`2026-07-04`
- 配套论文：`CREATOR Case: PMSM and IM Electric Machine Data for Validation and Benchmarking of Simulation and Modeling Approaches`
- 配套论文 DOI：`10.1108/COMPEL-11-2024-0462`

本轮已实际下载并人工审阅：

- `README.md`，`892 B`
- `CREATOR_Machine_Data_2024-11-04.pdf`，`2,088,845 B`
- `PM_synchronous_motor.zip`，`12,555,471 B`

下载文件保存在临时目录中用于字段级人工抽取，没有写入 Git 仓库。

## 2. 为什么选择它作为第一条真实 validation source

- 它是公开可追溯的数据集，具备 DOI、作者、机构、文件清单和明确许可说明。
- 它同时提供设计参数、材料、绕组、几何、低频等效参数和实验测量结果。
- 对 Phase 4C 来说，它足够完整，可以先建立一条真实 imported record，同时仍然保留项目现有 comparability 红线。

## 3. 它能验证哪些指标

本轮正式导入并保持可追溯的字段主要集中在：

- 输入侧：
  - `pole_pairs`
  - `rated_speed_rpm`
  - `dc_bus_voltage_v`
  - `phase_current_a`
  - `winding_connection`
  - `back_emf_waveform`
  - `stator_outer_diameter_m`
  - `stator_inner_diameter_m`
  - `air_gap_m`
  - `magnet_thickness_m`
  - `magnet_remanence_t`
- 输出侧：
  - `rated_torque_nm`
  - `back_emf_phase_peak_v`
  - `phase_resistance_ohm`
  - `rated_current_a`

这些字段足够支持：

- 正式 Phase 4A schema 导入
- loader 校验
- comparison engine 运行
- 在 comparability gate 下得到结构化 exclusion / mismatch 结果

## 4. 它不能验证哪些指标

本轮没有把以下字段写成正式可比较值：

- `rated_power_w`
- `turns_per_phase`
- `winding_factor`
- `phase_inductance_h`
- `back_emf_line_rms_v`
- `back_emf_constant_line_rms_v_per_krpm`
- `torque_constant_nm_per_a`
- `copper_loss_w`
- `iron_loss_w`
- `mechanical_loss_w`
- `efficiency`
- `required_voltage_v`

原因包括：

- 源文件没有直接给出该字段
- 该字段需要额外推导而本阶段禁止自动扩展推导
- 字段语义与当前 schema 不完全一致
- 对应量仍处于项目 legacy/provisional 范围

## 5. 它与当前项目 PMSM / BLDC / AFPM 模型的关系

- 这是一条 `PMSM` 记录，不是 `BLDC` 记录。
- 这是一台径向 PMSM 来源，而当前项目默认拓扑是 `双转子、单定子、双气隙` 的 `AFPM`。
- 因此，它适合作为“真实外部 record 已导入”的第一步，不适合作为当前 AFPM 默认拓扑的直接准确度声明。

## 6. 需要人工核验的字段

本轮仍需继续人工核验或后续单独导入的内容包括：

- `rated_power_w` 是否能从源中找到严格等价定义
- `turns_per_phase` 是否能安全从 turns-per-slot 推到 schema 字段
- `phase_inductance_h` 是否允许从 `Ld/Lq` 收敛到单一相电感字段
- drive-cycle 下的损耗/效率字段应绑定哪个具体工况点

## 7. 授权和引用注意事项

- 仓库页和 README 都写明 `CC BY-NC 4.0`。
- 这意味着当前只能按“非商业再利用受限”来记录，不能写成“可商业自由使用”。
- record 中只引用真实元数据、真实文件名、真实表格和真实字段；没有伪造 citation 或 license。

## 8. 不得外推的边界

- 不得把这条 `PMSM` record 外推到 `BLDC revised Ke/Kt`。
- 不得把这条径向 PMSM record 外推成项目默认 `AFPM` benchmark。
- 不得据此修改任何 production 公式、默认值、`legacy_baseline.json` 或 analytical fixtures。
- 不得把“成功导入真实 record”表述成“项目整体准确度已被真实实验验证”。
