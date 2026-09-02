# MotorCalculator v1.0.0-rc1 独立工程评审报告

**评审角色**：Principal Software Architect + Senior Motor / Mechatronics Engineering Reviewer
**评审性质**：first-pass independent technical review，只读，未修改任何 product code，未提交
**评审日期**：2026-08-31
**评审对象**：`D:\Codex\Projects\MotorCalculator`

---

> ## ⚠ 事后更正（v1.0.0-rc2 阶段补记）
>
> 本报告的 **D-02**（legacy `K_fill > 0.8 → "无法制造!"` 恒真误报）与 **D-03** 中
> "legacy 告警文案"的部分**被高估了**。
>
> RC2 阶段通过 MRO 实测确认：
>
> ```
> MRO: _RealMotorCalculatorApp -> MotorCalculatorAppMixin -> MotorCalculatorApp(legacy)
> _check_design_validity 解析到: MotorCalculatorAppMixin
> ```
>
> `MotorCalculatorAppMixin._check_design_validity`（`gui/main_window.py`）**早已覆盖**
> legacy 实现并委派给 `validation.design_feasibility`，因此这两段 legacy 文案
> **在实际运行的应用中不可达**。本报告定位了 legacy 代码，但未验证 MRO。
>
> **D-03 中真正在线的部分成立**：`run_optimization` 未被覆盖，其电压约束
> `V_required > V_dc` 确实使用了乐观基准，实测对可制造性起始示例误接受 8 个候选
> （`N_ph_turns = 60..81`）。该项已在 RC2 中修正。
>
> 详见 `docs/reviews/legacy_surface_inventory_zh.md` 与
> `docs/releases/v1.0.0-rc2_engineering_corrections_zh.md`。

---

## 1. Executive Summary

这个项目的**工程纪律远高于我在同类桌面计算工具中通常看到的水平**。protected-hash baseline、legacy regression anchor、evidence-level 分级、explicit availability status、"不是能力包络" 这类主动免责标注，都是成熟工程团队才会做的事。638 项回归全绿，受保护哈希与预期完全一致，release 三件产物的 SHA-256 与 manifest 逐一核对通过。

但本次评审发现了一个贯穿全局的结构性问题，我称之为 **dual-truth problem（双重口径问题）**：

> Phase 8G / 8H 新建的 `validation.design_feasibility` + `plots.dashboard` 层已经把电压口径、槽满率口径**修正到工程上正确的语义**；而 legacy GUI 层 `PMDC_Calculator_claude204.py` 仍在同一个窗口里用**旧的、乐观的、部分恒定误报的口径**给用户下结论。两套口径在同一屏幕上共存，且旧口径出现在用户最先看到的"结果/报告"文本区。

具体量化（application default 设计，V_dc=48 / P=800W / n=2500rpm / p=8 / coreless）：

| 指标 | legacy 口径（结果文本区） | same-basis 口径（Phase 8H 仪表板） | 差异 |
|---|---:|---:|---|
| 电压裕量 | **−7.33 %** | **−51.79 %** | 44.5 pp |
| 绕组占比 | **2.456**（245%） | 槽满率 `NOT_ENOUGH_GEOMETRY` | 量纲失真 |

对 `FEASIBLE_STARTING_OVERRIDES` 这个官方"可行起点"设计更糟：legacy 裕量 **+40.34 %** 触发 legacy 提示 *"电压裕量较大 (>40%) — 考虑增加匝数"*，而真实同基裕量只有 **+15.63 %**。**按 legacy 提示增加匝数会把真实裕量推向负值。** 这不是保守性不足，这是方向性相反的错误工程建议。

本质判断：

> 这是 **presentation-layer / legacy-boundary issue**，不是 core physics kernel 的计算 bug。`motor_core/calculations.py` 忠实地保存了 legacy 行为——这正是它被设计成这样的。问题在于 Phase 8G/8H 做了"新增正确层"而没有做"旧层退役"。

**发布结论**：我**不建议**把当前构建原样宣布为 public v1.0.0；但我**建议**保留 `RC_ACCEPTED_LOCALLY` 状态，并在 v1.0 公开前完成 **2 项 P0 UI/语义收口**（不改 protected kernel、不改任何 equation）。

---

## 2. Current Repository / Release State

全部为本次实测，非引用既有文档。

| 项目 | 实测值 |
|---|---|
| repository | `D:\Codex\Projects\MotorCalculator` |
| branch | `codex/phase8i-v1-rc1-acceptance` |
| HEAD | `b70982d450ae27a3493859d006b39e28317b5939` |
| HEAD message | `docs: finalize v1.0.0-rc1 acceptance evidence` |
| author / date | Zhaolin Wei / Mon Aug 31 21:35:35 2026 -0700 |
| working tree | **clean**（`git status --porcelain` 输出 0 行） |
| untracked files | 无 |
| tags | 无（**注意：v1.0.0-rc1 没有 git tag**） |
| APPLICATION_VERSION | `1.0.0-rc1`（`motor_calculator/version.py:15`） |
| RELEASE_CHANNEL | `release-candidate` |
| full regression | **638 passed in 31.01s**（`.venv\Scripts\python.exe -m pytest -q`，exit 0） |
| test files | 90 个 `test_*.py` |
| Python / PyInstaller / Tk | 3.12.10 / 6.16.0 / 8.6.15 |

### 受保护基线哈希核验

| 文件 | 期望 | 实测 | 结果 |
|---|---|---|---|
| `motor_calculator/motor_core/calculations.py` | `416330…b87a2d` | `416330175f2c770cd6e4c5c6e0df98e22eb7c290e3b5825926cc124642b87a2d` | ✅ MATCH |
| `motor_calculator/tests/fixtures/legacy_baseline.json` | `15598f…c17b9` | `15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9` | ✅ MATCH |

**两个 protected file 均未被本次评审触碰。**

### Release artifact 核验

`release/` 三项产物哈希与 `release_manifest.json` / `SHA256SUMS.txt` **逐字节一致**：

```
1afa405c…e79f3f4  MotorCalculator-1.0.0-rc1-win64-portable.zip   41,547,663 B  ✅
dd3b7c05…a212b9f2a MotorCalculator-1.0.0-rc1-win64-setup.exe     30,002,231 B  ✅
23c39097…f94f34343 dist/MotorCalculator/MotorCalculator.exe        8,667,902 B  ✅
```

manifest 内嵌的 `protected_model_hashes` 亦与实测一致。`git_commit` 字段记录构建自 `ee4ed13`，而 HEAD 已前进到 `b70982d`——两者之间只有 2 个 docs commit，**符合"代码未变、仅补验收文档"的说法，可接受**。

`release/` 中同时保留了 0.9.0 的 portable/setup，用于 upgrade 验证，合理。

---

## 3. Architecture Assessment

### 3.1 好的部分（应当保留，不要重构）

- **依赖方向干净**。实测：`motor_core/*` 没有任何一行 import `gui` / `plots` / `dynamics` / `project` / `advanced_afpm`。GUI-independence hard rule 得到了真实执行，不是口号。
- **零循环导入**。对 `motor_calculator.*` 全包 walk-import（排除 tests），**0 import failures**。
- **单位/常量集中**。`motor_core/units.py`、`constants.py`、`electrical_semantics.py` 三件套是这个项目最有价值的资产。`require_sinusoidal_control_mode()` 这种"拒绝在 BLDC 上做正弦 RMS/peak 换算"的显式守卫，是很成熟的做法。
- **数据模型质量高**。`@dataclass(frozen=True)` + 显式单位后缀 + `validate_result_object_finite()` 全字段有限性检查。
- **异常架构清晰**。`MotorCalculatorError → MotorValidationError / MotorCalculationError`，中文错误消息带 label / 当前值 / 合法范围 / 建议四要素，质量很高。
- **持久化架构扎实**。`serializer.py` 做到了 canonical JSON + SHA-256 integrity + `os.replace` 原子替换 + `.bak` 备份 + fsync；`recovery.py` 有 session 标记、corrupt quarantine、schema 版本。这是可以直接抄给别的项目的实现。

### 3.2 核心技术债：legacy GUI 仍是生产基类

这是本项目**最大的单点架构债**，必须明确记录：

```python
# gui/main_window.py:129-160
def _load_legacy_module():
    legacy_path = _RUNTIME_PATHS.resource("motor_calculator", "PMDC_Calculator_claude204.py")
    spec = importlib.util.spec_from_file_location("legacy_motor_calculator_ui", legacy_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PMDCMotorModel = LegacyGuiMotorModelBridge   # ← monkeypatch
    return module

class _RealMotorCalculatorApp(MotorCalculatorAppMixin, legacy_module.MotorCalculatorApp):
    ...
```

`PMDC_Calculator_claude204.py`（**2556 行，全仓最大文件**）在 AGENTS.md 中被描述为 "preserve original single-file motor calculator" 的历史基线，但实际上它是**运行时的 GUI 基类**。当前架构是：

`动态文件加载(exec_module)` + `模块级 monkeypatch` + `Mixin 多继承覆盖 2556 行 legacy 类`

后果：

