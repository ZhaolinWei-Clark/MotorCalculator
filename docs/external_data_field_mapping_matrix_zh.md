# 外部数据字段匹配矩阵

更新时间：2026-07-04

## 1. 说明

本文档将候选来源与 Phase 4A schema 的关键字段做静态映射。

字段状态只使用以下枚举：

- `available`
- `partially_available`
- `inferred`
- `unavailable`
- `not_applicable`
- `license_restricted`
- `needs_manual_extraction`
- `needs_user_supplied_source`

候选简称：

- `CREATOR-PMSM`
- `CREATOR-IM`
- `PYLEECAN`
- `FEMM-SPM`
- `FEMM-BLDC`
- `PDB-ELEC`
- `PDB-TEMP`
- `TUMFTM`
- `EMRAX`
- `PARVIAINEN-AFPM`
- `FENICSX-PMSM`

## 2. 运行点与电气字段

| source | pole_pairs | rated_speed_rpm | rated_power_w | dc_bus_voltage_v | phase_current_a | line_current_a | winding_connection | back_emf_waveform |
|---|---|---|---|---|---|---|---|---|
| CREATOR-PMSM | needs_manual_extraction | available | available | needs_manual_extraction | available | needs_manual_extraction | needs_manual_extraction | needs_manual_extraction |
| CREATOR-IM | needs_manual_extraction | available | available | needs_manual_extraction | available | needs_manual_extraction | needs_manual_extraction | not_applicable |
| PYLEECAN | available | available | available | partially_available | available | available | available | partially_available |
| FEMM-SPM | unavailable | partially_available | unavailable | unavailable | partially_available | unavailable | needs_manual_extraction | available |
| FEMM-BLDC | unavailable | unavailable | unavailable | unavailable | partially_available | unavailable | unavailable | partially_available |
| PDB-ELEC | unavailable | available | unavailable | available | available | partially_available | unavailable | unavailable |
| PDB-TEMP | unavailable | available | unavailable | available | available | partially_available | unavailable | unavailable |
| TUMFTM | available | available | available | partially_available | partially_available | partially_available | available | unavailable |
| EMRAX | partially_available | partially_available | available | partially_available | partially_available | unavailable | unavailable | unavailable |
| PARVIAINEN-AFPM | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source |
| FENICSX-PMSM | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source |

## 3. 几何字段

| source | stator_outer_diameter_m | stator_inner_diameter_m | rotor_outer_diameter_m | rotor_inner_diameter_m | air_gap_m | magnet_thickness_m | magnet_width_m |
|---|---|---|---|---|---|---|---|
| CREATOR-PMSM | available | available | available | available | available | available | available |
| CREATOR-IM | available | available | available | available | available | not_applicable | not_applicable |
| PYLEECAN | available | available | available | available | available | available | available |
| FEMM-SPM | available | available | available | available | available | available | unavailable |
| FEMM-BLDC | partially_available | partially_available | partially_available | partially_available | partially_available | partially_available | partially_available |
| PDB-ELEC | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| PDB-TEMP | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| TUMFTM | partially_available | partially_available | partially_available | partially_available | partially_available | partially_available | partially_available |
| EMRAX | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| PARVIAINEN-AFPM | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source |
| FENICSX-PMSM | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source |

## 4. 材料与绕组字段

| source | magnet_grade | magnet_remanence_t | turns_per_phase | winding_factor | phase_resistance_ohm | phase_inductance_h |
|---|---|---|---|---|---|---|
| CREATOR-PMSM | available | available | available | available | available | available |
| CREATOR-IM | not_applicable | not_applicable | available | available | available | available |
| PYLEECAN | available | available | available | available | available | available |
| FEMM-SPM | partially_available | partially_available | available | needs_manual_extraction | needs_manual_extraction | unavailable |
| FEMM-BLDC | partially_available | partially_available | partially_available | unavailable | unavailable | unavailable |
| PDB-ELEC | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| PDB-TEMP | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| TUMFTM | partially_available | partially_available | partially_available | partially_available | partially_available | partially_available |
| EMRAX | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| PARVIAINEN-AFPM | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source |
| FENICSX-PMSM | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source |

## 5. 输出字段

| source | back_emf_phase_peak_v | back_emf_phase_rms_v | back_emf_line_rms_v | back_emf_constant_line_rms_v_per_krpm | torque_nm | torque_constant_nm_per_a | copper_loss_w | iron_loss_w | mechanical_loss_w | efficiency | required_voltage_v | temperature |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CREATOR-PMSM | needs_manual_extraction | needs_manual_extraction | needs_manual_extraction | needs_manual_extraction | available | needs_manual_extraction | needs_manual_extraction | needs_manual_extraction | needs_manual_extraction | available | unavailable | unavailable |
| CREATOR-IM | not_applicable | not_applicable | not_applicable | not_applicable | available | not_applicable | needs_manual_extraction | needs_manual_extraction | needs_manual_extraction | available | unavailable | unavailable |
| PYLEECAN | partially_available | partially_available | partially_available | inferred | available | inferred | available | available | partially_available | partially_available | unavailable | partially_available |
| FEMM-SPM | partially_available | partially_available | unavailable | unavailable | unavailable | unavailable | partially_available | available | unavailable | unavailable | unavailable | unavailable |
| FEMM-BLDC | unavailable | unavailable | unavailable | unavailable | available | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| PDB-ELEC | unavailable | unavailable | unavailable | unavailable | partially_available | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| PDB-TEMP | unavailable | unavailable | unavailable | unavailable | partially_available | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable | available |
| TUMFTM | unavailable | unavailable | unavailable | unavailable | inferred | unavailable | partially_available | partially_available | partially_available | available | unavailable | unavailable |
| EMRAX | unavailable | unavailable | unavailable | unavailable | available | unavailable | unavailable | unavailable | unavailable | partially_available | unavailable | unavailable |
| PARVIAINEN-AFPM | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source |
| FENICSX-PMSM | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source | needs_user_supplied_source |

## 6. 读表结论

### 6.1 最接近“首条真实 validation record”的来源

- `CREATOR-PMSM`

原因：

- 几何、材料、绕组、工况和实测结果同时具备
- 有 DOI、数据包、授权说明
- 可进入 `LEVEL_3_CONTROLLED_MEASUREMENT`

### 6.2 最接近“首条 FEA-only record”的来源

- `FEMM-SPM`

原因：

- 公开
- 字段相对具体
- 可以清楚标记为 `fea_simulation`

### 6.3 明确不应误判为几何电磁 benchmark 的来源

- `PDB-ELEC`
- `PDB-TEMP`
- `EMRAX`

原因：

- 几何 / 材料 / 绕组字段缺失
- 只能做控制、热估计或厂家规格级弱参考

### 6.4 当前最需要用户补源的来源

- `PARVIAINEN-AFPM`
- `FENICSX-PMSM`

原因：

- 有高相关方向价值
- 但本轮未确认到可稳定引用并做字段抽取的全文来源
