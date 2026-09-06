# Phase 10B — 真实 FEMM 启用与首次 Ke 验证

**状态**：`PHASE10B_REAL_SOLVER_BLOCKED = FEMM_NOT_INSTALLED`
**分支**：`codex/phase10b-real-femm-ke-validation`
**应用版本**：`1.0.0-rc3`（Phase 10B 不提升版本号）

> **Phase 10B 未完成，且不能以 mock 数据关闭。**
> 本机没有安装 FEMM，**没有执行过任何真实场求解**，
> 因此不存在任何 FEA 数值、不存在 Ke 对比、不存在 `NUMERICAL_FEA` 证据记录。
> 本文档只记录**实际证据**，而实际证据就是：求解器缺席。

---

## 1. FEMM 安装检测（Step 3）

2026-09-05 在本机执行完整探测：

| 探测面 | 方法 | 结果 |
|---|---|---|
| `PATH` | `shutil.which` × `femm.exe` / `femm42.exe` / `femm` | 未发现 |
| `%ProgramFiles%` | `femm42\bin`、`femm42`、`FEMM\bin`、`FEMM` | 未发现 |
| `%ProgramFiles(x86)%` | 同上 | 未发现 |
| `%ProgramW6432%` | 同上 | 未发现 |
| `%LOCALAPPDATA%\Programs` | 同上 | 未发现 |
| 全部固定盘根目录（`C:\`、`D:\`） | 同上 | 未发现 |
| 注册表 `App Paths\femm.exe` | HKLM / HKCU，含 WOW6432Node | 键不存在 |
| 注册表 Uninstall 项 | HKLM / HKLM WOW6432Node / HKCU | 无 FEMM 条目 |
| `.fem` 文件关联 | HKCR | 无关联 |
| Python 接口 | `femm`、`pyfemm` | 不可导入 |
| 其他求解器 | `gmsh`、`pyaedt`、`mph`、`ansys` | 不可导入 |
| 磁盘扫描 | `C:\`、`D:\` 四层深度 `femm*.exe` | 无匹配 |

**结论：`FEMM_NOT_INSTALLED`。**

**未自动安装、未自动下载任何软件。**

### 一个需要澄清的假阳性

初次注册表扫描使用了较宽的匹配模式，命中了

```
Autodesk Interoperability Engine Manager 1.2.0.30
```

——它匹配的是 `Interoperability` 中的 `opera` 子串，**不是 FEA 求解器**。
正式探测因此把卸载项匹配令牌收紧为 `femm`，并加了一条回归测试锁定这一点：
一个过宽的令牌会让适配器把无关的可执行文件当成求解器去启动。

---

## 2. 本阶段实际改动（仅诊断与文档）

Step 3 允许在求解器缺席时「只接受经过论证的小幅诊断/文档改进」。
本阶段严格限于此，**没有实现任何 Phase 10B 主线交付物**
（未做通量链扫描、未做 Ke 对比、未改 GUI、未加并发、未做网格敏感性）。

理由：这些交付物的正确性依赖真实求解器的反馈。
在没有求解器的情况下盲写，只会把未经检验的假设固化进代码。

### 2.1 可用性探测加固 `v1 → v2`

本次准备工作暴露了 v1 探测的一个真实缺口：它只看 `PATH`、若干约定目录和
Python 接口。**把 FEMM 装到非系统盘或用注册表登记的安装，会被报成「未安装」。**
本机恰好有两个固定盘（`C:`、`D:`），项目本身就在 `D:` 上。

`phase10b.femm.probe.v2` 增加：

- Windows 注册表 `App Paths\femm.exe`（HKLM/HKCU，含 WOW6432Node）
- 注册表 Uninstall 项的 `InstallLocation`（令牌收紧为 `femm`）
- `.fem` 文件关联的 open 命令
- `%LOCALAPPDATA%\Programs`
- **全部固定盘根目录**，不只是系统盘

注册表优先于目录猜测：它给出的是**用户实际执行过的安装**，而不是约定路径的猜测。

探测覆盖面 **41 → 65 个位置**，单次耗时 261 ms（仅在对话框打开时执行一次）。
全部读取均为只读且防御式：缺键、拒绝访问或非 Windows 平台都只是「没找到」，
**不会抛异常**——探测失败关闭是正确的，探测崩溃不是。

### 2.2 最小真实求解 bring-up 用例（Step 5 的执行前置）

新增 `motor_calculator/fea/bringup.py`：空气域 + 单块永磁 + `A = 0` 边界，
三点取场。它检验的是**外部集成本身**，不是电机：

可执行文件能否启动、Lua 能否执行、**含空格的路径能否通过**、
工作目录能否使用、problem definition 与材料能否被接受、
网格与求解能否完成、解能否载入、能否取回一个标量场量、FEMM 能否干净退出。

工作目录名**刻意含空格**（`femm bringup`），因为路径引用正是它要证明的事情之一。

五项**可证伪**的场检查（不是拟合出来的期望值，而是一块正确建模并正确求解的
永磁体必须具备的性质，每一条都对应一类具体的集成故障）：

| 检查 | 捕捉的故障 |
|---|---|
| `field_is_nonzero` | 材料/充磁/求解未生效 |
| `field_below_remanence` | 单位或矫顽力错误 |
| `pole_face_polarity` | 充磁方向反了 |
| `field_decays_with_distance` | 边界离得太近，在加载解 |
| `pole_face_is_dominantly_axial` | 几何被旋转了 |

**诚实声明**：本模块写于没有 FEMM 的机器上，
**发出的 Lua 从未被真实求解器执行过**。
其结构与检查逻辑有单元测试；
「脚本格式正确」不等于「脚本能求解」，本文档不作后者的声明。

### 2.3 集成测试分离（Step 41）

新增 pytest marker `femm_integration`。真实求解器测试在 FEMM 缺席时
**skip 而不是 fail**——一个可选的外部求解器不该让常规回归失败，
它的缺席也不该被 mock 数据掩盖。

---

## 3. Phase 10B 各步骤的实际状态

| Step | 内容 | 状态 |
|---|---|---|
| 1 | 仓库状态核对 | **完成**（961 passed，两个受保护哈希未变） |
| 2 | 创建分支 | **完成** |
| 3 | FEMM 安装检测 | **完成 → `FEMM_NOT_INSTALLED`** |
| 4 | 记录 FEMM 版本/执行方式 | **阻塞**（无可执行文件可查询版本） |
| 5 | Hello-world bring-up | **脚本与检查已实现；执行阻塞** → `REAL_FEMM_BRINGUP = BLOCKED_BY_ENVIRONMENT` |
| 6 | 子进程健壮性 | Phase 10A 已具备；bring-up 沿用（显式路径、无 shell、超时、全量捕获、失败保留产物） |
| 7 | 求解 provenance | 结构已具备（含脚本 SHA-256）；**无真实运行可记录** |
| 8–18 | 预检 / 几何自检 / 单点求解 / 扫描 | **全部阻塞**（需要真实求解器） |
| 19–25 | BEMF 重建 / 导数交叉校验 / Ke 基准 | **未开始**（无数据可重建） |
| 26 | `NUMERICAL_FEA` 证据记录 | **未创建**（无真实结果） |
| 27–28 | 差异归因 / 不校准 | 无差异可归因；`AUTO_CALIBRATION_ENABLED` 仍为常量 `False` |
| 29 | 轻量网格敏感性 | **未开始** |
| 30 | 结果判定语言 | 无结果可判定 |
| 31–33 | GUI / 并发 / 取消 | **未改动**（真实运行耗时未知，无法论证并发必要性） |
| 34 | 失败诊断包 | bring-up 在失败时保留工作目录、退出码、stdout/stderr、脚本哈希 |
| 35–36 | 原始/对比导出 | **未开始**（无真实数据） |
| 37 | 本文档 | **完成** |
| 38–39 | 不做转矩、不做齿槽 | **遵守，未开始** |
| 40–41 | 测试与集成测试分离 | **完成** |
| 42 | 全量回归 | **完成** |
| 45 | 受保护哈希 | **未变** |

---

## 4. 未能提供的量

以下全部**没有数值**，因为没有求解器：

- FEMM 可执行文件路径、版本、架构
- hello-world 求解结果
- 单点电机求解结果
- 相磁链 `λ_A(θ_m)`、`λ_B`、`λ_C`
- 相平衡指标
- 磁钢极性场型验证
- BEMF 重建波形
- 谱微分 vs 有限差分交叉校验
- **FEMM Ke**
- 绝对差、相对差
- 网格敏感性
- campaign 耗时

解析侧 Ke 是已知的（Phase 10A 参考案例已捕获），但
**单边的数字不是对比**，因此本文档不列出它，以免被误读为验证结果。

---

## 5. 恢复 Phase 10B 的前置条件

1. 在本机安装 FEMM 4.2（**由人工完成**，本流程不自动安装第三方软件）。
2. 重新运行探测，确认 `FEMM_AVAILABLE` 并记录路径与版本。
3. 运行 `run_bringup()`，要求 `REAL_FEMM_BRINGUP = PASS`
   且五项场检查全部通过。**这一步大概率会暴露生成 Lua 中的问题**，
   因为它从未被真实执行过——这正是把它放在电机模型之前的原因。
4. 只有 bring-up 通过后，才进行单点电机求解（Step 11）。
5. 只有单点求解通过后，才进行粗扫（Step 14）与全扫（Step 17）。

**不得跳过 bring-up 直接跑 52 点扫描。**

---

## 6. 受保护基线

| 文件 | SHA-256 | Phase 10B 是否变化 |
|---|---|---|
| `motor_core/calculations.py` | `aad64af3d20afc1e73bd9d3510d25ebea7fa194c173f38229c1042c940b7e942` | **否** |
| `tests/fixtures/legacy_baseline.json` | `15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9` | **否** |

Phase 10B 未修改任何解析物理、电压语义、绕组系数、损耗、动态、
不确定性方程，也未改动优化器与可行性阈值。

---

## 7. 结论

**Phase 10B 不能关闭。**

成功判据要求 `REAL_FEMM_BRINGUP`、`REAL_MOTOR_SINGLE_POSITION_SOLVE`、
`REAL_FLUX_LINKAGE_SWEEP`、`BEMF_RECONSTRUCTION`、`KE_COMPARISON_COMPLETED`、
`NUMERICAL_FEA_EVIDENCE_RECORDED` 全部为 `PASS`，
而它们**全部依赖一个本机不存在的求解器**。

Phase 10A 的结论保持不变：

> **`FEA_BRIDGE_IMPLEMENTED_SOLVER_BLOCKED`**
> 目前没有任何 FEA 数值可以被当作已验证的证据。
