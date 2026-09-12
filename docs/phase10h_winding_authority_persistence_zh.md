# Phase 10H — 绕组权威、历史兼容、项目持久化与导出

**状态**：`NEW_PROJECTS_AUTO_LEGACY_PRESERVED`
**分支**：`validation/phase10h-winding-production-integration`（**堆叠**在 Phase 10G 之上）
**父提交**：`5105713`（Phase 10G）
**应用版本**：`1.0.0-rc4`（Phase 10H 不提升版本号）
**FEMM 求解**：**0 次**（本阶段为集成与治理，不需要求解）

> **一句话结论**：新项目默认 `AUTO_FROM_GEOMETRY`，
> 历史项目载入为 `LEGACY_MANUAL` 并**逐位保留原值**，
> 用户可显式迁移，手动覆盖始终可用，
> **剖分 FEA 绕组系数在结构上不可能成为生产权威**。
> 项目 schema **未升版**：绕组状态写入既有的 `ui_preferences`，
> 因此**每一个现存 .motorproj 的载入行为完全不变**，没有迁移可以出错。

---

## 1. 动机

项目中有三个数都叫 `k_w`，过去四个阶段大量精力花在厘清它们：

| 量 | 基线值 | 归属 |
|---|---|---|
| 用户输入 / 出厂预设 | **0.93** | 生产（当前） |
| 理想槽电势星形图 | **0.8660254** | 生产（可选） |
| 剖分几何（Phase 10E） | **0.9557520** | **仅 FEA 解释，永不进入生产** |

Phase 10G 给了它们名字。Phase 10H 决定**生产被允许使用哪一个**，并记录原因。

---

## 2. 权威状态（Step 2）

| 状态 | 语义 |
|---|---|
| `AUTO_FROM_GEOMETRY` | 生产绕组系数取自生产绕组模型的 `kd·kp·ks`（槽电势星形图），可由存储输入完整复现 |
| `MANUAL_OVERRIDE` | 用户显式选择手动值；软件同时显示几何推导值与二者之差，使覆盖可见 |
| `LEGACY_MANUAL` | 项目创建于本语义之前；**逐位保留**其存储值，**永不**重新推导 |
| `UNRESOLVED` | 选择了自动但几何不足，且无可用手动值；**不凭空生成数字** |

关键约束：`AUTO` 在几何不足时**不会**静默回退到手动值——它返回 `UNRESOLVED`
并告知调用方。静默回退正是本阶段要消除的行为。

---

## 3. 生产 kw 与剖分 kw 的防火墙（Step 3、23）

**结构性隔离，不是文档约定**：

1. `resolve_production_winding_factor()` **没有任何参数**可以传入剖分值
   （测试断言签名中不含 `mesh`/`fea`）
2. `ProductionWindingFactor.__post_init__` 对
   `MESHED_GEOMETRY_FEA_DIAGNOSTIC_ONLY` **直接抛异常**
3. `PRODUCTION_ADMISSIBLE_PROVENANCE` 白名单不含剖分来源
4. `authority.py` **不导入** `meshed_winding`（测试断言源码中无该名称）
5. 对基线案例，`AUTO` 返回 0.8660254 而剖分值为 0.9557520，测试断言二者不同

---

## 4. Proposal C 形式化评估（Step 4）

对出厂启动预设，把权威从手动 0.93 切到几何 0.8660254：

| 量 | 手动 0.93 | 几何 0.8660254 | 变化 |
|---|---:|---:|---:|
| 绕组系数 | 0.9300000 | 0.8660254 | **−6.879 %** |
| **Ke** [V·s/rad] | 0.074289 | 0.069179 | **−6.879 %** |
| **Kt** [N·m/A rms] | 0.222867 | 0.207536 | **−6.879 %** |
| **需求电压**（线电压有效值） | 41.095139 | 41.897794 | **+1.953 %** |
| **电压裕度** | 19.281524 % | 17.704960 % | **−8.177 %（相对）** |
| 相电流 | 14.283584 A | 15.338733 A | +7.387 % |
| 电流密度 | 4.209820 A/mm² | 4.520806 A/mm² | +7.387 % |
| 电压状态 | APPROXIMATE | APPROXIMATE | 不变 |
| 电流密度状态 | CALCULABLE | CALCULABLE | 不变 |
| 可行性问题数 | 1 | 1 | 不变 |

**结论**：该预设切换后仍然可行，但**每一个头条数字都会变**。
这不是一次 UI 默认值调整，因此历史项目必须被保护。

**决定：`NEW_PROJECTS_AUTO_LEGACY_PRESERVED`。**

---

## 5. 历史兼容与迁移规则（Step 5–8）

### 5.1 检测

载入项目时：

