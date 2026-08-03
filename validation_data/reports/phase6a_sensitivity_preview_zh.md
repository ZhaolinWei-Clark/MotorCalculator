# Phase 6A 参数敏感性沙盒预览报告

更新时间：2026-07-10

## 1. Sandbox boundary statement

本报告由 Phase 6A read-only sensitivity sandbox 生成，只回答：如果某个输入参数临时变化，现有模型输出会怎样变化。

本报告不执行 calibration，不拟合参数，不生成 calibrated model，也不允许把任何结果写回 production defaults。

## 2. Tested parameters

| parameter | internal field | unit | status | notes |
|---|---|---|---|---|
| `magnet_remanence_t` | `remanence_t` | T | available | Maps to MotorAnalysisInput.remanence_t. |
| `air_gap_m` | `air_gap_per_side_m` | m | available | Maps to the existing per-side mechanical air-gap field. |
| `magnet_thickness_m` | `magnet_thickness_m` | m | available | Maps directly to MotorAnalysisInput.magnet_thickness_m. |
| `turns_per_phase` | `turns_per_phase` | turns | available | Integer input; perturbations are rounded to the nearest turn. |
| `phase_current_a` | `N/A` | A | unavailable | The current production input model does not accept phase current as an independent input. |
| `rated_speed_rpm` | `mechanical_speed_rpm` | rpm | available | Maps to MotorAnalysisInput.mechanical_speed_rpm. |

## 3. Perturbation table

| parameter | perturbation | baseline | temporary | status |
|---|---:|---:|---:|---|
| `magnet_remanence_t` | -5.0% | 1.28 | 1.216 | ok |
| `magnet_remanence_t` | -1.0% | 1.28 | 1.2672 | ok |
| `magnet_remanence_t` | +1.0% | 1.28 | 1.2928 | ok |
| `magnet_remanence_t` | +5.0% | 1.28 | 1.344 | ok |
| `air_gap_m` | -5.0% | 0.001 | 0.00095 | ok |
| `air_gap_m` | -1.0% | 0.001 | 0.00099 | ok |
| `air_gap_m` | +1.0% | 0.001 | 0.00101 | ok |
| `air_gap_m` | +5.0% | 0.001 | 0.00105 | ok |
| `magnet_thickness_m` | -5.0% | 0.005 | 0.00475 | ok |
| `magnet_thickness_m` | -1.0% | 0.005 | 0.00495 | ok |
| `magnet_thickness_m` | +1.0% | 0.005 | 0.00505 | ok |
| `magnet_thickness_m` | +5.0% | 0.005 | 0.00525 | ok |
| `turns_per_phase` | -5.0% | 100 | 95 | ok |
| `turns_per_phase` | -1.0% | 100 | 99 | ok |
| `turns_per_phase` | +1.0% | 100 | 101 | ok |
| `turns_per_phase` | +5.0% | 100 | 105 | ok |
| `phase_current_a` | -5.0% | N/A | N/A | unavailable |
| `phase_current_a` | -1.0% | N/A | N/A | unavailable |
| `phase_current_a` | +1.0% | N/A | N/A | unavailable |
| `phase_current_a` | +5.0% | N/A | N/A | unavailable |
| `rated_speed_rpm` | -5.0% | 2500 | 2375 | ok |
| `rated_speed_rpm` | -1.0% | 2500 | 2475 | ok |
| `rated_speed_rpm` | +1.0% | 2500 | 2525 | ok |
| `rated_speed_rpm` | +5.0% | 2500 | 2625 | ok |

## 4. Output sensitivity table

