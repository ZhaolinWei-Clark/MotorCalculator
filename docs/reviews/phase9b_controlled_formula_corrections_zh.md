# Phase 9B — 受控公式修正实施记录

**仓库**：`D:\codex\Projects\MotorCalculator`
**起始分支/HEAD**：`codex/rc2-engineering-corrections` @ `e7e9556`（`707 passed`）
**工作分支**：`codex/phase9b-controlled-formula-corrections`
**版本**：`1.0.0-rc2`（**未提升**，按版本政策不提前 bump）
**回归**：`707 → 835 passed`

**`legacy_baseline.json` 全程冻结**，哈希始终为
`15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9`。

### 受保护 kernel 的批准变更链

| 阶段 | `calculations.py` SHA-256 | 说明 |
|---|---|---|
| 起点 | `416330175f2c770cd6e4c5c6e0df98e22eb7c290e3b5825926cc124642b87a2d` | v1.0.0-rc1 / rc2 冻结基线 |
| Batch B1 后 | `1609b2ee96ec93fa56a0af68ca4fe3eaea368807d70aa0e2078e7e18c72c1a14` | 谐波次数映射（仅显示） |
| Batch B2 后 | `032fe19062ba844f7ad12cf541d0ed6841050019fea9bb400f48ebd7b3b40970` | 自适应齿槽采样 + 解析峰值 |
| Batch C1 后 | `aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942` | 修正电压**并行**输出 |

变更链记录在 `motor_calculator/deployment/release.py` 的 `PROTECTED_FILE_HASHES` 上方，
6 处哈希门禁同步更新，`legacy_baseline.json` 门禁**从未改动**。

---

## Batch A — 零数值变化的标注

### 先前行为

| 项 | 标签 | 置信度 | 问题 |
|---|---|---|---|
| `eddy_loss_w` | `涡流损耗` | `empirical/model-limited` | 读起来像已验证的损耗预测 |
| `core_loss_w` | `铁芯损耗` | `empirical/model-limited` | 暗示定子铁损语义 |
| 速度扫描 | `…不是能力包络` | — | 措辞分散在三处，不一致 |

### 修正后行为

统一到新的 GUI 无关模块 `motor_core/loss_semantics.py`：

| 项 | 新标签 | 新状态码 |
|---|---|---|
| `eddy_loss_w` | `导体涡流损耗（实验性）` | `EXPERIMENTAL_SCALAR_AIRGAP_FIELD` |
| `core_loss_w` | `集总磁性损耗（额定点经验）` | `EMPIRICAL_LUMPED_RATED_POINT` |

**A1 限制说明（逐字统一）**：

> 实验性近似：使用单一气隙峰值磁密标量，并将其施加于包含端部绕组在内的全部铜体积；
> 未解析导体局部磁场分布、端部磁场衰减、电枢反应磁场、邻近效应与线股位置。
> 该项在中高速工况下可能主导效率估计。

**A2 限制说明**：

> 额定点经验集总项：按额定输出功率的固定比例取值，与转速和磁密完全解耦，
> 不是经过验证的定子铁芯损耗预测。无铁芯（coreless）拓扑下定子无铁，但转子背铁与磁钢
> 仍为铁磁/导电材料，其损耗既未建模也未与该项分离，因此该项不得被解读为可置零。

**A3 权威语句（逐字出现在扫描结果、每条派生曲线、图标题）**：

> 基于当前模型逐点重算，不是完整转矩-转速能力包络。

### 算法/基准

**无。Batch A 未改动任何方程。**

### 数值证据（零变化守卫）

测试 `test_batch_a_changes_no_loss_number` 以 `==`（非 approx）钉住：

| 设计 | copper_loss_w | eddy_loss_w | core_loss_w | mechanical_loss_w | input_power_w | efficiency_percent |
|---|---:|---:|---:|---:|---:|---:|
| application default | 39.53646488447724 | 18.93992541043538 | 8.0 | 3.5122759932001975 | 869.9886662881128 | 91.95522091262109 |
| 可制造性起始示例 | 16.789919517415793 | 44.59924272582511 | 6.0 | 2.3219444123047914 | 669.7111066555457 | 89.59086896383214 |

### 出现位置

仪表板损耗页、详细结果报告、机器可读导出（`eddy_loss_model_status` /
`core_loss_model_status` / `*_limitation_zh`）、`docs/releases/v1.0.0-rc2_capability_matrix_zh.md`。

### 兼容性影响

