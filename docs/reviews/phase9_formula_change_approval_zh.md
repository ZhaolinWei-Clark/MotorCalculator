# Phase 9 — Formula Change Approval 提案

**仓库**：`D:\codex\Projects\MotorCalculator`
**分支**：`codex/rc2-engineering-corrections`
**HEAD**：`e7e9556`
**版本**：`1.0.0-rc2`
**回归基线**：`707 passed`
**受保护文件哈希**（提案编写前后均已核验，未变）：

```
motor_core/calculations.py        416330175f2c770cd6e4c5c6e0df98e22eb7c290e3b5825926cc124642b87a2d
legacy_baseline.json              15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9
```

**本文档只做判定与提案，未实施任何公式变更，未修改任何产品代码。**

---

## 0. 执行摘要

| # | 发现 | 判定 | 是否真正的公式缺陷 |
|---|---|---|---|
| 1 | `required_voltage_v` 基准混用 + RSS 合成 | `CONFIRMED_FORMULA_DEFECT` | **是** |
| 2 | coreless 仍计铁损 | `MODEL_LIMITATION` | 否 |
| 3 | 磁密谐波轴映射反向 | `PRESENTATION_DEFECT` | 否 |
| 4 | 齿槽 360 点固定采样 | `CONFIRMED_NUMERICAL_DEFECT` | 否（数值/可视化） |
| 5 | 导体涡流损耗用气隙峰值 B 覆盖全部铜体积 | `MODEL_LIMITATION` | 否 |

**五项中只有一项（Finding 1）是真正的公式缺陷。** 其余四项分别是模型局限、显示缺陷和数值采样缺陷。

**关键副作用**：Finding 1 的修正会推翻 RC2 的一个结论——RC2 优化器推荐的
`N_ph_turns=51` 设计在一致基准下同基裕量为 **−7.18%**，即**实际不可行**；
"可制造性起始示例" 本身在一致基准下也是 **−5.10%**。

---

## Finding 1 — `required_voltage_v` 参考基准不一致与 RSS 形式

### A. 当前实现

**文件**：`motor_calculator/motor_core/calculations.py`（**受保护**）
**函数**：`MotorAnalysisEngine.run_full_analysis`
**行**：557–563

```python
resistive_voltage_drop_v = phase_current_rms_a * electrical_result.line_resistance_ohm
electrical_frequency_hz  = mechanical_speed_rpm_to_electrical_frequency_hz(...)
inductive_voltage_drop_v = 2.0 * PI * electrical_frequency_hz * electrical_result.line_inductance_h * phase_current_rms_a
required_voltage_v = sqrt(
    electrical_result.back_emf_line_rms_v**2 + resistive_voltage_drop_v**2 + inductive_voltage_drop_v**2
) * VOLTAGE_REQUIREMENT_MARGIN_FACTOR          # = 1.05
```

相关定义（同文件 231–240 行）：

```python
line_resistance_ohm = 2.0 * phase_resistance_ohm
mutual_inductance_h = BALANCED_THREE_PHASE_MUTUAL_RATIO * phase_inductance_h * AFPM_MUTUAL_REDUCTION_FACTOR
                      # = (-0.5) * 0.3 * L_ph = -0.15 * L_ph
line_inductance_h   = phase_inductance_h - mutual_inductance_h        # = 1.15 * L_ph
```

### A2. 完整量纲基准重构（特殊要求）

以"可制造性起始示例"实测（`V_dc=72 V, P=600 W, n=2200 rpm`）：

| 量 | 符号 | 实测值 | 相/线 | RMS/峰值 | 备注 |
|---|---|---:|---|---|---|
| 相电流 | `I_ph` | 9.816717 A | **相** | **RMS** | Y 接，线电流 = 相电流 |
| 相反电动势 | `E_ph` | 20.374910 V | **相** | **RMS** | |
| 线反电动势 | `E_line` | 35.290379 V | **线** | **RMS** | `= √3·E_ph`，比值实测 1.732051 ✅ |
| 相电阻 | `R_ph` | 0.058076 Ω | **相** | — | |
| `line_resistance_ohm` | `R_line` | 0.116151 Ω | **端子间（2×相）** | — | 比值实测 2.000000。这是**端子直流电阻**，不是平衡三相的 √3 关系 |
| 相自感 | `L_ph` | 993.1289 µH | **相** | — | |
| `line_inductance_h` | `L_s` | 1142.0983 µH | **相（同步）** | — | 比值实测 1.150000 = `L_ph − M`。**命名为 "line" 但实为每相同步电感** |
| 电角频率 | `ω_e` | 1843.0677 rad/s | — | — | |

**三项相加时的实际基准**：

| 项 | 表达式 | 实测值 | 相对每相量的倍数 |
|---|---|---:|---|
| 1 | `E_line_rms` | 35.290379 V | **√3×** ✅ |
| 2 | `I_ph · R_line` | 1.140226 V | **2×** ❌ |
| 3 | `I_ph · ω_e · L_s` | 20.663841 V | **1×** ❌ |

若统一到线 RMS 基准，应为：

```
项2 应为 √3·I·R_ph = 0.987465 V   （现值是它的 1.1547 倍）
项3 应为 √3·I·ω_e·L_s = 35.790823 V   （现值是它的 0.5774 倍，即偏小 42.3%）
```

**结论：同一根式内混用了三种基准（√3×、2×、1×），且第三项——主导项——偏小 42.3%。**

### B. 缺陷分类

**`CONFIRMED_FORMULA_DEFECT`**

### C. 物理推理

**支配物理**：表贴式 PMSM 稳态、`id = 0`（模型隐含假设，因为 `I = T_rated / K_t`，全部电流被视为转矩电流）、正弦对称三相：

```
V̄_ph = Ē_ph + I̅·(R_ph + j·ω_e·L_s)
```

`Ē_ph` 与 `I̅` 在 `id=0` 时**同相**，故 `R_ph·I` 与 `E_ph` **代数相加**，只有 `jω_e L_s I` 正交：

```
|V_ph| = √( (E_ph + I·R_ph)² + (I·ω_e·L_s)² )
```

代码的 `√(E² + (IR)² + (IX)²)` 把三项当作**两两正交**，这在相量上不成立。

**量纲一致性**：三项均为 V，量纲无误。缺陷是**基准与相量代数**，不是量纲。

**相/线约定**：`E` 已是线 RMS；`R_line = 2R_ph` 是端子直流测量口径，与平衡三相相量的 `√3` 关系不同；`L_s` 是每相量。三者混用。

**RMS/峰值约定**：三项均为 RMS，无 RMS/峰值混用。**该维度无缺陷。**

**假设**：`id = 0`；`L_d = L_q = L_s`（表贴式无凸极）；忽略饱和与谐波；`VOLTAGE_REQUIREMENT_MARGIN_FACTOR = 1.05` 为工程裕量系数，与基准问题无关。

### C2. 与既有 dq 公式的交叉验证

