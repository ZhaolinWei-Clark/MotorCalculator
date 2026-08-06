# Phase 7H 独立 FEA Reference 验证报告

## 1. 状态

`FEA_EXECUTION_STATUS = BLOCKED_BY_SOLVER_AVAILABILITY`

本机未发现 FEMM、Elmer、Gmsh/GetDP、ANSYS Maxwell 或 COMSOL 可执行环境，也没有外部 FEA CSV 结果。因此本阶段没有场求解、没有 FEA 输出、没有解析模型对 FEA 的误差。

证据边界：

- 已完成：solver 可行性审计、受控机器冻结、schema、adapter interface、外部 CSV importer、SHA-256、波形数值分析、网格收敛 gate。
- 未完成：3D mesh、场求解、磁链/反电势导出、网格收敛数值、解析-vs-FEA 比较。

## 2. Solver 选择与 fidelity

- 当前可执行 solver：无。
- 选定路径：外部 ANSYS Maxwell 3D 或 COMSOL 3D 生成结果，仓库只导入可再分发的 CSV 与 metadata。
- 目标 fidelity：`FEA_TIER_1`。
- 当前 achieved fidelity：无；不得把目标 tier 写成已完成 tier。
- FEMM 若未来安装，单截面结果只能作为 `FEA_TIER_3`，不能替代完整 AFPM 3D reference。

## 3. CONTROLLED_FEA_REFERENCE 机器

该机器为 Phase 7H 有意指定的合成 SSDR，不是实验电机，也不冒充任何论文原型。

| 类别 | 冻结值 |
|---|---|
| 拓扑 | coreless SSDR，1 定子、2 转子、2 有效气隙 |
| 有效半径 | 50-100 mm |
| 每侧物理气隙 | 1 mm |
| 磁体厚度 | 5 mm |
| 极对数 | 5 |
| 磁体覆盖 | 常数 0.70 |
| 磁体 | `Br=1.20 T`，`mur=1.05`，本 no-load 模型中 conductivity 明确设为 0 |
| 铁磁芯 | 无，因此不需要钢材 B-H 曲线 |
| 绕组 | 三相、12 个显式梯形线圈、25 匝/线圈、4 串/相、1 并联支路；`A+,C-,B+,A-,C+,B-` 重复布局 |
| 有效串联匝数 | 100 匝/相 |
| 连接 | Y |
| 解析投影 `kw` | 0.9330127019，与冻结的 12-slot/10-pole 布局一同在任何 FEA 输出出现前固定；FEA 使用显式线圈几何而非此因子 |
| 运行点 | no-load，1000 rpm，20 degC，0 A phase RMS |
| 角度范围 | 一个电周期：0-72 mechanical degrees，起点包含、重复终点排除 |
| 3D 外空气域 | 径向、轴向各留 30 mm margin |

完整机器定义：`validation_data/fea_reference/phase7h_controlled_ssdr_machine.json`。

## 4. 网格与收敛

预注册三档 mesh：

| Mesh | 全局尺寸 | 气隙尺寸 | 磁体边缘 | 绕组 |
|---|---:|---:|---:|---:|
| coarse | 6.0 mm | 0.50 mm | 1.50 mm | 2.0 mm |
| medium | 4.0 mm | 0.30 mm | 1.00 mm | 1.5 mm |
| fine | 2.5 mm | 0.20 mm | 0.60 mm | 1.0 mm |

项目接受门槛预注册为 1.0%：所有 coarse-to-medium 和 medium-to-fine 的已跟踪 back-EMF 与 flux-linkage 变化都必须不超过 1.0%。这只是项目门槛，不宣称行业标准。

实际网格元素数：**UNAVAILABLE**

实际收敛变化：**UNAVAILABLE**

收敛结论：**NOT_EVALUATED**

## 5. FEA 输出

| 输出 | 状态 |
|---|---|
| phase flux linkage vs rotor angle/time | UNAVAILABLE |
| source-native phase back-EMF waveform | UNAVAILABLE |
| phase total RMS | UNAVAILABLE |
| phase peak | UNAVAILABLE |
| phase fundamental RMS | UNAVAILABLE |
| no-load torque/cogging torque | optional, UNAVAILABLE |

Importer 接受列：`rotor_angle_deg,time_s,flux_linkage_phase_a_wb_turn,back_emf_phase_a_v,torque_nm`。时间和角度必须严格递增且等间隔。总 RMS 直接从 waveform samples 计算；基波 RMS 通过单周期第一 DFT 系数计算，不使用 `peak/sqrt(2)` 假设。

## 6. 解析输出与外部误差

解析 mean-radius 输出：**NOT_RUN_FOR_COMPARISON**

解析 radial-slice 输出：**NOT_RUN_FOR_COMPARISON**

独立 FEA 输出：**UNAVAILABLE**

mean-radius error：**UNAVAILABLE**

radial-slice error：**UNAVAILABLE**

原因：没有 FEA reference 时生成单边解析数字不能回答 Phase 7H 的比较问题。受控输入已在 FEA 前提交冻结，未来只能用同一版本机器定义执行两条解析路径；不得在看到 FEA 后调整参数。

## 7. 证据分类

- `INTERNAL_ANALYTICAL`：解析模型自身输出或一致性案例。
- `INDEPENDENT_FEA_REFERENCE`：独立 field solver、完整 metadata、来源文件哈希且 mesh 收敛通过的自生成 FEA。
- `PUBLISHED_FEA_REFERENCE`：外部出版物给出的 FEA 证据，保留论文 provenance 与模型完整性限制。
- `EXPERIMENTAL_MEASUREMENT`：真实机器测量；不能由 FEA 标签替代。

当前机器 JSON 只是 `CONTROLLED_FEA_REFERENCE` 定义。只有实际 FEA 运行和收敛接受后，其结果才可标记 `INDEPENDENT_FEA_REFERENCE`，并且永远不能标记为实验验证。

## 8. Phase 7I 决策

1. 当前环境能否执行独立 AFPM FEA：否。
2. 当前可实现 fidelity：没有已执行 tier；外部路径目标为 `FEA_TIER_1`。
3. 是否成功生成 controlled FEA result：否；仅成功冻结 controlled machine input。
4. 是否获得首个 analytical-vs-FEA error：否。
5. 精确 blocker：没有安装可用的独立 3D 电磁求解器，也没有带 solver/mesh metadata 的外部 Maxwell/COMSOL CSV。
6. Phase 7I 建议：**D. external ANSYS/COMSOL reference generation**。在真实场解到达前，不应进入磁路改进、谐波模型或 torque comparison。

## 9. 限制

- 无真实 mesh 或 solver execution。
- 无 saturation、iron loss、thermal、inverter 或 controller。
- 第一参考机为 coreless synthetic SSDR，不代表生产默认机器。
- `kw=0.9330127019` 只用于未来解析投影；独立 FEA 必须使用显式线圈域及已冻结相序/极性。
- 外部导入器验证格式、hash 与波形数值，但不能证明外部模型本身建模正确；solver 工程审计仍是 reference acceptance 的必要步骤。