**无数值影响。** 两处 Phase 8H 守卫更新为新的权威语句常量
`SPEED_SWEEP_SCOPE_STATEMENT_ZH`。

### 遗留限制

两项损耗的**物理模型完全未变**，仍是 Phase 9 判定的 `MODEL_LIMITATION`。

---

## Batch B1 — 谐波次数映射（PRESENTATION_DEFECT）

### 先前行为

```python
harmonics = np.arange(len(spectrum)) * pole_count / 2.0    # = k * pole_pairs
```

### 基准推导

`mechanical_angle_deg` 覆盖**一个机械周期**，故 FFT bin `k` = 每机械转 k 个周期。
电气基波位于 `k = pole_pairs`。因此：

```
机械阶次 = k
电气阶次 = k / pole_pairs
```

旧式写成 `k × pole_pairs`，**方向反了，误差因子 `pole_pairs²`**。

### 修正后算法

```python
mechanical_harmonic_order = np.arange(len(spectrum), dtype=float)
electrical_harmonic_order = mechanical_harmonic_order / float(i.pole_pairs)
# 返回三个键：mechanical_harmonic_order / electrical_harmonic_order / harmonics（= 电气阶次）
```

legacy `harmonics` 键**就地修正**——`k×p` 既不是电气阶次也不是机械阶次，
从无可辩护语义，且不出现在 `legacy_baseline.json`、任何导出或项目快照中。

legacy 绘图改读电气阶次，轴标签改为 `电气空间谐波次数（基波 = 1）`。

### 数值证据

**分解本身未动**（解析参考 `4/π·B_pk·sin(πα/2)`）：

| p | 基波 bin k | \|A_k\| | 解析值 | 比值 |
|---:|---:|---:|---:|---:|
| 2 | 2 | 0.7712059752265177 | 0.770353 | 1.0011 |
| 4 | 4 | 0.7712205623786551 | 0.770353 | 1.0011 |
| 8 | 8 | 0.7710732901134528 | 0.770353 | 1.0009 |

**`Bg_avg` / `Bg_rms` 逐位不变**：`0.47627468317123495` / `0.5686932270130303`。

**修正的具体缺陷**（绘图过滤 `order ≤ 25`）：

| p | 旧映射绘出柱数 | 基波是否在图上 | 新映射基波是否在图上 |
|---:|---:|---|---|
| 2 | 13 | 是 | 是 |
| 4 | 7 | 是 | 是 |
| **8** | **4** | **否** | **是** |

### 兼容性影响

**LOW。** `harmonics` 不被基线锚定、不进导出、不进快照。端点采样**本批未动**
（仍为 720 点含重复端点），这是刻意保留的独立决策。

### 遗留限制

端点重复导致的轻微谱泄漏（边带约 1.5%）**未修**——修它会改动已锚定的
`bg_avg_t` / `bg_rms_t`，风险高于收益。

---

## Batch B2 — 自适应齿槽采样（CONFIRMED_NUMERICAL_DEFECT）

### 先前行为

```python
rotor_position_rad = np.linspace(0.0, 2.0 * PI, 360)      # 固定 360 点
cogging_torque_peak_nm = np.max(np.abs(cogging_torque_nm))
```

### 采样规则的完整再推导

波形为 `sin(Nθ) + 0.3·sin(2Nθ) + 0.1·sin(3Nθ)`，`N = LCM(2p, Q)` 周/机械转。

```
最高表示阶次   H = 3 · N
有效采样率     f_s = n − 1        （linspace 端点重复）
严格 Nyquist   n − 1 > 2H
渲染保真       n − 1 ≥ S · H
```

`S = 8` 由实测扫描选定：

| n | 最坏峰值误差 | 最坏 RMS 误差 |
|---|---:|---:|
| `4H + 1` | 0.22590 % | 0.08668 % |
| **`8H + 1`** | **0.22590 %** | **0.04336 %** |
| `12H + 1` | 0.22590 % | 0.02891 % |

峰值误差在 `S ≥ 4` 后不再改善（离散采样对峰值位置的固有下限），
故取 `S = 8`（RMS 显著改善，成本可接受）。

### 最终规则

```python
COGGING_HIGHEST_HARMONIC_MULTIPLE = 3
COGGING_SAMPLES_PER_HIGHEST_CYCLE = 8
COGGING_MINIMUM_INTERVALS         = 359        # 保持旧密度下限
COGGING_MAXIMUM_SAMPLES           = 200_001    # 稳定性/内存上限
COGGING_SHAPE_PEAK_FACTOR         = 1.1283820906416413

intervals = max(359, 8 * 3 * LCM(2p, Q))
n         = min(intervals + 1, 200_001)
```