| parameter | perturbation | output | baseline | temporary | relative change | status |
|---|---:|---|---:|---:|---:|---|
| `magnet_remanence_t` | -5.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `magnet_remanence_t` | -5.0% | `back_emf_phase_peak_v` | 66.7642 | 63.426 | -5% | available |
| `magnet_remanence_t` | -5.0% | `back_emf_line_rms_v` | 81.7691 | 77.6806 | -5% | available |
| `magnet_remanence_t` | -5.0% | `torque_constant_nm_per_a` | 0.54098 | 0.513931 | -5% | available |
| `magnet_remanence_t` | -5.0% | `required_voltage_v` | 102.948 | 101.135 | -1.762% | available |
| `magnet_remanence_t` | -5.0% | `copper_loss_w` | 19.7682 | 21.9039 | +10.8% | available |
| `magnet_remanence_t` | -5.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `magnet_remanence_t` | -5.0% | `efficiency_percent` | 92.0429 | 92.2081 | +0.1795% | available |
| `magnet_remanence_t` | -1.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `magnet_remanence_t` | -1.0% | `back_emf_phase_peak_v` | 66.7642 | 66.0965 | -1% | available |
| `magnet_remanence_t` | -1.0% | `back_emf_line_rms_v` | 81.7691 | 80.9514 | -1% | available |
| `magnet_remanence_t` | -1.0% | `torque_constant_nm_per_a` | 0.54098 | 0.53557 | -1% | available |
| `magnet_remanence_t` | -1.0% | `required_voltage_v` | 102.948 | 102.553 | -0.3837% | available |
| `magnet_remanence_t` | -1.0% | `copper_loss_w` | 19.7682 | 20.1696 | +2.03% | available |
| `magnet_remanence_t` | -1.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `magnet_remanence_t` | -1.0% | `efficiency_percent` | 92.0429 | 92.0802 | +0.04057% | available |
| `magnet_remanence_t` | +1.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `magnet_remanence_t` | +1.0% | `back_emf_phase_peak_v` | 66.7642 | 67.4318 | +1% | available |
| `magnet_remanence_t` | +1.0% | `back_emf_line_rms_v` | 81.7691 | 82.5868 | +1% | available |
| `magnet_remanence_t` | +1.0% | `torque_constant_nm_per_a` | 0.54098 | 0.54639 | +1% | available |
| `magnet_remanence_t` | +1.0% | `required_voltage_v` | 102.948 | 103.358 | +0.3983% | available |
| `magnet_remanence_t` | +1.0% | `copper_loss_w` | 19.7682 | 19.3787 | -1.97% | available |
| `magnet_remanence_t` | +1.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `magnet_remanence_t` | +1.0% | `efficiency_percent` | 92.0429 | 92.0035 | -0.04277% | available |
| `magnet_remanence_t` | +5.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `magnet_remanence_t` | +5.0% | `back_emf_phase_peak_v` | 66.7642 | 70.1024 | +5% | available |
| `magnet_remanence_t` | +5.0% | `back_emf_line_rms_v` | 81.7691 | 85.8575 | +5% | available |
| `magnet_remanence_t` | +5.0% | `torque_constant_nm_per_a` | 0.54098 | 0.568029 | +5% | available |
| `magnet_remanence_t` | +5.0% | `required_voltage_v` | 102.948 | 105.138 | +2.127% | available |
| `magnet_remanence_t` | +5.0% | `copper_loss_w` | 19.7682 | 17.9304 | -9.297% | available |
| `magnet_remanence_t` | +5.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `magnet_remanence_t` | +5.0% | `efficiency_percent` | 92.0429 | 91.8268 | -0.2347% | available |
| `air_gap_m` | -5.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `air_gap_m` | -5.0% | `back_emf_phase_peak_v` | 66.7642 | 67.1382 | +0.5601% | available |
| `air_gap_m` | -5.0% | `back_emf_line_rms_v` | 81.7691 | 82.2271 | +0.5601% | available |
| `air_gap_m` | -5.0% | `torque_constant_nm_per_a` | 0.54098 | 0.54401 | +0.5601% | available |
| `air_gap_m` | -5.0% | `required_voltage_v` | 102.948 | 103.626 | +0.6581% | available |
| `air_gap_m` | -5.0% | `copper_loss_w` | 19.7682 | 19.5486 | -1.111% | available |
| `air_gap_m` | -5.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `air_gap_m` | -5.0% | `efficiency_percent` | 92.0429 | 92.0211 | -0.02369% | available |
| `air_gap_m` | -1.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `air_gap_m` | -1.0% | `back_emf_phase_peak_v` | 66.7642 | 66.8386 | +0.1115% | available |
| `air_gap_m` | -1.0% | `back_emf_line_rms_v` | 81.7691 | 81.8603 | +0.1115% | available |
| `air_gap_m` | -1.0% | `torque_constant_nm_per_a` | 0.54098 | 0.541583 | +0.1115% | available |
| `air_gap_m` | -1.0% | `required_voltage_v` | 102.948 | 103.083 | +0.1306% | available |
| `air_gap_m` | -1.0% | `copper_loss_w` | 19.7682 | 19.7242 | -0.2227% | available |
| `air_gap_m` | -1.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `air_gap_m` | -1.0% | `efficiency_percent` | 92.0429 | 92.0386 | -0.004662% | available |
| `air_gap_m` | +1.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `air_gap_m` | +1.0% | `back_emf_phase_peak_v` | 66.7642 | 66.6899 | -0.1113% | available |
| `air_gap_m` | +1.0% | `back_emf_line_rms_v` | 81.7691 | 81.6781 | -0.1113% | available |
| `air_gap_m` | +1.0% | `torque_constant_nm_per_a` | 0.54098 | 0.540378 | -0.1113% | available |
| `air_gap_m` | +1.0% | `required_voltage_v` | 102.948 | 102.814 | -0.1302% | available |
| `air_gap_m` | +1.0% | `copper_loss_w` | 19.7682 | 19.8123 | +0.2229% | available |
| `air_gap_m` | +1.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `air_gap_m` | +1.0% | `efficiency_percent` | 92.0429 | 92.0471 | +0.004624% | available |
| `air_gap_m` | +5.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `air_gap_m` | +5.0% | `back_emf_phase_peak_v` | 66.7642 | 66.3943 | -0.5539% | available |
| `air_gap_m` | +5.0% | `back_emf_line_rms_v` | 81.7691 | 81.3161 | -0.5539% | available |
| `air_gap_m` | +5.0% | `torque_constant_nm_per_a` | 0.54098 | 0.537983 | -0.5539% | available |
| `air_gap_m` | +5.0% | `required_voltage_v` | 102.948 | 102.283 | -0.646% | available |
| `air_gap_m` | +5.0% | `copper_loss_w` | 19.7682 | 19.9891 | +1.117% | available |
| `air_gap_m` | +5.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `air_gap_m` | +5.0% | `efficiency_percent` | 92.0429 | 92.0638 | +0.02275% | available |
| `magnet_thickness_m` | -5.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `magnet_thickness_m` | -5.0% | `back_emf_phase_peak_v` | 66.7642 | 65.4216 | -2.011% | available |
| `magnet_thickness_m` | -5.0% | `back_emf_line_rms_v` | 81.7691 | 80.1248 | -2.011% | available |
| `magnet_thickness_m` | -5.0% | `torque_constant_nm_per_a` | 0.54098 | 0.530101 | -2.011% | available |
| `magnet_thickness_m` | -5.0% | `required_voltage_v` | 102.948 | 102.17 | -0.7562% | available |
| `magnet_thickness_m` | -5.0% | `copper_loss_w` | 19.7682 | 20.5879 | +4.147% | available |
| `magnet_thickness_m` | -5.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `magnet_thickness_m` | -5.0% | `efficiency_percent` | 92.0429 | 92.1158 | +0.07927% | available |
| `magnet_thickness_m` | -1.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `magnet_thickness_m` | -1.0% | `back_emf_phase_peak_v` | 66.7642 | 66.5023 | -0.3923% | available |
| `magnet_thickness_m` | -1.0% | `back_emf_line_rms_v` | 81.7691 | 81.4483 | -0.3923% | available |
| `magnet_thickness_m` | -1.0% | `torque_constant_nm_per_a` | 0.54098 | 0.538858 | -0.3923% | available |
| `magnet_thickness_m` | -1.0% | `required_voltage_v` | 102.948 | 102.791 | -0.1523% | available |
| `magnet_thickness_m` | -1.0% | `copper_loss_w` | 19.7682 | 19.9243 | +0.7893% | available |
| `magnet_thickness_m` | -1.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `magnet_thickness_m` | -1.0% | `efficiency_percent` | 92.0429 | 92.0577 | +0.01618% | available |
| `magnet_thickness_m` | +1.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `magnet_thickness_m` | +1.0% | `back_emf_phase_peak_v` | 66.7642 | 67.0229 | +0.3876% | available |
| `magnet_thickness_m` | +1.0% | `back_emf_line_rms_v` | 81.7691 | 82.086 | +0.3876% | available |
| `magnet_thickness_m` | +1.0% | `torque_constant_nm_per_a` | 0.54098 | 0.543077 | +0.3876% | available |
| `magnet_thickness_m` | +1.0% | `required_voltage_v` | 102.948 | 103.105 | +0.1526% | available |
| `magnet_thickness_m` | +1.0% | `copper_loss_w` | 19.7682 | 19.6159 | -0.7706% | available |
| `magnet_thickness_m` | +1.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `magnet_thickness_m` | +1.0% | `efficiency_percent` | 92.0429 | 92.0278 | -0.01632% | available |
| `magnet_thickness_m` | +5.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `magnet_thickness_m` | +5.0% | `back_emf_phase_peak_v` | 66.7642 | 68.0273 | +1.892% | available |
| `magnet_thickness_m` | +5.0% | `back_emf_line_rms_v` | 81.7691 | 83.3161 | +1.892% | available |
| `magnet_thickness_m` | +5.0% | `torque_constant_nm_per_a` | 0.54098 | 0.551215 | +1.892% | available |
| `magnet_thickness_m` | +5.0% | `required_voltage_v` | 102.948 | 103.736 | +0.7653% | available |
| `magnet_thickness_m` | +5.0% | `copper_loss_w` | 19.7682 | 19.0409 | -3.679% | available |
| `magnet_thickness_m` | +5.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `magnet_thickness_m` | +5.0% | `efficiency_percent` | 92.0429 | 91.9667 | -0.08272% | available |
| `turns_per_phase` | -5.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `turns_per_phase` | -5.0% | `back_emf_phase_peak_v` | 66.7642 | 63.426 | -5% | available |
| `turns_per_phase` | -5.0% | `back_emf_line_rms_v` | 81.7691 | 77.6806 | -5% | available |
| `turns_per_phase` | -5.0% | `torque_constant_nm_per_a` | 0.54098 | 0.513931 | -5% | available |
| `turns_per_phase` | -5.0% | `required_voltage_v` | 102.948 | 97.8038 | -4.997% | available |
| `turns_per_phase` | -5.0% | `copper_loss_w` | 19.7682 | 20.8087 | +5.263% | available |
| `turns_per_phase` | -5.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `turns_per_phase` | -5.0% | `efficiency_percent` | 92.0429 | 92.1333 | +0.0983% | available |
| `turns_per_phase` | -1.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `turns_per_phase` | -1.0% | `back_emf_phase_peak_v` | 66.7642 | 66.0965 | -1% | available |
| `turns_per_phase` | -1.0% | `back_emf_line_rms_v` | 81.7691 | 80.9514 | -1% | available |
| `turns_per_phase` | -1.0% | `torque_constant_nm_per_a` | 0.54098 | 0.53557 | -1% | available |
| `turns_per_phase` | -1.0% | `required_voltage_v` | 102.948 | 101.919 | -0.9994% | available |
| `turns_per_phase` | -1.0% | `copper_loss_w` | 19.7682 | 19.9679 | +1.01% | available |
| `turns_per_phase` | -1.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `turns_per_phase` | -1.0% | `efficiency_percent` | 92.0429 | 92.0618 | +0.02061% | available |
| `turns_per_phase` | +1.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `turns_per_phase` | +1.0% | `back_emf_phase_peak_v` | 66.7642 | 67.4318 | +1% | available |
| `turns_per_phase` | +1.0% | `back_emf_line_rms_v` | 81.7691 | 82.5868 | +1% | available |
| `turns_per_phase` | +1.0% | `torque_constant_nm_per_a` | 0.54098 | 0.54639 | +1% | available |
| `turns_per_phase` | +1.0% | `required_voltage_v` | 102.948 | 103.977 | +0.9994% | available |
| `turns_per_phase` | +1.0% | `copper_loss_w` | 19.7682 | 19.5725 | -0.9901% | available |
| `turns_per_phase` | +1.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `turns_per_phase` | +1.0% | `efficiency_percent` | 92.0429 | 92.0235 | -0.02106% | available |
| `turns_per_phase` | +5.0% | `rated_torque_nm` | 3.056 | 3.056 | +0% | available |
| `turns_per_phase` | +5.0% | `back_emf_phase_peak_v` | 66.7642 | 70.1024 | +5% | available |
| `turns_per_phase` | +5.0% | `back_emf_line_rms_v` | 81.7691 | 85.8575 | +5% | available |
| `turns_per_phase` | +5.0% | `torque_constant_nm_per_a` | 0.54098 | 0.568029 | +5% | available |
| `turns_per_phase` | +5.0% | `required_voltage_v` | 102.948 | 108.093 | +4.997% | available |
| `turns_per_phase` | +5.0% | `copper_loss_w` | 19.7682 | 18.8269 | -4.762% | available |
| `turns_per_phase` | +5.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `turns_per_phase` | +5.0% | `efficiency_percent` | 92.0429 | 91.9421 | -0.1095% | available |
| `phase_current_a` | -5.0% | `rated_torque_nm` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -5.0% | `back_emf_phase_peak_v` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -5.0% | `back_emf_line_rms_v` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -5.0% | `torque_constant_nm_per_a` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -5.0% | `required_voltage_v` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -5.0% | `copper_loss_w` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -5.0% | `iron_loss_w` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -5.0% | `efficiency_percent` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -1.0% | `rated_torque_nm` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -1.0% | `back_emf_phase_peak_v` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -1.0% | `back_emf_line_rms_v` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -1.0% | `torque_constant_nm_per_a` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -1.0% | `required_voltage_v` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -1.0% | `copper_loss_w` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -1.0% | `iron_loss_w` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | -1.0% | `efficiency_percent` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +1.0% | `rated_torque_nm` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +1.0% | `back_emf_phase_peak_v` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +1.0% | `back_emf_line_rms_v` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +1.0% | `torque_constant_nm_per_a` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +1.0% | `required_voltage_v` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +1.0% | `copper_loss_w` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +1.0% | `iron_loss_w` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +1.0% | `efficiency_percent` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +5.0% | `rated_torque_nm` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +5.0% | `back_emf_phase_peak_v` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +5.0% | `back_emf_line_rms_v` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +5.0% | `torque_constant_nm_per_a` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +5.0% | `required_voltage_v` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +5.0% | `copper_loss_w` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +5.0% | `iron_loss_w` | N/A | N/A | N/A | unavailable |
| `phase_current_a` | +5.0% | `efficiency_percent` | N/A | N/A | N/A | unavailable |
| `rated_speed_rpm` | -5.0% | `rated_torque_nm` | 3.056 | 3.21684 | +5.263% | available |
| `rated_speed_rpm` | -5.0% | `back_emf_phase_peak_v` | 66.7642 | 63.426 | -5% | available |
| `rated_speed_rpm` | -5.0% | `back_emf_line_rms_v` | 81.7691 | 77.6806 | -5% | available |
| `rated_speed_rpm` | -5.0% | `torque_constant_nm_per_a` | 0.54098 | 0.54098 | +2.052e-14% | available |
| `rated_speed_rpm` | -5.0% | `required_voltage_v` | 102.948 | 99.3995 | -3.447% | available |
| `rated_speed_rpm` | -5.0% | `copper_loss_w` | 19.7682 | 21.9039 | +10.8% | available |
| `rated_speed_rpm` | -5.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `rated_speed_rpm` | -5.0% | `efficiency_percent` | 92.0429 | 92.2285 | +0.2017% | available |
| `rated_speed_rpm` | -1.0% | `rated_torque_nm` | 3.056 | 3.08687 | +1.01% | available |
| `rated_speed_rpm` | -1.0% | `back_emf_phase_peak_v` | 66.7642 | 66.0965 | -1% | available |
| `rated_speed_rpm` | -1.0% | `back_emf_line_rms_v` | 81.7691 | 80.9514 | -1% | available |
| `rated_speed_rpm` | -1.0% | `torque_constant_nm_per_a` | 0.54098 | 0.54098 | -2.052e-14% | available |
| `rated_speed_rpm` | -1.0% | `required_voltage_v` | 102.948 | 102.234 | -0.6939% | available |
| `rated_speed_rpm` | -1.0% | `copper_loss_w` | 19.7682 | 20.1696 | +2.03% | available |
| `rated_speed_rpm` | -1.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `rated_speed_rpm` | -1.0% | `efficiency_percent` | 92.0429 | 92.0843 | +0.04502% | available |
| `rated_speed_rpm` | +1.0% | `rated_torque_nm` | 3.056 | 3.02574 | -0.9901% | available |
| `rated_speed_rpm` | +1.0% | `back_emf_phase_peak_v` | 66.7642 | 67.4318 | +1% | available |
| `rated_speed_rpm` | +1.0% | `back_emf_line_rms_v` | 81.7691 | 82.5868 | +1% | available |
| `rated_speed_rpm` | +1.0% | `torque_constant_nm_per_a` | 0.54098 | 0.54098 | +0% | available |
| `rated_speed_rpm` | +1.0% | `required_voltage_v` | 102.948 | 103.665 | +0.696% | available |
| `rated_speed_rpm` | +1.0% | `copper_loss_w` | 19.7682 | 19.3787 | -1.97% | available |
| `rated_speed_rpm` | +1.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `rated_speed_rpm` | +1.0% | `efficiency_percent` | 92.0429 | 91.9994 | -0.04722% | available |
| `rated_speed_rpm` | +5.0% | `rated_torque_nm` | 3.056 | 2.91048 | -4.762% | available |
| `rated_speed_rpm` | +5.0% | `back_emf_phase_peak_v` | 66.7642 | 70.1024 | +5% | available |
| `rated_speed_rpm` | +5.0% | `back_emf_line_rms_v` | 81.7691 | 85.8575 | +5% | available |
| `rated_speed_rpm` | +5.0% | `torque_constant_nm_per_a` | 0.54098 | 0.54098 | +2.052e-14% | available |
| `rated_speed_rpm` | +5.0% | `required_voltage_v` | 102.948 | 106.552 | +3.501% | available |
| `rated_speed_rpm` | +5.0% | `copper_loss_w` | 19.7682 | 17.9304 | -9.297% | available |
| `rated_speed_rpm` | +5.0% | `iron_loss_w` | 8 | 8 | +0% | available |
| `rated_speed_rpm` | +5.0% | `efficiency_percent` | 92.0429 | 91.8063 | -0.257% | available |

## 5. Most sensitive parameters

| output | most sensitive parameter in this sweep |
|---|---|
| `rated_torque_nm` | `rated_speed_rpm` |
| `back_emf_phase_peak_v` | `rated_speed_rpm` |
| `back_emf_line_rms_v` | `rated_speed_rpm` |
| `torque_constant_nm_per_a` | `magnet_remanence_t` |
| `required_voltage_v` | `turns_per_phase` |
| `copper_loss_w` | `magnet_remanence_t` |
| `iron_loss_w` | `magnet_remanence_t` |
| `efficiency_percent` | `rated_speed_rpm` |

## 6. Nonlinear / unstable behavior notes

- phase_current_a: The current production input model does not accept phase current as an independent input.

## 7. Warnings

- Phase 6A is a read-only sensitivity sandbox.
- Sandbox results are not calibrated values and must not be written back to production defaults.
- The runner calls the existing calculation engine without modifying motor_core/calculations.py.
- 本报告中的敏感性排名只描述当前 baseline 附近的局部响应，不代表推荐校准方向。