1. legacy 文件里的 UI 逻辑、警告文案、优化器、绘图代码**全部在生产路径上**，但因为它挂着"历史基线不可删"的标签，容易被误认为已停用（本次发现的 4 个 confirmed defect 里有 3 个都在这个文件里）。
2. `MotorCalculatorAppMixin` 与 legacy 类之间没有显式接口契约，任何 legacy 方法名变动都会静默失效。
3. 打包后仍以 `.py` 源文件形式 exec，**没有做完整性校验**（虽然 manifest 里对 kernel 做了哈希）。
4. MRO 调试困难，`gui/main_window.py` 已达 1518 行，是第二大文件。

**建议**：不要重写。建议做 **legacy surface freeze**——把 legacy 文件中"仍在生产路径上的 UI 行为"清单化，逐项标注 `ACTIVE` / `SUPERSEDED_BY_PHASE8x` / `DEAD`，并在 v1.1 把 `SUPERSEDED` 项逐个下线（见 §16 P1-1）。

### 3.3 其他架构观察

| 观察 | 位置 | 评级 |
|---|---|---|
| 结果字典同时输出中文 key、英文长名 key、legacy 短名 key（`"E_a"` / `"phase_a_back_emf_v"` / `"E_rms"`） | `calculations.py:395-420, 454-467, 492-505` | 兼容别名膨胀，D |
| `models.py` 大量 legacy property 别名（`D_out`/`h_mag`/`g_eff`/`V_margin`/`K_fill`…） | `models.py` | 有意为之的 compat shim，可接受但需登记 |
| `_current_density` 在 kernel 与 feasibility 各实现一次 | `calculations.py:566` vs `design_feasibility.py:95` | 逻辑重复但**数值一致**（已实测），D |
| 裸 `except:`（吞掉 KeyboardInterrupt/SystemExit） | `PMDC_Calculator_claude204.py:2042` | 代码质量问题，P2 |
| `calculate_electrical_parameters` 单函数约 190 行，两分支各自赋值 ~25 个 `None` | `calculations.py:103-295` | 可读性差；但**在 protected file 内，不动** |
| 无 git tag 对应 rc1 | 仓库级 | 发布可追溯性缺口，P1 |
| `AGENTS.md` 停留在 Phase 4A/4B，宣称 `138 passed`、分支 `research/external-data-source-scouting` | `AGENTS.md` | 与实际相差 8 个 Phase，**上下文恢复文档失真**，P1 |

---

## 4. Physics / Mathematical Assessment

### 4.1 内部一致性良好、可以放心的部分（分类 D）

| 项 | 核验 |
|---|---|
| 每极面积 `π/(2p)·(Ro²−Ri²)·α_p` | ✅ 环形面积 / 极数，量纲与拓扑正确 |
| 双转子双气隙 | ✅ `MMF = 2·(Br/μ0)·lm/μr` 与 `R_m = 2·lm/(μ0·μr·A)` 成对出现，气隙 `g_eff = h_coil + 2·g_side`，自洽 |
| `B_avg = B_pk·α_p`、`B_rms = B_pk·√α_p` | ✅ 与方波占空比 α_p 解析式一致，且与 `calculate_flux_distribution` 的数值 `mean(|B|)` / `rms(B)` **数值互相验证通过** |
| 电/机速度语义 | ✅ `f_e = n·p/60`、`ω_e = ω_m·p`，`pole_pairs` 与 `pole_count` 严格区分 |
| PMSM 峰/RMS、相/线换算 | ✅ 全部经 `electrical_semantics.py` 且对 BLDC **主动抛异常拒绝**，语义纪律优秀 |
| `LEGACY_SINE_EMF_FACTOR = 4.44` 与波形 peak `2πfNΦk_w` | ✅ 比值 = 1.4152 ≈ √2，两处口径自洽 |
| 电流密度 `J = I_ph/(N_p·π(d/2)²)` | ✅ 并联支路均分假设正确，与 feasibility 层独立实现数值一致 |
| 线电阻 `R_line = 2·R_ph` | ✅ Y 接线线间电阻正确 |
| 风损 `½·Cf·ρ·ω³·(Ro⁵−Ri⁵)·2` | ✅ 环形盘面 + 双转子因子，形式正确 |

### 4.2 Confirmed defect（分类 A）

#### **D-01 · 气隙磁密谐波频谱横轴换算方向错误 → 基波被过滤出图**

`motor_core/calculations.py:490`（以及 legacy 同源实现 `PMDC_Calculator_claude204.py:755`）：

```python
harmonics = np.arange(len(spectrum)) * pole_count / 2.0    # = k · pole_pairs
```

`mechanical_angle_deg = linspace(0, 360, 720)` 覆盖**一个机械周期**，故 FFT bin `k` = 每机械转 k 个周期。电气基波位于 `k = pole_pairs`。因此电气谐波次数应为 `k / pole_pairs`，代码写成了 `k × pole_pairs`——**方向反了，误差因子 pole_pairs²**。

实测（default，p=8）：

```
最大幅值 FFT bin  k = 8   → 真实电气谐波次数 = 8/8 = 1（基波）
代码标注          = 8×8 = 64
harmonics[:8]     = [0, 8, 16, 24, 32, 40, 48, 56]
```

下游后果（`PMDC_Calculator_claude204.py:1854-1858`）：

```python
harmonics = flux_data.get("harmonics", ...)
valid_idx = harmonics <= 25
ax2.bar(harmonics[valid_idx], spectrum[valid_idx], ...)
```

`harmonics ≤ 25` 只保留 `[0, 8, 16, 24]`，即 **FFT bin k = 0,1,2,3**——全部是基波以下的泄漏 bin。**基波（k=8）被过滤掉了**。也就是说"气隙磁密谐波频谱"图对 p=8 的默认机器只画了 4 根几乎无意义的柱子。极对数越大越严重。

- 分类：**A. confirmed defect**
- 影响：display-only，**不影响任何数值结果**（`harmonics` 未参与任何计算）
- 位置：**在 protected file 内**，按规则仅记录，不修复
- 附带小问题：`linspace(0,360,720)` 端点重复（0° 与 360° 同为样本），引入轻微谱泄漏

#### **D-02 · legacy 设计校验恒定误报"无法制造"**

`PMDC_Calculator_claude204.py:1482`：

```python
if perf.K_fill > 0.8:
    warnings.append("⚠️ 严重: 填充系数超过实际限制 (>0.8) - 无法制造!")
```

`K_fill` 的定义（`calculations.py:567` / legacy:845）是**内圆周上的一维裸铜线宽占比**，不是槽满率：

```python
fill_factor = (3·N_ph·2·n_par·d_wire) / (π·D_in)
```

实测：

| 设计 | K_fill |
|---|---:|
| application default | **2.456** |
| `FEASIBLE_STARTING_OVERRIDES`（官方"可行起点"） | **3.274** |

该值在任何现实 AFPM 设计下都远大于 1，因此 **`>0.8` 分支永远命中**。用户每次点计算都会看到"严重：无法制造！"。

讽刺的是，Phase 8G 的 `design_feasibility.py` 已经**明确禁止**这种用法：

> `legacy 线性绕组占比 {:.3f} 不得用于宣称无法制造。`

Phase 8E 也已经把报告正文里的数值行改名为 `Legacy 线性绕组占比`（`legacy:1431`）——但 **`_check_design_validity` 的警告文案没有跟着改**，仍在做被明令禁止的事。

- 分类：**A. confirmed defect**（legacy 层，非 protected file）
- 影响：**高**。恒真的"严重"级告警会训练用户忽略所有告警（alarm fatigue），并直接与 Phase 8G 的工程结论矛盾

#### **D-03 · legacy 电压裕量提示给出方向相反的工程建议**

`PMDC_Calculator_claude204.py:1477-1480`：

```python
if perf.V_margin < 5:      "⚠️ 警告: 电压裕量不足 (<5%) - 动态响应受限"
elif perf.V_margin > 40:   "ℹ️ 提示: 电压裕量较大 (>40%) - 考虑增加匝数"
```

`V_margin` 是 legacy 口径 `(V_dc − V_required_line_rms)/V_dc`，把**线电压 RMS 直接与 DC 母线电压相比**，缺失调制系数。Phase 6F/8G 已确立正确同基包络为 `V_dc/√2`（线性 SVPWM）。

实测，`FEASIBLE_STARTING_OVERRIDES` 设计（V_dc=72）：

```
legacy V_margin    = +40.34 %   → 触发"考虑增加匝数"
same-basis margin  = +15.63 %   （可用 50.91 V / 所需 42.96 V）
```

用户按提示增加匝数 → E 上升 → 真实同基裕量从 15.6% 迅速逼近并越过 0。**这条提示会主动把用户推向不可实现的设计。**

同一根因还影响 legacy 内置优化器的硬约束（`legacy:2051`）：

```python
if perf.V_required > params["V_dc"]:   score -= 10000
```

阈值应为 `V_dc/√2`。由于这是**排序相关**的约束（不像 `K_fill` 那样恒定命中、不改变排序），优化器会真实地选出违反 SVPWM 包络的设计。

- 分类：**A. confirmed defect**
- 影响：**高**，且是唯一一条会导致用户做出错误设计决策的问题

#### **D-04 · 零值输入被拒，且提示文案自相矛盾**

`motor_core/validation.py:_parse_numeric_field`：`if lower is not None and parsed <= lower` → `min: 0.0` 实际含义是**严格大于 0**。但多个字段的 `suggestion` 文案写的是"非负"。

实测：

