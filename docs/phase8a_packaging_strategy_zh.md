# Phase 8A Windows 打包策略

## 方案比较

| 方案 | Tcl/Tk | 启动/调试 | matplotlib | 风险与维护 | 结论 |
|---|---|---|---|---|---|
| PyInstaller one-folder | hook 可收集 Tcl/Tk，文件可检查 | 启动较快，缺失 DLL/资源容易定位 | 可随构建环境包含，体积较大 | 文件较多，但杀毒误报通常低于 one-file，更新清晰 | 首选 |
| PyInstaller one-file | 运行时解压 Tcl/Tk | 启动较慢，临时目录问题更难诊断 | 解压和扫描成本更明显 | 较高杀毒误报概率，故障现场不透明 | Phase 8A 不采用 |
| Nuitka | 可行但需要额外编译器工具链 | 构建和调试成本更高 | 需单独验证插件配置 | 当前环境未安装，也没有收益证据 | 暂不采用 |

## 选定策略

使用 `packaging/MotorCalculator.spec` 构建 PyInstaller one-folder 包 `dist/MotorCalculator/`。可靠性优先于最小文件尺寸，`upx` 禁用。规范显式包括：

- legacy GUI Python 资源；
- Phase 7I 控制参考不确定性 JSON；
- Phase 7H 控制 FEA 参考 JSON；
- 可用时的 matplotlib Tk backend；
- PyInstaller 自动 Tcl/Tk hook 所需内容。

规范不包括 `tmp/`、论文/PDF、tests、用户反馈数据库、日志或开发报告。用户可变数据始终写入 `%LOCALAPPDATA%\MotorCalculator\`。

## 可复现构建

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-packaging.txt
powershell -ExecutionPolicy Bypass -File work\build_windows_preview.ps1
```

构建脚本先创建并销毁真实 Tk 根，再确认 PyInstaller，任何一步失败都停止。当前环境 Tk 探针失败且 PyInstaller 未安装，所以本阶段没有生成 `dist`；这避免把无效包误标为工程预览。

## 资源与 clean-machine 边界

运行时通过 `check_packaged_resources()` 检查必需 legacy GUI 文件和可选置信度资源。source/packaged 模式均不依赖当前工作目录。真正的 clean-machine 验证仍需在修复后的独立 Windows 环境执行，包括无 repo、无 `.venv`、无开发环境变量启动。
