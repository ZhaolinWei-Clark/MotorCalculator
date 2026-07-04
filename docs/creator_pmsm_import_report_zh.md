# CREATOR PMSM 导入报告

更新时间：2026-07-04

## 1. CREATOR PMSM 来源

- 数据集：`CREATOR Case: Permanent Magnet Synchronous Motor Data`
- DOI：`10.3217/sns1d-77m43`
- 仓库页：`https://repository.tugraz.at/records/sns1d-77m43`
- 发布机构：`Graz University of Technology`
- 创建者：
  - `Pawan Kumar Dhakal`
  - `Kourosh Heidarikani`
  - `Annette Muetze`
  - `Roland Seebacher`
- 发布日期：`2024-11-04`
- 当前访问日期：`2026-07-04`
- 已核验许可：`CC BY-NC 4.0`

配套论文：

- `CREATOR Case: PMSM and IM Electric Machine Data for Validation and Benchmarking of Simulation and Modeling Approaches`
- arXiv：`2501.15921`
- 相关 DOI：`10.1108/COMPEL-11-2024-0462`
- 论文年份：`2025`

## 2. 为什么它适合作为首条 validation source

- 它是当前 Phase 4B 侦察结果中最强的公开 PMSM 候选之一。
- 数据集同时具备设计参数和实验测量结果。
- 来源级元数据完整，含 DOI、发布机构、创建者、许可和文件清单。
- 配套论文可作为字段导航和验证边界说明。

## 3. 它的数据类型

从当前可追溯信息看，它属于：

- `PMSM` 数据源
- 公开发布的数据集
- 含实验测量结果的 published benchmark 候选

本轮没有把它直接定格为正式 `bench_measurement` record，原因是仓库是“成套发布的数据包”，而不是一条孤立的原始 bench log 文件。

## 4. 字段完整度

来源级完整度已经确认较高：

- 设计参数：已确认存在
- 实验结果：已确认存在
- 材料数据：已确认存在
- 绕组数据：已确认存在
- 几何数据：已确认存在
- 低频等效参数：已确认存在
- drive-cycle 测量结果：已确认存在

字段级完整度当前仍不足：

- 本轮没有逐字段抽取数值
- 本轮没有为数值字段建立 table/page/section 级引用
- 本轮没有确认 topology、control semantics、phase/line、RMS/peak、current_basis

## 5. 与本项目 schema 的映射

本轮已经建立：

- `validation_data/source_notes/creator_pmsm/field_mapping_draft_zh.md`

映射状态分为：

- `needs_manual_extraction`
- `needs_semantics_check`
- `needs_unit_conversion`
- `unavailable`

这些扩展状态只用于 draft 和 source note，不直接写入正式 Phase 4A loader schema。

## 6. 已成功导入的字段

本轮“已成功导入”的含义仅限于来源元数据，不包括正式 validation numeric record。

已核验并落盘的来源元数据包括：

- 标题
- DOI
- 仓库 URL
- 发布机构
- 创建者
- 发布日期
- 访问日期
- 许可类型
- 文件清单与文件大小
- 数据类别存在性说明

## 7. 未导入字段

本轮没有导入正式 numeric expected fields，因此以下字段仍未正式导入：

- `pole_pairs`
- `rated_speed_rpm`
- `rated_power_w`
- `dc_bus_voltage_v`
- `phase_current_a`
- `line_current_a`
- `winding_connection`
- `back_emf_waveform`
- `stator_outer_diameter_m`
- `stator_inner_diameter_m`
- `rotor_outer_diameter_m`
- `rotor_inner_diameter_m`
- `air_gap_m`
- `magnet_thickness_m`
- `magnet_width_m`
- `magnet_grade`
- `magnet_remanence_t`
- `turns_per_phase`
- `winding_factor`
- `phase_resistance_ohm`
- `phase_inductance_h`
- `back_emf_phase_peak_v`
- `back_emf_phase_rms_v`
- `back_emf_line_rms_v`
- `back_emf_constant_line_rms_v_per_krpm`
- `torque_nm`
- `torque_constant_nm_per_a`
- `copper_loss_w`
- `iron_loss_w`
- `mechanical_loss_w`
- `efficiency`
- `required_voltage_v`
- `temperature`

## 8. 需要人工核验字段

优先需要人工核验：

1. `topology`
2. `control_mode`
3. `winding_connection`
4. `phase/line` 语义
5. `RMS/peak` 语义
6. `current_basis`
7. 至少一个数值输出字段的表/页/节定位

## 9. 可比较指标

本轮结论是：

- `直接可比较字段：暂无`

原因不是数据源无效，而是当前没有完成字段级抽取与语义核验。

## 10. 不可比较指标

当前必须禁止直接比较的类别包括：

- `PMSM` vs `BLDC`
- 未确认拓扑时的 `AFPM` vs 非 AFPM
- `phase` vs `line`
- `RMS` vs `peak`
- 不同 `current_basis`
- 未确认字段定义的等效参数
- `required_voltage_v`
- 未核验到的 `temperature`

## 11. 初步结果

本轮没有生成正式 comparison report。

已生成：

- `validation_data/reports/creator_pmsm_import_blockers_zh.md`

结论：

- 当前仅适合创建 draft
- 当前不适合创建正式 imported validation record

## 12. 是否可用于准确度声明

当前不能。

可以声明的是：

- 已找到一个高价值、真实、可追溯的 PMSM 外部数据源
- 已完成来源级核验和首轮映射准备

不能声明的是：

- 本项目已获得真实准确度验证
- revised PMSM 已经被这条来源正式验证
- BLDC 已被该来源验证
- AFPM 默认拓扑已被该来源验证

## 13. 为什么不能外推到 BLDC / AFPM

- 数据源机型是 `PMSM`，不是 `BLDC`。
- 当前未核验其拓扑是否与本项目默认 `AFPM` 一致。
- 即使该来源后续能够形成正式 PMSM record，也只能说明“在特定 PMSM 语义和特定来源条件下”的有限 comparability，不能外推到 `BLDC` 或 `AFPM`。

## 14. 下一步需要用户提供什么

若要继续从 draft 升级到正式 record，至少需要你批准或手动提供：

1. `CREATOR_Machine_Data_2024-11-04.pdf`（仓库页标示 `2.1 MB`）
2. `PM_synchronous_motor.zip`（仓库页标示 `12.6 MB`）

拿到后我会继续：

1. 提取 topology / control semantics / winding_connection
2. 提取至少一个可直接比较的数值指标
3. 建立正式 `validation_data/imported/creator_pmsm_initial_record.json`
4. 再运行 loader 和 comparison engine
