# MotorCalculator Windows 安装器

Phase 8F 选择 Inno Setup 6 作为轻量 Windows 安装器方案。它直接封装已经验证的 PyInstaller one-folder 输出，不引入 Python、源代码、测试、`.venv`、`.git` 或 `tmp/`。

## 安装策略

- 默认安装目录：`%LOCALAPPDATA%\Programs\MotorCalculator`
- 默认不需要管理员权限
- 创建开始菜单快捷方式
- 桌面快捷方式为用户主动勾选项，默认关闭
- 卸载只移除程序文件和快捷方式
- `%LOCALAPPDATA%\MotorCalculator` 下的日志、恢复、反馈、设置与最近项目默认保留
- 用户自行保存的 `.motorproj` 文件不属于安装器管理范围

## 编译器

安装器源文件为 `installer/MotorCalculator.iss`。版本、发布者和稳定 AppId 由 `work/build_windows_release.ps1` 从 `motor_calculator/version.py` 注入，禁止手工复制版本号。

简体中文安装界面使用 `installer/third_party/ChineseSimplified.isl`。该文件固定自 `kira-96/Inno-Setup-Chinese-Simplified-Translation` 的明确提交；来源与提交记录在同目录 `ChineseSimplified.SOURCE.txt`，MIT 许可证保存在 `ChineseSimplified.LICENSE.txt`。构建不修改 Inno Setup 系统安装目录，也不依赖开发机额外安装语言文件。

当前构建机若未安装 Inno Setup，可以继续生成 one-folder 和便携 ZIP，但安装器状态必须记录为 `BLOCKED_BY_INSTALLER_COMPILER`。安装 Inno Setup 属于系统级外部软件操作，不由脚本静默执行。

## 签名

当前工程预览版不签名。流水线支持可选签名脚本，顺序为：构建 EXE、签名 EXE、构建安装器、签名安装器、校验签名、计算最终 SHA-256。不得用自签名证书暗示公开信任。
