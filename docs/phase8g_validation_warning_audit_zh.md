# Phase 8G：设计可行性基线与告警审计

## 1. 边界与结论

本阶段只修正**验证层的比较基准、可计算性分类和用户措辞**，没有修改生产电磁计算、动态/控制方程、默认输入或 legacy baseline。新增的“可制造性起始示例”是显式可选预设，不是优化结果、校准值或制造认证。

高频告警由三类原因共同造成：

1. 默认工作点的相电流相对于导体截面偏高，电流密度告警主要是正确的设计后果，同时说明默认示例不适合作为保守起点。
2. legacy `fill_factor` 实际是导体直径线性和与内圆周的比值，不是铜面积与槽面积之比；将其套用 `0.6/0.8` 槽满率阈值属于指标语义和措辞错误。
3. legacy 电压裕量直接用 DC 母线电压减 line-line RMS 需求电压，电压基准不一致；对正弦 PMSM 必须先换到一致的线 RMS 基准，对 BLDC 则因换相/PWM 语义不足而不能强制转换。

## 2. 告警链路审计

| 指标 | 生产结果来源 | 原 GUI 判断 | 输入及约定 | 原阈值/措辞 | 审计后验证层行为 |
|---|---|---|---|---|---|
| 电流密度 | `motor_calculator/motor_core/calculations.py` | `motor_calculator/PMDC_Calculator_claude204.py::_check_design_validity` | 相电流 RMS；并联路径均流；`d_wire` 为裸铜直径 mm | `>6` 警告，`>10` 严重 | 方程和阈值保留；显示实际数值与增大导体、增加并联路径或降低相电流的建议 |
| legacy 电压裕量 | 同上 | 同上 | `V_dc` 是 DC 母线；`required_voltage_v` 是 legacy line-line RMS 需求 | `<5%` 警告 | PMSM 用 SVPWM-compatible 线 RMS 可用电压比较；BLDC 标记 `NOT_ENOUGH_SEMANTICS` |
| legacy 绕组占比 | 同上 | 同上 | 导体直径线性和/内圆周，不含槽面积 | `>0.6` 警告，`>0.8` “无法制造” | 保留结果并改名为 legacy 线性绕组占比；不得用于制造结论 |
| 近似槽满率 | `motor_calculator/validation/design_feasibility.py` | `motor_calculator/gui/main_window.py::_check_design_validity` | 三相、每匝两导体边、每相串联匝数、并联路径、总槽数和近似槽面积 | `>0.50` INFO，`>0.60` WARNING，`>0.80` SEVERE DESIGN RISK | 仅有槽几何时计算，明确为裸铜近似值；无槽/无铁芯返回 `NOT_ENOUGH_GEOMETRY` |

严重等级固定为：`ERROR` 表示输入无效或模型不能计算；`SEVERE DESIGN RISK` 表示可计算但风险很高；`WARNING` 表示需要工程复核；`INFO` 只提供指导。验证层不再使用“无法制造/不可能”等超出模型证据的措辞。

## 3. 电流密度

生产与审计层采用同一量纲关系：

```text
A_conductor = pi * (d_wire / 2)^2                 [mm2]
I_conductor,rms = I_phase,rms / n_parallel       [A]
J = I_conductor,rms / A_conductor                [A/mm2]
```

`phase_current_rms_a` 是相 RMS 电流，不替换为峰值；每条并联路径假设均流。`d_wire` 只表示铜导体直径，面积不含漆包绝缘。当前 schema 没有单独的并绕股数、股间不均流、占空比或冷却能力字段，因此 `J` 可计算，但不能单独证明连续热安全。

原告警频繁的直接原因是默认 800 W/2500 rpm 工作点、0.9 mm 导线和两条并联路径得到约 `8.88 A/mm2`；这是真实的输入后果，也是默认示例并不保守的证据，不是阈值本身的缺陷。

## 4. 槽满率

### 4.1 Legacy 指标

原结果为：

```text
legacy_fill_proxy =
    3 * N_phase * 2 * n_parallel * d_wire
    / (pi * D_inner)
```

分子单位是 mm，分母也是 mm。它表示线性导体直径和与内圆周的比值，不是铜截面积/绕组窗口面积。默认值约 `2.456`，但这不能解释为 `245.6%` 槽满率，更不能据此宣称无法制造。

### 4.2 审计层近似值

对有槽输入，新验证层采用：

