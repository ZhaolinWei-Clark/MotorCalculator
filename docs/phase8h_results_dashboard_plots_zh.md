# Phase 8H 结果仪表板、工程曲线与设计解释

## 1. 范围与冻结边界

Phase 8H 将现有结果组织为中文优先的工程仪表板，并建立数据、渲染、Tk 嵌入和导出相互分离的绘图基础。本阶段没有修改 `motor_core/calculations.py`、电磁/advanced AFPM、动态/控制、不确定性或校准数学、默认输入、production 输出和 legacy baseline。

仪表板回答“当前模型实际算出了什么、工程状态如何、哪些分析尚不可用”。它不生成设计综合评分，不宣称优化、校准、制造认证或工业级能力图。

## 2. 架构

```text
AnalysisResult + Phase 8G feasibility
                |
                v
plots/models.py + dashboard.py + adapters.py
                |
        +-------+--------+
        |                |
performance.py       export.py
真实逐点模型计算      PNG/SVG/CSV
        |                |
        +-------+--------+
                v
gui/results_dashboard.py
```

- `models.py`：冻结的可用性、状态、KPI、曲线、动态、不确定性、敏感性和快照判断记录。
- `inventory.py`：所有仪表板候选结果的来源和边界清单。
- `dashboard.py`：从现有结果与 Phase 8G assessment 构建 KPI，不调用 Tk。
- `performance.py`：每个速度点复制输入，只改变 `n_rated`，调用现有模型；失败点保留为空白断点。
- `adapters.py`：只读适配显式运行的动态、不确定性和敏感性结果。
- `font_config.py`：从系统已安装字体选择中文字体，不绑定或打包专有字体路径。
- `results_dashboard.py`：Tk 组件、用户触发扫描、Matplotlib 嵌入及文件对话框。

## 3. 用户界面

顶层“结果仪表板”包含四个区段：

1. **结果总览**：转矩、输出功率、转速、当前模型估算效率、电流密度、同基电压裕量、近似裸铜槽占比、设计状态、Ke、Kt、相电流 RMS 和所需线电压 RMS。
2. **性能扫描**：最低/最高转速和点数由用户确认后运行；带 Matplotlib 工具栏并可导出。
3. **损耗与热**：逐项显示现有四类损耗及来源；静态温升明确不可用。
4. **分析可用性**：区分 `AVAILABLE`、`NOT_RUN`、`UNAVAILABLE` 和 `INVALID`，并显示具体原因。

Phase 8G 严重等级直接用于颜色和文字。设计状态只汇总严重、警告、建议检查和信息不足数量，不构造无证据的 0-100 分。

## 4. 速度扫描语义

扫描每个点均重新调用当前受支持的静态 calculation bridge。除机械转速外，所有输入保持不变，**包括额定输出功率**。因此当前可制造基线的功率在扫描中保持 600 W，而转矩按当前模型工作点随速度变化。这是“输入固定时模型会返回什么”的参数扫描，不是电流、逆变器、热、结构和控制共同约束的实际恒转矩/恒功率能力包络。

曲线包含：

- 转矩-转速；
- 输出功率-转速；
- 当前模型估算效率-转速，使用独立百分比纵轴；
- 所需/可用 line-RMS 电压-转速；
- 同基电压裕量-转速。

BLDC 模式不强制套用正弦 RMS/峰值关系，其同基可用电压和裕量曲线显示“当前 BLDC 模型语义不足”，而不是零值。无效采样点不插值、不桥接。

## 5. 导出、字体与性能

- PNG：160 dpi，保留中文标题和工程单位。
- SVG：可选矢量导出；中文字体来自运行系统的字体回退。
- CSV：UTF-8 BOM，含速度、实际输出、可用性、feasibility 状态和失败原因。
- 字体候选：Microsoft YaHei/JhengHei、SimHei、Noto/Source Han；均不存在时回退 DejaVu Sans，但不捆绑专有字体。
- 扫描不会自动执行。GUI 成功计算只更新 KPI，用户点击“生成曲线”后才运行。

2026-08-29 源 GUI 96 DPI 实测：初始仪表板更新约 `0.008 s`，7 点模型扫描约 `0.007 s`，四图渲染约 `0.48 s`。这些是本机交互观察，不是跨机器性能保证。

## 6. 结果快照

Phase 8B 已有 `ResultSnapshot` 现被 GUI 安全启用。成功计算后保存：结构化 result payload、输入哈希、应用/模型版本和 UTC 时间戳。

- 输入哈希和版本匹配：项目重开后可将快照标为当前，但只显示可安全恢复的结构化摘要；完整交互结果仍可重新计算。
- 输入已改变：仪表板标记为上一次成功结果，并要求重新计算。
- 模型/应用版本不同：标记历史/过期，不静默当作当前。
- 保存时若快照输入哈希与当前输入不匹配，则不写入项目。

## 7. 最终验证

- 变更前完整回归：`603 passed`。
- Phase 8H 前完整回归：`603 passed`。
- Phase 8H 后完整回归：`626 passed in 31.26s`；新增 23 项有效测试。
- 数据层、Phase 8A/8F 打包配置、项目持久化和 Phase 8G 定向门禁：`92 passed`。
- 源码真实 Tk GUI：`PASS`。96 DPI 下窗口、概览、性能图、PNG/CSV、项目快照保存/重开均实际通过。
- 高 DPI：使用 smoke-only Tk scaling `2.6666667` 获得等效 192 DPI；顶部 KPI、滚动后的电磁 KPI、范围条和性能图均通过窗口边界检查。实际窗口 `1824 x 980` 位于 `1920 x 1032` 工作区内。左侧 legacy 输入面板仍有少量窄栏文字裁切，不属于 Phase 8H 仪表板，也未在本阶段重构。
- 中文字体：源码与打包均实际选择系统 `Microsoft YaHei`；未捆绑专有字体。
- PyInstaller one-folder：Python `3.12.10`、Tcl/Tk `8.6.15`、PyInstaller `6.16.0` 重建成功；最终 `dist/MotorCalculator` 为 `90,100,670` bytes，含 1,244 个文件及 Tcl/Tk、Matplotlib。
- 打包真实 GUI：`PASS`。从仓库外目录启动，Phase 8H 曲线、中文、PNG/CSV、项目快照和既有 GUI 流程通过。
- strict no-source-.venv：`PASS`。源码 `.venv` 临时改名期间打包 smoke 完整通过，并在 `finally` 中恢复。
- Inno Setup `6.7.3`：使用最终 dist 实际重新编译成功；安装器为 `29,598,406` bytes，SHA-256 `7343025f8434dace6b07a574851fad0e676f733dba22d03dc4256bbc1772d6fa`。本阶段只验证兼容性，未重复 Phase 8F 安装/卸载验收。

## 8. 限制

- 扫描不是能力包络、效率地图、控制器仿真或热极限图。
- 静态温升不可用；动态热曲线只有显式运行 Phase 6O 后可显示。
- 生产 `required_voltage_v`、损耗与效率仍保留原模型局限。
- BLDC 电压裕量缺少足够语义。
- 不确定性和敏感性不会随普通静态计算自动运行。
- 当前没有把动态 sandbox 直接接入主 GUI 的运行入口；适配器仅为已有结果提供无重算可视化基础。