**端点重复保留**（闭合曲线便于绘图），但 Nyquist 判据显式写在 `n − 1` 上，
不再是"360 点其实只有 359 间隔"的隐含陷阱。

### 为什么旧网格的峰值看起来是对的 —— 一个数论巧合

```
linspace(0, 2π, 360) → 359 个间隔，359 是素数
θ_j = 2π·j/359
sin(LCM·θ_j) = sin(2π·(LCM·j mod 359)/359)
359 素数且 LCM % 359 ≠ 0 ⇒ j ↦ (LCM·j mod 359) 是 0..358 上的双射
三个分量在同一 j 求值 ⇒ (LCM·j, 2LCM·j, 3LCM·j) mod 359 = (i, 2i, 3i) mod 359
⇒ 采样序列是正确序列的一个置换 ⇒ max|·| 置换不变 ⇒ 峰值精确
```

**这是巧合而非设计**：

| n | 间隔数 | 素数? | 最坏峰值误差 |
|---:|---:|---|---:|
| **360** | 359 | 是 | −0.0000 % |
| 361 | 360 | 否 | **−100.0000 %** |
| 721 | 720 | 否 | **−100.0000 %** |
| 401 | 400 | 否 | −5.2968 % |

### 数值证据

| 案例 | 2p | Q | LCM | 3·LCM | 旧 n | 旧 Nyquist | 新 n |
|---|---:|---:|---:|---:|---:|---|---:|
| low_lcm | 20 | 12 | 60 | 180 | 360 | ❌ | 1441 |
| medium_lcm | 16 | 24 | 48 | 144 | 360 | ✅ | 1153 |
| previously_aliased | 20 | 48 | 240 | 720 | 360 | ❌ | 5761 |
| high_lcm | 40 | 27 | 1080 | 3240 | 360 | ❌ | 25921 |
| capped | 100 | 99 | 9900 | 29700 | 360 | ❌ | 200001（封顶） |

**绘图混叠已解决**：`2p=20 / Q=48` 旧网格上符号变化 239 次（物理应为 480，混叠因子 0.498），
新网格恢复到 `≈ 2·LCM`。

**峰值改为解析**：`cogging_torque_peak_nm = 1.1283820906416413 × k_cogging × T_ref`，
完全脱离采样。

### 运行时影响（实测中位数，完整静态分析）

| 案例 | n | 中位耗时 | 相对最小案例 |
|---|---:|---:|---:|
| low_lcm | 1441 | 0.707 ms | +0.0 % |
| medium_lcm | 1153 | 0.738 ms | +4.4 % |
| previously_aliased | 5761 | 0.994 ms | +40.6 % |
| high_lcm | 25921 | 2.141 ms | +202.9 % |
| capped_pathological | 200001 | 10.288 ms | +1355.3 % |

Phase 8I 记录的默认静态计算预算为 **117 ms**，故最坏情况新增约 **9%**，可接受。

### 齿槽比值语义（Decision 1，仅新增输出）

**legacy `k_cogging` 输入语义未被重定义。** 新增输出：

| 键 | 定义 | 与 legacy 的关系 |
|---|---|---|
| `k_cogging_fundamental` | 基波分量幅值 / 参考转矩 | **等于** legacy `k_cogging`（它一直就是这个） |
| `k_cogging_peak` | 峰值绝对齿槽转矩 / 参考转矩 | `= 1.1283820906416413 × k_cogging` |
| `legacy_k_cogging` | 原始输入值 | 逐位保留 |
| `k_cogging_semantics_status` | `legacy_k_cogging_equals_fundamental_amplitude_ratio` | 显式声明 |

### 兼容性影响

**LOW。** 齿槽波形与峰值**均未被 `legacy_baseline.json` 锚定**。
`cogging_torque_peak_nm` 从采样最大值改为解析值，变化约 **+4.3e-7 相对**（旧值本就巧合地精确）。

### 遗留限制

齿槽**幅值**仍由用户系数给定，**不是物理预测**。`0.3 / 0.1` 的谐波权重是模型内的固定假设。

---

## Batch C1 — 修正所需电压（强制并行输出）

### 先前行为

```python
required_voltage_v = sqrt(E_line_rms² + (I_ph·R_line)² + (I_ph·ω_e·L_s)²) × 1.05
```

### C1.1 完整基准重构

以可制造性起始示例（`V_dc=72, P=600 W, n=2200 rpm`）实测：

