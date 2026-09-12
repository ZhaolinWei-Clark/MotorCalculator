# Phase 10H.1 — 启动预设权威与打包产品门

**状态**：`STARTUP_AUTHORITY_ALIGNED` / `PACKAGED_GATE_PASSED`
**分支**：`validation/phase10h1-startup-preset-product-gate`（**堆叠**在 Phase 10H 之上）
**父提交**：`766c803`（Phase 10H）
**应用版本**：`1.0.0-rc4`（本阶段不提升版本号）
**FEMM 求解**：0 次

> **一句话结论**：新增 `design.manufacturability_start.v3` —— 与 v2 **完全同一台机器**，
> 仅声明 `AUTO_FROM_GEOMETRY`。启动首屏的绕组系数因此变为 **0.8660254**，
> 与新项目权威默认一致。**v1 与 v2 的输入值一个都没改**，
> 应用 v2 仍然精确复现其公开发表的 19.2815 % 裕度。
> **实际打包产物冒烟 PASS。**

---

## 1. 审计结论（Step 1）

启动示例由 `_apply_startup_example()` 在首次启动时写入 GUI 字段，
它是**示例设计**，不是"新建项目"。

**关键发现：0.93 根本不来自启动预设。**

```
v2.values = {V_dc, P_rated, n_rated, N_ph_turns, d_wire, n_parallel, slot_type, coreless}
```

**其中没有 `k_w`。** 0.93 来自被冻结的 `APPLICATION_DEFAULTS`，
而真正的开关是**绕组权威模式**，其默认值是 `MANUAL`。

### 1.1 需要更正的 Phase 10H 陈述

Phase 10H 报告里我把「新项目默认 AUTO」说成已生效行为。
**实际上 `new_project_state()` 从未接入 GUI**——它是有测试覆盖的库函数，
但没有生产消费者。真实的 GUI 新建路径仍然走 `MANUAL`。
本阶段把这一点写清楚，并从启动预设这一侧关闭不一致。

---

## 2. 产品决策（Step 2）

| 选项 | 评估 |
|---|---|
| A. 直接把启动预设改成 AUTO | 需要修改已发布的 v2 记录，等于覆盖历史参考证据 |
| B. 保持 LEGACY_MANUAL | 不一致继续存在，本阶段没有意义 |
| **C. 两个显式命名的预设** | **采用** |

### 选择 C 的理由

1. **仓库已有此先例**：Phase 9C 在电压语义变化时新增 v2 而非改写 v1
2. **历史可复现性完整保留**：v1、v2 的 `values` **逐字节未变**
3. **新用户获得语义一致**：首屏权威与新项目默认一致
4. **公开发表的观测仍然成立**：v2 的 41.0951 V / 19.2815 % 仍可复现

**未静默覆盖任何历史参考证据。**

---

## 3. v3 的构造（Step 3）

```
v3.values  ==  v2.values      （测试断言相等）
v3.winding_authority = "AUTO_FROM_GEOMETRY"
v3.coil_span_slots   = 1
```

**同一台机器**：槽数、极数、匝数、线径、几何全部相同。
**唯一差别是绕组系数的来源。**

`coil_span_slots` 必须由预设提供，因为旧参数 schema 里没有线圈节距字段，
而 `AUTO` **绝不允许猜测**节距。声明 `AUTO` 但不提供节距的预设**在载入时被拒绝**。

生产绕组系数取 **槽电势星形图 `kd·kp·ks` = 0.8660254**。
**不是**剖分 FEA 值 0.9557520 —— 后者在结构上不可能进入生产（Phase 10H 防火墙），
本阶段另有测试对启动预设单独断言这一点。

### 3.1 量化影响（首屏）

| 量 | v2（手动 0.93） | v3（几何 0.8660254） | 变化 |
|---|---:|---:|---:|
| 绕组系数 | 0.9300000 | 0.8660254 | **−6.879 %** |
| **Ke** | 0.074289 | 0.069179 | **−6.879 %** |
| **Kt** | 0.222867 | 0.207536 | **−6.879 %** |
| **需求电压**（线 RMS） | 41.095139 V | 41.897794 V | **+1.953 %** |
| **修正电压裕度** | 19.281524 % | 17.704960 % | **−8.177 %（相对）** |
| 电流密度 | 4.209820 | 4.520806 A/mm² | +7.387 % |
| 槽占比 | 0.400288 | 0.400288 | 不变 |
| ERROR | 无 | 无 | 不变 |
| SEVERE_DESIGN_RISK | 无 | 无 | 不变 |

**新首屏设计仍然可行**，且问题条数未增加。

---

## 4. 历史可复现性（Step 4）

v1 与 v2 **新增一条显式声明**：

```
winding_authority = "LEGACY_MANUAL"
```

**没有改动任何输入数值**（测试逐字段断言 v2 的 8 个值）。

为什么需要这条声明：若用户当前处于 AUTO 会话再应用 v2，
没有声明的预设会**保持** AUTO，v2 就不再复现其历史数字。
声明让预设**自描述**，从而在任何会话状态下都恢复 LEGACY_MANUAL。

**打包产物中验证通过**：应用 v2 后裕度回到
`19.281523849990723 %`，与 RC3/RC4 公开记录**逐位相同**。

---

## 5. 变更暴露的两个既有缺陷