```text
A_copper,total = 3 * 2 * N_phase * n_parallel * A_conductor
A_slot,one = ((w_top + w_bottom) / 2) * h_slot - w_top * h_wedge
fill_slot,approx = A_copper,total / (slots * A_slot,one)
```

`N_phase` 只按每相匝数计一次，再把总导体边分布到全部槽中；没有把每相匝数误当作每槽匝数。该值仍标为 `APPROXIMATE`，因为 schema 没有槽衬、漆包线外径、端部排布、实际线圈节距、压实率和绕线工艺。无槽/无铁芯输入没有可用槽面积，状态为 `NOT_ENOUGH_GEOMETRY`，不做严重制造性判断。

`0.50–0.60` 只作为圆线绕组的审慎复核区，`>0.60` 需要工艺复核，`>0.80` 是严重设计风险而非数学不可能。实际边界依赖绝缘、导体类型、槽形和制造方法。

## 5. 电压裕量

生产 `required_voltage_v` 的语义保持不变：它是 legacy 正弦 line-line RMS 需求估计，包含反电势、线电阻压降、线电感压降的矢量合成和 legacy `1.05` 系数。

原 GUI 使用：

```text
legacy_margin = (Vdc - Vrequired,line_rms) / Vdc
```

该式把 DC 与 line RMS 直接比较，基准不一致。对正弦 PMSM，Phase 6F 的线性 SVPWM-compatible dq 电压包络为 `Vphase,peak = Vdc / sqrt(3)`，其平衡正弦线电压 RMS 等价值为：

```text
Vavailable,line_rms = Vdc / sqrt(2)
margin = (Vavailable,line_rms - Vrequired,line_rms)
         / Vavailable,line_rms
```

验证层按 `<0%` 严重风险、`0–10%` 警告、`10–15%` 信息提示、`>=15%` 无电压告警处理。这里仍标为 `APPROXIMATE`，因为静态 schema 没有明确调制策略和控制余量。BLDC 梯形波不能安全套用正弦 RMS/峰值关系，因此返回 `NOT_ENOUGH_SEMANTICS`，而不是给出虚假裕量。

## 6. 告警频率调查

脚本 `work/run_phase8g_warning_frequency.py` 对每个起点执行 11 个确定性单变量样本：基线，以及 `Vdc +/-10%`、功率 `+/-20%`、转速 `+/-10%`、导线直径 `+/-20%`、匝数 `+/-10%`。共 44 个样本；这是 UX 邻域检查，不是电机设计总体统计。

| 起点 | 样本 | Legacy 高/严重电流密度 | Legacy fill 严重 | Legacy 低电压裕量 | 审计后严重样本 | 审计后 WARNING 样本 |
|---|---:|---:|---:|---:|---:|---:|
| 应用默认 | 11 | 9 / 2 | 11 | 11 | 11 | 9 |
| PMSM 起始模板 | 11 | 9 / 2 | 11 | 11 | 11 | 9 |
| BLDC 起始模板 | 11 | 7 / 4 | 11 | 9 | 4 | 7 |
| SSDR 起始模板 | 11 | 9 / 2 | 11 | 11 | 11 | 9 |

PMSM/默认/SSDR 的 11 个样本全部存在同基电压严重风险。BLDC 的 11 个样本全部改为电压语义不足，不再用错误基准判定。所有四组均为无槽/无铁芯起点，legacy fill 严重告警全部缺乏槽面积证据，审计后均改为信息级 `NOT_ENOUGH_GEOMETRY`。

## 7. 可制造性起始示例

UX 采用 **Option B**：冻结应用默认值，新增显式预设“可制造性起始示例”，避免改变已有项目、回归基线和默认输出。

相对 `APPLICATION_DEFAULTS` 仅改变：

| 输入 | 值 |
|---|---:|
| DC 母线电压 | 72 V |
| 额定输出功率 | 600 W |
| 额定转速 | 2200 rpm |
| 导线直径 | 1.2 mm |
| 槽型 | 半闭口槽 |
| 无铁芯 | 否 |

其余字段继续使用冻结的应用默认值，包括每相 50 匝和 2 条并联路径。