`dynamics/pmsm_model.py:78-99` 的 dq 方程，稳态（`did/dt = diq/dt = 0`，`id = 0`）：

```
v_d = −ω_e · L_q · i_q
v_q =  R_s · i_q + ω_e · ψ_f
|V_dq| = √(v_d² + v_q²)          ← 幅值不变 Park，故 |V_dq| = 相峰值
```

`dynamics/inverter.py:55` 的包络为 `V_dc/√3` 作用于 `hypot(v_d, v_q)`，确认为**幅值不变（峰值）** 约定。
换算：`V_line_rms = |V_dq| · √3/√2`，包络 `V_dc/√3 · √3/√2 = V_dc/√2` ✅ 与 `design_feasibility` 一致。

**实测交叉验证**：

```
psi_f = Kt_peak/(1.5p) = 0.01563397 Wb
ω_e·psi_f = 28.814474 V   vs   √2·E_ph = 28.814474 V   比值 1.000000 ✅

[B] 相量式（L = L_s）  = 53.509477 V
[E] dq 稳态式（L = L_s）= 53.509477 V
|B − E| = 0.000000000 V   → 两者为同一公式 ✅
```

**提议的修正式与本项目自身的 dq 模型逐位一致**，这是最强的内部一致性证据。

> **附带发现（不在本提案的受保护范围内）**：`analysis_service.py:168` 的 dq 桥接使用
> `Ld = Lq = phase_inductance_h`（`L_ph`），而静态路径使用 `line_inductance_h`（`L_s = 1.15 L_ph`）。
> 物理上 dq 的 `L_d/L_q` 应为同步电感 `L_s`。这是**第三处**基准不一致，位于**非受保护文件**，
> 建议在同一批次内单独处理。

### D. 可复现数值探针

脚本位于 scratchpad（未写入仓库），全部为只读调用。

**速度扫描**（`P_rated = 600 W` 固定，`V_dc = 72 V`）：

| rpm | f_e Hz | I_ph A | legacy V | 相量(L_s) V | 相量(L_ph) V | Δ(L_s) % | legacy 裕量 % | 相量裕量 % |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 600 | 80.0 | 35.995 | 24.334 | 40.071 | 35.515 | **+64.67** | +52.20 | +21.29 |
| 1000 | 133.3 | 21.597 | 27.593 | 42.167 | 37.863 | +52.81 | +45.80 | +17.18 |
| 1400 | 186.7 | 15.426 | 32.099 | 45.253 | 41.272 | +40.98 | +36.95 | +11.12 |
| 1800 | 240.0 | 11.998 | 37.310 | 49.091 | 45.448 | +31.57 | +26.72 | +3.58 |
| **2200** | 293.3 | 9.817 | **42.956** | **53.509** | 50.188 | **+24.57** | **+15.63** | **−5.10** |
| 2600 | 346.7 | 8.306 | 48.883 | 58.375 | 55.347 | +19.42 | +3.98 | −14.66 |
| 3000 | 400.0 | 7.199 | 54.998 | 63.584 | 60.816 | +15.61 | −8.03 | −24.89 |
| 4400 | 586.7 | 4.908 | 77.223 | 83.556 | 81.469 | +8.20 | −51.68 | −64.12 |

**电流扫描**（`n = 2200 rpm` 固定）：

| P_W | I_ph A | legacy V | 相量(L_s) V | Δ % | legacy 裕量 % | 相量裕量 % |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 1.636 | 37.231 | 37.751 | +1.40 | +26.87 | +25.85 |
| 300 | 4.908 | 38.615 | 42.010 | +8.79 | +24.15 | +17.48 |
| 600 | 9.817 | 42.956 | 53.509 | +24.57 | +15.63 | −5.10 |
| 1200 | 19.633 | 57.113 | 84.736 | +48.37 | −12.18 | −66.44 |
| 2400 | 39.267 | 94.489 | 155.866 | +64.96 | −85.59 | −206.15 |

**符号一致性**：在 `400–5000 rpm × 200/600/1200/2000 W` 的 **96/96** 采样点上，
相量式结果**恒大于** legacy 式，最小相对差 **+0.907%**。
**legacy 式在整个工况域内单向非保守。**

**application default（48 V, 800 W, 2500 rpm, coreless）**：
legacy `51.5178 V` vs 相量 `66.6719 V`（**+29.42%**）；同基裕量 `−51.79%` → `−96.43%`。

### E. 影响分析

| 输出 | 是否受影响 |
|---|---|
| `required_voltage_v` | ✅ 直接改变 |
| `voltage_margin_percent`（legacy 与同基） | ✅ |
| 速度扫描电压曲线 / CSV | ✅ |
| 优化器候选接受与排序 | ✅ |
| `VOLTAGE_MARGIN_*` 可行性严重度码 | ✅ |
| 仪表板电压量程条、RC2 导出电压字段 | ✅ |
| legacy TXT/JSON/CSV 电压行 | ✅ |
| **转矩、电流、Ke/Kt、各项损耗、效率、电流密度、槽占比、磁路、波形、热、dq 动态** | ❌ **不受影响** |

**实测确认**：`required_voltage_v` 是**终端输出**，在 kernel 内不作为任何损耗/转矩项的输入
（转矩、电流、效率均在其之前计算完成）。**爆炸半径被限制在电压/可行性/优化器。**

**具体影响量化**：

- 优化器（同基包络 `50.9117 V`）：legacy `V_req` 接受 `N=15..57`（15 个）；相量 `V_req` 接受 `N=15..45`（11 个）。**legacy 仍多接受 4 个：`N = 48, 51, 54, 57`。**
- **RC2 推荐设计 `N=51, n_par=2`：legacy 裕量 `+13.94%` → 相量裕量 `−7.18%`，实际不可行。**
- 可制造性起始示例的可行转速带：legacy `≤ 2600 rpm` → 相量 `≤ 1800 rpm`。

### F. 候选修正

**先确定单一基准**：全部化到**线电压 RMS**。

```
V_required_line_rms
    = √3 · | Ē_ph + I̅·(R_ph + j·ω_e·L_s) |   · k_margin
    = √3 · √( (E_ph_rms + I_ph_rms·R_ph)² + (I_ph_rms·ω_e·L_s)² ) · k_margin

其中
    E_ph_rms  = back_emf_phase_rms_v            [相, RMS]
    I_ph_rms  = phase_current_rms_a             [相, RMS]
    R_ph      = phase_resistance_ohm            [相]
    L_s       = phase_inductance_h − mutual_inductance_h   [相, 同步]
    ω_e       = 2π·f_e
    k_margin  = VOLTAGE_REQUIREMENT_MARGIN_FACTOR = 1.05
```

**每一项都是每相 RMS 量，最后统一乘 √3 转到线 RMS。不再出现 `2×` 与 `1×` 的混用。**

