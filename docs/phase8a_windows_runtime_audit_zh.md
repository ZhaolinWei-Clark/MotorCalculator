# Phase 8A Windows 运行时审计

## 审计结论

审计日期为 2026-08-06。当前 `.venv` 可运行无界面计算和全部 pytest，但不能创建 Tcl 解释器或 Tk 根窗口。问题来自 `.venv` 继承的基础 Python 发行包，而不是 motor calculator 代码，也不是 matplotlib。

| 项目 | 检测结果 |
|---|---|
| 操作系统 | Windows 11，AMD64 |
| Python | 3.12.13，64 bit，MSC v.1944 |
| `.venv` 解释器 | `.venv\Scripts\python.exe` |
| 基础解释器 | `%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python` |
| tkinter | 可导入 |
| 编译时 Tcl/Tk | 8.6 / 8.6 |
| Tcl/Tk DLL 文件版本 | 8.6.12 |
| Tcl/Tk 根初始化 | FAILED |
| numpy | 2.3.5 |
| matplotlib | 3.11.0，可导入，仍为可选功能 |
| pytest | 9.1.1 |
| pip / setuptools / wheel | 25.0.1 / 83.0.0 / 0.47.0 |
| PyInstaller | 未安装 |
| Nuitka | 未安装 |

## `init.tcl` 根因

`init.tcl` 并非物理缺失。文件存在于基础解释器的 `tcl\tcl8.6\init.tcl`，大小为 25,633 bytes；`tcl86t.dll`、`tk86t.dll` 和编码数据也存在。初始 `TCL_LIBRARY`、`TK_LIBRARY` 均未设置。

关键诊断证据如下：

1. `.venv` 和基础解释器直接运行 `tkinter.Tcl()` 都报 `Can't find a usable init.tcl`，证明 venv 只是继承故障。
2. 显式把 `TCL_LIBRARY`、`TK_LIBRARY` 指向该基础解释器的 Tcl/Tk 目录后仍失败，因此不是单纯环境变量缺失。
3. 原生 Tcl 对实际路径 `<USER_HOME>/.cache/...` 执行 `file normalize` 时把 `.cache` 路径段归一化为空，并报告 `file exists = 0`；PowerShell 和 Python 文件 API 同时确认文件存在。
4. 运行的是明确指定的 `.venv`/基础 Python，不是 PATH 中的另一解释器；源代码模式尚未进入打包，因此不是 PyInstaller 配置造成。

结论：当前 Codex bundled Python 的 Tcl 原生文件系统无法正确解析其自身位于隐藏 `.cache` 目录下的 Tcl 库路径，属于基础 Python/Tcl 发行环境不完整或不兼容。仅设置环境变量不能修复。

## 可复现验证与修复

验证命令：

```powershell
.venv\Scripts\python.exe work\check_tk_runtime.py
```

可靠修复路径：安装包含 Tcl/Tk 的完整 64-bit Windows CPython（建议 python.org 安装包），用该解释器重新创建 `.venv`，安装依赖后再次运行探针。不要把当前机器的绝对 Tcl 路径写入代码，也不要从不匹配的 Python 发行包混拷 DLL/脚本。

本阶段没有修改当前受管基础 Python，因此 `TCL_TK_REPAIR_STATUS = BLOCKED_BY_BASE_PYTHON_DISTRIBUTION`。

## 入口点

- 推荐开发入口：`.venv\Scripts\python.exe motor_calculator\app.py`
- Tcl/Tk 验证入口：`.venv\Scripts\python.exe work\check_tk_runtime.py`
- Windows one-folder 构建入口：`work\build_windows_preview.ps1`
- `PMDC_Calculator_claude204.py` 是受保护的 legacy UI 实现，不是新部署流程的推荐入口。

## 运行时健康层

`motor_calculator/runtime/health.py` 返回 `OK`、`WARNING`、`FAILED` 结构化结果。Tk、Python、numpy、核心计算模块、用户数据可写性和必需资源是关键检查；matplotlib 与控制参考验证资源缺失只产生警告。失败详情保留在本地旋转日志，不发送网络遥测。
