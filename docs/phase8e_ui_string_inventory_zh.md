# Phase 8E GUI 用户可见字符串清单

## 审计边界

本清单覆盖主窗口、菜单、引导输入、preset、项目持久化、恢复、置信度与验证、不确定性、反馈、导出、正常错误提示和 packaged runtime 启动提示。完整逐项清单以 `motor_calculator/i18n/strings_en_US.py` 与 `strings_zh_CN.py` 中一一对应的 stable key 为准；测试会拒绝缺失或空白 key。

| 字符串族 | 原英文示例 | 中文替换 | 主要模块 | 保留缩写/符号 |
|---|---|---|---|---|
| 应用与菜单 | Motor Calculator / File / Save As | 电机电磁计算器 / 文件 / 另存为 | `gui/main_window.py` | MotorCalculator 文件类型 |
| 输入模式 | Basic / Advanced / Help | 基础 / 高级 / 帮助 | `gui/guided_input_panel.py` | 内部 `BASIC`、`ADVANCED` 不变 |
| 工程输入 | Air Gap / Pole Pairs / Winding Factor | 气隙 / 极对数 / 绕组系数 | `i18n/strings_zh_CN.py` | Br、Ke、Kt、RMS 与单位不译 |
| Preset | Starting Template / Assumptions / Provenance | 起始模板 / 假设条件 / 来源与溯源信息 | `gui/guided_input_panel.py`、`gui/main_window.py` | PMSM、BLDC、AFPM、SSDR、DSSR、NdFeB |
| 工程提示 | ERROR / WARNING / INFO / UNUSUAL | 错误 / 警告 / 提示 / 非典型 | `gui/main_window.py`、`gui/confidence_panel.py` | 后端 enum 值不变 |
| 项目文件 | New Project / Open / Unsaved Changes | 新建项目 / 打开项目 / 未保存修改 | `gui/main_window.py` | `.motorproj`、schema |
| 恢复 | Restore / Discard / Later / Details | 恢复 / 丢弃 / 稍后处理 / 详情 | `gui/recovery_dialog.py` | 路径、版本号原样保留 |
| 置信度 | Engineering Confidence / Validation Evidence | 工程置信度 / 验证证据 | `gui/confidence_panel.py` | FEA、Monte Carlo、P10-P90 |
| 不确定性 | Parameter Uncertainty / Normal Distribution | 参数不确定性 / 正态分布 | `gui/uncertainty_dialog.py` | 参数内部名称不变 |
| 验证反馈 | Feedback Record / Direct Comparison / Blocked | 验证反馈记录 / 直接可比 / 暂不可比 | `gui/feedback_dialog.py` | APE、RMS、FEA |
| 导出 | Export Summary / Text | 导出摘要 / 文本 | `gui/main_window.py` | JSON |
| Runtime | GUI startup failed / Detected Python | GUI 启动失败 / 检测到的 Python | `runtime/health.py` | Python、Tcl/Tk、Tkinter、路径 |

## 审计结论

- 正常首启与主要交互不再依赖英文显示文本作为内部 key。
- preset 的英文 provenance、assumptions、notes 在显示层按精确文本映射为中文，原 JSON 及序列化值保持不变。
- 原始异常与 traceback 只写本地日志；正常用户提示使用中文。
- 波形枚举“正弦波/梯形波”及 legacy 报告中的既有中文语义保持原样，未改动计算字段。
- 外部证据自由文本、用户项目名、文件路径和来源引用属于用户/数据内容，不强制翻译。
