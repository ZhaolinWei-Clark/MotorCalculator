# Windows Engineering Preview 使用说明

## 启动

解压 one-folder 发布目录后运行 `MotorCalculator.exe`。应用不需要仓库、`.venv`、管理员权限或互联网。当前仓库尚未生成可发布包；只有完成打包烟雾清单的产物才可称为 engineering preview。

开发模式使用：

```powershell
.venv\Scripts\python.exe work\check_tk_runtime.py
.venv\Scripts\python.exe motor_calculator\app.py
```

## 用户数据

默认根目录为 `%LOCALAPPDATA%\MotorCalculator\`：

| 内容 | 位置 |
|---|---|
| validation feedback | `validation_feedback\feedback_records.jsonl` |
| 日志 | `logs\app.log`，1 MB 轮转，保留 3 个备份 |
| 默认本地导出 | `exports\` |
| 缓存 | `cache\` |

首次运行只创建目录；反馈 JSONL 在首次提交时才创建。记录继续使用 Phase 7J schema、append + flush + fsync 和哈希完整性验证。损坏记录由现有置信度层优雅降级，不会改动生产计算。

`MOTOR_CALCULATOR_USER_DATA` 可用于受控便携/测试位置，不应被安装程序硬编码。应用资源只读，研究数据、tests 和报告属于开发数据，不会迁移或删除。

## 导出与日志

Confidence 页使用本地文件选择器导出 JSON/TXT，默认打开 `exports`，也可选择 Documents 等其他可写位置。应用没有遥测或云依赖。日志仅记录启动和运行故障，不主动转储完整用户验证记录。

## Tcl/Tk 故障

如果显示 `Tkinter runtime could not be initialized`：

1. 运行 `work\check_tk_runtime.py`（开发环境）；
2. 确认使用完整 Windows CPython，安装时包含 Tcl/Tk；
3. 重新创建 `.venv`，不要混用不同 Python 的 Tcl DLL 和脚本；
4. 查看 `%LOCALAPPDATA%\MotorCalculator\logs\app.log`；
5. 不要把个人机器绝对路径写进项目代码。

## 显示缩放

启动前请求 Windows system DPI awareness，初始窗口最大限制为可用屏幕的 95%，以降低 100%、125%、150% 缩放下的裁切风险。当前环境不能创建窗口，因此这只是实现准备，不是视觉验收；必须按 smoke checklist 实机确认。

## 工程预览边界

该应用仍是 engineering-preview 工具。置信度和用户证据功能不等于实验认证；外部 AFPM 电磁精度仍受 Phase 7 证据边界约束。Phase 8A 没有修改电磁公式、默认数值、动态控制方程或 calibration governance。
