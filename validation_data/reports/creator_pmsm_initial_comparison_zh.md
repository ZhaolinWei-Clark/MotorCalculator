# CREATOR PMSM 初始比较报告

更新时间：2026-07-04

## 1. 结论

已成功创建并加载正式 record：

- `validation_data/imported/creator_pmsm_initial_record.json`

已成功运行 comparison engine。

本轮没有形成任何数值误差结论，原因不是 loader 失败，而是 comparability gate 按预期拦截了直接比较：

- 该记录是 `PMSM`
- 该来源是径向 PMSM
- 当前项目默认拓扑仍是 `双转子、单定子、双气隙` 的 `AFPM`

因此，已导入的可追溯字段在进入误差计算前就被判定为 `TOPOLOGY_MISMATCH`。

## 2. 本轮使用的正式 record

- record 路径：`validation_data/imported/creator_pmsm_initial_record.json`
- source type：`published_benchmark`
- evidence level：`LEVEL_2_PUBLISHED_OR_FEA`
- motor type：`PMSM`
- control mode：`pmsm_sinusoidal`
- topology：`PMSM; air-gap length (radial direction); 4 poles; 6 stator slots`

## 3. comparison engine 运行方式

comparison engine 需要一个项目内 `AnalysisResult` 作为对照对象。本轮仅使用现有项目 AFPM PMSM 计算链生成的 `PMSM` 控制语义结果来验证 comparability gate 是否按设计工作。

重要边界：

- 这不是把 CREATOR 几何“映射成”本项目 AFPM 真机
- 这不是对 CREATOR 数据做自动校准
- 这不是对 production chain 做任何修改
- 因为 topology gate 先触发，所以本轮没有生成可用的误差数字

## 4. 已导入且参与 gate 判断的字段

以下字段已成功进入正式 record，并在 comparison engine 中被处理：

- `rated_torque_nm`
- `back_emf_phase_peak_v`
- `phase_resistance_ohm`
- `rated_current_a`

处理结果：

| 字段 | comparability_status | 说明 |
|---|---|---|
| `rated_torque_nm` | `topology_mismatch` | 来源拓扑与项目默认 AFPM 拓扑不一致 |
| `back_emf_phase_peak_v` | `topology_mismatch` | 同上 |
| `phase_resistance_ohm` | `topology_mismatch` | 同上 |
| `rated_current_a` | `topology_mismatch` | 同上 |

## 5. 已明确排除的字段

以下字段没有被伪造或强行比较，而是明确写入 exclusion / unavailable：

| 字段 | 结果 | 原因 |
|---|---|---|
| `phase_inductance_h` | `not_available` | 来源给的是 `Ld` / `Lq`，本轮不收敛为单一 schema 字段 |
| `back_emf_line_rms_v` | `not_available` | 本轮未导入直接引用的 line-RMS 值 |
| `back_emf_constant_line_rms_v_per_krpm` | `not_available` | 本轮禁止自动从 phase-peak 派生 |
| `torque_constant_nm_per_a` | `not_available` | 缺少正式 current basis 对齐 |
| `copper_loss_w` | `not_available` | 未绑定具体可追溯工况点 |
| `iron_loss_w` | `not_available` | 未绑定具体可追溯工况点 |
| `mechanical_loss_w` | `not_available` | 未绑定具体可追溯工况点 |
| `efficiency` | `not_available` | 未绑定具体可追溯工况点 |
| `required_voltage_v` | `not_available` | 项目该量仍是 legacy/provisional，且源中未导入直接同义字段 |

## 6. 本轮不能得出的结论

本轮不能声称：

- 项目整体精度已被 CREATOR 真实实验验证
- 当前默认 `AFPM` 拓扑已被 CREATOR 记录验证
- `BLDC` 已被该来源验证
- `required_voltage_v`、损耗、电感、槽满率、退磁或温升模型已被真实外部 benchmark 验证

## 7. 下一步

若继续推进同一来源，可优先做：

1. 选定一个具体 drive-cycle 或 steady-state 工况点导入损耗/效率字段
2. 决定是否允许把 `Ld` / `Lq` 以新的可追溯方式保留在 schema 外层说明中继续使用，而不强行压缩成 `phase_inductance_h`
3. 若未来需要准确度声明，优先寻找与项目默认 `AFPM` 拓扑更接近的真实外部来源