### 5.1 「全部重置」不重置绕组权威

`reset_defaults()` 把所有输入字段恢复到 `APPLICATION_DEFAULTS`，
但**不重置绕组权威**。AUTO 会话下重置后，其他字段回到冻结默认值，
`k_w` 却仍由几何推导——**"恢复默认值"没有给出默认值**。

冻结默认值携带手动 `k_w`，因此重置态应为 `MANUAL`。已修复。

### 5.2 RC3 冒烟硬断言 v2 为启动预设

原断言 `raise RuntimeError("RC3 startup must use ...v2")`。
现改为守护**当前**启动预设，并**额外要求**其绕组系数来自几何。
v2 没有被抛弃：其可复现性在测试中以**无 GUI 状态**的方式断言，
包括电压、裕度与电流密度三项公开数字。

（我最初把 v2 复现检查插在冒烟中段，直接操作 GUI 状态，
导致后续 Phase 8D 门失败。改为无头断言是更干净的做法。）

---

## 6. 打包产物冒烟（Step 5）

从 10H.1 最终提交**本地构建**（未发布任何版本）：

```
status  = PASS
mode    = packaged
version = 1.0.0-rc4

phase10h1_startup_preset_id            design.manufacturability_start.v3
phase10h1_startup_authority            auto
phase10h1_startup_kw                   0.8660254037844386
phase10h1_startup_kw_is_geometry       True
phase10h_authority_control_present     True
phase10h_auto_disables_manual_entry    True
phase10h_manual_enables_entry          True
phase10h_switch_warns                  True
phase10h_production_never_meshed       True
phase10g_winding_dialog_opened         True
phase10g_slot_fill_computed            True
project_exact_inputs_restored          True
project_calculation_reproduced         True
phase8h_csv_exported / figure_exported True
confidence_export_exists               True
diagnostic_export_exists               True
phase8d_reset_all_confirmed            True
```

**无缺失的惰性导入，无缺失资源。**

---

## 7. 产品一致性（Step 6）

| 消费者 | 首屏（v3 / AUTO） |
|---|---|
| 启动预设 | k_w = 0.8660254 |
| 仪表板 | 裕度 17.704960 % |
| 可行性 | 需求电压 41.897794 V |
| 电流密度 | 4.520806 A/mm² |
| 扫掠 | 使用修正电压 ✓ |
| 导出 | 使用权威命名 ✓ |
| 保存/载入 | 输入精确还原、计算可复现 ✓ |
| 生产是否用剖分值 | **否** ✓ |

**所有消费者共用 `_get_params()` 这一个解析点，因此一致性是结构性的。**

一处需要说明：`rc3_startup_corrected_margin` 在冒烟中报 19.2815 %。
这**不是**不一致——该指标在冒烟序列中位于「应用 v2」之后，
报的是 v2 语境下的值，恰好证明 §4 的历史可复现性在打包产物中成立。
两个数值（v3 的 17.7050 %、v2 的 19.2815 %）正确共存。

---

## 8. 回归（Step 7）

**1240 → 1259 passed, 3 skipped**（+19）。

两处因本变更而需要更新，均为**语义更新而非放宽**：

- `test_every_preset_has_a_localized_display_name`：为 v3 补中英显示名
- `test_v2_is_the_startup_default_after_phase9c_promotion`：
  改名为 `test_v2_remains_available_after_the_phase10h1_authority_move`，
  **保留其原有意图**——v1、v2 必须仍然可用——并断言新的启动默认

受保护哈希两项均未变：

```
calculations.py        aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942
legacy_baseline.json   15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9
```

`APPLICATION_DEFAULTS["k_w"]` 仍为 **0.93**（冻结未动）。

---

## 9. 已知局限

- `new_project_state()` 仍未接入 GUI 的「新建项目」路径；
  本阶段从启动预设一侧对齐，**File→New 的权威默认仍是 MANUAL**
- 权威切换仍只有文字警告，没有逐值 before/after 预览
- v3 与 v2 的 `values` 完全相同，因此在已应用 v2 的会话中切到 v3
  会被 `_apply_preset_by_id` 判为无变更（既有行为，未修改）
- 未构建或发布任何正式发行版
- 可制造性问题仍未并入主仪表板可行性摘要
- **仍然没有任何物理台架数据**

---

## 10. 决定

**启动预设策略：选项 C —— 两个显式命名的预设。**

- 出厂启动：`design.manufacturability_start.v3`，`AUTO_FROM_GEOMETRY`，k_w = 0.8660254
- 历史参考：`v2`（RC3/RC4 首屏）与 `v1`，均声明 `LEGACY_MANUAL`，输入值未动
- 剖分 FEA 绕组系数永不进入生产

---

## 11. Phase 11 是否可以开始

**可以。** 本阶段关闭了 10H 遗留的产品不一致，并首次在**实际打包产物**上
完成了完整产品门。

建议 Phase 11 首先补上两件小事，再进入实验/公开参考数据框架：

1. 把 `new_project_state()` 接入 GUI 的「新建项目」路径
2. 把可制造性问题并入主仪表板可行性摘要

**然后进入 Phase 11：实验/公开参考数据框架**——
这是把任何 `NUMERICAL_FEA` 升级为 `VALIDATED` 的唯一途径。
