# Phase 8F Windows 部署、安装器与发布打包

## 范围与冻结边界

Phase 8F 仅建设发布身份、Windows 安装配置、便携包、发布清单、诊断导出与部署验证，不修改电机电磁公式、advanced AFPM、动态/控制方程、不确定性或校准数学、默认计算输出和 legacy baseline。

应用版本固定为 pre-1.0 工程预览版 `0.9.0`。唯一版本源是 `motor_calculator/version.py`；项目元数据、窗口标题、日志、诊断导出、PyInstaller Windows 版本资源、安装器参数和发布文件名均从该文件取得。中性发布者为 `MotorCalculator Project`，未虚构公司或法律实体。稳定安装升级标识为 `{A5F90D43-686B-4DDB-9F67-CF96B7A4A33D}`。

## 安装器技术审计

| 方案 | Windows/自动化 | AFPM 应用适配 | 当前环境 |
|---|---|---|---|
| Inno Setup 6 | 原生 Windows、脚本清晰、命令行 ISCC | 适合封装 one-folder、每用户安装、中文 UI、快捷方式、卸载与同 AppId 升级 | 已选；编译器当前未安装 |
| NSIS | 原生 Windows、脚本灵活 | 可实现，但需要更多定制逻辑 | 未安装 |
| WiX Toolset | MSI 能力完整 | 对当前小型工程预览发布过重 | 未安装 |

本阶段选择 Inno Setup。当前主机未发现 `ISCC.exe`、NSIS 或 WiX，也未发现可用 `winget`。遵循禁止静默安装外部系统软件的要求，只提交安装器源和构建说明。安装器实际编译状态为 `BLOCKED_BY_INSTALLER_COMPILER`，不得写成成功。

## 安装与用户数据策略

- 默认程序目录：`%LOCALAPPDATA%\Programs\MotorCalculator`
- 权限：`PrivilegesRequired=lowest`，正常路径不要求管理员权限
- 开始菜单：必建应用快捷方式及卸载入口
- 桌面快捷方式：可选任务，默认不勾选
- 用户数据：`%LOCALAPPDATA%\MotorCalculator`
- 用户项目：`.motorproj` 保留在用户选择的位置
- 卸载：只移除程序文件与快捷方式，默认不删除日志、恢复、反馈、设置、最近项目或用户项目
- 重装：稳定 AppId 和相同用户数据目录为后续安装/卸载/重装门禁提供基础

`.motorproj` 文件关联本阶段暂缓。当前应用启动入口尚未接受并安全验证命令行项目路径；在未完成该链路前注册关联会制造不可验证行为。多实例策略保持现状，不增加锁或 IPC。

## 发布构建流程

执行：

```powershell
.\work\build_windows_release.ps1
```

流水线依次检查工作树、受保护文件哈希、部署测试、生成 build metadata 与 Windows 版本资源、构建 PyInstaller one-folder、核验 Tcl/Tk、执行可选 EXE 签名、调用 Inno Setup、执行可选安装器签名、生成便携 ZIP、SHA-256 与 JSON manifest。缺少 Inno Setup 时默认失败但保留已验证便携产物；显式使用 `-AllowMissingInstallerCompiler` 才允许记录阻塞状态并完成部分发布候选。

生成目录不提交：

```text
release/
  MotorCalculator-0.9.0-win64-portable.zip
  MotorCalculator-0.9.0-win64-setup.exe   # 仅编译器可用时
  SHA256SUMS.txt
  release_manifest.json
```

安装器输入严格限定为 `dist\MotorCalculator\*`。`.venv`、源码、测试、`.git`、`tmp/`、build cache 和开发文档均不进入安装包。

## 隔离验证与证据等级

优先环境依次为 Windows Sandbox、Hyper-V/VMware/VirtualBox 虚拟机或另一台干净 Windows 主机。本阶段不会自动启用 Windows 功能。只有在无 Python、无仓库、无 `.venv`、无开发环境变量且只复制发布产物的系统中完成安装/卸载/重装，才能标记 `TRUE_CLEAN_MACHINE_PASS`。

若无此环境，只能报告 `ISOLATED_LOCAL_PASS`，同时保留 `CLEAN_MACHINE_TEST = BLOCKED_BY_ENVIRONMENT`。本地隔离门禁必须在仓库外解压便携 ZIP，清除 `TCL_LIBRARY`、`TK_LIBRARY` 和 `PYTHONPATH`，并临时禁用源码 `.venv` 后运行真实 GUI smoke。

## 签名、Defender 与 SmartScreen

当前工程预览产物不签名，不购买证书，也不用自签名证书暗示公开信任。未来签名钩子顺序为：构建 EXE、签名 EXE、构建安装器、签名安装器、校验签名、计算最终哈希。未签名 EXE/安装器可能触发 Microsoft Defender SmartScreen 或显示“未知发布者”，这不等同于恶意软件判定，不应通过关闭安全功能或添加排除项规避。

若本机 Defender 命令行扫描可安全使用，可扫描 EXE、便携 ZIP和安装器并记录结果；不得关闭防病毒或改变系统安全策略。

## 升级策略与局限

稳定 AppId、`UsePreviousAppDir` 和相同安装目录保证未来安装器可覆盖升级，而不是意外并行安装。`0.8.99-test -> 0.9.0` 的真实升级、安装/卸载/重装、开始菜单入口和用户数据保留必须在安装器编译器与隔离 Windows 环境可用后完成。

当前剩余门禁：Inno Setup 编译器、真正干净 Windows 安装测试、卸载/重装与模拟升级、可信代码签名。Phase 8F 可以完成便携发布基础，但在这些门禁关闭前不能宣称安装器或真正干净机器部署通过。
