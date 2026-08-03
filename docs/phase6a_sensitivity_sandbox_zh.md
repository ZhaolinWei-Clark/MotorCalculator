# Phase 6A 参数敏感性沙盒说明

更新时间：2026-07-10

## 1. 阶段目标

Phase 6A 建立只读参数敏感性沙盒，用于回答：

> What happens if this parameter changes?

本阶段不回答：

> What should the calibrated value be?

## 2. 边界

- 不修改 `motor_core/calculations.py`
- 不修改 `legacy_baseline.json`
- 不切换默认模型
- 不修改 production formula
- 不写回任何参数
- 不生成 calibrated model
- 不修改 GUI calculation behavior

沙盒代码位于 `motor_calculator/calibration_sandbox/`，只通过既有 `MotorAnalysisEngine` 运行临时副本。

## 3. 数据结构

Phase 6A 新增以下只读 dataclass：

- `PerturbationSpec`：记录 `parameter_name`、`baseline_value`、`perturbation_percent`、`temporary_value`
- `SensitivityTarget`：记录可测试参数、内部字段、单位和可用性
- `SensitivityRunResult`：记录单次扰动和 affected outputs
- `SensitivitySummary`：记录 sweep 汇总、敏感性排名、边界警告和不稳定说明

## 4. 首批参数

| 参数 | 状态 | 说明 |
|---|---|---|
| `magnet_remanence_t` | available | 映射到 `remanence_t` |
| `air_gap_m` | available | 映射到现有单侧气隙字段 `air_gap_per_side_m` |
| `magnet_thickness_m` | available | 直接映射 |
| `turns_per_phase` | available | integer 输入，小扰动会四舍五入 |
| `phase_current_a` | unavailable | 当前 production input 不把相电流作为独立输入 |
| `rated_speed_rpm` | available | 映射到 `mechanical_speed_rpm` |

## 5. 输出观测指标

首批观测指标：

- `rated_torque_nm`
- `back_emf_phase_peak_v`
- `back_emf_line_rms_v`
- `torque_constant_nm_per_a`
- `required_voltage_v`
- `copper_loss_w`
- `iron_loss_w`
- `efficiency_percent`

若字段在 `AnalysisResult` 中不可用，沙盒只记录 `unavailable`，不新增 production 字段。

## 6. 报告

预览报告路径：

- `validation_data/reports/phase6a_sensitivity_preview_zh.md`

报告仅用于局部敏感性观察，不能作为 calibration 结论或默认参数修改依据。
