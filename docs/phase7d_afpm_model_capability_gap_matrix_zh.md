# Phase 7D AFPM Model Capability Gap Matrix

## 边界

本文件是设计提案，不实现 enum/dataclass，不修改 production equations、default outputs 或 GUI。分类如下：

- A：schema limitation
- B：geometry-model limitation
- C：winding-model limitation
- D：electromagnetic-model limitation
- E：output-semantics limitation
- F：loss/mechanical boundary limitation

## 14 个 BLOCKED Rows

| source | metric | source representation | current model representation | mismatch | class |
|---|---|---|---|---|---|
| Abdelli 2026 | back_emf_phase_waveform | DSSR, open-slot tooth coils, measured/FEA harmonic plots | default SSDR scalar flux, scalar `kw`, sinusoidal PMSM scalar output | topology、turns/connection、graph-only output、waveform 与 scalar magnetic model 不兼容 | A/B/C/D/E |
| Abdelli 2026 | torque_nm | DSSR measured/FEA torque-current sweep at 1000 rpm | rated torque from power/speed; no source-current electromagnetic operating-point API | topology、operating point 和 torque-current model boundary 不兼容 | A/D/E/F |
| Price 2009 | back_emf_phase_peak_v | SSDR/coreless, Y, 108 turns/phase, measured sinusoidal phase peak | SSDR-compatible class but requires scalar Br、gap、pole arc、leakage、kw | missing source physics inputs plus radius-dependent rectangular geometry | B/C/D |
| Price 2009 | torque_nm | 10 A phase RMS, 12.6 Nm measured average shaft torque | electromagnetic Kt derives from modeled back-EMF; shaft loss torque not explicit | electromagnetic/shaft boundary and missing magnetic prediction | D/E/F |
| Parviainen 2005 | back_emf_phase_rms_v | DSSR, star stators in parallel, sinusoidal-planform magnets, flattened measured phase waveform | SSDR, one phase winding, scalar pole arc/leakage/kw, sinusoidal scalar RMS/peak | topology、magnet geometry、waveform 和 winding network mismatch | A/B/C/D/E |
| Parviainen 2005 | phase_resistance_ohm | 3.7 ohm DC per-stator phase; two stators parallel; temperature unstated | one scalar phase resistance from one winding geometry and coil temperature | terminal network、temperature 和 conductor/end-turn representation mismatch | A/C/F |
| Parviainen 2005 | Ld_h | inverter-estimated d-axis synchronous inductance | scalar phase self-inductance plus fixed mutual reduction | axis quantity cannot map to scalar output | A/D/E |
| Parviainen 2005 | Lq_h | inverter-estimated q-axis synchronous inductance | scalar phase self-inductance plus fixed mutual reduction | axis quantity cannot map to scalar output | A/D/E |
| Parviainen 2005 | efficiency_percent | measured motor efficiency under natural cooling | empirical production losses on default topology and rated chain | topology、operating point、cooling/loss boundary mismatch | A/D/F |
| Hosseini 2008 | back_emf_no_load_peak_to_peak_v | SSDR/coreless, rectangular magnets, harmonic phase Vpp | scalar sinusoidal PMSM RMS/peak or provisional BLDC scalar | turns/connection、radius-dependent magnet arc、harmonic Vpp semantics mismatch | B/C/D/E |
| Hosseini 2008 | output_voltage_fundamental_peak_to_peak_v | loaded terminal fundamental Vpp under 10-ohm load | no-load modeled back-EMF; no generator/load terminal equation | winding network and quantity boundary mismatch | A/C/D/E |
| Hosseini 2008 | efficiency_percent | nominal generator output, phase V/I with unknown current basis | motor-oriented rated chain and empirical loss model | current/terminal semantics and generator loss boundary mismatch | A/D/E/F |
| Hosseini 2008 | Xsd_ohm | d-axis synchronous reactance at 300 Hz; safely derived Ld | scalar phase inductance | Ld output/model absent | A/D/E |
| Hosseini 2008 | Xsq_ohm | q-axis synchronous reactance at 300 Hz; safely derived Lq | scalar phase inductance | Lq output/model absent | A/D/E |

## Topology Representation Proposal

建议未来新增 opt-in、与 `MotorAnalysisInput` 分离的 `AFPMTopologySpec`：

```python
class AFPMTopologyType(Enum):
    SSDR = "single_stator_double_rotor"
    DSSR = "double_stator_single_rotor"
    SINGLE_SIDED = "single_stator_single_rotor"

@dataclass(frozen=True)
class AFPMTopologySpec:
    topology_type: AFPMTopologyType
    stator_count: int
    rotor_count: int
    active_air_gap_count: int
    winding_placement: tuple[str, ...]
    magnet_placement: tuple[str, ...]
    flux_path_interpretation: str
    stator_electrical_interconnection: str | None
```