| 量 | 值 | 相/线 | RMS/峰值 |
|---|---:|---|---|
| `I_ph` | 9.816717 A | **相** | **RMS** |
| `E_ph` | 20.374910 V | **相** | **RMS** |
| `E_line` | 35.290379 V | **线** | **RMS**（`= √3·E_ph`，实测比 1.732051） |
| `R_ph` | 0.058076 Ω | **相** | — |
| `R_line` | 0.116151 Ω | **端子（2×相）** | — （实测比 2.000000，**不是 √3**） |
| `L_ph` | 993.1289 µH | **相** | — |
| `line_inductance_h` | 1142.0983 µH | **相（同步）** | — （实测比 1.150000 = `L_ph − M`） |
| `ω_e` | 1843.0677 rad/s | — | — |

**旧式三项的实际基准**：

| 项 | 值 | 相对每相的倍数 |
|---|---:|---|
| `E_line_rms` | 35.290379 V | **√3×** ✅ |
| `I·R_line` | 1.140226 V | **2×** ❌ |
| `I·ω_e·L_s` | 20.663841 V | **1×** ❌ |

统一到线基准应为：项2 `√3·I·R_ph = 0.987465 V`（旧式是 1.1547 倍）；
项3 `√3·I·ω_e·L_s = 35.790823 V`（旧式是 0.5774 倍，**偏小 42.3%**）。

### C1.1 修正后的单一基准

```
back_emf   : phase_rms_volt
current    : phase_rms_ampere
resistance : phase_ohm
inductance : phase_synchronous_henry
result     : line_rms_volt
```

**每一项输入都是每相 RMS 量，仅在最后统一乘 √3。**

### C1.2 修正方程

```
V_required_line_rms = √3 · √( (E_ph_rms + I_ph_rms·R_ph)² + (I_ph_rms·ω_e·L_s)² ) · k_margin

L_s       = phase_inductance_h − mutual_inductance_h
k_margin  = VOLTAGE_REQUIREMENT_MARGIN_FACTOR = 1.05（与 legacy 共用）
```

`id = 0` 是模型自身的假设（额定电流由 `T_rated / K_t` 得到，全部电流被视为转矩电流），
故 `E_ph` 与 `I·R_ph` **同相代数相加**，只有 `jω_e·L_s·I` 正交。

### C1.5 dq 等价性（未创建第三条公式）

由 Phase 6 `PMSMDynamicModel.compute_electrical_derivatives` 令 `did/dt = diq/dt = 0`、`id = 0`：

```
v_d = −ω_e·L_q·i_q
v_q =  R_s·i_q + ω_e·ψ_f
|V_dq| = hypot(v_d, v_q)                      ← 幅值不变 Park ⇒ 相峰值
V_line_rms = |V_dq|/√2 · √3 · k_margin,   i_q = √2·I_ph_rms
```

`dynamics/inverter.py` 的包络 `V_dc/√3` 作用于 `hypot(v_d, v_q)`，确认为幅值不变（峰值）约定。

**实测结果**：

```
ψ_f = Kt_peak/(1.5p) = 0.01563397 Wb
ω_e·ψ_f = 28.814474 V  vs  √2·E_ph = 28.814474 V        比值 1.000000 ✅

相量式 = 53.509476885063116 V
dq 式  = 53.509476885063116 V        |差| = 0.000e+00   ✅ 逐位相同
```

测试容差 `1e-12` 相对，实测为 0。

### C1.3 并行结果

| 键 | 含义 | 状态 |
|---|---|---|
| `required_voltage_v` | legacy 混合基准 RSS | **逐位不变，仍为生产默认** |
| `voltage_margin_percent` | legacy 同基裕量 | **逐位不变，仍驱动严重度判据** |
| `required_voltage_line_rms_corrected_v` | 修正单一基准相量值 | 新增并行 |
| `required_voltage_legacy_corrected_relative_difference` | `corrected/legacy − 1` | 新增 |
| `required_voltage_corrected_status` | `corrected_single_basis_steady_state_phasor` | 新增 |
| `DesignFeasibilityAssessment.corrected_voltage_margin_percent` | 修正同基裕量 | 新增并行 |

**BLDC**：修正值为 `None`，状态 `not_applicable_non_sinusoidal_control_mode`。

两个参考设计：