**不提议**改动 `k_margin`、`R_line`、`L_s` 的定义本身——只改**组合方式与基准**。
`line_resistance_ohm` / `line_inductance_h` 的**命名**建议在同批次澄清为
`terminal_resistance_ohm` / `synchronous_inductance_h`（**不改数值**）。

### G. 向后兼容风险

**MEDIUM**

- `legacy_baseline.json` 的 3 个用例**均锚定 `required_voltage_v`**
  （`49.95207924850739` / `15.026245524087711` / `110.66855045604889`）。
  **就地修改必然破坏 `test_legacy_regression.py`，而该 fixture 被禁止修改。**
- 但 `required_voltage_v` 不参与任何下游物理，故不会污染转矩/损耗/效率锚点。
- 已保存项目的 `result_snapshot` 会因模型版本变化而标记为需重算（既有的安全降级路径）。

### H. 并行输出迁移方案

1. **新增** `revised_required_voltage_line_rms_v` 与 `revised_voltage_margin_percent`，
   `required_voltage_v` 与 `voltage_margin_percent` **保持 legacy 语义不变**。
2. 新增状态字段 `required_voltage_model_status`：
   `legacy_rss_mixed_basis` / `revised_single_basis_phasor`。
3. 新增 `required_voltage_legacy_revised_relative_difference`。
4. 沿用 Phase 3B/3C/3E 已验证的 parallel-output 模式：**修正值不进入默认路径**。
5. UI 与导出先以"legacy（兼容值）+ 修正值（并行）"并列展示，标注两者基准差异。
6. 优化器与 feasibility **暂不切换**，待并行期证据积累后单独批准切换。
7. 切换默认路径为**独立的后续阶段**，需要 §J 的外部证据。

### I. 需要的测试

1. 基准重构断言：`E_line/E_ph = √3`、`R_line/R_ph = 2`、`L_s/L_ph = 1.15`。
2. 相量式与 dq 稳态式（`id=0`，同一 `L`）**逐位相等**（已验证 `|Δ| = 0.000000000 V`）。
3. 单向性：在 `rpm × P` 网格上断言 `revised ≥ legacy`，并记录最小相对差。
4. `legacy_baseline.json` 三例的 `required_voltage_v` **逐位不变**。
5. 下游隔离：断言修正值不改变 torque / current / Ke / Kt / 各项损耗 / 效率 / 电流密度 / 槽占比。
6. 极限工况：`I → 0` 时 `revised → √3·E_ph·k`；`ω_e → 0` 时 `revised → √3·(E_ph+I·R_ph)·k`。
7. 优化器候选集合在并行期**不变**（未切换默认）。

### J. 需要的外部验证

- **必需**：一台真实 AFPM 样机在若干负载点的**端电压（线 RMS）实测** vs 转速/电流，
  与 `E_ph`、`R_ph`、`L_s` 的独立实测（空载反电动势 + LCR 表）。
- **充分性**：`E_ph`、`R_ph`、`L_s` 三者一旦有实测锚点，本修正即可从"内部一致性"
  升级为"外部验证"。这是当前**信息增益/成本比最高**的一项验证工作。
- **注意**：即便没有外部数据，本修正的**内部**依据已经充分——它与本项目自身
  Phase 6E dq 模型逐位一致，而 legacy 式与之矛盾。

---

## Finding 2 — coreless 配置仍报告铁损

### A. 当前实现

**文件**：`motor_calculator/motor_core/calculations.py`（**受保护**）
**函数**：`MotorAnalysisEngine.calculate_losses`
**行**：325

```python
core_loss_w = CORE_LOSS_RATED_POWER_RATIO * i.rated_output_power_w    # 0.01 * P_rated
```

单位 W。**不查询 `is_coreless`，不含频率、磁密、材料、体积或几何依赖。**

### A2. 几何/材料语义追溯（特殊要求）

| 追溯项 | 实测结果 |
|---|---|
| `is_coreless` 在 kernel 中的使用点 | **仅 1 处**：`calculations.py:357`（齿槽转矩置零）。**铁损处未被查询** |
| `is_coreless` 对输出的实际影响 | `coreless=True/False`：`core_loss` 均为 6.0000 W，`eddy` 均为 44.5992 W，`eff` 均为 89.590869%；**仅 `cogging_peak` 从 0.000000 变为 0.058778** |
| `yoke_height_m`（"定子轭部高度"） | 传入 `StatorGeometry` 后**从未参与任何计算**。实测 `h_yoke = 0.5 / 5.0 / 50.0 mm` 时 `Bg_pk`、`core_loss`、`efficiency`、`L_ph` **逐位相同** |
| 磁路是否含钢磁阻 | **否**。`pole_flux = MMF / (R_gap + σ·R_magnet)`，实测与公式逐位吻合。**无任何钢件磁阻项** |

**材料语义结论**：

- 默认拓扑为**双转子、单定子、双气隙 AFPM**。`coreless` 指**定子无铁芯**。
- **转子背铁仍然存在**——它是磁通返回路径，且模型通过"无钢磁阻项"**隐式假设其磁导率无穷大且无损耗**。
- 因此 **"coreless" ≠ "无铁磁材料"**。按特殊要求，**不能假设该损耗应为零**。
- 表贴式转子背铁在基波下随磁场同步旋转，自身坐标系中见到近似恒定磁通 → 基波铁损趋近于零；
  但槽谐波、电枢反应谐波引起的转子/磁钢涡流损耗**不为零，且当前模型完全未建模**。

**该项实际代表什么**：一个**集总经验占位项**（额定功率的 1%），
既不是定子铁损模型，也不是转子损耗模型。

### B. 缺陷分类

**`MODEL_LIMITATION`**

理由：
- 无法称为公式缺陷——它没有声称实现任何具体的铁损公式（无 Steinmetz、无 `f^a·B^b`）。
- 无法称为"应当置零"——转子背铁与磁钢仍是铁磁/导电材料，且其损耗未建模。
- 真正的问题是**命名与不变性**：它被命名为"铁损 / core_loss"，暗示定子铁损语义；
  且它**与转速和磁密完全解耦**。

### C. 物理推理

**支配物理**：铁损通常为 `P_fe = k_h·f·B^α + k_e·f²·B²`（Steinmetz + 涡流）。
当前式对 `f` 与 `B` 的指数**均为 0**。

**量纲**：W = 无量纲 × W ✅ 一致。

**假设**：额定工况下的所有未建模磁性损耗 ≈ 额定输出功率的 1%。
这是一个**在额定点校准的集总常数**，**不能外推到其他转速**。

### D. 可复现数值探针

**转速扫描（可制造性起始示例，`P_rated = 600 W` 固定）**：

