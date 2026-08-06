# Phase 7H 独立 FEA 求解器可行性审计

## 1. 审计结论

2026-08-06 对当前 Windows 工作环境进行命令、Python 包及标准安装目录探测，结果如下：

- `femm` / `femm42`：未发现
- `ElmerSolver` / `ElmerGrid`：未发现
- `gmsh` / `getdp`：未发现
- Python `gmsh`、`pyfemm`、Elmer 等包：未发现
- ANSYS Electronics Desktop / Maxwell：未发现
- COMSOL：未发现

因此：

`FEA_EXECUTION_STATUS = BLOCKED_BY_SOLVER_AVAILABILITY`

当前没有实际达到任何 FEA fidelity tier。Phase 7H 建立的是面向 `FEA_TIER_1` 外部 3D 结果的可复现输入、导入和收敛门控路径，而不是伪造一个场解。

## 2. 求解器矩阵

| 路径 | 许可/平台 | 自动化 | 维度与 AFPM 适用性 | PM、绕组、运动与输出 | 可复现/CI | 当前结论 |
|---|---|---|---|---|---|---|
| FEMM 4.2 | 开源，Windows 原生 | Lua、OctaveFEMM、pyFEMM | 平面 2D/轴对称；不能等价表示完整 AFPM 3D 主磁路 | 支持 PM、线路、力/转矩和磁链类后处理；旋转通常通过位置步进 | Windows CI 可行，但 GUI/COM 自动化需管理 | 未安装；即使安装，对本项目首个完整 AFPM 参考最多为 `FEA_TIER_3` |
| Elmer FEM | 开源，多平台，有 Windows installer | 文本 SIF、命令行；可由 Python 外部调度 | 支持 2D/3D 电磁问题，理论上可建立 AFPM 3D/准 3D | PM、线圈、磁动力学和积分后处理可配置；旋转机器模型搭建成本高 | 开源批处理适合 CI，但 3D 网格和求解资源较重 | 未安装；潜在 `FEA_TIER_1/2`，当前无已验证 AFPM 模板 |
| Gmsh + GetDP | 开源，多平台/Windows binary | Gmsh Python API + GetDP 命令行/问题文件 | Gmsh 支持 3D 网格，GetDP 支持磁静态/磁准静态；AFPM 需要自建完整 formulation | PM、线圈、运动耦合、磁链/转矩均需显式 formulation 与后处理 | 输入文本可版本化，CI 潜力高；开发与验证成本高 | 均未安装；潜在 `FEA_TIER_1/2`，但当前不存在已验证旋转 AFPM case |
| 已安装的其他求解器 | 不适用 | 不适用 | 未发现适合的独立电磁场求解器 | 不适用 | 不适用 | 无 |
| ANSYS Maxwell 3D | 商业，Windows | AEDT scripting / PyAEDT，可无界面执行和 CSV 导出 | 完整 3D 旋转电机路径，适合 AFPM | PM、绕组、运动、磁链、反电势与转矩均可建模/导出 | 商业 license 限制 CI；模型与导出可复现 | 本机未安装、license 未知；可作为外部 `FEA_TIER_1` 来源 |
| COMSOL AC/DC | 商业，Windows/多平台 | Java API、LiveLink 及结果 export | Rotating Machinery, Magnetic 支持 2D/3D；官方有 3D PM rotating machinery 示例 | PM、线圈、旋转域、磁链/电压/转矩与数据导出可实现 | 商业 license 限制 CI；Java 模型与导出可版本化 | 本机未安装、license 未知；可作为外部 `FEA_TIER_1` 来源 |

FEMM 官方文档列出了 Lua、pyFEMM 等自动化接口；Elmer 官方仓库提供 Windows 构建并覆盖电磁多物理；Gmsh 是 3D 网格器，GetDP 官方教程展示磁准静态和积分后处理。ANSYS Maxwell 支持报告导出 CSV，COMSOL 的 Rotating Machinery, Magnetic 接口支持 2D/3D 并有 3D 永磁旋转机器教程。

## 3. 为什么 AFPM 不能被单一 2D 截面等价替代

AFPM 的主磁通沿轴向穿过磁体、气隙与定子，而不是像常规径向磁通机器那样主要位于一个径向-切向平面。完整场解还同时包含：

- 切向速度 `v = omega * r` 随半径变化，内外半径对应不同局部线速度。
- 极距、线圈边长度和磁体周向宽度随半径变化。
- 扇形、梯形或圆柱磁体的局部覆盖率可能随半径改变。
- 内外圆周边缘和磁体端部存在三维边缘漏磁与 fringing。
- SSDR/DSSR 有多个轴向气隙，磁通回路和定子/转子耦合不同。
- 线圈端部、径向导体段、切向导体段和跨半径连接形成真正的 3D 绕组几何。

因此，单一 2D slice 可以作为简化磁参考，但不能声称与完整 3D AFPM FEA 等价。

## 4. Fidelity 分类

- `FEA_TIER_1`：完整 3D 电磁参考；显式机器几何、材料、绕组、边界、运动和网格收敛。
- `FEA_TIER_2`：经独立验证的 quasi-3D 或 multi-slice FEA；需说明切片组合和遗漏的 3D 效应。
- `FEA_TIER_3`：单一 2D slice、轴对称或其他简化磁参考；不可用于完整 AFPM 精度声明。

当前 achieved tier：**无**。受控机器的目标 tier 为 `FEA_TIER_1`，但在外部求解完成且收敛通过之前，它仅是输入定义。

## 5. 选定路径

当前选定：**外部 ANSYS Maxwell 3D 或 COMSOL 3D 求解 + 仓库内确定性 CSV 导入**。

理由：

- 不把 FEMM 单截面包装成完整 AFPM 3D 参考。
- 不在没有验证模板的情况下仓促实现 Elmer/GetDP 旋转机器 formulation。
- 允许外部商业求解器保留模型版本、solver version、网格和导出数据，并由仓库验证文件哈希、波形语义和收敛。
- 商业工程文件不进入仓库；只提交允许再分发的配置、元数据和 CSV 输出。

## 6. CI 与可复现边界

CI 当前可以执行：schema 校验、CSV 解析、SHA-256、波形 RMS/基波分析、网格收敛判定和参数不变性测试。CI 当前不能执行：任何真实 FEA 求解。若未来引入 Elmer/GetDP，应固定 solver/container 版本；若使用 Maxwell/COMSOL，应把 license-dependent solve 与开源 import/verification 分离。