| topology | stators | rotors | active gaps | winding placement | magnet placement | flux path interpretation |
|---|---:|---:|---:|---|---|---|
| SSDR | 1 | 2 | 2 | central stator | inward faces of both rotors | flux crosses rotor-gap-stator-gap-rotor; coreless/slotted variant must be explicit |
| DSSR | 2 | 1 | 2 | one winding system per outer stator | both faces of central rotor | each rotor face couples to its adjacent stator; stator series/parallel network is explicit |
| SINGLE_SIDED | 1 | 1 | 1 | one stator | facing surface of one rotor | one active gap with a separate return-yoke interpretation |

禁止由 `stator_count` 自动推断 series/parallel connection，也禁止把 topology 转换成隐藏倍率。

## Geometry Representation Proposal

建议 `AFPMAnnulusGeometry` 显式保存 `inner_radius_m`、`outer_radius_m`、`mean_radius_m`（派生）、各 active gap、disc count 和 magnet shape：

- `SCALAR_ARC_RATIO`：仅用于来源确实给出 radius-independent pole arc。
- `RADIUS_DEPENDENT_WIDTH`：保存 `magnet_width_m(r)` 的来源参数或 samples，不自动拟合。
- `POLYGON_OR_PROFILE`：保存来源轮廓 metadata；没有物理积分器时不可生成 flux。
- `SOURCE_ONLY`：只用于 comparability，明确当前模型不能求解。

当前公式的关键限制：

- `calculate_magnetic_circuit()` 用一个 `pole_arc_coefficient` 乘整个 active annulus pole area，假设 pole arc 对半径不变。
- turn/end-winding length 用 average diameter 和 mean-radius pole pitch。
- scalar inductance 用 active annulus 的 1/6 与统一 effective gap。
- back-EMF waveform 用同一个 pole arc 控制梯形区间，不能表示 Price/Hosseini 的 radius-dependent rectangular magnets 或 Parviainen sinusoidal planform。

## Winding Representation Proposal

建议 `AFPMWindingSpec`：

```text
turns_per_coil
coils_per_phase
series_coils_per_phase
parallel_branches
turns_per_phase (derived only when topology is explicit)
connection: Y / DELTA / OPEN / SOURCE_DEFINED
winding_type: concentrated / distributed / lap / source_defined
pitch_factor
distribution_factor
source_equivalent_winding_factor
stator_winding_interconnection
```

分类：

- 直接可由现有模型消费：`turns_per_phase`、`parallel_branches`、一个明确且来源等价的 `winding_factor`。
- 需要新公式支持：从 coil layout 计算 pitch/distribution factor、多 stator series/parallel network、radius-dependent coil span。
- metadata only：concentrated/distributed/lap 标签；没有几何和公式时不得自动生成 `kw`。
- `conductors_per_coil` 不等于 `turns_per_coil`，除非来源明确其定义。

## Back-EMF Representation Proposal

建议独立 `BackEMFRepresentation`：

1. `SINUSOIDAL_SCALAR`：phase peak/RMS、line RMS 可用严格正弦关系转换。
2. `HARMONIC_SPECTRUM`：fundamental RMS 与显式 harmonic amplitudes；只接受模型或来源提供的谐波。
3. `WAVEFORM_SAMPLES`：`electrical_angle_rad[]`、phase samples、sample provenance；从 samples 数值计算 native peak/RMS/fundamental。

候选输出：`phase_peak_v`、`phase_rms_v`、`line_rms_v`、`fundamental_phase_rms_v`、`harmonic_amplitudes_v`、`waveform_samples`。未知谐波不得合成；只有 scalar magnetic physics 时，advanced mode 必须返回 `waveform_prediction_unavailable`，而不是生成看似合理的波形。

## Inductance Representation Proposal

迁移目标是 optional extended result，不替换现有 `phase_inductance_h`：

```text
scalar_phase_inductance_h: optional
ld_h: optional
lq_h: optional
mutual_inductance_h: optional
inductance_matrix_h: future optional
quantity_basis / measurement_frequency / provenance
```

兼容规则：旧模式继续只产生 scalar phase/line/mutual 值；advanced mode 可产生 Ld/Lq。`Ld == Lq` 也不自动等于 scalar phase inductance，除非经独立批准的模型桥。reactance-to-inductance 只保留 axis 与 frequency semantics。

## Torque Boundary Proposal

建议 `TorqueQuantityType`：`ELECTROMAGNETIC`、`SHAFT`、`LOAD`、`COGGING`、`MECHANICAL_LOSS`，并保存 motor/generator quadrant。

电动状态仅在 mechanical-loss torque 明确可得时使用：

`T_shaft = T_em - T_mechanical_loss`

发电状态的输入轴转矩符号/功率流必须单独定义，不能复用上述式子后忽略方向。Price 12.6 Nm 应继续标记 measured shaft torque，不能直接成为 electromagnetic Kt reference。