```
若 ui_preferences 中不存在 winding.authority：
    若存储了绕组系数  -> LEGACY_MANUAL（保留原值）
    否则              -> UNRESOLVED
若存在但值非法        -> LEGACY_MANUAL（降级方向是保守的，绝不升到 AUTO）
```

**永远不会在载入时把历史项目提升为 AUTO。**

### 5.2 新项目

几何充分 → `AUTO_FROM_GEOMETRY`；
几何不足但有手动值 → `MANUAL_OVERRIDE`；
两者皆无 → `UNRESOLVED`（**不编造**）。

### 5.3 显式迁移

四种转换全部支持且**必须显式**：
`LEGACY_MANUAL → AUTO`、`LEGACY_MANUAL → MANUAL`、
`AUTO → MANUAL`、`MANUAL → AUTO`。

切换时状态栏明确提示：
「Ke、Kt、电压需求、电压裕度与可行性判定都会随之重新计算。」
**不自动切换，不重复弹窗。**

---

## 6. 项目持久化（Step 9–11）

### 6.1 为什么**不**升 schema 版本

`ui_preferences` 本来就被持久化、本来就能往返，且已经承载 RC2 的
`winding_factor_mode`。把绕组状态以扁平命名空间标量写在那里：

- `PROJECT_SCHEMA_VERSION` **不动** → **每个现存 .motorproj 载入行为完全不变**
- **没有迁移路径可以写错**，也不会让任何历史文件失效
- `winding.authority` 的**缺失本身**就是「该项目早于本语义」的信号

升版本能买到的是一个嵌套块，代价是为所有既有文件写一条迁移路径。
**这笔交易不划算**，决定记录在 `persistence.py` 的模块文档里。

### 6.2 持久化内容

`winding.` 前缀下：`authority`、`manual_winding_factor`、`coil_span_slots`、
`layers`、`parallel_strands`、`skew_slots`、`turns_per_coil`、
`insulated_diameter_mm`、`insulation_ratio`、`liner_thickness_mm`、
`clearance_mm`、`packing_factor`。

**不持久化派生量**：`kd`、`kp`、`ks`、生产 kw、各满率。
它们是存储输入的确定性函数；存副本会制造第二个可能漂移的真值来源。
测试对此固化。

### 6.3 往返

- AUTO 项目：保存→载入→权威、节距、层数、装填系数全部一致
- MANUAL 项目：手动值**逐位保留**，所有允许量一致
- 历史项目（仅有 RC2 的 `winding_factor_mode`）：
  → `LEGACY_MANUAL`，`k_w = 0.93` 原样保留

---

## 7. 导出（Step 12–13）

**不存在裸 `kw` 字段**，`assert_no_ambiguous_winding_factor()` 会对
`kw` / `k_w` / `winding_factor` 直接抛异常。

导出块：

```
authority.production_winding_factor            0.93
authority.production_winding_factor_source     LEGACY_MANUAL
authority.production_winding_factor_provenance LEGACY_PROJECT
authority.ideal_geometry_winding_factor        0.8660254
authority.manual_winding_factor                0.93
authority.overrides_geometry                   true
authority.geometry_delta_percent               +7.387
fea_diagnostic.meshed_fea_winding_factor       0.9557520
fea_diagnostic.status                          NOT_PRODUCTION_AUTHORITATIVE
calibration_status                             NONE
```

另含 `geometry`（Q、2p、m、q、节距、层数、并联支路）、
`factors`（kd、kp、ks、理想 kw、生产权威 kw）、
`slot_fill`（毛/可用面积、裸铜/包络面积、四个满率、装填系数、可制造性状态）。

---

## 8. 生产消费者一致性（Step 14–15）

**审计结论：架构已经是单点。** `main_window._get_params()` 是唯一的生产入口，
它在返回参数前应用绕组系数解析；**11 个调用点**（仪表板、可行性、优化器、
扫掠、导出、FEA、启动、项目保存等）全部经由它取参数，因此天然一致。

本阶段**没有**新增第二条解析路径，而是把权威语义补齐在既有单点之上。

---

## 9. 优化器语义（Step 16）

- `AUTO_FROM_GEOMETRY`：候选设计改变槽/极/节距时，kw 随候选几何重新推导
- `MANUAL_OVERRIDE` / `LEGACY_MANUAL`：手动 kw 在优化过程中**保持固定**

后者是刻意的：手动值代表用户对某个具体绕组的判断，
把它跨几何不兼容的候选设计套用是错误的，但**这是已声明的模式**，
而不是静默行为——面板与导出都会写明当前权威。

---

## 10. 可行性语义（Step 17）

绕组可制造性成为一等可行性理由，且**严格附加**：