```
k_cogging  = 0 → REJECTED：合法范围为 > 0.0；建议：请输入非负齿槽转矩系数。
k_ripple_6 = 0 → REJECTED：…建议：请输入非负 6 次谐波系数。
k_ripple_12= 0 → REJECTED：…建议：请输入非负 12 次谐波系数。
h_yoke     = 0 → REJECTED：…建议：请输入非负轭部高度。
h_slot     = 0 → REJECTED：…建议：请输入非负槽深。
```

工程后果：**用户无法建模"理想无齿槽、无转矩脉动"的算例**——而这恰恰是 coreless AFPM（本项目默认拓扑）最自然的基准工况。`h_yoke = 0` 对无铁芯定子同样是合法输入。

- 分类：**A. confirmed defect**（validation 层，非 protected file）
- 影响：中；阻断了一类合法建模场景，且错误消息误导用户反复重试

#### **D-05 · coreless 设计仍被计入铁损**

`calculations.py:325`：

```python
core_loss_w = CORE_LOSS_RATED_POWER_RATIO * i.rated_output_power_w   # 0.01 · P_rated
```

该式**不查询 `is_coreless`**，也不随频率/磁密变化。而 `calculate_cogging_torque()`（`:357`）是查 `is_coreless` 的——同一模型内对同一个拓扑开关处理不一致。

实测（default，`coreless=True`，`slot_type="无槽"`）：

```
core_loss_w = 8.00 W   （总损耗 69.99 W 的 11.4%）
copper 39.54 / eddy 18.94 / mech 3.51 / core 8.00
efficiency = 91.96 %
```

对一台**没有定子铁芯**的电机收取 8 W 定子铁损。若正确置零，效率约升至 92.7%。

- 分类：**A. confirmed defect**（一致性缺陷）/ 同时是 **C. modeling limitation**（`core_loss` 与转速、磁密完全解耦）
- 位置：**在 protected file 内**，仅记录
- 附带：因 `core_loss ∝ P_rated` 而非 `∝ f^1.5·B²`，**速度扫描中的效率曲线在物理上不可信**（P_rated 在扫描中保持不变，故铁损在整个转速范围内是常数）

#### **D-06 · 发布校验和文件的可用性缺陷**

```
release/SHA256SUMS.txt : ASCII text, with CRLF line terminators
$ sha256sum -c SHA256SUMS.txt
sha256sum: 'MotorCalculator-...zip'$'\r': No such file or directory   ← 3/3 FAILED
```

同时，`SHA256SUMS.txt` 列出了 `MotorCalculator.exe`，但该文件**不在 `release/` 目录**（它在 `dist/` 与 zip 内部）。

哈希值本身**全部正确**（我用绝对路径逐一重算比对通过）。问题纯粹是分发文件的可用性：Git Bash / WSL / MSYS 用户无法直接 `-c` 校验。

- 分类：**A. confirmed defect**（deployment 层，低严重度）

### 4.3 Suspected risk，需要测试确认（分类 B）

#### **R-01 · `required_voltage_v` 中 R 与 X 使用了不同的电气基准**

`calculations.py:557-562`：

```python
resistive_voltage_drop_v = I_ph · line_resistance_ohm            # = I·2R_ph      → 线间基准
inductive_voltage_drop_v = 2π·f_e · line_inductance_h · I_ph     # = I·ω·1.15L_ph → 每相同步基准
required_voltage_v = sqrt(E_line_rms² + IR² + IX²) · 1.05
```

`line_inductance_h = phase_inductance_h − mutual_inductance_h`，实测比值 **1.15**（因 `M = −0.5 × 0.3 × L_ph`）。这**是每相同步电感 L_s**，不是线间电感（线间应为 `2(L_ph − M)`）。

同一根式中：`E` 线基准 ✅、`IR` 线基准 ✅、`IX` 每相基准 ❌。

实测（default）：

```
E_line_rms = 40.885 V
I·R_line   =  2.333 V
I·X        = 27.025 V      ← 主导项
```

由于 `IX` 是主导项，基准差 2× 对结果影响很大。

#### **R-02 · `required_voltage_v` 用三项 RSS 而非相量合成**

对 id=0 控制，`E` 与 `I·R` 基本同相，正确形式应为 `sqrt((E+IR)² + (IX)²)`，而非 `sqrt(E² + IR² + IX²)`。

实测：

```
代码 RSS-of-3      = 51.518 V   （= perf.required_voltage_v）
相量 (E+IR) 合成   = 53.520 V
差值               = +2.00 V  (+3.89 %)   ← 代码偏低，非保守
```

R-01 与 R-02 **方向一致，都使所需电压偏低、裕量偏乐观**，与 D-03 的显示口径问题叠加。

- 分类：**B. likely defect requiring test**
- 位置：**protected file 内**，且 AGENTS.md 明确列 `required_voltage_v` 为需批准才可改。**本次仅记录证据，不做任何修改。**
- 建议：v1.1 走 Formula Change Approval Rule，提供 legacy / revised 并行输出（沿用 Phase 3B/3C 已验证的 parallel-output 模式），不切默认路径

#### **R-03 · 齿槽转矩波形存在采样上限风险**

`calculations.py:355`：`rotor_position_rad = np.linspace(0, 2π, 360)`（359 个区间 → 有效采样率 359/机械转），波形含 `3×LCM(pole_count, slot_count)` 次谐波。Nyquist 上限 ≈ 179.5。

- default（p=8, slots=24）：LCM=48 → 3·LCM=144 < 179.5，**安全**。实测密采样峰值因子 1.1283821 vs 360 点 1.1283816，一致 ✅
- 但 p=10 / slots=30 → LCM=60 → 3·LCM=180 **> 179.5，触发混叠**，报告峰值将变成采样伪影

- 分类：**B**，触发条件明确、可写成 property-based test
- 位置：protected file 内

#### **R-04 · 齿槽转矩峰值语义与用户输入不一致**

用户输入 `k_cogging` 直觉上是"齿槽峰值 / 额定转矩"。但波形叠加了 0.3 与 0.1 的 2/3 次谐波，实测峰值因子 = **1.1284**：

```
k_cogging·T_rated（用户意图） = 0.06112 N·m
实际报告峰值                  = 1.1284 × 该值
```

（default 因 `coreless=True` 直接返回全零，故当前默认路径不暴露此问题。）

- 分类：**B / E**，低影响，属命名与文档问题

#### **R-05 · `line_inductance_h` 命名误导**

该字段实为每相同步电感 `L_s = L_ph − M`。它被 Phase 8I 动态仿真用作 `Ld = Lq`（按 phase8i 文档："`Ld=Lq` 来自标量相电感"）——**在动态侧用法是对的**，恰恰说明静态 `required_voltage_v` 里把它当线电感用是不一致的。

- 分类：**B**，命名问题放大了 R-01

#### **R-06 · 反电动势波形字典的 `E_rms` 对梯形波不成立**

`calculations.py:407, 419`：

```python
"back_emf_phase_rms_v_legacy_waveform": peak_back_emf_v / sqrt(2.0)
"E_rms": peak_back_emf_v / sqrt(2.0)
```

无论 PMSM 还是 BLDC 都除以 √2。对梯形波，RMS/peak ≠ 1/√2（理想 120° 梯形约为 0.8165）。字段名含 `legacy_waveform` 算是有标注，但 `E_rms` 别名没有。

- 分类：**B**，需确认是否被 UI/导出消费

#### **R-07 · 铜导体涡流损耗使用气隙峰值磁密覆盖全部铜体积**

`calculations.py:308, 317-323`：`local_flux_density_t = air_gap_flux_density_peak_t`，乘以包含端部绕组的 `copper_volume_m3`。端部绕组所处磁密远低于气隙峰值 → **系统性高估**。对 coreless AFPM 而言导体涡流损耗是主导损耗之一（实测 18.94 W，占总损耗 27%），这个高估不可忽略。

- 分类：**B / C**

#### **R-08 · legacy GUI 模块以源码形式动态 exec，无完整性校验**

`gui/main_window.py:129` 对 `PMDC_Calculator_claude204.py` 执行 `spec.loader.exec_module()`。项目对 kernel 做了 SHA-256 保护并写入 release manifest，但**这个同样在生产路径上、且体量最大的文件没有被纳入哈希保护**。

- 分类：**B**（一致性/供应链完整性），本地桌面应用风险有限，但与项目自身的 protected-baseline 纪律不符

---

## 5. Validation & Accuracy Assessment

`validation/` 与 `motor_core/validation_*.py` 这一层是本项目**第二高价值的资产**。framework 的规则设计（`source_type` / `evidence_level` / `provided|inferred|unavailable|not_applicable` / 只有 `directly_comparable` 才算误差 / 禁止用 0 表示未知 / 禁止自动标定）在方法论上是正确的，且被测试真实约束（`test_creator_pmsm_no_overclaim.py` 这类命名本身就说明问题意识到位）。

### 回答规定的五个问题

**1. 哪些输出具有强内部一致性证据？**

- PMSM `Ke`/`Kt` 修正口径：单位语义、三相功率平衡、独立解析参考、下游隔离，四重验证
- BLDC `Ke`/`Kt` 修正口径：分段推导 + 独立数值积分 + 解析参考 + 生产/参考交叉验证
- 严格 SI 额定转矩 vs legacy `9.55·P/n`
- 磁密 peak/avg/rms 三口径（解析式与 720 点数值互验，本次评审独立复现 ✅）
- Clarke/Park、SVPWM 平均模型、RK4/Euler 收敛性、dq 电流环、MTPA/弱磁
- 项目 schema v1 往返、integrity、迁移、恢复分类

