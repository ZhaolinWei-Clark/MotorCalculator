# Phase 8F Windows 部署、安装器与发布打包

## 范围与冻结边界

Phase 8F 仅建设发布身份、Windows 安装配置、便携包、发布清单、诊断导出与部署验证，不修改电机电磁公式、advanced AFPM、动态/控制方程、不确定性或校准数学、默认计算输出和 legacy baseline。

应用版本固定为 pre-1.0 工程预览版 `0.9.0`。唯一版本源是 `motor_calculator/version.py`；项目元数据、窗口标题、日志、诊断导出、PyInstaller Windows 版本资源、安装器参数和发布文件名均从该文件取得。中性发布者为 `MotorCalculator Project`，未虚构公司或法律实体。稳定安装升级标识为 `{A5F90D43-686B-4DDB-9F67-CF96B7A4A33D}`。

## 安装器技术审计

| 方案 | Windows/自动化 | AFPM 应用适配 | 当前环境 |
|---|---|---|---|
| Inno Setup 6 | 原生 Windows、脚本清晰、命令行 ISCC | 适合封装 one-folder、每用户安装、中文 UI、快捷方式、卸载与同 AppId 升级 | 已选；6.7.3 编译器已验证 |
| NSIS | 原生 Windows、脚本灵活 | 可实现，但需要更多定制逻辑 | 未安装 |
| WiX Toolset | MSI 能力完整 | 对当前小型工程预览发布过重 | 未安装 |

本阶段选择 Inno Setup。Phase 8F 初次审计时主机没有编译器；Phase 8F.1 已在 `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` 验证 Inno Setup `6.7.3`，并实际生成安装器。简体中文安装界面使用仓库内固定版本的 MIT 许可用户贡献翻译，来源和固定 commit 记录在 `installer/third_party/ChineseSimplified.SOURCE.txt`，不依赖构建机全局安装额外语言文件。

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

## Phase 8F.1 本地安装验收

验收日期：`2026-08-29`。候选安装器为 `release/MotorCalculator-0.9.0-win64-setup.exe`，大小 `29,616,246` bytes，SHA-256 为 `710ec86d78549f33da77a94f70843b619feed81c446eb9e7039a1ab4c41abe2c`。Windows 版本资源显示应用版本 `0.9.0`、中性发布者 `MotorCalculator Project`；Authenticode 状态为 `NotSigned`。

| 门禁 | 结果 | 实际证据 |
|---|---|---|
| 本地每用户安装 | PASS | 安装器退出码 0；程序进入 `%LOCALAPPDATA%\Programs\MotorCalculator` |
| 开始菜单 | PASS | 实际从“电机设计计算器”快捷方式启动安装目录中的 EXE |
| 桌面快捷方式策略 | PASS | 默认未创建；仍为可选且默认不勾选 |
| 已安装 GUI smoke | PASS | 中文 UI、0.9.0、正常计算、预设、置信度页、项目流程、恢复、反馈、导出、日志、matplotlib、正常关闭 |
| 项目保存/加载 | PASS | 安装版 smoke 通过真实文件对话框保存和打开仓库外 `.motorproj`，精确恢复输入并复现计算 |
| Recovery | PASS | 快照写入 `%LOCALAPPDATA%\MotorCalculator\recovery`，恢复后输入精确且可计算 |
| 反馈持久化 | PASS | 独立重启前记录数 12，重启后读回 12 并追加到 13；重装后继续读回 |
| 真实卸载 | PASS | 调用 `unins000.exe`；程序目录、开始菜单和卸载登记均移除 |
| 用户数据保留 | PASS | 仓库外 `.motorproj` 与反馈数据库卸载前后 SHA-256 不变；用户数据目录保留 |
| 重装 | PASS | 0.9.0 重新安装，唯一稳定 AppId 登记恢复，安装版完整 smoke 再次通过 |
| 安装目录审计 | PASS | 1,246 个运行文件；无 tests、`.git`、`.venv`、`tmp/`、pytest cache 或 build log |
| 源路径独立 | PASS | 安装目录未发现 D 盘规范仓库或旧 C 盘仓库运行时硬编码 |
| Tcl/Tk | PASS | 安装目录和便携目录均含 `_tcl_data/init.tcl`、`_tk_data/tk.tcl`、`tcl86t.dll`、`tk86t.dll` |
| source/package/portable smoke | PASS | 三种实际 GUI 运行均完成；portable 运行时源码 `.venv` 已临时移走且成功恢复 |
| Defender | PASS_NO_THREATS | 系统 `MpCmdRun.exe` 对安装器、安装 EXE、便携 EXE 三次扫描均退出 0 且报告未发现威胁 |

安装使用 `/SILENT` 执行以保证可重复日志；本机流程中没有观察到 SmartScreen 对话框。该观察不能证明其他机器不会显示 SmartScreen 或“未知发布者”，因为当前产物未签名。没有关闭 Defender、SmartScreen，也没有创建排除项。

## 升级策略与局限

稳定 AppId、`UsePreviousAppDir` 和相同安装目录为覆盖升级提供结构基础。本阶段没有伪造 `0.8.99-test` 应用二进制；仓库不存在可验证显示 0.8.99 的历史发行包，仅改变安装器标签而复用 0.9.0 EXE 不能证明真实升级，因此记录 `UPGRADE_TEST_BLOCKED`。后续应使用真正的历史构建执行升级验收。

本机没有 Windows Sandbox/Hyper-V 门禁；VMware Workstation 17.6.4 虽已安装并登记一个 `Win11_AB` 虚拟机，但该虚拟机不是已证明干净、可丢弃的发布测试镜像，且可能承载用户 PLC 环境，因此没有擅自启动或修改。`TRUE_CLEAN_MACHINE_TEST = BLOCKED_BY_ENVIRONMENT`，应转入 release-candidate 阶段。可信代码签名仍为 `NotSigned`，安装路径含空格的额外自定义路径测试未执行。

在本地闭环方面，安装器构建、每用户安装、开始菜单启动、安装版功能 smoke、卸载、用户数据保留、重装、便携回归和完整 pytest 均有实际证据，因此 Phase 8F 可按项目规则正式关闭；真正干净 Windows、真实历史版本升级和可信签名继续作为后续发布候选门禁，而不是伪报 PASS。
