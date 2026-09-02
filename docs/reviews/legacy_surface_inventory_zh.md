# Legacy GUI Surface Inventory（`PMDC_Calculator_claude204.py`）

**建立于**：v1.0.0-rc2 工程修正阶段
**目的**：登记 legacy GUI 文件中**仍在生产路径上**的行为，为后续逐项退役提供受控清单。
**本阶段不重写该文件。**

---

## 1. 运行时事实（实测，非推断）

```
MRO: _RealMotorCalculatorApp -> MotorCalculatorAppMixin -> MotorCalculatorApp(legacy) -> object
```

`gui/main_window.py:_load_legacy_module()` 通过 `spec_from_file_location` + `exec_module()`
动态加载 legacy 文件，注入 `module.PMDCMotorModel = LegacyGuiMotorModelBridge`，
再以 Mixin 多继承方式构造运行时类。

**因此：legacy 文件不是历史归档，它是运行时 GUI 基类。**

实测方法解析结果：

| 类别 | 数量 |
|---|---:|
| 已被 modern mixin 覆盖（legacy 实现不可达） | **4** |
| legacy 实现仍然直接生效 | **29** |

### 已被覆盖（`WRAPPED_BY_MODERN_LAYER`）

| 方法 | 覆盖者 | 说明 |
|---|---|---|
| `_check_design_validity` | `MotorCalculatorAppMixin` | **关键**。legacy 的 `K_fill > 0.8 → "无法制造!"` 与 `V_margin > 40 → "考虑增加匝数"` 在运行时**不可达**，已由 `validation.design_feasibility` 接管 |
| `_get_params` | `MotorCalculatorAppMixin` | 严格解析 + RC2 绕组系数 AUTO/MANUAL 解析 |
| `run_analysis` | `MotorCalculatorAppMixin` | 现代错误处理、仪表板、快照、RC2 摘要注入 |
| `reset_defaults` | `MotorCalculatorAppMixin` | Phase 8D 引导式重置 |

> **RC1 评审更正**：RC1 报告将 `_check_design_validity` 中的恒真"无法制造"告警列为
> confirmed defect D-02，并将"增加匝数"提示列为 D-03 的一部分。本阶段通过 MRO 实测确认，
> 这两段 legacy 文案**在实际应用中不可达**。RC1 定位了代码但未验证 MRO，属于**高估**。
> 真正在线的是 `run_optimization` 中的电压基准缺陷（见下）。RC2 已为该覆盖关系增加
> 回归锁定测试，防止未来退化。

---

## 2. 仍然生效的 legacy 行为清单

分类口径：

- `KEEP` — 行为正确或无工程结论含义，保留
- `WRAPPED_BY_MODERN_LAYER` — legacy 实现被 modern 层覆盖
- `DEPRECATED` — 仍在线但已被 modern 语义取代，应逐步退役
- `REPLACE_LATER` — 需要替换，但需独立阶段
- `UNUSED` — 已无调用方

### 2.1 告警与工程结论

| 行为 | 位置 | 分类 | 备注 |
|---|---|---|---|
| `_check_design_validity` 阈值与文案 | `:1467-1490` | `WRAPPED_BY_MODERN_LAYER` | 不可达；建议 v1.1 物理删除，需先确认无第三方调用 |
| 报告正文 `Legacy 直流母线差额` | `:1430` | `KEEP` | 已显式标注为 legacy 兼容值，不作工程结论 |
| 报告正文 `Legacy 线性绕组占比` | `:1431` | `KEEP` | 同上；RC2 已在其上方插入同基摘要 |

### 2.2 自动优化器

| 行为 | 位置 | 分类 | 备注 |
|---|---|---|---|
| `run_optimization` 整体 | `:2003+` | `REPLACE_LATER` | **legacy 实现直接生效**，未被覆盖 |
| 硬约束 `V_required > V_dc` | 原 `:2051` | **RC2 已修正** | 改为同基包络 `V_dc/√2`。修正前接受 `N=15..81`，修正后 `15..57`，误接受 8 个候选 |
| 电压利用率目标 `0.85·V_dc` | 原 `:2020` | **RC2 已修正** | 改为 `0.85 ×` 同基可用线电压 RMS。旧目标本身超出包络约 20% |
| 槽面积惩罚 `K_fill > fill_limit` | 原 `:2063` | **RC2 已修正** | 改用 Phase 8G 近似裸铜槽占比；槽几何不足时不施加惩罚 |
| 优化结果摘要标签 | `:2112+` | **RC2 已修正** | 改为 `同基电压裕量` / `近似裸铜槽占比`；legacy 值保留但标注为兼容值 |
| `optimization_log` 键名 | `:2085+` | **RC2 已修正** | `K_fill` → `legacy_K_fill`，新增 `slot_occupancy` |
| 裸 `except:` | `:2043` | `REPLACE_LATER` | 吞掉 `KeyboardInterrupt`/`SystemExit`；低风险但应收窄 |
| 评分权重（效率 ×10、脉动 ×10、电压 ×2） | `:2078-2080` | `KEEP` | 经验权重，非物理结论；如需改动应单独立项 |