**2. 哪些输出具有有意义的外部证据？**

- `CREATOR PMSM Data`（唯一一份真实导入的外部记录），且被 comparability 规则严格限制了可比字段
- Phase 7B1 AFPM 外部校验 campaign + Phase 7G benchmark evidence + Phase 7H FEA reference foundation

**坦率结论**：外部证据的**广度**（1 份 PMSM 记录 + 有限 AFPM 文献）远不足以支撑任何跨设计空间的精度声明。项目自身对此的表述是诚实的。

**3. 哪些输出基本未经验证？**

按证据强度从弱到强排序，**未验证**的是：

- 铁损、机械损、风损、轴承损、磁体涡流损 —— 全部是经验系数或常数比例；`core_loss` 甚至与转速无关（见 D-05）
- 静态温升 —— 仪表板已诚实标注 `静态温升 = UNAVAILABLE`，正确
- `required_voltage_v` —— 无外部证据，且本次发现两处基准问题（R-01/R-02）
- `fill_factor`（K_fill）—— 不是可验证的物理量（见 D-02）
- 齿槽转矩、转矩脉动 —— 幅值完全由用户系数给定，不是预测
- 电感（`phase_inductance_h`）—— `π(Ro²−Ri²)/6` 是纯几何近似，无验证
- AFPM 径向切片 back-EMF / winding network —— sandbox 级
- 动态 FOC/热 —— 明确定位为 engineering sandbox，**不是 digital twin**

**4. 用户在哪里可能把 confidence 误读为 accuracy？**

这是本节最重要的发现，共三处：

- **(a) 双重口径同屏（最严重）**。仪表板给出经过严谨语义修正的 `同基电压裕量`，同一窗口的 legacy 结果文本区给出相差 44.5 pp 的另一个数。用户看到"仪表板很专业"，就会默认"整个应用的数字都同样严谨"——**Phase 8H 的高质量表达反而给 legacy 层背了书**。
- **(b) `参数不确定性 ≠ 总预测误差`**。Phase 7I 文档明确写了，但 100 样本 Monte Carlo 输出的置信区间在视觉上与"预测精度区间"无法区分。UI 上需要比文档更强的阻断式提示。
- **(c) 速度扫描图**。图注写了"不是电驱能力包络"，措辞正确；但四象限里画着"转矩-转速"曲线——这个图形语汇在电机工程里几乎专指能力包络。**图注对抗不了图形本身的语义暗示。** 且该曲线实为 `T = 9.55·P_rated/n` 的等功率双曲线，因为扫描保持 `P_rated` 不变。

**5. 下一步信息增益最高的验证数据是什么？**

排序（按 信息增益 / 获取成本）：

1. **一台真实 coreless AFPM 样机的 no-load back-EMF vs 转速曲线**。成本最低（一台电机 + 示波器 + 一次拖动），却能一次性验证磁路链（`pole_flux` → `Ke` → `B_g`）——这是整个模型的**上游**，上游错则全错。当前 `B_g,peak` 完全无外部锚点。
2. **同一样机的 DC 相电阻 + 相电感（LCR 表）**。直接检验 `phase_resistance_ohm` 与 `phase_inductance_h`，后者是 R-01/R-02 争议的核心参数。成本近乎为零。
3. **一条负载工况的实测输入功率/输出功率/效率分解**。可将 `core_loss`、`eddy_loss` 的经验系数从"猜测"降级为"拟合残差"，为 P2 的损耗模型改造提供依据。
4. 2D/3D FEA 的气隙磁密波形（用于验证 α_p 方波假设与 Carter 系数）—— 成本高，排第 4。

**关键点**：前三项加起来是"一台样机 + 一个下午"，却能把当前 `largely unvalidated` 的比例显著降低。**这比再做三个 Phase 的软件功能更有价值。**

---

## 6. GUI / UX Assessment

### 6.1 做得好的

- Phase 8H 仪表板的 `AvailabilityStatus` / `DashboardStatus` 分级 + `interpretation_zh` 逐指标解释，是**同类工具里少见的诚实**
- `NOT_ENOUGH_GEOMETRY` / `NOT_ENOUGH_SEMANTICS` 这种"说不出来就明说说不出来"的状态设计非常好
- 中文优先本地化 + Basic/Advanced 模式 + preset + 单位切换 + 引导面板，覆盖完整
- 高 DPI 已做 200% 实测（1824×980 主窗口，无裁切），有截图证据
- 恢复/自动保存对用户透明，且有 corrupt quarantine

### 6.2 问题

#### **U-01 · 首次启动即呈现一个三重不可行的设计（P1）**

实测 application default 同时触发：

```
电流密度   J = 8.88 A/mm²        → CURRENT_DENSITY_HIGH（>6）
同基电压裕量 = −51.79 %           → VOLTAGE_MARGIN_SEVERE（严重设计风险）
legacy 绕组占比 = 2.456           → legacy "无法制造!"（恒真误报，D-02）
```

而项目里**已经有**一个官方可行起点 `FEASIBLE_STARTING_OVERRIDES`（V_dc=72 / P=600 / n=2200 / d_wire=1.2 / 半闭口槽 / coreless=False），实测：

```
J = 4.34 A/mm²  ✅   槽满率 = 0.318 ✅   同基裕量 = +15.63 % ✅
仅一条 INFO 级摘要，无任何 WARNING/SEVERE
```

**它没有被用作应用默认值。** 新用户第一眼看到满屏红色告警，无法区分"这是我的设计问题"还是"这个软件坏了"。

#### **U-02 · 同一窗口两套口径（P0，见 D-03/§1）**

`Legacy 直流母线差额` 与 `同基电压裕量` 相差 44.5 pp；文本区的**告警文案**仍用旧口径下结论。数值行 Phase 8E 已改名，告警文案漏改。

#### **U-03 · 恒真的"严重"告警（P0，见 D-02）**

alarm fatigue 的教科书案例：一条永远为真的"严重"级消息会使用户忽略**所有**告警，包括那条真正重要的 `VOLTAGE_MARGIN_SEVERE`。

#### **U-04 · 谐波频谱图实际无内容（P2，见 D-01）**

用户看到一张标着"谐波"的柱状图，实际只有 4 根低次泄漏柱，基波不在图上。比"没有这张图"更糟。

#### **U-05 · 零值输入被拒的错误提示（P1，见 D-04）**

错误消息自己写着"请输入非负"却拒绝 0，用户会反复尝试。

#### **U-06 · 转矩-转速图的语义暗示（P1，见 §5-4c）**

建议：把该子图标题从"转矩-转速"改为"等额定功率下的转矩-转速（非能力包络）"，或在曲线上加显式水印。文字免责已经做了，但**图形语汇的默认含义压过文字**。

#### **U-07 · 术语一致性**

`填充系数` / `绕组占比` / `槽满率` / `裸铜槽占比` 四个词在不同层指代不同量。Phase 8E/8G 已做了大部分区分（`Legacy 线性绕组占比` vs `近似裸铜槽占比`），但 legacy 告警文案与 legacy 优化器输出（`legacy:2099` "填充系数"）仍用旧词。

---

## 7. Performance Assessment

**结论：当前不存在需要并发化的真实瓶颈。Phase 8I 保持同步执行的决定是正确的，我支持它。**

Phase 8I 记录的观测（本次未复测，但与代码结构相符）：

| 操作 | 时间 |
|---|---:|
| 默认静态计算 | 117.4 ms |
| 7 点静态速度扫描 | 9 ms |
| 100 样本不确定性分析 | 535 ms |
| 4 点敏感性分析 | 10 ms |
| 项目保存 / 加载 | 10.0 / 3.7 ms |
| 性能图渲染 | 686 ms |

评估：

| 手段 | 是否值得 | 依据 |
|---|---|---|
| worker thread / 取消状态机 | **否** | 最慢的分析 535 ms，远低于人类感知痛阈；引入线程会带来 Tk 主线程约束、取消语义、状态一致性三类新风险 |
| multiprocessing | **否** | 同上，且 Windows spawn 开销会超过计算本身 |
| 向量化 | **局部值得（P3）** | `_trapezoidal_back_emf` 对 720 点做 Python for-loop（×3 相），`calculate_flux_distribution` 对 720 点做 for-loop。可 `np.select` 向量化，但收益在毫秒级，**除非速度扫描点数提高到 201 否则不值得** |
| 缓存 / memoization | **有条件值得（P2）** | 速度扫描每点完整重跑 `parse → engine → feasibility`。21 点 ≈ 21×117ms？实测 7 点仅 9 ms，说明单点远快于 117 ms 的首次调用（首次含 import/numpy 预热）。**先测量再优化** |
| 惰性加载 | **值得（P2）** | 安装版启动 7.3–18.5 s 是唯一真正影响体验的数字。主要来自 matplotlib + Tk + PyInstaller one-folder 解压。可考虑推迟 matplotlib import 到首次绘图 |
| 批处理 / GUI 重绘节流 | 否 | 无证据 |

**最有价值的性能工作是启动时间（7.3–18.5 s），不是计算。** 建议先做启动 profiling 再决定。

内存：安装版空闲 working set 98 MiB / private 551 MiB。private 偏高，但对 matplotlib+Tk 桌面应用属正常范围。

---

## 8. Test Quality Assessment

638 passed / 90 个测试文件。**不按数量评价，按覆盖语义评价。**