| rpm | f_e Hz | Bg_pk T | core_w | copper_w | eddy_w | mech_w | eff % |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 600 | 80.0 | 0.6661 | **6.000** | 225.731 | 3.317 | 0.602 | 71.800 |
| 1200 | 160.0 | 0.6661 | **6.000** | 56.433 | 13.269 | 1.220 | 88.637 |
| 2200 | 293.3 | 0.6661 | **6.000** | 16.790 | 44.599 | 2.322 | 89.591 |
| 3200 | 426.7 | 0.6661 | **6.000** | 7.936 | 94.359 | 3.575 | 84.285 |
| 4400 | 586.7 | 0.6661 | **6.000** | 4.197 | 178.397 | 5.376 | 75.570 |

`core_loss` 在 7.3 倍转速范围内**完全不变**。

**占比与置零影响**：

| 设计 | core_w | 总损耗 W | 占比 | 效率 | 置零后效率 | 差 |
|---|---:|---:|---:|---:|---:|---:|
| application default（coreless） | 8.000 | 69.989 | 11.43% | 91.9552% | 92.8086% | **+0.8534 pp** |
| 可制造性起始示例（slotted） | 6.000 | 69.711 | 8.61% | 89.5909% | 90.4008% | **+0.8099 pp** |

### E. 影响分析

受影响：`core_loss_w`、`input_power_w`、`efficiency_percent`、损耗饼图/表、
速度扫描效率曲线、`EFFICIENCY_REVIEW` 可行性提示、所有导出的效率字段。
不受影响：电压、电流、转矩、磁路、槽占比、绕组系数、热、dq 动态。

**最严重的实际后果**：因为该项与转速无关，**速度扫描的效率曲线在物理上不可信**
（`P_rated` 在扫描中保持不变 → 铁损在整个转速范围内恒定）。

### F. 候选修正

**不提议在无数据的情况下引入新的铁损公式。** 提议分两步：

**第一步（不改物理，仅改语义与可见性）**：

- 将输出重命名/标注为 `lumped_unmodelled_magnetic_loss_w`（中文：`集总未建模磁性损耗`），
  并明确标注：`额定点经验常数，与转速/磁密解耦；不是定子铁损模型；coreless 拓扑下
  转子背铁与磁钢损耗仍未建模`。
- 在速度扫描图上显式声明"效率曲线中的该项为常数，非物理外推"。

**第二步（需要数据，见 §J）**：引入可标定的 `k_h·f·B^α + k_e·f²·B²` 形式，
且**只在有实测损耗分解锚点时**才允许启用。

### G. 向后兼容风险

**MEDIUM**（第一步为 **LOW**）

`legacy_baseline.json` 锚定了 `core_loss_w`（8.0 / 1.5 / 25.0）、
`input_power_w` 与 `efficiency_percent`。任何数值改动都会破坏回归，必须走并行输出。
第一步只改标签与文案，**数值不变，风险 LOW**。

### H. 并行输出迁移方案

1. 立即执行**第一步**（纯标注，不改数值，不触碰受保护文件——可在
   `plots/inventory.py`、`i18n`、仪表板 `interpretation_zh` 层完成）。
2. 第二步在拿到实测损耗分解后，新增 `revised_core_loss_w` 并行输出 +
   `core_loss_model_status`，legacy 保持默认。
3. 在并行期同时输出 `revised_efficiency_percent`，不替换 `efficiency_percent`。

### I. 需要的测试

1. `is_coreless` 与 `core_loss_w` 的当前关系被显式记录（当前：无关系）。
2. `h_yoke` 对所有输出无影响的断言（防止未来误以为它已接入）。
3. 磁路无钢磁阻项的断言（记录"背铁磁导率无穷"假设）。
4. `core_loss_w` 与转速无关的断言（记录当前局限）。
5. 标签测试：输出清单中该项**不得**被称为定子铁损。

### J. 需要的外部验证

- **必需**：同一样机在**至少 3 个转速点**的实测输入功率/输出功率/效率分解。
- 理想：空载损耗 vs 转速曲线（可分离机械损与磁性损）。
- **在此之前不得引入任何新的铁损系数**——那只是把一个猜测换成另一个猜测。

---

## Finding 3 — 磁密谐波轴映射反向

### A. 当前实现

**文件**：`motor_calculator/motor_core/calculations.py`（**受保护**）
**函数**：`MotorAnalysisEngine.calculate_flux_distribution`
**行**：472、489–490、503–504

```python
mechanical_angle_deg = np.linspace(0.0, 360.0, 720)          # 一个机械周期
...
spectrum  = np.abs(np.fft.fft(B)[:len(B)//2]) / len(B) * 2.0
harmonics = np.arange(len(spectrum)) * pole_count / 2.0       # = k * pole_pairs
...
return {..., "harmonics": harmonics[:50], "spectrum": spectrum[:50]}
```

下游唯一消费者 `PMDC_Calculator_claude204.py:1854-1858`：

```python
harmonics = flux_data.get("harmonics", ...)
valid_idx = harmonics <= 25
ax2.bar(harmonics[valid_idx], spectrum[valid_idx], ...)
```

### B. 缺陷分类

**`PRESENTATION_DEFECT`**

按特殊要求逐项判定：

| 维度 | 判定 |
|---|---|
| 数值 Fourier 分解 | ✅ **正确**（见 §D） |
| 谐波次数映射 | ❌ **错误**（`k×p` 应为 `k/p` 或 `k`） |
| 绘图坐标轴 | ❌ 受上一项影响 |
| 下游物理 | ✅ **不受影响** |

**因此不构成公式缺陷。**

### C. 物理推理

`mechanical_angle_deg` 覆盖**一个机械周期**，故 FFT bin `k` 对应
**每机械转 k 个周期**。电气基波位于 `k = pole_pairs`。

- 机械阶次 = `k`
- 电气阶次 = `k / pole_pairs`

代码写成 `k × pole_pairs`，**方向反了，误差因子 `pole_pairs²`**。

### D. 可复现数值探针

**分解本身正确**（方波占空比 α 的解析基波 `4/π·B_pk·sin(πα/2)`）：

| p | argmax bin k | 期望 | \|A_k\| | 解析值 | 比值 |
|---:|---:|---:|---:|---:|---:|
| 2 | 2 | 2 | 0.771206 | 0.770353 | 1.001108 |
| 4 | 4 | 4 | 0.771221 | 0.770353 | 1.001127 |
| 8 | 8 | 8 | 0.771073 | 0.770353 | 1.000935 |

**次数映射错误**：

| p | 基波 bin | 代码标注 `harmonics[k]` | 真实电气阶次 | 真实机械阶次 |
|---:|---:|---:|---:|---:|
| 2 | 2 | **4.0** | 1.0 | 2 |
| 4 | 4 | **16.0** | 1.0 | 4 |
| 8 | 8 | **64.0** | 1.0 | 8 |

**绘图后果**（`harmonics ≤ 25`）：

| p | 实际绘出柱数 | 绘出的 bin | 基波是否在图上 |
|---:|---:|---|---|
| 2 | 13 | 0–12 | ✅ 是 |
| 4 | 7 | 0–6 | ✅ 是 |
| **8** | **4** | **0–3** | ❌ **否，基波被过滤掉** |

