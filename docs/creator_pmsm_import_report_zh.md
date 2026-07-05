# CREATOR PMSM 导入报告

更新时间：2026-07-04

## 1. CREATOR PMSM 来源

- 数据集：`CREATOR Case: Permanent Magnet Synchronous Motor Data`
- DOI：`10.3217/sns1d-77m43`
- 仓库页：`https://repository.tugraz.at/records/sns1d-77m43`
- 机构：`Graz University of Technology`
- 作者：`Pawan Kumar Dhakal`、`Kourosh Heidarikani`、`Annette Muetze`、`Roland Seebacher`
- 数据发布日期：`2024-11-04`
- 访问日期：`2026-07-04`
- 许可：`CC BY-NC 4.0`

本轮已下载并人工审阅：

- `README.md`，`892 B`
- `CREATOR_Machine_Data_2024-11-04.pdf`，`2,088,845 B`
- `PM_synchronous_motor.zip`，`12,555,471 B`

原始文件保留在临时目录中，没有提交进 Git。

## 2. 为什么它适合作为首条 validation source

- 元数据完整，可追溯到 DOI、仓库、作者、机构和许可。
- 既有设计参数，也有实验结果和等效参数。
- 能够验证 Phase 4A 的 imported record、loader、comparability gate 和 no-overclaim 约束是否能在真实外部来源上工作。

## 3. 它的数据类型

本轮按以下方式记录：

- `source_type = published_benchmark`
- `evidence_level = LEVEL_2_PUBLISHED_OR_FEA`
- `motor_type = PMSM`

之所以不把它直接写成 `bench_measurement`，是因为这次导入的是“公开发布的数据包中的首条结构化记录”，而不是单一原始 bench log 文件。

## 4. 字段完整度

本轮正式导入了足够创建真实 imported record 的字段，但没有强行覆盖所有 schema 字段。

已正式导入的输入字段：

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

已正式导入的输出字段：

- `rated_torque_nm`
- `back_emf_phase_peak_v`
- `phase_resistance_ohm`
- `rated_current_a`

## 5. 与本项目 schema 的映射

正式 record：

- `validation_data/imported/creator_pmsm_initial_record.json`

字段映射草案：

- `validation_data/source_notes/creator_pmsm/field_mapping_draft_zh.md`

本轮采用的策略是：

- 能直接引用的字段写成 `provided`
- 可由同一来源内明确字段安全推出的写成 `inferred`
- 不能安全映射的保持 `unavailable`
- 不把 `0` 用作未知值

## 6. 已成功导入字段

关键已导入值包括：

- `pole_pairs = 2`，由 `No. of poles = 4` 推得
- `rated_speed_rpm = 2000`
- `dc_bus_voltage_v = 326`
- `phase_current_a = 0.21 A rms`
- `winding_connection = Y`
- `back_emf_waveform = sinusoidal`
- `stator_outer_diameter_m = 0.113`
- `stator_inner_diameter_m = 0.0478`
- `air_gap_m = 0.0004`
- `magnet_thickness_m = 0.00435`
- `magnet_remanence_t = 0.41`
- `rated_torque_nm = 0.1`
- `back_emf_phase_peak_v = 47.37`
- `phase_resistance_ohm = 8.9462`
- `rated_current_a = 0.21`

## 7. 未导入字段

本轮明确未导入为正式值的字段包括：

- `rated_power_w`
- `turns_per_phase`
- `winding_factor`
- `phase_inductance_h`
- `back_emf_phase_rms_v`
- `back_emf_line_rms_v`
- `back_emf_constant_line_rms_v_per_krpm`
- `torque_constant_nm_per_a`
- `copper_loss_w`
- `iron_loss_w`
- `mechanical_loss_w`
- `efficiency`
- `required_voltage_v`
- `temperature`

## 8. 需要人工核验字段

后续仍需要继续人工核验：

- `rated_power_w` 与源中的 `maximum power` / `optimum power` 是否存在严格等义字段
- `turns_per_phase` 是否能从 `turns per slot` 安全映射
- `phase_inductance_h` 是否允许由 `Ld/Lq` 收敛
- drive-cycle / no-load 结果中应选哪个工况点作为损耗或效率记录

## 9. 可比较指标

本轮成功进入 comparison engine 的正式字段有：

- `rated_torque_nm`
- `back_emf_phase_peak_v`
- `phase_resistance_ohm`
- `rated_current_a`

但它们没有进入误差计算，而是在 comparability gate 下统一得到：

- `topology_mismatch`

## 10. 不可比较指标

本轮被明确排除或保持 unavailable 的字段包括：

- `phase_inductance_h`
- `back_emf_line_rms_v`
- `back_emf_constant_line_rms_v_per_krpm`
- `torque_constant_nm_per_a`
- `copper_loss_w`
- `iron_loss_w`
- `mechanical_loss_w`
- `efficiency`
- `required_voltage_v`

## 11. 初步 comparison 结果

比较报告：

- `validation_data/reports/creator_pmsm_initial_comparison_zh.md`

结论：

- formal record 已创建成功
- loader 已通过
- comparison engine 已运行成功
- 没有生成任何准确度误差数字
- 原因是 record 所描述的是径向 PMSM 来源，而当前项目默认模型拓扑仍是 `AFPM`

## 12. 是否可用于准确度声明

当前不可用于整体准确度声明。

本轮最多只能说明：

- 项目已经成功导入第一条真实外部 PMSM validation record
- Phase 4A 的 loader / comparability / no-overclaim 机制可以在真实来源上工作
- 当前 comparability gate 正在阻止不安全的 AFPM 直接误差声明

## 13. 为什么不能外推到 BLDC / AFPM

- 来源机型是 `PMSM`，不是 `BLDC`
- 来源机器是径向 PMSM，不是当前项目默认 `AFPM`
- 因此不能把这条 record 的存在解释成：
  - `BLDC revised` 已获验证
  - `AFPM default topology` 已获验证
  - 整个 production chain 已被真实 benchmark 证实

## 14. 下一步需要用户提供什么文件或确认什么字段

如果还要继续深挖同一来源，下一步建议用户批准的不是“再导入一条空泛记录”，而是对以下方向做取舍：

1. 是否继续从同一 ZIP 中选取一个具体工况点，导入损耗或效率字段
2. 是否接受 `Ld/Lq` 保持为 source note 层面的 d-q 参数，而不强压为单一 `phase_inductance_h`
3. 是否优先寻找与项目默认 `AFPM` 拓扑更接近的真实 benchmark，以便后续形成真正的直接误差比较