### 覆盖良好的

| 维度 | 证据 |
|---|---|
| 物理语义 | `test_ke_kt_units.py`、`test_bldc_ke_definitions.py`、`test_bldc_kt_definitions.py`、`test_bldc_waveform_rms.py`、`test_bldc_power_balance.py`、`test_energy_consistency.py`、`test_motor_control_modes.py` —— **RMS/peak、相/线、波形语义有专门测试，这在同类项目中很罕见** |
| 回归 | `test_legacy_regression.py` + 受哈希保护的 `legacy_baseline.json` |
| 数值收敛 | `test_integrator_basic.py`、Phase 6C solver validation |
| 隔离性 | `test_bldc_revised_isolation.py`、`test_bldc_parallel_outputs.py` —— 专门测"修正值没有污染默认路径" |
| 不过度声明 | `test_creator_pmsm_no_overclaim.py`、`test_creator_pmsm_comparability.py` —— **把"不许吹牛"写成测试**，方法论上非常成熟 |
| 打包/部署 | `test_phase8a_runtime_packaging.py`、`test_phase8f_deployment.py`（46 项部署专项） |
| 保存/恢复 | `test_project_persistence.py`、`test_phase8c_recovery.py`（372 行，含损坏文件隔离） |
| GUI 冒烟 | `test_gui_imports.py`、`runtime/gui_smoke.py`（873 行） |
| 可选依赖降级 | `test_optional_matplotlib_dependency.py`、`test_chart_save_behavior.py` |

### 高价值缺失测试（按优先级）

| # | 缺失测试 | 理由 | 会捕获 |
|---|---|---|---|
| T-1 | **跨层口径一致性测试**：断言 UI 上任何两个同名/近名指标不得来自不同基准，或至少断言 `legacy V_margin` 与 `same-basis margin` 的差异被显式标注 | 本次最严重问题无任何测试覆盖 | D-03、U-02 |
| T-2 | **告警可达性测试**：对 default + feasible preset，断言 legacy `_check_design_validity` 不产生恒真告警 | 恒真告警是 640 项测试全绿下的盲区 | D-02 |
| T-3 | **频谱轴次数测试**：断言 `flux["harmonics"]` 中最大幅值 bin 对应电气次数 ≈ 1 | 纯断言即可，成本极低 | D-01 |
| T-4 | **property-based：极对数 × 槽数扫描下的采样充分性**（Hypothesis） | 当前所有测试都在 p=8/slots=24 附近 | R-03 混叠 |
| T-5 | **拓扑开关一致性测试**：`is_coreless=True` ⇒ 齿槽=0 **且** 铁损=0 | 同一开关的两处处理不一致 | D-05 |
| T-6 | **边界值参数化测试**：所有 `min: 0.0` 字段的 0 值行为，与 suggestion 文案断言一致 | suggestion 与规则脱节无测试 | D-04 |
| T-7 | **数值参考测试（numerical reference）**：一组手算的 AFPM 磁路/Ke 参考值，独立于 legacy baseline | 当前 3 个 legacy baseline 全是 BLDC 路径，PMSM 默认路径**没有独立数值锚点** | 潜在 PMSM 路径回归 |
| T-8 | **畸形项目文件模糊测试**：截断 JSON、错误 schema_version、integrity 哈希不匹配、超长字段、非法 UTF-8 | 已有 corrupt 分类，但未见系统化 fuzz | 加载路径鲁棒性 |
| T-9 | **发布校验和可用性测试**：断言 `SHA256SUMS.txt` 为 LF，且所列文件均存在于 `release/` | | D-06 |

### 测试结构问题

- **按 Phase 命名的测试文件（`test_phase7k_*`、`test_phase8d_*` …）随时间会变成考古学**。它们测的是"某个 Phase 交付了什么"，而不是"某个能力是否正确"。建议 v1.1 后逐步按 capability 重组（低风险、纯重命名/移动）。
- `test_phase7d_proposal_docs.py` 之类**对文档存在性的测试**属于实现细节测试，脆弱且价值低。
- 未见 property-based testing（Hypothesis）与 golden numerical reference（除 legacy baseline 外）。

---

## 9. Deployment Assessment

| 项 | 状态 | 评价 |
|---|---|---|
| PyInstaller 6.16.0 one-folder | ✅ | 1,248 文件 / 91.1 MB；one-folder 优于 one-file（启动更快、Tk 更稳），选择正确 |
| Inno Setup 6.7.3 | ✅ | 稳定 AppId `{A5F90D43-…}`，原地升级验证通过 |
| Portable ZIP | ✅ | 41.5 MB，仓库外运行、清除 `PYTHONHOME`/`PYTHONPATH`/`TCL_LIBRARY`/`TK_LIBRARY` 验证通过 |
| release manifest | ✅ | 字段完备，含 protected hash、test counts、各项 gate 状态 |
| checksums | ⚠️ | 哈希**全部正确**（本次独立重算验证），但 CRLF + 列出未随附文件（D-06） |
| 版本管理 | ⚠️ | `version.py` 单一真相源 ✅，但**仓库无 git tag**，`release_manifest.git_commit`(`ee4ed13`) 与 HEAD(`b70982d`) 不同（仅 2 个 docs commit，可接受） |
| 升级身份 | ✅ | 0.9.0 → 1.0.0-rc1 实测通过，`.motorproj`、恢复/反馈数据、用户数据标记均保留 |
| 用户数据 | ✅ | `%LOCALAPPDATA%\MotorCalculator`，与安装目录分离，卸载保留 |
| 卸载/重装 | ✅ | 实测通过 |
| 日志/诊断导出 | ✅ | `_export_runtime_diagnostics` 存在 |
| Defender | ✅ | 4.18.26060.3008-0，三件产物均无威胁 |
| 代码签名 | ❌ | `signed: false`，`NotSigned` |
| 干净机器验证 | ❌ | `TRUE_CLEAN_MACHINE_TEST = BLOCKED_BY_ENVIRONMENT`（Sandbox 不可用，无一次性干净 Windows VM） |
| SmartScreen | ❓ | `NOT_OBSERVED_SILENT_LOCAL_TEST_UNSIGNED` |

### 是否存在其他 release blocker？

除已知三项（未签名 / 无干净机器 / SmartScreen 未知）外，**我没有发现新的技术性 release blocker**。

但我要指出一个**非技术性的 release blocker**：

> D-02（恒真"无法制造！"）与 D-03（方向相反的匝数建议）是**产品可信度 blocker**。一个电机设计工具在首次启动时告诉用户"无法制造"，并在用户改用官方推荐参数后建议一个会破坏可行性的修改——这在技术上不算 crash，但在工程工具的语境下比 crash 更严重。**这是我不建议原样公开 v1.0.0 的主要理由，优先级高于代码签名。**

---

## 10. Security / Data Safety Assessment

按"本地工程桌面应用"的合理标准评估，**不建议引入企业级安全特性**。

| 检查项 | 结果 |
|---|---|
| `eval` / `exec` 于产品代码 | ✅ 无（唯一 `exec_module` 是 legacy GUI 动态加载，见 R-08） |
| `pickle` | ✅ 无（且 `test_phase8c_recovery.py:366` 主动断言 payload 中不含 "pickle"，很好） |
| `os.system` / `shell=True` | ✅ 无 |
| `subprocess` | ✅ 仅 `version.py:28` 调用 `git rev-parse HEAD`（**已用 `sys.frozen` 守卫，打包版不执行**，参数为固定列表非 shell，2 s 超时，返回值做 40 位 hex 校验）——实现得相当谨慎 |
| 硬编码绝对路径 | ✅ 产品代码中无（grep 唯一命中是英文文案误匹配） |
| JSON 解析 | ✅ 标准 `json`，无自定义 decoder hook |
| 原子保存 | ✅ 临时文件 + fsync + `os.replace` |
| 覆盖保护 | ✅ `.bak` 备份，且备份本身也走临时文件 + `os.replace` |
| 完整性校验 | ✅ canonical JSON + SHA-256，加载时 `_verify_integrity` |
| 恢复文件损坏处理 | ✅ `_quarantine()` 隔离而非删除 |
| 路径穿越 | ✅ 路径均经 `Path(...).expanduser().resolve()`；用户提供的路径来自 `filedialog`，无来自文件内容的路径拼接 |
| 破坏性清理 | ✅ `cleanup_project` 有 uuid + input hash 双重限定 |
| 敏感数据泄露 | ✅ 本地应用，无网络出口；诊断导出内容需确认不含完整用户路径（低风险） |
| 用户数据位置 | ✅ `%LOCALAPPDATA%`，可用 `MOTOR_CALCULATOR_USER_DATA` 覆盖（仅用于受控测试） |

### 唯一实质性观察

**R-08**：`PMDC_Calculator_claude204.py` 以源码形式在运行时被 `exec_module()`，且未纳入 protected hash 集合。对本地应用而言实际风险很低（攻击者若能改这个文件，也能改 `.exe`），但它与项目自身"对 kernel 做哈希保护"的纪律不一致。建议把它加入 `protected_model_hashes`（**这是 manifest/构建脚本层面的改动，不触碰产品代码**）。

**总体评价：安全与数据安全方面没有 release blocker，实现质量高于同类桌面工具的平均水平。**

---

## 11. Confirmed Defects（8 项）