**下游物理不受影响**（直接由波形计算，不经 `harmonics`）：

```
数值 Bg_avg = 0.47627468   解析 Bpk·α       = 0.47533156
数值 Bg_rms = 0.56869323   解析 Bpk·√α      = 0.56812989
```

**附带次要问题**：`linspace(0, 360, 720)` 端点重复（0° 与 360° 同为样本），
周期实为 719 个间隔 → 轻微谱泄漏。实测边带 `0.011293 / 0.771073 / 0.008382`（约 1.5%）。

### E. 影响分析

受影响：**仅**"气隙磁密谐波频谱"柱状图（`p ≥ 5` 时基波不可见）。
不受影响：`Bg_peak/avg/rms`、`pole_flux`、`Ke/Kt`、电压、电流、转矩、损耗、效率、
可行性、导出（`harmonics` 不在任何导出字段中）。

### F. 候选修正

```python
# 机械阶次（每机械转的周期数）——最直接、无歧义
mechanical_harmonic_order = np.arange(len(spectrum))

# 电气阶次（相对电气基波）
electrical_harmonic_order = np.arange(len(spectrum)) / pole_pairs
```

建议**同时返回两者**并明确命名，绘图侧使用电气阶次并把过滤条件改为
`electrical_harmonic_order <= 25`。

可选次要改进：`np.linspace(0.0, 360.0, 720, endpoint=False)` 消除端点重复与泄漏
（**会改变 `Bg_avg`/`Bg_rms` 的第 3 位小数，因此属于数值改动，需并行输出**）。

### G. 向后兼容风险

**LOW**

`harmonics` **未被 `legacy_baseline.json` 锚定**，也不在任何导出/项目快照字段中。
唯一消费者是一张图。

> ⚠ 但 `endpoint=False` 的可选改进会改变 `Bg_avg`/`Bg_rms`，而这两项**已被锚定**
> （`bg_avg_t = 0.4753315649867375`、`bg_rms_t = 0.5681298853918393`）。
> **两项改动必须分开批准**：轴映射修正风险 LOW，采样端点修正风险 MEDIUM。

### H. 并行输出迁移方案

轴映射修正**不需要并行输出**——旧的 `harmonics` 键从未有正确语义，
建议新增 `mechanical_harmonic_order` / `electrical_harmonic_order` 两键，
保留 `harmonics` 一个发布周期并标注为 deprecated，然后移除。

端点采样改动**必须**并行输出（`revised_bg_avg_t` / `revised_bg_rms_t`）。

### I. 需要的测试

1. 基波 bin 的电气阶次断言 ≈ 1.0，对 `p ∈ {1,2,4,8,12}` 参数化。
2. FFT 幅值与解析式 `4/π·B_pk·sin(πα/2)` 的一致性断言（容差 0.5%）。
3. 绘图过滤条件下基波必须可见的断言。
4. `Bg_avg`/`Bg_rms` 逐位不变的断言（确认轴修正不影响物理）。

### J. 需要的外部验证

**不需要。** 这是纯粹的内部一致性/索引问题，可由解析式完全判定。

---

## Finding 4 — 固定 360 点齿槽采样可能混叠高空间阶次

### A. 当前实现

**文件**：`motor_calculator/motor_core/calculations.py`（**受保护**）
**函数**：`MotorAnalysisEngine.calculate_cogging_torque`
**行**：350–367

```python
least_common_multiple = (pole_count * slot_count) // gcd(pole_count, slot_count)
rotor_position_rad = np.linspace(0.0, 2.0 * PI, 360)
if i.is_coreless:
    return rotor_position_rad, np.zeros_like(rotor_position_rad)
cogging_peak_nm = i.cogging_factor * calculate_legacy_rated_torque_nm(...)
cogging_waveform = cogging_peak_nm * (
    np.sin(1*LCM*θ) + 0.3*np.sin(2*LCM*θ) + 0.1*np.sin(3*LCM*θ)
)
```

消费者：`cogging_torque_peak_nm = np.max(np.abs(cogging_torque_nm))`（`calculations.py:602`）+ 波形图。

### A2. 最高空间阶次推导（特殊要求）

`θ` 覆盖**一个机械周期**。波形含 `LCM`、`2·LCM`、`3·LCM` 三个分量。

```
H_max = 3 · LCM(2p, Q)          [周/机械转]
```

**采样率**：`np.linspace(0, 2π, 360)` 产生 360 个点，但**端点重复**（0 与 2π 同为样本），
故独立间隔数 = **359**，有效采样率 `f_s = 359 samples / mech-rev`。

**Nyquist 判据**：

```
f_s / 2 = 179.5 周/转
要求 3·LCM ≤ 179.5   ⇔   LCM ≤ 59
```

### B. 缺陷分类

**`CONFIRMED_NUMERICAL_DEFECT`**（严重度 **LOW**）

理由：Nyquist 在大量现实槽极组合下确被违反（波形确实混叠），
但当前**唯一被消费的标量**（峰值）因一个数论巧合而恰好精确。

### C. 物理推理

齿槽转矩的基本空间频率为 `LCM(2p, Q)` 周/机械转（标准结果）。
模型用固定 `0.3 / 0.1` 权重人为叠加 2 次与 3 次分量，
故模型内的最高阶次为 `3·LCM`。**幅值不是物理预测**（由用户 `k_cogging` 给定），
但**空间频率是拓扑决定的**，必须被正确采样。

### D. 可复现数值探针

**混叠扫描**（56 个现实槽极组合）：

```
扫描 2p ∈ {8,10,16,20,24,30,40,48} × Q ∈ {12,18,24,27,30,36,48}
42 / 56 组合违反 Nyquist（3·LCM > 179.5）
然而全部 42 组的峰值误差 = -0.000 %
```

**为什么峰值恰好精确 —— 一个数论巧合**：

```
359 是素数（已验证）。
θ_j = 2π·j/359, j = 0..358
sin(LCM·θ_j) = sin(2π·(LCM·j mod 359)/359)
359 为素数且 LCM % 359 ≠ 0  ⇒  j ↦ (LCM·j mod 359) 是 0..358 上的双射
三个分量在同一 j 上求值，故 (LCM·j, 2·LCM·j, 3·LCM·j) mod 359 = (i, 2i, 3i) mod 359
⇒ 采样序列是"正确采样序列"的一个置换
⇒ max|·| 对置换不变  ⇒  报告的峰值精确
```

**这是巧合，不是设计。** 证据：

| n | 独立间隔 | 间隔数是否素数 | LCM 集合上的最坏峰值误差 |
|---:|---:|---|---:|
| **360** | **359** | **是** | **−0.0000 %** |
| 361 | 360 | 否 | **−100.0000 %** |
| 362 | 361 | 否 | −0.0021 % |
| 401 | 400 | 否 | −5.2968 % |
| 721 | 720 | 否 | **−100.0000 %** |
| 1000 | 999 | 否 | −0.0438 % |