| 指标 | 结果 | 状态 |
|---|---:|---|
| 相电流 RMS | 9.8167 A | 生产输出 |
| 单路径导体电流 RMS | 4.9084 A | 审计推导 |
| 裸铜面积 | 1.1310 mm2 | 可计算 |
| 电流密度 | 4.3399 A/mm2 | 低于 5 A/mm2 起始目标 |
| 近似裸铜槽占比 | 0.3177 | `APPROXIMATE` |
| legacy 线性绕组占比 | 3.2740 | 仅保留显示，不用于制造结论 |
| 可用线电压 RMS | 50.9117 V | SVPWM-compatible 近似 |
| 所需线电压 RMS | 42.9565 V | legacy 生产输出 |
| 同基电压裕量 | 15.6255% | 达到 15% 起始目标 |
| 额定转矩 | 2.6045 N.m | 生产输出 |
| 输出功率 | 600 W | 输入工作点 |
| 转速 | 2200 rpm | 输入工作点 |
| legacy 效率估计 | 89.5909% | 生产输出 |
| 热状态 | `UNAVAILABLE_STATIC` | 只有温度输入和电阻修正，没有静态温升闭环 |

该预设没有 `ERROR`、`WARNING` 或 `SEVERE DESIGN RISK`，仅保留包含工程数值和证据边界的 `INFO` 摘要。它是保守的**起始示例**，不是经过热、结构、绝缘、制造、FEA 或实验验证的成品设计。

## 8. GUI 与兼容性

- 预设选择器可加载“可制造性起始示例”；只在用户确认后覆盖上述六个字段。
- 计算报告显示“设计可行性检查”，每条消息带严重等级、实际数值和可操作建议。
- legacy 结果仍显示，但名称明确为“Legacy 直流母线差额”和“Legacy 线性绕组占比”，避免将其误读为同基电压裕量或物理槽满率。
- 项目保存/加载保留实际输入，因此重算可得到相同可行性状态；验证结果不是写回生产参数的隐藏状态。
- 输入解析器的 `min` 是严格下界。原正整数字段错误使用 `min=1`，会拒绝合法值 1；现改为 `min=0`，与下游 `>=1` 正整数约束一致。该修复只恢复合法输入，不改变同一输入的计算结果。
- 默认值、生产输出和 legacy baseline 均未改变。

## 9. 限制与后续验证

- 电流密度没有股间不均流、占空比、冷却和温升闭环。
- 槽满率没有漆包绝缘、槽衬、端部、压实率、线圈节距和详细槽/绕组几何。
- PMSM 电压检查使用线性 SVPWM-compatible 包络，不代表具体逆变器、PWM、死区或控制器余量。
- BLDC 缺少安全的静态换相电压基准，当前只报告语义不足。
- 生产 `required_voltage_v`、损耗和效率仍是 legacy 近似；本阶段没有替换这些公式。
- 该起始示例仍需热、结构、绝缘、退磁、制造和外部实测/FEA 验证。

## 10. 冻结确认

- `motor_calculator/motor_core/calculations.py`：未修改。
- `motor_calculator/tests/fixtures/legacy_baseline.json`：未修改。
- 电磁、advanced AFPM、动态、控制、校准和不确定性数学：未修改。

## 11. 最终验证证据

- 变更前完整回归：`590 passed`。
- Phase 8G、单位、输入 UX、本地化与 runtime/packaging 定向回归：`81 passed`。
- 变更后完整回归：`603 passed in 27.81s`。
- 源码真实 Tk GUI：`PASS`。预设无 ERROR/SEVERE，故意坏设计触发 `CURRENT_DENSITY_SEVERE`、`SLOT_FILL_SEVERE` 和 `VOLTAGE_MARGIN_SEVERE`；项目重算、matplotlib、截图和工作区适配均通过。
- PyInstaller one-folder：使用 Python `3.12.10`、Tcl/Tk `8.6.15`、PyInstaller `6.16.0` 重建成功。
- 打包真实 GUI：`PASS`。从仓库外工作目录启动，已清除 `PYTHONPATH`、`PYTHONHOME`、`TCL_LIBRARY`、`TK_LIBRARY`；Phase 8G 数值与源码一致，反馈、导出、项目重算和关闭流程通过。
- 打包目录包含 `_internal/_tcl_data` 与 `_internal/_tk_data`。one-folder 总大小 `90,124,759` bytes，EXE 大小 `8,443,564` bytes。
- 源码与打包烟雾证据位于仓库外 `D:/Codex/PackageSmoke/Phase8G/`，不作为产品数据提交。
- `motor_core/calculations.py` SHA-256：`416330175f2c770cd6e4c5c6e0df98e22eb7c290e3b5825926cc124642b87a2d`。
- `legacy_baseline.json` SHA-256：`15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9`。