| ID | 摘要 | 位置 | 严重度 | 物理是否改变 |
|---|---|---|---|---|
| **D-01** | 磁密谐波频谱横轴按 `k×p` 而非 `k/p`，导致基波被 `harmonics ≤ 25` 过滤出图 | `calculations.py:490`（**protected**）+ `PMDC_…204.py:755,1854-1858` | 中（display-only） | 否 |
| **D-02** | `K_fill > 0.8 → "无法制造!"` 恒真误报（实测 default 2.456 / feasible 3.274） | `PMDC_…204.py:1482` | **高** | 否 |
| **D-03** | legacy `V_margin > 40 → "考虑增加匝数"` 基于乐观口径，建议方向与真实同基裕量相反；同根因影响 legacy 优化器硬约束 `V_required > V_dc` | `PMDC_…204.py:1477-1480, 2051` | **高** | 否 |
| **D-04** | `min: 0.0` 实为严格 >0，但 suggestion 文案写"非负"；`k_cogging/k_ripple_6/k_ripple_12/h_yoke/h_slot` 的 0 值被拒 | `motor_core/validation.py` | 中 | 否 |
| **D-05** | `is_coreless=True` 时齿槽转矩置零但铁损不置零（default 计入 8 W，占总损耗 11.4%） | `calculations.py:325`（**protected**） | 中 | **是**（修复会改结果） |
| **D-06** | `release/SHA256SUMS.txt` 为 CRLF，`sha256sum -c` 3/3 失败；且列出未随附的 `MotorCalculator.exe` | `release/` | 低 | 否 |
| **D-07** | 仓库无 `v1.0.0-rc1` git tag，发布可追溯性依赖 manifest 中的 commit 字段 | 仓库级 | 低 | 否 |
| **D-08** | `AGENTS.md` 停留在 Phase 4A/4B：宣称 `138 passed`、分支 `research/external-data-source-scouting`、"Phase 4A 之后无已批准阶段"——与实际相差 8 个 Phase | `AGENTS.md` | 中（上下文恢复失真） | 否 |

---

## 12. Suspected Risks Requiring Verification（8 项）

| ID | 摘要 | 位置 | 需要的验证 |
|---|---|---|---|
| **R-01** | `required_voltage_v` 中 R 用线基准(`2R_ph`)、X 用每相同步基准(`1.15L_ph`)，基准混用；IX=27.0 V 为主导项 | `calculations.py:557-562`（protected） | 手工相量推导 + 与 Phase 6F dq 稳态解对拍 |
| **R-02** | 同式用三项 RSS 而非相量合成；实测比 `sqrt((E+IR)²+IX²)` 低 3.89 %，方向非保守 | 同上 | 同上 |
| **R-03** | 齿槽波形 360 点采样，含 `3×LCM` 次谐波；`3×LCM > 179.5` 时混叠（p=10/slots=30 即触发） | `calculations.py:355`（protected） | property-based 扫描 p × slots |
| **R-04** | 报告齿槽峰值 = 1.1284 × `k_cogging` × `T_rated`，与用户输入语义不符 | `calculations.py:360-366`（protected） | 数值断言 + 文档澄清 |
| **R-05** | `line_inductance_h` 实为每相同步电感，命名误导；动态侧当 `Ld=Lq` 用法正确，反证静态侧不一致 | `calculations.py:240` / `models.py` | 交叉核对静态与动态两处用法 |
| **R-06** | 波形字典 `E_rms = E_peak/√2` 对梯形波不成立（理想 120° 应 ≈0.8165） | `calculations.py:407,419`（protected） | 确认下游消费者；数值断言 |
| **R-07** | 导体涡流损耗以气隙峰值 B 覆盖全部铜体积（含端部），系统性高估；该项占默认总损耗 27 % | `calculations.py:308,317-323`（protected） | 与实测效率分解对比（需 §5-Q5 第 3 项数据） |
| **R-08** | 生产路径上的 legacy GUI 模块以源码 `exec_module()` 加载，未纳入 protected hash | `gui/main_window.py:129` | 决策：是否纳入 manifest 哈希集合 |

---

## 13. Modeling Limitations（确认既有，并补充）

Prompt 中列出的 12 项限制，本次评审**逐项确认属实**，并补充量化证据：

| # | 限制 | 本次评审补充 |
|---|---|---|
| 1 | AFPM 外部实验/FEA 验证有限 | 确认。`B_g,peak` 无任何外部锚点，而它是整条模型链的上游 |
| 2 | 参数不确定性 ≠ 总预测误差 | 确认，且 UI 上缺乏阻断式区分（§5-Q4b） |
| 3 | model-form uncertainty 未完全量化 | 确认 |
| 4 | 静态热保真度有限 | 确认，且 UI 已诚实标注 `静态温升 = UNAVAILABLE`，处理正确 |
| 5 | 铁损/机械损/风损/轴承损/磁体涡流损可能不完整 | **确认并加重**：`core_loss = 0.01·P_rated` 与转速、磁密**完全解耦**，且不查 `is_coreless`（D-05）。这使**速度扫描的效率曲线在物理上不可信** |
| 6 | 速度扫描不是真实转矩-转速能力包络 | 确认。实为 `T = 9.55·P_rated/n` 等功率双曲线；文字免责到位但图形语汇有误导（U-06） |
| 7 | BLDC 同基电压裕量语义不完整 | 确认，且处理得当：`voltage_status = NOT_ENOUGH_SEMANTICS`，曲线显式标 unavailable。**这是本项目处理"不知道"的最佳范例** |
| 8 | 槽占比是近似裸铜几何占比 | 确认。Phase 8G 的 `_slot_fill` 实现合理（扣除槽楔），但 legacy `K_fill` 是完全不同的一维线宽比，且被误用于"无法制造"判定（D-02） |
| 9 | 动态模型是 sandbox 而非 digital twin | 确认。单节点热 RC（绕组→环境）无定子/转子/磁体节点 |
| 10 | 无 FEA 等价性声明 | 确认，未发现任何越界表述 |
| 11 | 无制造认证声明 | 确认，且 `design_feasibility.py` 主动禁止此类推断 |
| 12 | 无普适精度保证 | 确认 |

**补充第 13 项限制**：

> **13. 静态与动态两条路径的电压约束语义不一致。** 动态侧（Phase 6F）用 `V_dc/√3` dq 相峰值包络；feasibility 侧（Phase 8G）用等效 `V_dc/√2` 线 RMS；静态 kernel 侧（legacy）用 `V_dc` 直接比较。三者共存于同一应用，只有前两者互相对齐。

---

## 14. Technical Debt（登记表）

| ID | 债务 | 位置 | 成本 | 风险 |
|---|---|---|---|---|
| TD-1 | legacy GUI 作为生产基类（动态 exec + monkeypatch + Mixin 覆盖 2556 行） | `gui/main_window.py:129-160` + `PMDC_…204.py` | 高 | 高（3/8 confirmed defect 在此） |
| TD-2 | `PMDC_…204.py` 2556 行 / `main_window.py` 1518 行，超大模块 | 同上 | 高 | 中 |
| TD-3 | 结果字典三套 key（中文 / 英文长名 / legacy 短名） | `calculations.py:395-505` | 中 | 中（消费者不明确） |
| TD-4 | `models.py` 大量 legacy property 别名 | `models.py` | 低 | 低（有意为之） |
| TD-5 | 电流密度逻辑双实现 | `calculations.py:566` / `design_feasibility.py:95` | 低 | 低（已实测数值一致） |
| TD-6 | 测试文件按 Phase 命名而非按 capability | `tests/test_phase*.py`（约 20 个） | 中 | 中（可维护性随时间恶化） |
| TD-7 | 对文档存在性的测试（implementation-detail test） | `test_phase7d_proposal_docs.py` 等 | 低 | 低 |
| TD-8 | 裸 `except:` | `PMDC_…204.py:2042` | 低 | 低 |
| TD-9 | 720/360 点 Python for-loop 生成波形 | `calculations.py:429-444, 476-485` | 低 | 低（性能非瓶颈） |
| TD-10 | `AGENTS.md` 严重过时 | 根目录 | 低 | **中高**（这是明文的 context-recovery 文档，失真会误导后续所有工作） |
| TD-11 | 阈值硬编码散布（`> 10.0` / `> 6.0` / `> 0.80` / `> 40` / `< 5`） | `design_feasibility.py` + `PMDC_…204.py:1467-1490` | 中 | 中（两套阈值无单一真相源） |
| TD-12 | 无 git tag 对应发布 | 仓库级 | 极低 | 低 |

---

## 15. Optimization Opportunities（对 prompt 13 项的就绪度评估，**不实施**）

