# Phase 8E D 盘受控迁移记录

## 目标

- 原仓库：`%USERPROFILE%\Documents\Codex\2026-07-03\agents-md-docs-project-status-zh\repo`
- 新 canonical 仓库：`D:\Codex\Projects\MotorCalculator`
- 解释器：`D:\Python312\python.exe`

迁移采用可逆复制，不删除原仓库。复制保留 `.git`、源代码、文档、validation data 与构建配置；不复制 `.venv`、`build/`、`dist/`、缓存和原仓库未跟踪 `tmp/`。新位置必须重建 `.venv` 后再完成完整测试、source GUI smoke、one-folder 打包、packaged GUI smoke 与 strict no-source-.venv 门禁。

## 路径审计

运行时代码与 `MotorCalculator.spec` 不包含旧仓库绝对路径。历史 Phase 8A 文档保留当时解释器及构建路径作为审计证据，不作为 runtime 配置。用户数据继续位于 `%LOCALAPPDATA%\MotorCalculator`，不会迁入仓库。

## 最终门禁

### Git 与环境

- 分支：`codex/phase8e-chinese-ui-d-drive-migration`
- 本地化 checkpoint：`b49248c`
- Python：`3.12.10`，解释器基路径 `D:\Python312`
- Tcl/Tk：`8.6.15`
- NumPy / Matplotlib / pytest / PyInstaller：`2.3.5 / 3.11.0 / 9.1.1 / 6.16.0`
- D 盘 `.venv` 为重新创建，不是 C 盘环境副本。

### 测试与 GUI

- Phase 8E 前基线：`564 passed`
- 本地化、高 DPI 与温度单位显示修复后：`576 passed`
- 常规 96 DPI source GUI smoke：`PASS`
- 约 200% 的 192 DPI source GUI smoke：`PASS`
- 192 DPI 窗口：`1824 x 980`，Windows 工作区：`1920 x 1032`
- 中文主标题、文件菜单、引导输入、置信度 tab、反馈对话框与不确定性对话框均通过 stable-key 检查。
- 高 DPI 审计发现并修复了置信度操作按钮被挤出的问题；最终 `confidence_actions_visible = true`，两个对话框均位于屏幕范围内。

### Package

- one-folder 目录：`D:\Codex\Projects\MotorCalculator\dist\MotorCalculator`
- EXE：`D:\Codex\Projects\MotorCalculator\dist\MotorCalculator\MotorCalculator.exe`
- 包大小：`90,100,432` bytes（`85.93 MiB`），共 `1243` 个文件。
- packaged GUI smoke：`PASS`
- strict no-source-.venv smoke：`PASS`；运行时 `.venv` 已临时重命名，工作目录位于仓库外，且未提供 `TCL_LIBRARY`、`TK_LIBRARY`、`PYTHONPATH`。
- 重启持久化：首次反馈计数 `0 -> 1`，第二次进程启动为 `1 -> 2`。
- Tcl/Tk 资源存在：`_tcl_data/init.tcl`、`_tk_data/tk.tcl`、`tcl86t.dll`、`tk86t.dll`。
- dist 二进制审计未发现旧 C 盘仓库绝对路径。

### 兼容性与冻结边界

- C 盘生成的 schema v1 `.motorproj` 已由 D 盘环境加载、保存并精确恢复输入：`PASS`。
- 默认用户数据仍为 `%LOCALAPPDATA%\MotorCalculator`；迁移未移动日志、恢复、反馈、设置或最近项目。
- `motor_core/calculations.py` SHA-256：`416330175f2c770cd6e4c5c6e0df98e22eb7c290e3b5825926cc124642b87a2d`
- `legacy_baseline.json` SHA-256：`15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9`
- 原 C 盘仓库保留，未删除。原未跟踪 `tmp/` 未修改、未复制、未提交。

### 局限

本次视觉门禁覆盖当前 96 DPI 与 Tk 192 DPI 模拟缩放，不代表所有多显示器、远程桌面、自定义系统字体或辅助功能设置均已认证。one-file、安装器、代码签名和自动更新仍不在 Phase 8E 范围内。
