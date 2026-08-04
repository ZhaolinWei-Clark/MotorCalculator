# Phase 7A：验证目标锁定与决策

## 1. Phase 7A 决策

Phase 7A 只回答“今天能证明什么”。基线运行器读取 CREATOR 正式记录和 PMSM/BLDC 分析夹具，不调用 AFPM production 模型去拟合径向 PMSM，也不更新任何参数。

### A. 现在可验证什么？

- PMSM phase/line、peak/RMS、Ke/Kt 和三相功率关系可做 `INTERNAL_ONLY` 解析一致性验证。
- BLDC 理想 120 度波形语义、RMS、Ke/Kt 与功率关系可做 `INTERNAL_ONLY` 验证。
- Phase 6 PMSM dq 方程、Euler/RK4 收敛、稳态 torque balance、控制层接口和单节点热 RC 可做 numerical/internal validation。
- CREATOR 来源、字段状态和 topology comparability gate 可验证；其 AFPM 数值精度不可验证。

### B. 现在不能验证什么？

- AFPM production/default 电磁输出的外部准确度。
- BLDC 真实电机的外部准确度。
- startup/load-step 的实测瞬态准确度。
- iron loss、efficiency 与 winding temperature 的实测准确度。

## 2. Track 与 primary source

| Track | primary | secondary | current decision |
|---|---|---|---|
| A PMSM shared semantics / dq | CREATOR PMSM（外部来源优先，但仅 partial） | PMSM analytical cases（internal） | PARTIAL / INTERNAL_ONLY |
| B AFPM production/default | 无；Parviainen 2005 为 leading blocked candidate | 无 | BLOCKED |
| C BLDC semantics | 无 external primary | BLDC analytical cases（internal） | INTERNAL_ONLY；external BLOCKED |
| D dynamic control | 无 external primary；Paderborn electrical 为 future candidate | Phase 6 numerical reports | INTERNAL_ONLY；physical BLOCKED |
| E loss / thermal | 无 external primary；Paderborn thermal 为 future candidate | Phase 6O internal equations | INTERNAL_ONLY；physical BLOCKED |

## 3. 目标矩阵

| Track | Metric | ValidationStatus | exact reason |
|---|---|---|---|
| A/B | `back_emf_phase_peak_v` | PARTIAL | CREATOR 有该量，但径向 PMSM 与 AFPM topology mismatch |
| A | `back_emf_phase_rms_v` | INTERNAL_ONLY | 只有 PMSM 解析语义用例 |
| A/C | `back_emf_line_rms_v` | INTERNAL_ONLY | 只有 PMSM/BLDC 解析波形用例 |
| A/C | `Ke` | INTERNAL_ONLY | 定义与换算已内部验证，无兼容外部值 |
| A/C | `Kt` | INTERNAL_ONLY | 功率平衡推导已内部验证，无兼容外部值 |
| A/B | `rated_torque_nm` | PARTIAL | CREATOR 有径向机转矩，不能外推 AFPM |
| A/B | `phase_resistance_ohm` | PARTIAL | CREATOR 有相电阻，但绕组/几何不对应 Track B |
| A | `inductance` | PARTIAL | 来源有 Ld/Lq，正式记录未不安全地折算为 phase inductance |
| D | steady-state current | INTERNAL_ONLY | 有动态方程检查，无外部电流轨迹 |
| D | steady-state speed | INTERNAL_ONLY | 有收敛检查，无外部速度轨迹 |
| D | torque balance | INTERNAL_ONLY | 有机械平衡恒等式，无测量 |
| D | startup response | BLOCKED | 缺输入、负载、惯量和同步测量 |
| D | load-step response | BLOCKED | 缺同步 load-step/current/speed/torque 数据 |
| E | `copper_loss_w` | INTERNAL_ONLY | 有代数监测，无外部同工况数据 |
| E | `iron_loss_w` | BLOCKED | 无 defensible source；默认保持 unavailable |
| E | efficiency | BLOCKED | 无同工况输入/输出功率记录 |
| E | `winding_temperature_c` | BLOCKED | 无热历史、冷却边界和测点 |

计数：`READY=0`、`PARTIAL=4`、`BLOCKED=5`、`INTERNAL_ONLY=8`。

## 4. Pre-calibration baseline

执行：

```powershell
.venv\Scripts\python.exe work\run_phase7a_accuracy_baseline.py
```

确定性报告位于 `validation_data/reports/phase7a_accuracy_baseline_zh.md`：

- 37 行总比较记录。
- CREATOR 13 个输出字段全部 `blocked`：4 个已有 reference 因 topology mismatch 不产生 prediction/error；9 个来源字段 unavailable。
- 24 个 PMSM/BLDC internal analytical comparisons 通过内部 `absolute(relative error) <= 1e-9` 标准。
- directly comparable external rows = 0；external pass/warning/fail = 0/0/0。

这不是“零误差”的外部基线。当前外部精度基线是 **insufficient compatible evidence**。

### E/F. 容差失败与归因

当前没有可评价的 external tolerance failure，也没有证据支持把任何差异归因为 model error。CREATOR 阻断属于 topology mismatch；未导入 phase/line、Ke/Kt、loss 等字段属于 insufficient evidence；未来若定义不匹配，应归为 semantic mismatch。blocked 不得计为 pass 或 fail。

## 5. Phase 7B readiness

### G. 是否可进入 Phase 7B Static Accuracy Validation？

可以进入 **受限 Phase 7B**：只允许完善 CREATOR Track A 字段映射/语义比较，或导入一个经过 comparability 审查的 AFPM benchmark。没有新来源时，Phase 7B 不应运行 AFPM 数值精度或校准。

### H. AFPM production validation 是否 blocked？

是。解除阻断需要带完整 topology、geometry、winding、material、operating point、back-EMF/torque 等输出及 provenance 的 AFPM 来源。优先动作是补充并审查 Parviainen 2005 全文；如果其数据仍不足，则继续寻找公开 AFPM bench/FEA benchmark，而不是使用 CREATOR 替代。

## 6. Freeze confirmation

本阶段没有修改模型公式、动态方程、控制器、逆变器、SVPWM、损耗、热模型、production defaults 或 calibration 参数。`motor_core/calculations.py` 与 `legacy_baseline.json` 保持冻结。