| # | 方向 | 就绪度 | 前置条件 | 判断 |
|---|---|---|---|---|
| 1 | **更好的 AFPM 电磁验证** | **就绪** | 一台样机的 no-load back-EMF vs 转速 + LCR 实测 R/L | **最高优先级。** 成本最低、信息增益最高、无需改任何代码即可开始 |
| 2 | 真实转矩-速度能力包络 | 部分就绪 | 需先解决 R-01/R-02（电压约束基准）与 D-05（铁损随速度） | 依赖链长；但一旦 #1 完成，这是最有产品价值的功能 |
| 3 | 改进 BLDC 电压/电流语义 | 部分就绪 | 需定义受控 PWM/换相电压基准 | Phase 3E 已把 BLDC Ke/Kt 做扎实，缺的是**开关侧**语义 |
| 4 | 更好的损耗模型 | **未就绪** | 需 §5-Q5 第 3 项（实测效率分解）作为拟合锚点 | 无数据的损耗模型升级只是换一组猜测系数。**不要先做这个** |
| 5 | 改进热网络 | 未就绪 | 需实测温升数据 + 至少绕组/定子/机壳三节点几何 | 同上 |
| 6 | 饱和/非线性磁路 | 未就绪 | 对 coreless AFPM（本项目默认拓扑）**收益很低**——无铁芯即无饱和 | 优先级应低于文档暗示的位置 |
| 7 | 谐波反电动势 | 部分就绪 | Phase 7E 径向切片 back-EMF 已有基础；需先修 D-01 才能可视化验证 | 中等 |
| 8 | 齿槽 / 转矩脉动 | 未就绪 | 当前完全由用户系数给定，不是预测。要变成预测需要磁导谐波模型 | 需先解决 R-03 采样 |
| 9 | 绕组 / 制造模型 | **部分就绪** | Phase 8G `_slot_fill` 已是可用起点；需加入绝缘、线规、排布 | 中等偏高价值（直接服务用户实际决策） |
| 10 | 参数优化 | 部分就绪 | legacy 优化器已存在但硬约束用错基准（D-03）。**先修基准再谈优化** | 修完 D-03 后就绪度立刻变高 |
| 11 | 物理信息代理模型（PINN/surrogate） | **未就绪** | 需要 #1/#4 提供的真实数据；无数据的 surrogate 只是在拟合自己的假设 | 明确建议**推迟到 v2.0 之后** |
| 12 | 数据辅助残差修正 | **未就绪** | 同上，且与项目"禁止自动标定"的既有规则直接冲突，需先做政策决策 | 政策问题先于技术问题 |
| 13 | 自动化设计空间探索 | 部分就绪 | 依赖 #10 与正确的可行性判据 | 修完 D-02/D-03 后，可基于 `design_feasibility` 做，价值较高 |

**核心判断**：#4/#5/#11/#12 看起来最"高级"，但它们**全部阻塞在同一个前置条件上——缺少真实测量数据**。而 #1 的成本是"一台样机 + 一个下午"。

> **如果这个项目在未来 6 个月只能做一件事，那应该是拿到一台真实 AFPM 样机的空载反电动势曲线，而不是再写三个 Phase 的软件。**

---

## 16. P0 / P1 / P2 / P3 Roadmap

### P0 — 公开 v1.0 前必须处理（correctness / 可信度 blocker）

#### **P0-1 · 停用 legacy `_check_design_validity` 中已被 Phase 8G 取代的判据**

- **问题**：D-02（恒真"无法制造!"）+ D-03（方向相反的匝数建议）
- **证据**：K_fill 实测 2.456 / 3.274，`>0.8` 分支恒真；feasible preset legacy 裕量 40.34% vs 同基 15.63%
- **影响**：消除唯一一类会导致用户做出错误设计决策的输出；消除 alarm fatigue
- **风险**：**低**。仅移除/改写 legacy 告警文案，不触碰任何计算
- **实施范围**：`PMDC_Calculator_claude204.py:1467-1490` 的三个分支（`V_margin`、`K_fill`）——改为委派给 `format_feasibility_messages_zh()`，或直接删除并保留 Phase 8G 输出
- **影响文件**：`PMDC_Calculator_claude204.py`（**注意：Hard Rule 禁止删除该文件，但未禁止修改其 UI 文案；仍需用户明确批准**）
- **物理是否改变**：**否**
- **所需测试**：T-2（告警可达性），并在 default + feasible preset 两组输入上断言
- **预期收益**：产品可信度从"首启即自相矛盾"回到"自洽"

#### **P0-2 · legacy 优化器硬约束改用同基电压包络**

- **问题**：D-03 同根因，`legacy:2051` `if perf.V_required > params["V_dc"]` 应为 `V_dc/√2`
- **影响**：优化器不再推荐违反 SVPWM 线性区的设计
- **风险**：**中**。这会改变优化器输出（虽不改变任何 kernel 公式）。需回归 `legacy_baseline.json` 确认不受影响（优化器不在 baseline 路径上）
- **实施范围**：单行阈值 + 相应中文说明
- **物理是否改变**：**否**（判据非公式）
- **所需测试**：优化器在已知不可行设计上不再返回 `best_results`

> **两项 P0 均不触碰 protected `calculations.py`，不改任何 equation，不改 `legacy_baseline.json`。**

### P1 — 高价值下一步

| ID | 项目 | 问题 | 影响文件 | 物理变更 | 风险 |
|---|---|---|---|---|---|
| **P1-1** | legacy surface freeze：把 `PMDC_…204.py` 中仍在生产路径的 UI 行为清单化并标注 `ACTIVE`/`SUPERSEDED`/`DEAD` | TD-1，是 D-02/D-03 得以长期潜伏的根因 | 新增 `docs/legacy_gui_surface_inventory_zh.md` | 否 | 极低（纯文档） |
| **P1-2** | 把 `FEASIBLE_STARTING_OVERRIDES` 提升为 application default | U-01，首启三重不可行 | `input_ux/metadata.py` | 否（改默认输入不改公式） | 低（需更新依赖 default 的测试） |
| **P1-3** | 修正 `min: 0.0` 字段的 suggestion 文案，或放宽为真正的非负 | D-04 | `motor_core/validation.py` | 否 | 低 |
| **P1-4** | 更新 `AGENTS.md` 到 Phase 8I 实际状态 | D-08，context-recovery 文档失真 | `AGENTS.md` | 否 | 极低 |
| **P1-5** | 打 `v1.0.0-rc1` git tag；修正 `SHA256SUMS.txt`（LF + 只列随附文件）；把 legacy GUI 文件纳入 `protected_model_hashes` | D-06/D-07/R-08 | `release/`、`work/finalize_windows_release.py` | 否 | 低 |
| **P1-6** | 速度扫描"转矩-转速"子图加显式非包络标注（图内而非仅图注） | U-06 | `plots/performance.py` | 否 | 极低 |
| **P1-7** | 获取一台 AFPM 样机的 no-load back-EMF + LCR 实测 R/L | §5-Q5，解锁 #1/#2/#4 全部后续 | 无（数据采集） | 否 | 无 |
| **P1-8** | 补齐 T-1/T-2/T-3/T-5/T-6 五项测试 | 覆盖本次全部可测 confirmed defect | `tests/` | 否 | 低 |

### P2 — 有意义但不紧急

| ID | 项目 | 说明 |
|---|---|---|
| P2-1 | `required_voltage_v` 基准/相量修正（R-01/R-02）—— **走 Formula Change Approval Rule，采用 Phase 3B/3C 的 parallel-output 模式，legacy 保留为默认** | 需用户批准；物理**会**改变 |
| P2-2 | `is_coreless` ⇒ `core_loss = 0`（D-05）—— 同样需批准，同样建议 parallel output | 物理**会**改变 |
| P2-3 | 谐波频谱轴修正（D-01）—— protected file，需批准；display-only，物理不变 | 建议与 P2-1/P2-2 打包成一个 formula-change phase |
| P2-4 | 阈值单一真相源：把 `10/6/5`、`0.80/0.60/0.50`、`0/10/15` 集中到 `constants.py` 或 feasibility policy 模块 | TD-11 |
| P2-5 | 启动时间 profiling（7.3–18.5 s）+ matplotlib 惰性 import | §7，唯一真实体验瓶颈 |
| P2-6 | 速度扫描缓存/复用评估（先测量） | §7 |
| P2-7 | 畸形项目文件 fuzz 测试（T-8） | |
| P2-8 | PMSM 默认路径的独立数值参考用例（T-7） | 当前 3 个 baseline 全是 BLDC 路径 |

### P3 — 可选 / 未来

| ID | 项目 |
|---|---|
| P3-1 | 波形生成向量化（`_trapezoidal_back_emf` / `calculate_flux_distribution`）—— 仅在扫描点数上到 201 时才值得 |
| P3-2 | 测试按 capability 重组（TD-6） |
| P3-3 | 结果字典 key 收敛为单一命名体系（TD-3）—— 需先确认所有消费者 |
| P3-4 | 齿槽峰值语义澄清（R-04）与 `E_rms` 梯形波标注（R-06） |
| P3-5 | property-based testing 引入（Hypothesis），起点为 R-03 采样充分性 |

---

## 17. Recommended v1.0 Release Actions

**结论：不建议把当前构建原样宣布为 public v1.0.0。建议保留 `RC_ACCEPTED_LOCALLY`。**

理由排序（注意：**产品可信度问题排在代码签名之前**）：

1. **P0-1 / P0-2 未处理**。首启即出现恒真的"严重：无法制造！"，以及一条会破坏可行性的匝数建议。这两条不修，任何精度讨论都没有意义——用户根本不会信任这个工具。
2. **未签名 + SmartScreen 未知**。公开分发下会出现"未知发布者"提示。
3. **真干净 Windows 验收 `BLOCKED_BY_ENVIRONMENT`**。本地验收不能替代。

### 建议的 v1.0 行动清单