| 代码 | 严重度 | 触发条件 |
|---|---|---|
| `WINDING_FACTOR_UNRESOLVED` | ERROR | 自动模式但几何不足且无手动值 |
| `SLOT_OVERFILLED` | SEVERE_DESIGN_RISK | 包络面积超过装填系数下的可达面积 |
| `SLOT_GEOMETRICALLY_IMPOSSIBLE` | ERROR | 包络占比 > 100 %，与装填无关 |
| `SLOT_FILL_TIGHT` | WARNING | 落在偏紧带 |
| `SLOT_FILL_NOT_CALCULABLE` | WARNING | 扣除允许量后无可用面积 |

每一条都**只在真的有问题时触发**，因此此前可行的设计仍然可行、
问题列表逐条一致。**任何情况下都不会为了让设计通过而减匝数、改线径或放宽装填系数。**

---

## 11. GUI（Step 18–20）

「绕组工程」对话框新增**生产绕组系数权威**分区：

- 模式下拉（自动 / 手动覆盖 / 历史项目手动值）
- 手动 kw 输入框：**自动模式下禁用**，手动模式下启用
- 状态行：切换时明确提示会重新计算 Ke、Kt、电压、裕度与可行性
- 面板分区显示：权威模式、生产 kw（含原因）、几何推导值、手动值、
  手动相对几何的百分比

打开时默认 `LEGACY_MANUAL`——对未声明的项目，这是保守读法。

---

## 12. 打包验证（Step 24）

Phase 10H 的四个模块加入 PyInstaller 隐藏导入
（`authority`、`persistence`、`export`、`feasibility`）。

**源码 GUI 冒烟 PASS**，覆盖：

```
phase10h_authority_control_present     True
phase10h_default_authority             LEGACY_MANUAL
phase10h_auto_authority                AUTO_FROM_GEOMETRY
phase10h_auto_uses_geometry            True
phase10h_auto_disables_manual_entry    True
phase10h_manual_enables_entry          True
phase10h_manual_authority              MANUAL_OVERRIDE
phase10h_switch_warns                  True
phase10h_production_never_meshed       True
```

**未构建公开发行版**（按要求）。

---

## 13. 向后兼容结果（Step 21–22）

| 检查 | 结果 |
|---|---|
| 历史项目载入分类 | `LEGACY_MANUAL` ✓ |
| 历史 kw 是否原样保留 | `0.93` 逐位相等 ✓ |
| 历史项目是否被静默改为几何值 | **否** ✓ |
| 现有 .motorproj 是否需要迁移 | **否**（schema 未升版）✓ |
| 新 AUTO 项目是否会回落到 0.93 | **否**（无权威则 `UNRESOLVED`）✓ |
| 剖分 kw 能否成为生产权威 | **结构上不可能** ✓ |
| 受保护物理哈希 | 两个均未变 ✓ |

回归：**1204 → 1240 passed, 3 skipped**（+36）。

---

## 14. 已知局限

- 权威状态存于 `ui_preferences`，是扁平标量而非一等嵌套块
- 优化器在手动模式下固定 kw 的行为已声明但未提供逐候选覆盖机制
- 可制造性问题目前由绕组面板呈现；尚未合并进主仪表板的可行性摘要列表
- 切换权威时给出的是文字警告，**没有**逐值 before/after 预览
- 打包冒烟未在实际打包产物上运行（本阶段不构建发行版）
- 槽满率仍按梯形槽解析计算，无真实排线校核
- **仍然没有任何物理台架数据**

---

## 15. 决定

### **`NEW_PROJECTS_AUTO_LEGACY_PRESERVED`**

- 新项目默认 `AUTO_FROM_GEOMETRY`（几何充分时）
- 历史项目载入为 `LEGACY_MANUAL`，原值逐位保留
- 用户可显式迁移，四种转换全部支持
- 手动覆盖始终可用且可见
- 剖分 FEA 绕组系数**在结构上不可能**成为生产权威

**注意**：本阶段实现了权威模型、持久化、导出与 GUI，
但**没有把出厂预设 `k_w = 0.93` 改成几何值**——
预设属于产品内容而非权威机制，改动它会改变所有新用户看到的首屏数字，
应作为独立的产品决定。

---

## 16. 建议的 Phase 11

1. **出厂预设的权威决定**：是否把 `design.manufacturability_start.v2` 的
   `k_w = 0.93` 改为声明式 `AUTO_FROM_GEOMETRY`（首屏 Ke 会降 6.9 %）
2. 把可制造性问题并入主仪表板的可行性摘要
3. 权威切换的逐值 before/after 预览
4. 在实际打包产物上跑一次完整冒烟
5. **实验/公开参考数据框架**——这是把任何 `NUMERICAL_FEA` 升级为
   `VALIDATED` 的唯一途径，也是当前最大的缺口
