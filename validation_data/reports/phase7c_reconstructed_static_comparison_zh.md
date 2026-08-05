# Phase 7C 重建静态比较报告

## 冻结边界

本报告仅加载逐字段来源重建记录并审计可比性。没有向缺失字段写入 production defaults，没有修改公式、参数、GUI、dynamic/controller chain 或 legacy baseline。

## 状态计数

- before: DIRECT=1, SAFE_TRANSFORM=0, APPROXIMATE=0, BLOCKED=14, UNAVAILABLE=6
- after: DIRECT=1, SAFE_TRANSFORM=0, APPROXIMATE=0, BLOCKED=14, UNAVAILABLE=6
- new DIRECT rows: 0
- new SAFE_TRANSFORM comparison rows: 0

没有新增 model prediction/reference pair。Phase 7C 恢复的是来源语义与模型能力边界，不把安全派生的 source field 冒充 production comparison。

## 新增 Reconstructed Comparison Rows

| source | metric | source-native semantics | reconstructed case | predicted | reference | absolute error | percentage error | comparability | provenance | uncertainty | remaining blockers |
|---|---|---|---|---:|---:|---:|---:|---|---|---|---|
| none | none | no source-compatible production prediction | four cases audited | unavailable | unavailable | unavailable | unavailable | BLOCKED | see case-level field provenance | source uncertainty retained | see blocker inventory |

## 已恢复但仍不可比较的量

| source | recovered item | result | remaining blocker |
|---|---|---|---|
| Price 2009 | current basis and torque boundary | 10 A phase RMS; 12.6 Nm measured average shaft torque; shaft ratio 1.26 Nm/A | production electromagnetic prediction and mechanical-loss torque are unavailable |
| Hosseini 2008 | Xsd/Xsq to axis inductance | Ld=Lq=0.00111408460164 H at 300 Hz | production predicts scalar phase inductance, not Ld/Lq |
| Parviainen 2005 | winding and voltage semantics | 840 turns per stator phase; star; parallel stators; 211 V phase RMS | DSSR topology, flattened waveform and source-specific magnet/leakage model |

## Blocker 明细

