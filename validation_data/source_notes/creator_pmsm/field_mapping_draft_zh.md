# CREATOR PMSM 字段映射草案

更新时间：2026-07-04

## 1. 说明

本文件是 `CREATOR PMSM` 到 Phase 4A schema 的首轮字段映射草案。

当前状态特点：

- 本轮只核验了仓库页、README 预览和配套论文的来源级信息。
- 本轮没有下载 `PM_synchronous_motor.zip` 或 `CREATOR_Machine_Data_2024-11-04.pdf`。
- 因此大部分数值字段只能标记为：
  - `needs_manual_extraction`
  - `needs_semantics_check`
  - `needs_unit_conversion`
  - `unavailable`

这些扩展状态只用于本草案和 draft JSON，不会写入正式 Phase 4A record 的 loader schema。

## 2. 来源级参考

- 仓库页：`https://repository.tugraz.at/records/sns1d-77m43`
- README 预览：仓库内 `README.md`
- 配套论文：`arXiv:2501.15921`
- 论文相关说明：
  - Section 6.1：PMSM design parameters
  - Section 6.2：PMSM measurement results
  - 论文正文说明存在：
    - geometry
    - material properties
    - electrical parameters
    - winding scheme
    - low-frequency equivalent parameters
    - drive-cycle measurement results

## 3. 输入参数映射草案

| 项目字段 | 状态 | 候选来源 | source file / table / section | 备注 |
|---|---|---|---|---|
| `pole_pairs` | `needs_manual_extraction` | 数据包内 PMSM 总参数表 | `PM_synchronous_motor.zip` / `CREATOR_Machine_Data_2024-11-04.pdf` / PMSM general parameters | 当前未逐表抽取 |
| `rated_speed_rpm` | `needs_manual_extraction` | 数据包内 PMSM 总参数表 | 同上 | 预计存在，但未摘录 |
| `rated_power_w` | `needs_manual_extraction` | 数据包内 PMSM 总参数表 | 同上 | 预计存在，但未摘录 |
| `dc_bus_voltage_v` | `needs_manual_extraction` | 数据包内 PMSM 电参数表 | `PM_synchronous_motor.zip` / `PDF` / PMSM electrical parameters | 不能根据 IM 章节推断 |
| `phase_current_a` | `needs_semantics_check` | 数据包电参数或实验结果表 | `ZIP` / `PDF` / PMSM electrical parameters or measurements | 必须确认 `phase/line` 与 `RMS/peak` |
| `line_current_a` | `needs_semantics_check` | 数据包电参数或实验结果表 | 同上 | 需和 `phase_current_a` 区分 |
| `winding_connection` | `needs_manual_extraction` | 数据包电参数表或绕组说明 | `ZIP` / `PDF` / PMSM electrical parameters / winding scheme | 不能假定为 Y |
| `back_emf_waveform` | `needs_semantics_check` | 配套论文 + 数据包说明 | `arXiv 2501.15921` / `ZIP` / `PDF` | `PMSM` 不等于自动确认本项目 `PMSM_SINUSOIDAL` 语义 |
| `stator_outer_diameter_m` | `needs_manual_extraction` | PMSM geometry | `ZIP` / `PDF` / PMSM geometry | 若原文为 mm，后续需显式换算 |
| `stator_inner_diameter_m` | `needs_manual_extraction` | PMSM geometry | 同上 | 同上 |
| `rotor_outer_diameter_m` | `needs_manual_extraction` | PMSM geometry | 同上 | 当前 schema 正式 record 尚不直接接收该输入字段，只能先写 draft |
| `rotor_inner_diameter_m` | `needs_manual_extraction` | PMSM geometry | 同上 | 同上 |
| `air_gap_m` | `needs_manual_extraction` | PMSM geometry | `ZIP` / `PDF` / PMSM geometry | 若原文为 mm，需显式换算 |
| `magnet_thickness_m` | `needs_manual_extraction` | PMSM material / geometry | `ZIP` / `PDF` / PMSM geometry / material | 需确认是否为轴向厚度定义 |
| `magnet_width_m` | `needs_manual_extraction` | PMSM geometry | `ZIP` / `PDF` / PMSM geometry | 当前正式 schema 尚不直接接收 |
| `magnet_grade` | `needs_manual_extraction` | PMSM material | `ZIP` / `PDF` / PMSM material | 需核对原文牌号 |
| `magnet_remanence_t` | `needs_manual_extraction` | PMSM material | `ZIP` / `PDF` / PMSM material | 若仅给牌号则可能要保持 unavailable |
| `turns_per_phase` | `needs_manual_extraction` | PMSM winding scheme | `ZIP` / `PDF` / PMSM winding scheme | 需确认每相还是每层 |
| `winding_factor` | `needs_manual_extraction` | PMSM winding scheme | 同上 | 若未直接给出，不得猜 |
| `phase_resistance_ohm` | `needs_manual_extraction` | measured low-frequency equivalent parameters | `ZIP` / `PDF` / PMSM equivalent parameters | 需确认是否为 phase resistance 与温度基准 |
| `phase_inductance_h` | `needs_semantics_check` | measured low-frequency equivalent parameters | 同上 | 需确认定义是否与项目字段一致 |