### 2.3 计算显示与报告

| 行为 | 位置 | 分类 | 备注 |
|---|---|---|---|
| `_display_report` 报告主体 | `:1309+` | `KEEP` | RC2 在其顶部注入同基工程摘要 |
| `_copy_report` / `_save_report` / `_print_report` | — | `KEEP` | 纯文本操作 |
| `_export_full_txt` 电压/槽占比行 | `:2391` | **RC2 已修正** | 改为同基口径 + 显式标注的 legacy 兼容值 |
| `export_json` / `export_csv` | — | `REPLACE_LATER` | 需审计是否以 `slot_fill_factor` 之名导出 legacy K_fill（见 §4 未决项） |

### 2.4 绘图

| 行为 | 位置 | 分类 | 备注 |
|---|---|---|---|
| `_plot_flux_distribution` 谐波频谱 | `:1854-1858` | `REPLACE_LATER` | RC1 defect D-01：`harmonics = k × pole_pairs` 方向反了，`harmonics ≤ 25` 把基波过滤出图。**数据源在受保护的 `calculations.py:490`，需批准后修** |
| `_plot_performance_curves` / `_plot_back_emf` / `_plot_torque` | — | `KEEP` | 显示用 |
| `_draw_geometry` | `:1927+` | `KEEP` | 有 matplotlib `color` 覆盖 `edgecolor` 的 UserWarning，纯样式问题 |
| `_register_figure` / `_clear_figure` / `_set_chart_placeholder` | — | `KEEP` | matplotlib 缺失时的降级路径 |

### 2.5 输入面板

| 行为 | 位置 | 分类 | 备注 |
|---|---|---|---|
| `_create_inputs` 字段构建 | `:1100+` | `KEEP` | Phase 8D 在其上叠加引导面板；RC2 在其下追加绕组系数面板 |
| `add_field("fill_limit", "填充系数限制", ...)` | `:1199` | `DEPRECATED` | 标签沿用"填充系数"旧词。RC2 已让优化器改用同基占比判据，但**输入标签本身未改**（见 §4） |
| `_on_magnet_select` | — | `WRAPPED_BY_MODERN_LAYER` | Phase 8D 已 `unbind` 并 `disable` 该 combobox |
| `_setup_styles` / `_create_buttons` / `_create_*_tab` | — | `KEEP` | 纯布局 |

---

## 3. 结构性风险

| 风险 | 说明 | 建议 |
|---|---|---|
| 动态 `exec_module` + monkeypatch + Mixin | 没有显式接口契约；legacy 方法改名会静默失效 | v1.1：为 4 个被覆盖方法增加断言测试（RC2 已覆盖 `_check_design_validity`） |
| legacy 文件未纳入 `protected_model_hashes` | 它在生产路径上且体量最大（2556 行），却不受哈希保护 | v1.1：加入 release manifest 哈希集合 |
| 2556 行单文件 | 29 个方法仍在线 | 不重写；按本清单逐项退役 |

---

## 4. 本阶段未处理的已知项（明确记录，不隐藏）

1. **`fill_limit` 输入标签仍为"填充系数限制"**。RC2 已把优化器判据改为同基占比，
   但输入项标签与 Phase 8G 术语尚未统一。改动涉及 i18n 字符串与 `NUMERIC_FIELD_SPECS`，
   留待 v1.1 一次性统一。
2. **`export_json` / `export_csv` 未审计**。RC2 只修正了 `_export_full_txt`。
   需确认这两个导出是否以现代名称导出 legacy 指标。
3. **气隙磁密谐波频谱轴（D-01）**。数据源在受保护的 `calculations.py:490`，
   按安全规则**未修改**，等待显式批准。
4. **`required_voltage_v` 相量与基准问题（RC1 R-01/R-02）**。同样在受保护文件内，未修改。
5. **`_check_design_validity` legacy 实现物理删除**。当前保留为死代码以最小化本阶段风险。
