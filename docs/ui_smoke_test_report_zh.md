# Phase UI-1 GUI Runtime Smoke Test Report

## 1. 基本信息

- 测试时间：2026-07-04
- 当前分支：`fix/gui-runtime-smoke-test`
- Python 解释器：`C:\Users\10099\Documents\Codex\2026-07-03\agents-md-docs-project-status-zh\repo\.venv\Scripts\python.exe`
- 启动命令：`.venv\Scripts\python.exe motor_calculator\app.py`

## 2. GUI 真实启动结果

- 是否成功真实打开 GUI：否
- 当前真实失败原因：本机当前 `.venv` 所基于的 Python 运行时无法正确初始化 Tcl/Tk，`tk.Tk()` 启动时失败，现已改为输出明确中文错误而不是在导入阶段因 `matplotlib` 崩溃
- 当前启动错误摘要：`GUI 启动失败：当前 Python 环境的 Tcl/Tk 运行时不可用，请参考 README 中的 GUI 启动说明修复 Python/Tcl/Tk 安装。`

## 3. matplotlib 状态

- 当前开发环境未安装 `matplotlib`
- 修复前现象：`motor_calculator\app.py` 在导入 legacy GUI 时立即抛出 `ModuleNotFoundError: No module named 'matplotlib'`
- 修复后状态：
  - `app.py` 可导入
  - `gui.main_window` 可导入
  - legacy GUI 模块可导入
  - 图表页改为延迟处理
  - 无 `matplotlib` 时图表显示与图表保存被禁用，并返回中文提示

## 4. Tcl/Tk 状态

- `tkinter` 模块可导入
- 当前环境仍无法可靠完成 Tcl/Tk runtime 初始化
- 本阶段未把 Tcl/Tk 文件复制进仓库
- 本阶段未在生产代码中硬编码 `TCL_LIBRARY` / `TK_LIBRARY` 绝对路径
- README 已补充推荐修复方式：使用带完整 Tcl/Tk 的 Windows CPython 重新创建 `.venv`，或在本机会话中临时设置环境变量后再启动

## 5. 默认参数 headless 计算检查

使用当前默认样例参数执行 headless 计算，结果成功：

- `rated_torque_nm`：`3.0560`
- `efficiency_percent`：`91.9552`
- `Ke_v_per_krpm`：`16.3538`
- `required_voltage_v`：`51.5178`
- `phase_current_rms_a`：`11.2980`

说明：

- 该检查仅证明当前 GUI 所依赖的 headless 计算路径仍可用
- 不构成任何新的物理准确度声明

## 6. 非法输入错误提示检查

使用非法输入 `V_dc = "abc"` 做解析检查，返回明确中文错误信息，核心内容如下：

- 参数“直流母线电压”当前输入为“abc”，不是可识别的数值
- 合法范围为 `> 0.0 V`
- 建议输入示例：`48.0`

## 7. 导出与保存检查

- JSON 保存：通过 headless smoke test，文件真实生成
- CSV 保存：通过 headless smoke test，文件真实生成
- 文本报告保存：通过 headless smoke test，文件真实生成
- 图表保存：
  - 无 `matplotlib` 时不会假成功，会返回中文错误
  - 仅当图像文件真实落盘后才提示成功
  - 若未生成任何文件，不再提示成功

## 8. 本阶段已修复的问题

- 修复了 GUI 启动阶段对 `matplotlib` 的强依赖
- 修复了 `app.py` 的导入兼容性，使其可作为入口模块导入
- 修复了图表保存“提示成功但实际上未生成任何文件”的假成功问题
- 新增 GUI runtime smoke tests，覆盖导入、可选依赖、图表保存真实性、headless 默认计算与 JSON/CSV/TXT 导出

## 9. 当前未解决的问题

- 本机当前 `.venv` 仍无法真实打开 Tk GUI，根因仍是 Tcl/Tk runtime 环境问题，不是仓库内公式或 GUI 业务逻辑问题
- 由于当前环境未安装 `matplotlib`，真实图表渲染与真实图像导出仍无法在本机 GUI 会话中完成

## 10. 测试状态

- GUI 相关新增 smoke tests：`9 passed`
- 完整 pytest：待本阶段全部文档更新后再运行并作为最终验收结果记录

## 11. 是否建议进入 UI-2 中文界面优化

- 当前不建议立即进入 UI-2
- 建议先解决本机 Tcl/Tk 运行时问题，并在可真实打开 GUI 的环境中补做一次人工交互 smoke test
