# CREATOR PMSM 字段映射草案

更新时间：2026-07-04

## 1. 说明

本文件记录 CREATOR PMSM 到 Phase 4A schema 的字段级人工映射结果。

状态值含义：

- `provided`：源文件直接给出，可正式进入 imported record
- `inferred`：可由源文件内明确字段安全推得
- `unavailable`：本阶段不安全或无直接字段，不进入正式值
- `not_applicable`：当前 schema 或当前记录不适用
- `needs_manual_extraction`：来源存在，但本轮未继续细化
- `needs_unit_conversion`：来源存在，但若导入需显式换算
- `needs_semantics_check`：字段定义与当前 schema 可能不完全同义
- `license_restricted`：许可允许查看，但不适合原样入库

注意：正式 Phase 4A record 只接受 `provided / inferred / unavailable / not_applicable`。扩展状态只用于 source note。

## 2. 输入参数映射

| 项目字段 | 状态 | 值/说明 | source file / table / page / section | 备注 |
|---|---|---|---|---|
| `pole_pairs` | `inferred` | `2` | `Geometry_parameters_PMSM.csv`; PDF Table 12 / Appendix B | 由 `No. of poles = 4` 推得 |
| `rated_speed_rpm` | `provided` | `2000 rpm` | `PMSM_general_specification.csv`; PDF Table 6 | 正式导入 |
| `rated_power_w` | `unavailable` | `null` | `Electrical_properties_of_PMSM.csv`; PDF Table 8 | 仅见 `Maximum power = 70 W`、`Optimum power = 7 W`，没有严格同义 `rated_power_w` |
| `dc_bus_voltage_v` | `provided` | `326 V` | `Electrical_properties_of_PMSM.csv`; PDF Table 8 | 原字段是 `Maximum dc-link voltage` |
| `phase_current_a` | `provided` | `0.21 A rms` | `Electrical_properties_of_PMSM.csv`; PDF Table 8 | 作为 `phase_rms` 导入 |
| `line_current_a` | `unavailable` | `null` | 未见直接字段 | 不用 `phase_current_a` 代填 |
| `winding_connection` | `provided` | `Y` | `Electrical_properties_of_PMSM.csv`; PDF Table 8 | 正式导入 |
| `back_emf_waveform` | `provided` | `sinusoidal` | PDF Fig. 14, Table 10, Appendix B PMSM ECM, PMSM control description | 按 PMSM 正弦语义导入，但不放宽 topology 边界 |
| `stator_outer_diameter_m` | `provided` | `0.113 m` | `Geometry_parameters_PMSM.csv`; PDF Table 12 | 由 `113 mm` 显式换算 |
| `stator_inner_diameter_m` | `provided` | `0.0478 m` | `Geometry_parameters_PMSM.csv`; PDF Table 12 | 由 `47.8 mm` 显式换算 |
| `rotor_outer_diameter_m` | `provided` | `0.047 m` | `Geometry_parameters_PMSM.csv`; PDF Table 12 | 当前 formal loader 不接收，保留在 note 中 |
| `rotor_inner_diameter_m` | `unavailable` | `null` | 未见直接字段 | 不猜测 |
| `air_gap_m` | `provided` | `0.0004 m` | `Geometry_parameters_PMSM.csv`; PDF Table 12 | 原字段为 `Air-gap length (radial direction)` |
| `magnet_thickness_m` | `provided` | `0.00435 m` | `Geometry_parameters_PMSM.csv`; PDF Table 12 | 原字段为 `Magnet length (radial direction)`，已在 notes 保留原语义 |
| `magnet_width_m` | `needs_semantics_check` | `Magnet height = 17.599 mm` | `Geometry_parameters_PMSM.csv`; PDF Table 12 | 当前不把 `Magnet height` 直接写成 schema 的 `magnet_width_m` |
| `magnet_grade` | `unavailable` | `null` | `Motor_parts_material.csv`; PDF Table 7 | 只确认到 `Sintered ferrite`，未见明确 grade |
| `magnet_remanence_t` | `provided` | `0.41 T` | `Ferrite_properties.csv`; `Motor_parts_material.csv`; PDF Table 7 | 20 deg C remanence |
| `turns_per_phase` | `unavailable` | `null` | `Winding_properties_of_PMSM.csv`; PDF Table 9 | 只给 `No. of turns per slot = 328` |
| `winding_factor` | `unavailable` | `null` | 未见直接字段 | 不推算 |
| `phase_resistance_ohm` | `provided` | `8.9462 ohm` | `Equivalent_circuit_parameters_PMSM.csv`; PDF Table 10 | 作为 expected output 导入 |
| `phase_inductance_h` | `needs_semantics_check` | `Ld = 0.2055 H`, `Lq = 0.332 H` | `Equivalent_circuit_parameters_PMSM.csv`; PDF Table 10; Section 6.2.2 | 本轮不收敛成单一 schema 字段 |

## 3. 输出字段映射

| 项目字段 | 状态 | 值/说明 | source file / table / page / section | 备注 |
|---|---|---|---|---|
| `back_emf_phase_peak_v` | `provided` | `47.37 V peak` | `Equivalent_circuit_parameters_PMSM.csv`; PDF Table 10; PDF Fig. 14 text | 正式导入 |
| `back_emf_phase_rms_v` | `unavailable` | `null` | 未见直接字段 | 不从 phase-peak 自动换算 |
| `back_emf_line_rms_v` | `unavailable` | `null` | 未见直接字段 | 不从 phase-peak 自动换算 |
| `back_emf_constant_line_rms_v_per_krpm` | `unavailable` | `null` | 未见直接字段 | 不自动推导 |
| `torque_nm` | `provided` | `0.1 Nm` | `PMSM_general_specification.csv`; PDF Table 6 | 作为 `rated_torque_nm` 导入 |
| `torque_constant_nm_per_a` | `unavailable` | `null` | 未见直接字段 | current basis 未形成正式可比字段 |
| `copper_loss_w` | `unavailable` | `null` | drive-cycle / no-load 文件存在 | 本轮未绑定具体工况点 |
| `iron_loss_w` | `unavailable` | `null` | drive-cycle / no-load 文件存在 | 本轮未绑定具体工况点 |
| `mechanical_loss_w` | `unavailable` | `null` | drive-cycle / no-load 文件存在 | 本轮未绑定具体工况点 |
| `efficiency` | `unavailable` | `null` | drive-cycle power 文件存在 | 本轮未绑定具体工况点 |
| `required_voltage_v` | `unavailable` | `null` | 未见直接同义字段 | 项目该量仍是 legacy/provisional |
| `temperature` | `unavailable` | `null` | 未在本轮正式映射中导入 | 不猜测 |

## 4. 正式 imported record 已落盘字段

正式 record 路径：

- `validation_data/imported/creator_pmsm_initial_record.json`

本轮正式导入字段包括：

- 输入：
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
- 输出：
  - `rated_torque_nm`
  - `back_emf_phase_peak_v`
  - `phase_resistance_ohm`
  - `rated_current_a`

## 5. 需要保持边界的字段

以下项目即使源中存在相关信息，本轮也没有越界导入：

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

## 6. Comparability 结论

- 该 record 的 `motor_type` 为 `PMSM`，不能直接用于 `BLDC` 验证。
- 该 record 描述的是径向 PMSM 来源，不是当前项目默认 `AFPM` 拓扑。
- 因此 comparison engine 运行后，已导入的可比较量会被 topology gate 拦截，不形成准确度声明。