## 4. 输出字段映射草案

| 项目字段 | 状态 | 候选来源 | source file / table / section | 备注 |
|---|---|---|---|---|
| `back_emf_phase_peak_v` | `needs_semantics_check` | no-load / back-EMF related results | `ZIP` / `PDF` / PMSM measurements | 必须确认 phase 与 peak |
| `back_emf_phase_rms_v` | `needs_semantics_check` | no-load / back-EMF related results | 同上 | 必须确认 phase 与 RMS |
| `back_emf_line_rms_v` | `needs_semantics_check` | no-load / back-EMF related results | 同上 | 必须确认 line 与 RMS |
| `back_emf_constant_line_rms_v_per_krpm` | `needs_unit_conversion` | 反电势测试或可推导字段 | 同上 | 若原文不给 `V/krpm`，换算必须显式记录 |
| `torque_nm` | `needs_manual_extraction` | steady-state or drive-cycle measurements | `ZIP` / `PDF` / PMSM measurement results | 需绑定具体工况点 |
| `torque_constant_nm_per_a` | `needs_semantics_check` | 直接给出或可推导 | `ZIP` / `PDF` / PMSM measurements | 当前最敏感，必须明确 `current_basis` |
| `copper_loss_w` | `needs_manual_extraction` | measured losses | `ZIP` / `PDF` / drive-cycle results | 需确认是否分项给出 |
| `iron_loss_w` | `needs_manual_extraction` | measured losses | 同上 | 需确认是否分项给出 |
| `mechanical_loss_w` | `needs_manual_extraction` | measured losses | 同上 | 需确认是否单列 |
| `efficiency` | `needs_manual_extraction` | measured output/input power or reported efficiency | `ZIP` / `PDF` / steady-state or drive-cycle results | 若需由功率计算，必须显式记录 |
| `required_voltage_v` | `unavailable` | 当前未见直接对应 | 未核验到 | 本项目该量还是 legacy/provisional，不应强行映射 |
| `temperature` | `unavailable` | 当前未从仓库描述或 README 核验到 | 未核验到 | 不得猜测存在 |

## 5. 正式 record 创建前必须补齐的字段

至少需要补齐以下项目，才适合创建 `validation_data/imported/creator_pmsm_initial_record.json`：

1. `control_mode` 是否能安全映射到 `PMSM_SINUSOIDAL`
2. `topology` 的原文定义
3. 至少一个有明确工况、明确单位、明确语义的 `directly_comparable` 数值指标
4. 至少一个可定位到具体表/页/节的输入字段引用
5. `winding_connection`
6. `phase/line`、`RMS/peak`、`current_basis` 的明确说明

## 6. 当前不应强行导入的字段

以下字段本轮不能强行写成正式 record 的 `provided` 或 `inferred`：

- `back_emf_waveform`
- `topology`
- `back_emf_*`
- `torque_constant_nm_per_a`
- `required_voltage_v`
- `temperature`

原因分别是：

- 语义尚未确认；
- 原始数值尚未抽取；
- 可能与本项目正式字段定义不一致；
- 当前没有足够依据做显式单位换算或 current-basis 归一。