**退化情形**：`LCM` 为 359 的倍数时波形整体塌陷为零：

```
LCM = 359 / 718 / 1077 → peak@360 = 0.000000000（真值 1.128382091）→ −100 % 误差
```

需要 `2p` 或 `Q` 被 359 整除，即 `p = 359` 或 `Q = 359`。
**对本机型不具现实可达性**，据实记录，不作为主要风险。

**绘制的波形确实混叠**：

| LCM | 360 点轨迹的符号变化次数 | 物理基波每转过零次数 | 混叠因子 |
|---:|---:|---:|---:|
| 48 | 96 | 96 | 1.000 |
| 120 | 240 | 240 | 1.000 |
| **240** | **239** | **480** | **0.498** |

**峰值语义（附带发现）**：

```
sin(x)+0.3sin(2x)+0.1sin(3x) 的真实峰值因子 = 1.128382091
⇒ 报告的齿槽峰值 = 1.1284 × (k_cogging × T_rated)，而非 1.0000 ×
```

用户输入 `k_cogging` 的直觉是"齿槽峰值/额定转矩"，实际报告值高 **12.84%**。

**RMS（一个可能的未来消费者）在退化情形下同样崩溃**：
`LCM=359` 时 `rms@360 = 0.000000`（真值 0.741620），误差 −100%。

### E. 影响分析

受影响：齿槽转矩**波形图**（`LCM ≥ 180` 时显示低频伪影）；
任何未来在该轨迹上做 RMS/FFT/THD 的消费者。
**当前不受影响**：`cogging_torque_peak_nm`（精确）、效率、转矩、电压、可行性、导出。
默认设计 `coreless=True` 时波形被强制置零，**默认路径完全不暴露该问题**。

### F. 候选修正（自适应采样，不使用任意大常数）

```python
PHASE9_COGGING_HARMONIC_ORDERS = 3          # 模型内最高阶次倍数
PHASE9_COGGING_OVERSAMPLING    = 8          # 每个最高阶周期的采样点数
PHASE9_COGGING_MIN_SAMPLES     = 360        # 保持既有下限，避免稀疏图

highest_order = PHASE9_COGGING_HARMONIC_ORDERS * least_common_multiple
sample_count  = max(PHASE9_COGGING_MIN_SAMPLES,
                    PHASE9_COGGING_OVERSAMPLING * highest_order + 1)
rotor_position_rad = np.linspace(0.0, 2.0 * PI, sample_count)
```

**过采样因子选择依据**（实测）：

| n | 最坏峰值误差 | 最坏 RMS 误差 |
|---|---:|---:|
| `4·H + 1` | 0.22590 % | 0.08668 % |
| **`8·H + 1`** | **0.22590 %** | **0.04336 %** |
| `12·H + 1` | 0.22590 % | 0.02891 % |
| `16·H + 1` | 0.22590 % | 0.02168 % |

峰值误差在 `S ≥ 4` 后不再改善（离散采样对峰值位置的固有下限），
**故推荐 `S = 8`**：RMS 误差降到 0.043%，成本可接受。

**成本**：

| LCM | H = 3·LCM | `n(S=8)` |
|---:|---:|---:|
| 48 | 144 | 1,153 |
| 240 | 720 | 5,761 |
| 1080 | 3,240 | 25,921 |

**更优的补充建议**：`cogging_torque_peak_nm` 应**解析计算**而非从采样轨迹取 max：

```python
COGGING_SHAPE_PEAK_FACTOR = 1.128382091      # max|sin(x)+0.3sin(2x)+0.1sin(3x)|
cogging_torque_peak_nm = COGGING_SHAPE_PEAK_FACTOR * cogging_peak_nm
```

这样峰值**完全脱离采样**，并可顺带澄清 `k_cogging` 的语义。

### G. 向后兼容风险

**LOW**

- 齿槽波形与峰值**均未被 `legacy_baseline.json` 锚定**。
- 采样点数改变会改变 `waveforms["cogging"]` 数组长度 —— 需检查绘图与导出是否假定长度 360。
- 解析峰值会把 `cogging_torque_peak_nm` 改变 **+12.84%**（从 1.0× 变为 1.1284× 语义澄清），
  这是**用户可见的数值变化**，需要并行输出或明确的语义说明。

### H. 并行输出迁移方案

1. 采样点数自适应：**无需并行输出**（峰值不变、波形更正确），但需版本说明。
2. 解析峰值：**需要并行输出** `revised_cogging_torque_peak_nm` +
   `cogging_peak_semantics_status`，或改为把 `k_cogging` 显式定义为"真实峰值比"
   并在 UI 说明中澄清。二选一，需用户决策。

### I. 需要的测试

1. Property-based（Hypothesis）：对 `2p × Q` 网格断言 `intervals ≥ 2·H`。
2. 峰值与稠密参考（4×10⁶ 点）的一致性断言，容差 0.5%。
3. 退化情形 `LCM % 359 == 0` 的显式断言（记录当前塌陷行为）。
4. 波形符号变化次数 ≈ `2·LCM` 的断言（证明未混叠）。
5. `is_coreless=True` 时波形恒为零的断言。
6. 采样点数上界断言（防止 `LCM` 极大时内存爆炸）。

### J. 需要的外部验证

**不需要。** 纯数值采样问题，可由稠密参考解完全判定。
（齿槽**幅值**的物理验证是另一件事，当前幅值本就是用户输入而非预测。）

---

## Finding 5 — 导体涡流损耗对整个导体体积施加气隙峰值 B

### A. 当前实现

**文件**：`motor_calculator/motor_core/calculations.py`（**受保护**）
**函数**：`MotorAnalysisEngine.calculate_losses`
**行**：307–323

```python
resistivity          = RHO_CU_20 * (1.0 + RHO_CU_TEMP_COEFF * (T_coil - 20.0))
local_flux_density_t = magnetic_result.air_gap_flux_density_peak_t      # 单一标量
turn_length_m        = 2*L_eff + 2*pole_pitch*END_WINDING_LENGTH_FACTOR
copper_volume_m3     = 3 * N_ph * turn_length_m * copper_area_m2        # 含端部绕组
skin_depth_m         = sqrt(2*rho / (MU0 * 2*PI*f_e))
skin_factor          = 1.0 if d_wire < 2*skin_depth else d_wire/(2*skin_depth)
eddy_loss_w = (PI**2/24) * (f_e * B * d_wire)**2 / rho * copper_volume_m3 * skin_factor
```

单位 W。参考基准：`B` 为**气隙峰值磁密**（单一标量，非局部值）。

### B. 缺陷分类

**`MODEL_LIMITATION`**（并建议将输出标注为 `EXPERIMENTAL / APPROXIMATE`）

### C. 物理推理

**支配物理**：置于交变横向磁场中的圆导体，低频（`d ≪ 2δ`）涡流损耗
单位体积功率具有 `p_v ∝ d²·f²·B_pk²/ρ` 的结构。

