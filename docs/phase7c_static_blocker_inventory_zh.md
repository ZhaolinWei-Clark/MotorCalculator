# Phase 7C 静态 Blocker Inventory

## 边界与优先级

本清单覆盖 Phase 7B.1 的全部 14 个 `BLOCKED` 外部 metric rows。优先级固定为：back-EMF/Ke、torque-current/Kt、phase resistance、inductance、efficiency/loss。未知字段不由 production defaults 补齐。

Blocker category 计数变化：`current_basis_unknown 2 -> 1`，`torque_boundary_unknown 1 -> 0`；其他类别数量不变。状态行仍为 `DIRECT=1, SAFE_TRANSFORM=0, APPROXIMATE=0, BLOCKED=14, UNAVAILABLE=6`。

## 逐行清单

| priority | source | metric | known | exact missing / mismatch | categories after | recoverable? | fundamental? |
|---:|---|---|---|---|---|---|---|
| 1 | Abdelli 2026 | back_emf_phase_waveform | 1000 rpm, p=6, diameters, gap, magnet thickness, measured/FEA plots | prototype turns/phase, connection, Br, kw, leakage, scalar pole arc, tabulated V | missing_turns, missing_winding_connection, topology_mismatch, model_input_not_supported | plot could only yield approximate scalar | yes |
| 2 | Abdelli 2026 | torque_nm | 1000 rpm, 20-400 A sweep | authoritative point and exact torque/current boundary; topology bridge | operating_point_incomplete, topology_mismatch, model_input_not_supported | plot estimate possible but low-value | yes |
| 1 | Price 2009 | back_emf_phase_peak_v | 600 rpm, Y, 108 turns/phase, 37 V phase peak, sinusoidal, SSDR/coreless | pole pairs, Br, permeability, physical per-side gap, kw, leakage, scalar pole arc | missing_geometry, model_input_not_supported | full source exhausted | yes |
| 2 | Price 2009 | torque_nm | 500 rpm, 10 A phase RMS, 12.6 Nm average shaft torque, Y, sinusoidal current | production electromagnetic prediction and mechanical-loss torque | model_input_not_supported | current and shaft boundary recovered | yes |
| 1 | Parviainen 2005 | back_emf_phase_rms_v | 300 rpm, p=6, diameters, gap, Br@100 C, 840 turns/stator phase, star, 211 V phase RMS | DSSR parallel-stator representation, coil height, source-equivalent kw/leakage/pole shape | nonsinusoidal_waveform, topology_mismatch, model_input_not_supported | source fields largely recovered | yes |
| 3 | Parviainen 2005 | phase_resistance_ohm | 3.7 ohm DC per stator phase, 840 turns, star/parallel stators | measurement temperature, conductor/parallel paths, end-turn geometry | temperature_unknown, topology_mismatch, model_input_not_supported | temperature transform only after T is known | yes |
| 4 | Parviainen 2005 | Ld_h | 0.055 H, inverter estimate | approved DSSR Ld -> scalar phase-L bridge | inductance_structure_mismatch, topology_mismatch | source already explicit | yes |
| 4 | Parviainen 2005 | Lq_h | 0.060 H, inverter estimate | approved DSSR Lq -> scalar phase-L bridge | inductance_structure_mismatch, topology_mismatch | source already explicit | yes |
| 5 | Parviainen 2005 | efficiency_percent | 89.2%, steady state, natural convection/radiation | exact matched powers, temperatures, loss decomposition | operating_point_incomplete, topology_mismatch, model_input_not_supported | more curve extraction cannot fix model | yes |
| 1 | Hosseini 2008 | back_emf_no_load_peak_to_peak_v | complete diameters/gap/coil height/Br/mu, p=12, 160 V phase Vpp | turns/phase, interconnection, kw, leakage/pole-arc semantics | missing_turns, missing_winding_connection, ambiguous_peak_rms, nonsinusoidal_waveform, model_input_not_supported | source gives conductors/coil, not safe turns | yes |
| 1 | Hosseini 2008 | output_voltage_fundamental_peak_to_peak_v | 102 V fundamental phase Vpp, 3000 rpm, 10-ohm load | winding mapping and loaded-terminal-voltage model | missing_turns, missing_winding_connection, ambiguous_peak_rms, operating_point_incomplete | fundamental conversion does not fix quantity scope | yes |
| 5 | Hosseini 2008 | efficiency_percent | 78.1%, 390 W, 40 V phase, 3.6 A phase, 3000 rpm | current RMS/peak, connection, input/loss boundary | current_basis_unknown, operating_point_incomplete, model_input_not_supported | source cannot resolve basis | yes |
| 4 | Hosseini 2008 | Xsd_ohm | 2.1 ohm at 300 Hz -> Ld=0.0011140846 H | production Ld output or approved scalar bridge | inductance_structure_mismatch | axis-preserving transform recovered | yes |
| 4 | Hosseini 2008 | Xsq_ohm | 2.1 ohm at 300 Hz -> Lq=0.0011140846 H | production Lq output or approved scalar bridge | inductance_structure_mismatch | axis-preserving transform recovered | yes |

## 不在 14 行内的访问问题

Bumby 2004 的 back-EMF/inductance rows 在 Phase 7B.1 已是 `UNAVAILABLE`，不是 `BLOCKED`，因此不计入上表。其数值全文仍为 `source_access_blocked`；摘要中的 5%/10% 不能代替 machine-level prediction/reference values。