| 顺序 | 动作 | 是否需要用户批准 |
|---|---|---|
| 1 | 批准并实施 **P0-1**（停用 legacy 恒真/反向告警） | **是**（涉及 Hard-Rule 保护文件的 UI 文案） |
| 2 | 批准并实施 **P0-2**（优化器电压阈值同基化） | **是** |
| 3 | 实施 **P1-8**（补 5 项测试），确认 638 → 643+ 全绿 | 否 |
| 4 | 实施 **P1-2**（可行默认值）、**P1-3**（文案）、**P1-4**（AGENTS.md）、**P1-6**（图标注） | 否 |
| 5 | 实施 **P1-5**（tag / SHA256SUMS / legacy 文件纳入哈希保护） | 否 |
| 6 | 重新构建并重跑 Phase 8I 全部部署门禁 | 否 |
| 7 | 获取代码签名证书（OV/EV），重签 installer 与 EXE | 商务决策 |
| 8 | 在**真正一次性干净 Windows**（云上一台按小时计费的 Windows VM 即可，成本 < 数元）完成安装/启动/卸载验收 | 否 |
| 9 | 仅在 1–8 完成后，宣布 v1.0.0 | — |

**若无法完成 7–8**：建议以 `v1.0.0-rc2` 或明确的 **"工程预览版 / Engineering Preview"** 名义发布，并在 README 与 About 对话框中显式声明未签名与未做干净机器验收。**这个项目在诚实标注方面一贯做得很好，保持这个传统。**

---

## 18. Recommended v1.1 Scope

**主题：把"正确的口径"变成唯一的口径，并拿到第一份真实电磁数据。**

1. **P1-1 legacy surface freeze** —— 完成 legacy UI 行为清单，为后续逐项下线建立受控路径
2. **P1-7 样机实测**（no-load back-EMF vs 转速 + LCR 实测 R/L）—— v1.1 最重要的单项工作，且不需要写代码
3. **P2-1/P2-2/P2-3 打包成一个受控 formula-change phase**：
   - `required_voltage_v` 基准与相量修正
   - `is_coreless ⇒ core_loss = 0`
   - 谐波频谱轴修正
   - 严格遵循 Formula Change Approval Rule，全部采用 **parallel output**（legacy 保留为默认），与 Phase 3B/3C/3E 完全相同的模式
   - `legacy_baseline.json` 保持不变
4. **P2-4 阈值单一真相源**
5. **P2-5 启动时间优化**
6. **P2-8 PMSM 默认路径独立数值参考用例**
7. 若 P1-7 数据到位：把 `B_g,peak` / `Ke` 的外部证据等级从 `analytical_reference` 提升到 `bench_measurement`，这是**整个 validation framework 建立以来第一次真正的实验锚点**

**明确不做**：任何 surrogate / 残差修正 / 自动标定；任何架构重写；任何损耗或热模型升级（无数据）。

---

## 19. Recommended v2.0 / Research Scope

前提：v1.1 的样机数据已到位，且损耗分解实测可用。

1. **真实转矩-速度能力包络**（#2）—— 建立在修正后的电压约束 + 随速度变化的铁损之上。这是从"工作点计算器"跃迁到"驱动系统设计工具"的关键
2. **BLDC 开关侧电压/电流语义**（#3）—— 解除当前 `NOT_ENOUGH_SEMANTICS` 的限制
3. **损耗模型升级**（#4）—— 以实测效率分解为拟合锚点，Steinmetz 型铁损 + 修正后的导体涡流（R-07）
4. **多节点热网络**（#5）—— 绕组/定子/机壳/环境，以实测温升标定
5. **绕组与制造模型**（#9）—— 在 Phase 8G `_slot_fill` 上加入绝缘、线规、排布，直接服务用户实际决策
6. **谐波反电动势**（#7）—— 基于 Phase 7E 径向切片
7. **自动化设计空间探索**（#13）—— 建立在修正后的可行性判据上
8. **推迟**：饱和模型（#6，coreless 拓扑收益低）、PINN/surrogate（#11）、残差修正（#12，且与"禁止自动标定"政策冲突，需先做政策决策)

---

## 20. Final Assessment

这是一个**工程纪律优秀但存在明确遗留边界问题**的项目。

我要明确肯定几件事，因为它们在同类项目中很罕见：

- 把"不许过度声明"写成自动化测试（`test_creator_pmsm_no_overclaim.py`）
- 对说不清的东西明确输出 `NOT_ENOUGH_SEMANTICS` / `NOT_ENOUGH_GEOMETRY` 而不是给个数字糊弄过去
- 修正值与 legacy 值长期并行、不切默认路径
- protected hash + legacy baseline + 逐 Phase 证据文档
- 在验收文档里主动写 `TRUE_CLEAN_MACHINE_TEST = BLOCKED_BY_ENVIRONMENT` 而不是含糊过关

这些说明项目主导者**理解工程可信度的本质**。

本次评审发现的问题，**没有一个是 core physics kernel 的计算错误**。8 项 confirmed defect 中，5 项在 legacy GUI / validation / release 层，3 项在 protected kernel 内且其中 2 项是 display-only。核心计算链的内部一致性经我独立数值复核（磁密三口径、Ke 峰/RMS 比、电流密度双实现）**全部通过**。

真正的问题是一句话：

> **Phase 8G/8H 建立了正确的工程口径，但没有让旧口径退场。** 结果是一个高质量的新层，正在为一个恒定误报、方向相反的旧层背书。

好消息是：**修复成本很低。** 两项 P0 都不触碰 protected 文件、不改任何 equation、不动 `legacy_baseline.json`，本质上是"删掉/改写两段已被取代的告警文案 + 一个阈值"。

最后，关于优先级的一个直率判断：

> 这个项目已经在软件工程上投入了 8 个 Phase，软件层面的边际收益正在快速递减。而 `B_g,peak`——整条模型链的最上游——至今没有一个外部锚点。**下一个数量级的价值提升不在代码里，在一台样机和一台示波器上。**

---

## 附录 A · 本次评审的可复现命令

```bash
# 仓库状态
git -C D:/Codex/Projects/MotorCalculator status --porcelain
git -C D:/Codex/Projects/MotorCalculator log -1 --format='%H %s'

# 受保护哈希
sha256sum motor_calculator/motor_core/calculations.py \
          motor_calculator/tests/fixtures/legacy_baseline.json

# 完整回归
.venv/Scripts/python.exe -m pytest -q          # → 638 passed

# 发布产物核验
sha256sum release/MotorCalculator-1.0.0-rc1-win64-portable.zip \
          release/MotorCalculator-1.0.0-rc1-win64-setup.exe \
          dist/MotorCalculator/MotorCalculator.exe

# 导入健康（0 failures）
python -c "import pkgutil,importlib,motor_calculator; [importlib.import_module(m.name) for m in pkgutil.walk_packages(motor_calculator.__path__,'motor_calculator.') if '.tests' not in m.name]"
```

## 附录 B · 关键实测数值速查

```
application default (V_dc=48, P=800W, n=2500rpm, p=8, coreless=True, slot_type=无槽)
  required_voltage_v      = 51.518 V
  legacy voltage margin   = -7.329 %      ← 结果文本区
  same-basis margin       = -51.786 %     ← Phase 8H 仪表板 (available 33.941 V)
  legacy fill_factor      = 2.456         ← 恒定触发 "无法制造!"
  current density         = 8.880 A/mm²   ← CURRENT_DENSITY_HIGH
  core_loss               = 8.000 W       ← coreless 却计入铁损
  copper/eddy/mech        = 39.536 / 18.940 / 3.512 W
  efficiency              = 91.955 %
  cogging peak            = 0.000 N·m     (coreless 分支)

FEASIBLE_STARTING_OVERRIDES (V_dc=72, P=600W, n=2200rpm, d_wire=1.2, 半闭口槽, coreless=False)
  legacy voltage margin   = +40.338 %     ← 触发 "考虑增加匝数"（有害建议）
  same-basis margin       = +15.625 %     ← 真实裕量
  current density         = 4.340 A/mm²   ✅
  slot fill (Phase 8G)    = 0.318         ✅
  legacy fill_factor      = 3.274         ← 仍恒定触发 "无法制造!"

required_voltage 相量对比
  E_line_rms = 40.885 V, I·R_line = 2.333 V, I·X = 27.025 V
  code RSS-of-3            = 51.518 V
  sqrt((E+IR)²+IX²)        = 53.520 V     (+3.89 %, 代码非保守)
  line_inductance_h / phase_inductance_h = 1.15  (= L_ph − M，每相同步电感)

磁密谐波轴 (p=8)
  最大幅值 FFT bin k = 8 → 真实电气次数 = 1
  代码标注 harmonics[8] = 64
  下游 valid_idx = harmonics ≤ 25 → 仅保留 bin k = 0,1,2,3，基波被过滤出图

齿槽采样
  default: LCM(16,24)=48, 3·LCM=144 < 179.5 → 安全
  密采样峰值因子 1.1283821 vs 360 点 1.1283816 → 一致
  风险边界: 3·LCM > 179.5 (例如 p=10, slots=30 → LCM=60) → 混叠

零值输入
  k_cogging / k_ripple_6 / k_ripple_12 / h_yoke / h_slot = 0 → 全部 REJECTED
  错误消息同时写 "合法范围为 > 0.0" 与 "建议：请输入非负…"
```

---

*本报告为 first-pass independent review。评审过程中未修改任何 product code，未创建任何 commit，未触碰 `tmp/`，未访问 C 盘旧仓库。唯一写入仓库的文件为本报告本身。所有 protected hash 在评审前后均经核验，保持不变。*
