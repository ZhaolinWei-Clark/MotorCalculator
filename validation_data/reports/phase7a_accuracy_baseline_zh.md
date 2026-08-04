# Phase 7A 预校准精度基线

## 边界声明

本报告只读取既有外部记录与分析夹具，不修改参数、公式、默认值、GUI 或 production calculation chain。
CREATOR 为径向磁通 PMSM，禁止用其数值误差声称 AFPM 默认模型精度。内部分析用例只证明代数/语义一致性。

## 基线结论

- 外部记录行：13；可直接比较：0；blocked：13。
- 内部一致性通过：24；这些结果不属于外部 accuracy validation。
- 当前没有可归因于模型误差的外部 tolerance failure；原因是缺少兼容 benchmark，而不是模型已通过精度验证。

## 比较明细

| benchmark | track | metric | operating point | predicted | reference | unit | absolute error | relative error % | tolerance | outcome | blocker / notes |
|---|---|---|---|---:|---:|---|---:|---:|---|---|---|
| creator_pmsm_initial_record | A/B boundary | rated_torque_nm | 2000 rpm; source-specific conditions | unavailable | 0.1 | Nm | unavailable | unavailable | not applied: comparison blocked | blocked | Topology mismatch (PMSM; air-gap length (radial direction); 4 poles; 6 stator slots); CREATOR radial PMSM is not routed through the AFPM production model. |
| creator_pmsm_initial_record | A/B boundary | back_emf_phase_peak_v | 2000 rpm; source-specific conditions | unavailable | 47.37 | V | unavailable | unavailable | not applied: comparison blocked | blocked | Topology mismatch (PMSM; air-gap length (radial direction); 4 poles; 6 stator slots); CREATOR radial PMSM is not routed through the AFPM production model. |
| creator_pmsm_initial_record | A/B boundary | phase_resistance_ohm | 2000 rpm; source-specific conditions | unavailable | 8.9462 | ohm | unavailable | unavailable | not applied: comparison blocked | blocked | Topology mismatch (PMSM; air-gap length (radial direction); 4 poles; 6 stator slots); CREATOR radial PMSM is not routed through the AFPM production model. |
| creator_pmsm_initial_record | A/B boundary | rated_current_a | 2000 rpm; source-specific conditions | unavailable | 0.21 | A | unavailable | unavailable | not applied: comparison blocked | blocked | Topology mismatch (PMSM; air-gap length (radial direction); 4 poles; 6 stator slots); CREATOR radial PMSM is not routed through the AFPM production model. |
| creator_pmsm_initial_record | A/B boundary | phase_inductance_h | 2000 rpm; source-specific conditions | unavailable | unavailable | H | unavailable | unavailable | not applied: comparison blocked | blocked | Source field unavailable: The source reports Ld = 0.2055 H and Lq = 0.332 H, but this initial record does not collapse those d-q values into a single schema phase_inductance field. |
| creator_pmsm_initial_record | A/B boundary | back_emf_line_rms_v | 2000 rpm; source-specific conditions | unavailable | unavailable | V | unavailable | unavailable | not applied: comparison blocked | blocked | Source field unavailable: No line-to-line RMS back-EMF value was quoted directly in the reviewed source files for this initial record. |
| creator_pmsm_initial_record | A/B boundary | back_emf_constant_line_rms_v_per_krpm | 2000 rpm; source-specific conditions | unavailable | unavailable | V/krpm | unavailable | unavailable | not applied: comparison blocked | blocked | Source field unavailable: This initial record keeps the line-RMS back-EMF constant unavailable rather than deriving it from the phase-peak quantity. |
| creator_pmsm_initial_record | A/B boundary | torque_constant_nm_per_a | 2000 rpm; source-specific conditions | unavailable | unavailable | Nm/A | unavailable | unavailable | not applied: comparison blocked | blocked | Source field unavailable: No directly traceable torque-constant field with project-compatible current basis was imported in this initial record. |
| creator_pmsm_initial_record | A/B boundary | copper_loss_w | 2000 rpm; source-specific conditions | unavailable | unavailable | W | unavailable | unavailable | not applied: comparison blocked | blocked | Source field unavailable: Drive-cycle and no-load loss files exist, but this initial record does not import a traceable copper-loss operating point. |
| creator_pmsm_initial_record | A/B boundary | iron_loss_w | 2000 rpm; source-specific conditions | unavailable | unavailable | W | unavailable | unavailable | not applied: comparison blocked | blocked | Source field unavailable: No single imported field was designated as a directly comparable iron-loss operating point in this initial record. |
| creator_pmsm_initial_record | A/B boundary | mechanical_loss_w | 2000 rpm; source-specific conditions | unavailable | unavailable | W | unavailable | unavailable | not applied: comparison blocked | blocked | Source field unavailable: Mechanical-loss separation was not imported as a standalone comparable field in this first record. |
| creator_pmsm_initial_record | A/B boundary | efficiency | 2000 rpm; source-specific conditions | unavailable | unavailable | % | unavailable | unavailable | not applied: comparison blocked | blocked | Source field unavailable: The source package contains drive-cycle power results, but this initial record does not import a formal efficiency operating point. |
| creator_pmsm_initial_record | A/B boundary | required_voltage_v | 2000 rpm; source-specific conditions | unavailable | unavailable | V | unavailable | unavailable | not applied: comparison blocked | blocked | Source field unavailable: The project's required_voltage_v chain remains legacy/provisional and no directly matching source field was imported. |
| analytical_case_1_basic_integer | A | Ke_line_rms_v_per_krpm | 95.4929658551 rpm | 256.509966032 | 256.509966032 | V/krpm | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal analytical reference only; not external accuracy evidence. |
| analytical_case_1_basic_integer | A | Kt_phase_rms_nm_per_a | 95.4929658551 rpm | 4.24264068712 | 4.24264068712 | Nm/A | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal power-balance reference only; not external accuracy evidence. |
| analytical_case_2_rpm_conversion | A | Ke_line_rms_v_per_krpm | 1000 rpm | 29.3938769134 | 29.3938769134 | V/krpm | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal analytical reference only; not external accuracy evidence. |
| analytical_case_2_rpm_conversion | A | Kt_phase_rms_nm_per_a | 1000 rpm | 0.486170810725 | 0.486170810725 | Nm/A | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal power-balance reference only; not external accuracy evidence. |
| analytical_case_3_low_speed_high_torque | A | Ke_line_rms_v_per_krpm | 60 rpm | 122.474487139 | 122.474487139 | V/krpm | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal analytical reference only; not external accuracy evidence. |
| analytical_case_3_low_speed_high_torque | A | Kt_phase_rms_nm_per_a | 60 rpm | 2.02571171135 | 2.02571171135 | Nm/A | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal power-balance reference only; not external accuracy evidence. |
| analytical_case_4_high_speed_low_torque | A | Ke_line_rms_v_per_krpm | 6000 rpm | 2.44948974278 | 2.44948974278 | V/krpm | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal analytical reference only; not external accuracy evidence. |
| analytical_case_4_high_speed_low_torque | A | Kt_phase_rms_nm_per_a | 6000 rpm | 0.0405142342271 | 0.0405142342271 | Nm/A | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal power-balance reference only; not external accuracy evidence. |
| basic_flat_top_case | C | phase_back_emf_rms_v | 95.4929658551 rpm | 17.6383420738 | 17.6383420738 | V | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| basic_flat_top_case | C | line_back_emf_rms_v | 95.4929658551 rpm | 29.8142397 | 29.8142397 | V | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| basic_flat_top_case | C | phase_current_rms_a | 95.4929658551 rpm | 3.26598632371 | 3.26598632371 | A | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| basic_flat_top_case | C | electromagnetic_power_w | 95.4929658551 rpm | 160 | 160 | W | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| common_rpm_case | C | phase_back_emf_rms_v | 1000 rpm | 21.1660104885 | 21.1660104885 | V | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| common_rpm_case | C | line_back_emf_rms_v | 1000 rpm | 35.77708764 | 35.77708764 | V | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| common_rpm_case | C | phase_current_rms_a | 1000 rpm | 4.89897948557 | 4.89897948557 | A | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| common_rpm_case | C | electromagnetic_power_w | 1000 rpm | 288 | 288 | W | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| low_speed_high_torque_case | C | phase_back_emf_rms_v | 60 rpm | 5.29150262213 | 5.29150262213 | V | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| low_speed_high_torque_case | C | line_back_emf_rms_v | 60 rpm | 8.94427191 | 8.94427191 | V | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| low_speed_high_torque_case | C | phase_current_rms_a | 60 rpm | 9.79795897113 | 9.79795897113 | A | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| low_speed_high_torque_case | C | electromagnetic_power_w | 60 rpm | 144 | 144 | W | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| high_speed_low_torque_case | C | phase_back_emf_rms_v | 6000 rpm | 10.5830052443 | 10.5830052443 | V | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| high_speed_low_torque_case | C | line_back_emf_rms_v | 6000 rpm | 17.88854382 | 17.88854382 | V | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| high_speed_low_torque_case | C | phase_current_rms_a | 6000 rpm | 0.653197264742 | 0.653197264742 | A | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |
| high_speed_low_torque_case | C | electromagnetic_power_w | 6000 rpm | 19.2 | 19.2 | W | 0 | 0 | absolute(relative error) <= 1e-9 (internal algebraic consistency) | internal_pass | Internal ideal 120-degree analytical reference only; not external accuracy evidence. |

## Target 状态计数

- READY: 0
- PARTIAL: 4
- BLOCKED: 5
- INTERNAL_ONLY: 8

## 禁止用途

不得将本报告中的内部分析结果解释为实测精度，不得从 blocked 行推导校准值，也不得据此写回 production 参数。
