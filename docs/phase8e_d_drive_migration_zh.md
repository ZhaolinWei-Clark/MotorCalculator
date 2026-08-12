# Phase 8E D 盘受控迁移记录

## 目标

- 原仓库：`C:\Users\10099\Documents\Codex\2026-07-03\agents-md-docs-project-status-zh\repo`
- 新 canonical 仓库：`D:\Codex\Projects\MotorCalculator`
- 解释器：`D:\Python312\python.exe`

迁移采用可逆复制，不删除原仓库。复制保留 `.git`、源代码、文档、validation data 与构建配置；不复制 `.venv`、`build/`、`dist/`、缓存和原仓库未跟踪 `tmp/`。新位置必须重建 `.venv` 后再完成完整测试、source GUI smoke、one-folder 打包、packaged GUI smoke 与 strict no-source-.venv 门禁。

## 路径审计

运行时代码与 `MotorCalculator.spec` 不包含旧仓库绝对路径。历史 Phase 8A 文档保留当时解释器及构建路径作为审计证据，不作为 runtime 配置。用户数据继续位于 `%LOCALAPPDATA%\MotorCalculator`，不会迁入仓库。

## 最终门禁

此节在 D 盘验证后填写最终提交、测试数、GUI smoke、package 路径、`.motorproj` 跨路径兼容、Tcl/Tk 资源和 protected-file hash。