**量纲验证**（已核）：

```
[Hz²·T²·m²]/[Ω·m] · [m³]
 = (1/s²)(Wb²/m⁴)(m²)/(Ω·m) · m³
 = Wb²/(s²·m²·Ω·m) · m³ = V²·s²/(s²·Ω) = V²/Ω = W        ✅ 量纲正确
```

**系数**：代码为 `π²/24`，常见教科书形式为 `π²/32`，比值 `32/24 = 1.3333`。
**不同参考文献因场取向与峰值/RMS 约定而异**，在未指明参考推导的前提下
**不能单凭系数判定其错误**。

**信息充分性判定（特殊要求的核心）**：

模型**拥有**的场信息：**1 个标量** `Bg_peak = 0.666060 T`。

模型**不拥有**的信息：

- 径向分布 `B(r)`（AFPM 的 `r_out/r_in = 2.000`，跨度大）
- 轴向分布 `B(z)`
- 端部区域磁场（端部绕组处于气隙外，实际场远低于气隙峰值）
- 电枢反应磁场
- 导体所见 `B` 的谐波频谱
- 导体间邻近效应（proximity effect）
- 绞线/换位（transposition）

**关键定量事实**：

```
每匝有效径向长度  = 2 × 35.000 mm = 70.000 mm
每匝端部长度      = 2 × 26.802 mm = 53.603 mm
每匝总长          = 123.603 mm
⇒ 端部绕组占铜体积 43.37 %
```

**模型对这 43.37% 的铜施加了完整的气隙峰值磁密**，而端部绕组物理上位于气隙之外。

**结论：模型没有足够的局部电磁信息来物理地计算导体涡流损耗。**
按特殊要求，**不发明修正系数**。

**附带问题**：`skin_factor` 被乘在一个**本身就假设 `d ≪ 2δ`** 的低频公式上。
实测在现实频率范围内它**从未激活**：

| rpm | f_e Hz | δ mm | d mm | `d/(2δ)` | skin_factor |
|---:|---:|---:|---:|---:|---:|
| 2200 | 293.3 | 4.2843 | 1.200 | 0.1400 | 1.0000 |
| 6000 | 800.0 | 2.5943 | 1.200 | 0.2313 | 1.0000 |
| 12000 | 1600.0 | 1.8344 | 1.200 | 0.3271 | 1.0000 |

即该分支是**休眠代码**；一旦激活，它是**特设外推**而非推导极限。

### D. 可复现数值探针

**该项主导损耗**：

| rpm | f_e Hz | copper_w | eddy_w | **eddy 占总损耗** | eff % |
|---:|---:|---:|---:|---:|---:|
| 600 | 80.0 | 225.731 | 3.317 | 1.41% | 71.800 |
| 1200 | 160.0 | 56.433 | 13.269 | 17.25% | 88.637 |
| 2200 | 293.3 | 16.790 | 44.599 | **63.98%** | 89.591 |
| 3200 | 426.7 | 7.936 | 94.359 | **84.35%** | 84.285 |
| 4400 | 586.7 | 4.197 | 178.397 | **91.97%** | 75.570 |

**对未验证标量的平方敏感性**（`eddy ∝ B²`）：

| Br 缩放 | Bg_pk T | eddy W | eff % |
|---:|---:|---:|---:|
| ×0.50 | 0.3330 | 11.150 | 87.383 |
| ×0.80 | 0.5328 | 28.544 | 90.484 |
| ×1.00 | 0.6661 | 44.599 | 89.591 |
| ×1.25 | 0.8326 | 69.686 | 87.114 |
| ×2.00 | 1.3321 | 178.397 | 75.861 |

### E. 影响分析

受影响：`eddy_loss_w`、`input_power_w`、`efficiency_percent`、损耗分解、
速度扫描效率曲线、`EFFICIENCY_REVIEW` 提示、所有效率导出。
不受影响：电压、电流、转矩、磁路、槽占比、绕组系数、可行性电压/电流密度判据。

**风险特征**：在中高速工况下该项**主导效率预测**（64%–92% 的总损耗），
却建立在一个**无外部锚点、且被施加于 43% 不适用体积**的标量上。

### F. 候选修正

**不提议改变公式，也不提议引入新系数。** 提议三项**非物理**改动：

1. **标注为实验性**：把该输出的证据等级标为 `EXPERIMENTAL / APPROXIMATE`，
   在输出清单、仪表板与导出中显式声明：
   > `导体涡流损耗为集总近似：使用单一气隙峰值磁密，且施加于包含端部绕组的全部铜体积；
   > 未建模径向/轴向场分布、端部场衰减、电枢反应、谐波与邻近效应。`
2. **暴露假设敏感性**：在结果中并行给出"若端部绕组不计入涡流体积"的下界估计
   （**纯诊断量，不改默认输出**），让用户看到该项的不确定跨度。
3. **休眠分支显式化**：`skin_factor` 在 `d ≥ 2δ` 时的行为标注为特设外推，
   或在该条件下直接返回 `NOT_VALID_IN_THIS_REGIME` 状态而非静默外推。

**如果未来要做真正的修正**，最低前提是引入
`conductor_region_flux_density_t`（有效区）与 `end_region_flux_density_t`（端部区）
两个**独立可标定**的场输入 —— 而这需要 §J 的数据。

### G. 向后兼容风险

**LOW**（按上述提案，数值完全不变）

若未来改动数值：**MEDIUM**——`efficiency_percent` 与 `input_power_w` 已被
`legacy_baseline.json` 锚定（`eddy_loss_w` 本身未直接锚定，但通过这两项间接锚定）。

### H. 并行输出迁移方案

1. 第一阶段：仅标注 + 诊断性下界，**零数值变化**，无需并行输出。
2. 第二阶段（需数据）：`revised_eddy_loss_w` 并行输出 + `eddy_loss_model_status`，
   legacy 保持默认，直至实测损耗分解支持切换。

### I. 需要的测试

1. 量纲/缩放律断言：`eddy ∝ f²`、`∝ B²`、`∝ d²`、`∝ V`、`∝ 1/ρ`。
2. 端部体积占比的显式断言（记录 43.37% 这一结构事实）。
3. `skin_factor` 在现实参数域内恒为 1.0 的断言（记录休眠状态）。
4. `skin_factor` 在 `d = 2δ` 处连续性断言（当前连续 ✅）。
5. 证据等级标注测试：该输出**不得**被标为已验证。
6. 若引入诊断下界：断言下界 < 默认值，且默认值不变。

### J. 需要的外部验证

- **必需**：同一样机的**实测损耗分解**（至少 3 个转速点的输入/输出功率）+
  空载损耗 vs 转速曲线（分离机械损）。
- **理想**：直流铜损与交流铜损的分离测量（例如同一绕组的直流电阻损耗 vs
  实际交流工况损耗之差）。
- **在此之前，任何"修正系数"都只是把一个未验证假设换成另一个未验证假设。**

---

