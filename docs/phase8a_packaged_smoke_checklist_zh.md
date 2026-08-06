# Phase 8A Windows 打包烟雾检查清单

## 前置记录

- [ ] 记录构建 commit、Python、PyInstaller、Tcl/Tk 版本。
- [ ] `work/check_tk_runtime.py` 返回 `OK`。
- [ ] 从干净 `dist/MotorCalculator/` 开始，不设置 `TCL_LIBRARY`/`TK_LIBRARY`。
- [ ] 测试用户没有仓库、`.venv` 或管理员权限。
- [ ] 网络断开，确认程序不要求联网。

## 必测流程

1. [ ] `MotorCalculator.exe` 启动且没有控制台 traceback。
2. [ ] 主窗口打开并能在 100%、125%、150% 缩放下访问关键控件。
3. [ ] 运行一个 legacy 基线计算，输出与对应 baseline 数值一致。
4. [ ] 打开 `Confidence & Validation` 页。
5. [ ] 不确定性不可用时显示降级说明且主计算不崩溃。
6. [ ] 打开 validation feedback 对话框。
7. [ ] 保存反馈到 `%LOCALAPPDATA%\MotorCalculator\validation_feedback\feedback_records.jsonl`。
8. [ ] 关闭并重启，既有反馈可读取。
9. [ ] 导出 JSON 和 TXT 到用户选择目录，默认目录为用户数据下 `exports`。
10. [ ] matplotlib 存在时图表工作；构建不含 matplotlib 时核心 GUI 仍启动。
11. [ ] 删除一个必需打包资源后，启动明确报告缺失资源而非静默失败。
12. [ ] 正常关闭后进程退出，无残留写锁。

## 当前执行状态

本清单在 Phase 8A 当前机器上为 `BLOCKED`：没有生成包，真实 Tk 根不能创建。因此不能宣称主窗口、反馈重启、导出、DPI 或 clean-machine 流程已经通过。已自动验证的是路径隔离、反馈 lazy creation、日志、资源检查、可选 matplotlib 导入边界和 legacy 回归。