| source | metric | categories after | known fields | exact missing fields | approved transform | fundamentally blocked | resolution |
|---|---|---|---|---|---|---|---|
| abdelli_2026_dssr_afpm | back_emf_phase_waveform | missing_turns, missing_winding_connection, topology_mismatch, model_input_not_supported | 1000 rpm; 6 pole pairs; 245/140 mm active diameters; 1 mm gap; 10 mm magnet; measured/FEA plots | prototype turns-per-phase, connection, Br, winding factor, production-equivalent leakage and pole-arc semantics, tabulated voltage | None approved for graph-only harmonic waveform. | yes | No plot digitization performed; DSSR/open-slot tooth-coil physics remains outside the default SSDR model. |
| abdelli_2026_dssr_afpm | torque_nm | operating_point_incomplete, topology_mismatch, model_input_not_supported | 1000 rpm; current sweep 20-400 A; measured and FEA torque curves | authoritative point value, exact current/torque boundary for a selected point, source-compatible production topology | No safe transform produces a production torque-current prediction. | yes | Low-value digitization was rejected while Priority-1 back-EMF remains blocked. |
| price_2009_coreless_afpm_generator | back_emf_phase_peak_v | missing_geometry, model_input_not_supported | 600 rpm; Y; 108 turns/phase; 37 V measured phase peak; sinusoidal waveform; SSDR/coreless class | pole pairs, Br, magnet permeability, physical per-side gap, winding factor, leakage factor, scalar pole arc | Native phase peak requires no RMS conversion. | yes | The production magnetic model cannot be run without inventing material and scalar-factor inputs. |
| price_2009_coreless_afpm_generator | torque_nm | model_input_not_supported | 500 rpm; 10 A phase RMS; 12.6 Nm measured average shaft torque; three-phase Y; sinusoidal current | source-compatible electromagnetic torque prediction and quantified shaft mechanical-loss torque | 12.6/10 = 1.26 Nm/A is a shaft ratio, not production electromagnetic Kt. | yes | Two semantic blockers resolved; the remaining boundary/model gap prevents a comparison or Kt claim. |
| parviainen_2005_afpm_prototype | back_emf_phase_rms_v | nonsinusoidal_waveform, topology_mismatch, model_input_not_supported | 300 rpm; 6 pole pairs; 328/197 mm; 4 mm magnet; Br 1.05 T at 100 C; 840 turns/stator phase; star; 211 V phase RMS | production-equivalent coil height, leakage, winding factor, scalar pole arc and DSSR parallel-stator representation | No sqrt(2) conversion because Figure 3.6 shows flattened non-sinusoidal phase voltage. | yes | The remaining blockers are model/schema capability gaps, not merely missing headline metadata. |
| parviainen_2005_afpm_prototype | phase_resistance_ohm | temperature_unknown, topology_mismatch, model_input_not_supported | 3.7 ohm measured DC per-stator phase; 840 turns; star stator; stators parallel by default | measurement temperature, exact conductor area/parallel paths, source-compatible end-turn geometry | Copper temperature normalization is approved only after source temperature is known. | yes | The reported 3.7 ohm is retained without normalizing or treating two parallel stators as one production phase. |
| parviainen_2005_afpm_prototype | Ld_h | inductance_structure_mismatch, topology_mismatch | Ld=0.055 H estimated by inverter for the DSSR prototype | approved bridge from per-axis DSSR inductance to production scalar phase inductance | No axis-to-scalar conversion approved. | yes | This is a model input/output structure mismatch. |
| parviainen_2005_afpm_prototype | Lq_h | inductance_structure_mismatch, topology_mismatch | Lq=0.060 H estimated by inverter for the DSSR prototype | approved bridge from per-axis DSSR inductance to production scalar phase inductance | No axis-to-scalar conversion approved. | yes | This is a model input/output structure mismatch. |
| parviainen_2005_afpm_prototype | efficiency_percent | operating_point_incomplete, topology_mismatch, model_input_not_supported | 89.2% measured steady-state efficiency; natural convection and radiation; rated prototype context | matched electrical/mechanical powers, temperatures and loss decomposition for the exact point | No safe efficiency transformation. | yes | Loss and cooling boundaries remain incompatible. |
| hosseini_2008_coreless_afpm_generator | back_emf_no_load_peak_to_peak_v | missing_turns, missing_winding_connection, ambiguous_peak_rms, nonsinusoidal_waveform, model_input_not_supported | 3000 rpm; 12 pole pairs; complete active radii/gap/coil height/magnet Br and permeability; 160 V phase Vpp | turns per phase, series/parallel and terminal connection, winding factor, source-equivalent leakage and pole arc | No harmonic Vpp-to-RMS or Vpp-to-production-peak conversion approved. | yes | This is the strongest geometry case, but winding and waveform blockers remain decisive. |
| hosseini_2008_coreless_afpm_generator | output_voltage_fundamental_peak_to_peak_v | missing_turns, missing_winding_connection, ambiguous_peak_rms, operating_point_incomplete | 102 V phase Vpp fundamental at 3000 rpm under 10-ohm load | winding mapping and source-equivalent loaded-terminal-voltage model | A sinusoidal fundamental Vpp conversion is mathematically possible, but it would still be loaded terminal voltage, not no-load back-EMF. | yes | Quantity-scope mismatch remains even after isolating the fundamental. |
| hosseini_2008_coreless_afpm_generator | efficiency_percent | current_basis_unknown, operating_point_incomplete, model_input_not_supported | 78.1%; 390 W output; 40 V phase; 3.6 A phase; 3000 rpm | current RMS/peak basis, connection, complete input-power/loss boundary | No safe transform for unknown current basis. | yes | Efficiency remains lower priority than unresolved back-EMF. |
| hosseini_2008_coreless_afpm_generator | Xsd_ohm | inductance_structure_mismatch | Xsd=2.1 ohm and f=300 Hz; safely derived Ld=0.00111408460164 H | production Ld output or approved bridge to scalar phase inductance | Ld = Xsd/(2*pi*f), labelled SAFE_TRANSFORM field only. | yes | Unit/semantic reconstruction resolved; comparison remains blocked by production scalar-inductance structure. |
| hosseini_2008_coreless_afpm_generator | Xsq_ohm | inductance_structure_mismatch | Xsq=2.1 ohm and f=300 Hz; safely derived Lq=0.00111408460164 H | production Lq output or approved bridge to scalar phase inductance | Lq = Xsq/(2*pi*f), labelled SAFE_TRANSFORM field only. | yes | Unit/semantic reconstruction resolved; comparison remains blocked by production scalar-inductance structure. |

## 新增误差与诊断

无。没有新增 DIRECT/SAFE_TRANSFORM comparison，因此不存在可归因于 magnetic circuit、leakage/fringing 或 winding factor 的新数值误差。把 blocked 行计算成误差会混淆 source-data limitation 与 model-physics limitation。

## 决策

当前仍不能评估 production AFPM electromagnetic accuracy。下一步应优先获取一个 SSDR source 的 Br、physical per-side gap、series turns/phase、connection、winding factor/leakage definition 与 tabulated native back-EMF；或者先提出 Phase 7D schema/model capability proposal。没有多点外部 electromagnetic comparison，不建议 calibration。