| 设计 | legacy V | 修正 V | 相对差 | legacy 裕量 | 修正裕量 |
|---|---:|---:|---:|---:|---:|
| 可制造性起始示例 | 42.9565 | 53.5095 | +24.567 % | +15.6255 % | **−5.1025 %** |
| application default | 51.5178 | 66.6719 | +29.415 % | −51.7858 % | −96.4339 % |

### C1.4 受控对比活动

确定性网格 **180 点**：转速 `{1200, 1800, 2200, 2800, 3400}` × 功率 `{200, 600, 1200}`
× `k_w {0.85, 0.93}` × 匝数 `{35, 51, 70}` × 线径 `{1.0, 1.2}`。

> **这些是该网格上的抽样统计，不是电机总体的population statistics。**

| 指标 | min | median | max |
|---|---:|---:|---:|
| 绝对差 | 0.8471 V | 11.3753 V | 47.7953 V |
| 相对差 | 1.8276 % | 28.1286 % | 66.8746 % |
| 裕量差 | −93.8789 pp | −22.3433 pp | −1.6639 pp |

```
符号变化（corrected < legacy）      : 0
可行性翻转 OK → NOT OK              : 36
两者均可行                          : 70
两者均不可行                        : 74
反向翻转 NOT OK → OK                : 0（测试断言不可能发生）
```

### C1.6 下游消费者清单

| 消费者 | 分类 | 说明 |
|---|---|---|
| feasibility | `DUAL_DISPLAY` | 同时给出两个裕量；严重度判据仍由 legacy 驱动 |
| optimizer | `NEEDS_REVIEW` | RC2 已同基化包络，但输入仍为 legacy 电压；C2 以对比模式评估 |
| dashboard | `DUAL_DISPLAY` | 所需电压与裕量均并列展示 |
| plots | `NEEDS_REVIEW` | 扫描曲线暂不加第二条线，避免同图两种基准 |
| exports | `DUAL_DISPLAY` | 显式不同键名，legacy 键语义不变 |
| reports | `DUAL_DISPLAY` | 详细摘要列出两者与相对差 |
| presets | `NEEDS_REVIEW` | v1 在修正基准下为负；C3 准备并行候选 v2 |
| project_snapshots | `LEGACY_KEEP` | 快照存 `to_dict()`，新增字段自动包含；输入哈希与 schema 不变 |
| uncertainty | `LEGACY_KEEP` | 不消费所需电压 |
| sensitivity | `LEGACY_KEEP` | 复用完整结果对象 |

**测试断言：目前没有任何消费者被标为 `MIGRATE_TO_CORRECTED`。**

### 兼容性影响

**MEDIUM。** `legacy_baseline.json` 锚定 `required_voltage_v`
（`49.95207924850739` / `15.026245524087711` / `110.66855045604889`）——
因为采用并行输出，这三个值**逐位不变**，回归自动通过。
`PROJECT_INPUT_SPECS`、解析参数键集合、项目输入哈希、schema 版本**均未变**。

### 遗留限制

- 修正式仍假设 `id = 0`、`L_d = L_q`、无饱和、无谐波、稳态。
- `line_resistance_ohm` / `line_inductance_h` 的**命名**仍误导（提案 C2 项），本批未改名以免扩大改动面。
- `analysis_service.py:168` 的 dq 桥接仍用 `L_ph` 而非 `L_s`——**第三处基准不一致，本批未动**。

---

## Batch C2 — 优化器对比模式

**legacy `run_optimization` 未修改、未删除。** 新增只读模块
`validation/optimizer_comparison.py`，精确镜像其评分规则并对两种电压基准各评估一次。

| 项 | legacy 路径 | 修正路径 |
|---|---|---|
| 同基包络 | 50.9117 V | 50.9117 V（相同） |
| 接受 / 拒绝 | 15 / 20 | 11 / 24 |
| 仅本路径接受的匝数 | **48, 51, 54, 57** | 无 |
| 排序 top-5 | (51, 48, 45, 42, 39) | (39, 42, 45, 30, 27) |
| 推荐 | `N=51, n_par=2` | `N=39, n_par=2` |
| 推荐 V_req | 43.8150 V | 41.9001 V |
| 推荐裕量 | +13.9393 % | +17.7005 % |
| 推荐 J | 4.2548 A/mm² | 5.5640 A/mm² |
| 推荐槽占比 | 0.3240 | 0.2478 |
| 推荐效率 | 89.5156 % | 90.2751 % |

**legacy 推荐的 `N=51` 在修正基准下不可行**（测试直接断言）。
另有测试断言 legacy 优化器源码仍含 RC2 的同基包络修正，且**未**引入 C1 修正量。