## 决策表

| # | 发现 | 分类 | 严重度 | 置信度 | 建议动作 | 需改物理? | 建议并行输出? | 需外部验证? |
|---|---|---|---|---|---|---|---|---|
| 1 | `required_voltage_v` 基准混用 + RSS | `CONFIRMED_FORMULA_DEFECT` | **HIGH** | **HIGH** | **批准修正**，走并行输出 | **是** | **是（必须）** | 推荐（非阻塞） |
| 2 | coreless 仍计铁损 | `MODEL_LIMITATION` | MEDIUM | HIGH | 先重命名 + 标注（零数值变化）；公式升级**推迟**至有数据 | 否（第一步） | 是（第二步） | **是（阻塞第二步）** |
| 3 | 谐波轴映射反向 | `PRESENTATION_DEFECT` | MEDIUM | **HIGH** | **批准修正**索引与标签；采样端点改动**单独批准** | 否 | 否（轴）/ 是（端点） | 否 |
| 4 | 齿槽 360 点固定采样 | `CONFIRMED_NUMERICAL_DEFECT` | **LOW** | HIGH | **批准**自适应采样；峰值语义澄清需用户决策 | 否 | 否（采样）/ 是（峰值语义） | 否 |
| 5 | 导体涡流损耗场信息不足 | `MODEL_LIMITATION` | **HIGH**（对效率） | HIGH | **仅标注为 EXPERIMENTAL/APPROXIMATE**；不发明系数 | 否 | 否（第一步） | **是（阻塞任何数值修正）** |

**严重度口径**：对用户工程决策的实际影响。
**置信度口径**：判定本身的证据强度。

---

## 建议实施顺序

分三批。**每批完成后跑全量回归并复核受保护哈希。**

### 批次 A — 零数值变化，零风险（可立即批准）

> 目标：先让所有已知局限**在界面上诚实可见**，再动任何公式。

| 顺序 | 项 | 涉及文件 | 受保护文件? |
|---:|---|---|---|
| A1 | Finding 5 标注为 `EXPERIMENTAL / APPROXIMATE` + 假设说明 | `plots/inventory.py`、`plots/dashboard.py`、`i18n` | 否 |
| A2 | Finding 2 第一步：重命名为"集总未建模磁性损耗"+ 转速无关声明 | 同上 | 否 |
| A3 | 速度扫描效率曲线加"损耗模型转速无关"标注 | `plots/performance.py` | 否 |
| A4 | 记录性测试：`h_yoke` 无影响、`is_coreless` 仅影响齿槽、`skin_factor` 休眠、端部体积 43.37% | `tests/` | 否 |

**理由**：不改任何数值，不碰受保护文件，立即降低"用户把 confidence 误读为 accuracy"的风险。

### 批次 B — 受保护文件的低风险修正（需批准，逐项并行输出）

| 顺序 | 项 | 风险 | 并行输出 |
|---:|---|---|---|
| B1 | **Finding 3 轴映射**：新增 `mechanical_harmonic_order` / `electrical_harmonic_order`，`harmonics` 标 deprecated | LOW | 否（新增键） |
| B2 | **Finding 4 自适应采样**：`n = max(360, 8·3·LCM + 1)` | LOW | 否 |
| B3 | **Finding 4 峰值语义**：解析峰值 或 澄清 `k_cogging` 定义 —— **需用户先决策二选一** | LOW | 是 |

**理由**：均不影响 `legacy_baseline.json` 锚定值，可先建立"修改受保护文件"的受控流程，
用低风险项验证流程本身。

### 批次 C — 核心公式修正（需批准，强制并行输出）

| 顺序 | 项 | 风险 | 并行输出 |
|---:|---|---|---|
| C1 | **Finding 1**：新增 `revised_required_voltage_line_rms_v` + `revised_voltage_margin_percent` + `required_voltage_model_status` + 相对差字段。**legacy 默认路径完全不变** | MEDIUM | **是（强制）** |
| C2 | 命名澄清：`line_resistance_ohm` → 增加 `terminal_resistance_ohm` 别名；`line_inductance_h` → 增加 `synchronous_inductance_h` 别名（**数值不变**） | LOW | 别名 |
| C3 | `analysis_service.py:168` 的 dq 桥接 `Ld=Lq` 由 `L_ph` 改为 `L_s`（**非受保护文件**，但会改变动态仿真结果，需独立批准） | MEDIUM | 是 |
| C4 | UI/导出并列展示 legacy 与修正电压裕量，明确标注基准差异 | LOW | — |

**C 批次之后单独立项**：默认路径切换（把 feasibility / 优化器切到修正值）。
该切换会使"可制造性起始示例"与 RC2 优化器推荐从可行变为不可行，
**必须**先重新审定这两个官方示例，否则会再次出现"首启即不可行"。

### 明确推迟（不在本提案的批准范围）

| 项 | 阻塞原因 |
|---|---|
| Finding 2 第二步（`k_h·f·B^α + k_e·f²·B²` 铁损） | 无实测损耗分解锚点 |
| Finding 5 数值修正（分区磁密） | 无端部/有效区场数据 |
| Finding 3 采样端点 `endpoint=False` | 会改变已锚定的 `bg_avg_t`/`bg_rms_t`，收益低于风险 |

---

## 前置决策请求

在批次 B/C 开始前，需要用户明确回答三点：

1. **Finding 4 峰值语义**：`k_cogging` 应被定义为
   (a) 齿槽波形真实峰值 / 额定转矩（则报告值不变，仅澄清文档），还是
   (b) 基波分量幅值 / 额定转矩（则报告峰值应为 `1.1284 × k_cogging × T_rated`，语义不变但需说明）？
2. **Finding 1 并行期长度**：修正电压在并行输出多久之后才考虑切换默认路径？
3. **官方示例重定**：若 Finding 1 修正最终切换默认，
   `design.manufacturability_start.v1` 需要重新选参（当前在修正基准下为 −5.10%）。
   是否授权在批次 C 期间**同步准备**一组新的、在修正基准下可行的起始参数？

---

## 附录：本提案的可复现命令

```bash
# 状态与受保护哈希
git -C D:/codex/Projects/MotorCalculator log -1 --format='%H %s'
sha256sum motor_calculator/motor_core/calculations.py \
          motor_calculator/tests/fixtures/legacy_baseline.json

# 全量回归
.venv/Scripts/python.exe -m pytest -q          # -> 707 passed
```

数值探针脚本位于会话 scratchpad，全部为只读调用，**未写入仓库**：
`probe_voltage.py`、`probe_voltage_sweep.py`、`probe_coreloss.py`、
`probe_harmonics.py`、`probe_cogging.py`、`probe_cogging2.py`、
`probe_eddy.py`、`probe_impact.py`。

---

*本提案未修改任何产品代码，未创建提交，未触碰 `tmp/`，未访问 C 盘旧仓库。
受保护文件哈希在提案编写前后均已核验，保持不变。*