---

## Batch C3 — 修正基准下的起始预设候选

`design.manufacturability_start.v1` **逐字节不变**，且**仍是启动默认**。
新增并行候选 `design.manufacturability_start.v2`。

| 项 | 值 |
|---|---|
| `V_dc` | 72.0 V |
| 额定功率 | 600.0 W |
| 额定转速 | 1800.0 rpm |
| 每相匝数 | 42 |
| 导线直径 | 1.2 mm |
| 并联支路 | 3 |
| 绕组系数 `k_w` | 0.93 |
| 槽型 / 无铁芯 | 半闭口槽 / 否 |
| **转矩** | **3.1833 N·m** |
| **电流密度** | **4.2098 A/mm²** |
| **近似裸铜槽占比** | **0.4003** |
| **legacy 所需电压** | **31.3318 V** |
| **修正所需电压** | **41.0951 V** |
| **legacy 同基裕量** | **38.4586 %** |
| **修正同基裕量** | **19.2815 %** |
| **效率（当前损耗模型）** | **90.1726 %** |
| 相电流 RMS | 14.2836 A |

**目标达成情况**：无 ERROR ✅、无 SEVERE ✅、无 WARNING ✅、
`J ≤ 5 A/mm²` ✅（4.21）、槽占比保守区 ✅（0.400 < 0.50）、
修正裕量 `≥ 10–15%` ✅（19.28%）、几何有效 ✅、转矩/功率/转速合理 ✅。

**未放宽任何校验器**：`DEFAULT_FILL_LIMIT` 仍为 0.65；v2 是以余量通过
6 A/mm² 与 0.50 占比的指导带，而不是靠移动阈值。

---

## 电压推广门禁状态

| # | 门禁 | 状态 | 证据 |
|---|---|---|---|
| 1 | 确定性参考测试 PASS | ✅ | `test_phase9b_c1_corrected_voltage.py` 20 项 |
| 2 | 量纲/基准审计 PASS | ✅ | C1.1 基准表；测试断言五项基准描述符 |
| 3 | dq 稳态交叉验证 PASS | ✅ | 逐位相同，`|差| = 0.000e+00`，容差 1e-12 |
| 4 | 速度/电流扫描对比完成 | ✅ | 180 点网格，统计见 C1.4 |
| 5 | 预设重新评估完成 | ✅ | v1 修正裕量 −5.10%；v2 候选 +19.28% |
| 6 | 优化器重新评估完成 | ✅ | C2 对比模式，推荐由 N=51 变为 N=39 |
| 7 | 可行性行为已审查 | ✅ | `DUAL_DISPLAY`，严重度仍由 legacy 驱动 |
| 8 | 仪表板/导出已审查 | ✅ | 两个值并列，键名显式不同 |
| 9 | 项目快照兼容性已审查 | ✅ | 输入哈希、schema 版本、参数键集合均未变 |
| 10 | 无未解释回归 | ✅ | 835 passed；`legacy_baseline.json` 冻结 |

**10/10 技术门禁通过。** 但按 Decision 2，**推广为默认仍需显式批准**，本阶段不执行。

---

## 明确推迟（未实施）

| 项 | 状态 |
|---|---|
| coreless 铁损/集总磁性损耗的**数值**修正 | **推迟**，等待实测损耗分解 |
| 导体涡流损耗的**数值**修正 | **推迟**，等待局部场信息 |
| 谐波频谱端点采样 `endpoint=False` | **推迟**，会改动已锚定的 `bg_avg_t` / `bg_rms_t` |
| `line_resistance_ohm` / `line_inductance_h` 改名 | **推迟**，避免扩大本批改动面 |
| `analysis_service.py` dq 桥接 `Ld=Lq` 改用 `L_s` | **推迟**，需独立批准（会改变动态仿真结果） |
| 修正电压推广为默认 | **推迟**，需显式批准 |
| 版本提升到 `1.0.0-rc3` | **推迟**，按版本政策 |

**未发明任何修正系数。**

---

## 提交序列

```
39652b0  docs: record the phase 9 formula change approval proposal
8aaf2db  feat: label experimental and empirical loss terms without changing any number
e4d966e  fix:  map magnetic-density harmonics to the electrical order
41bdeb8  fix:  derive the cogging sample grid from the represented spatial content
fac9de2  feat: publish the corrected required voltage as a mandatory parallel output
9892478  feat: add optimizer comparison mode and a corrected-basis starting candidate
(本文档) docs: document phase 9b controlled formula corrections
```
