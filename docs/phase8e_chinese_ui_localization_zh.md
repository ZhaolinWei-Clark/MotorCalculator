# Phase 8E 中文优先界面本地化

## 架构

本地化层位于 `motor_calculator/i18n/`。GUI 通过 `tr()`、`input_label()`、`input_tooltip()`、`preset_name()`、`localize_status()` 和 `localize_message()` 使用 stable key；默认 locale 为 `zh_CN`，`en_US` 资源保留未来切换能力，运行不需要网络。

内部 Python 标识符、enum、schema key、`.motorproj` 字段与计算语义保持英文。未命名项目在序列化中仍为 `Untitled`，只在窗口标题显示为“未命名项目”。

## 术语策略

采用自然工程中文，同时保留 PMSM、BLDC、AFPM、SSDR、DSSR、RMS、Ke、Kt、Ld、Lq、FOC、PI、SVPWM、FEA 等通用缩写，以及 mm、m、rpm、rad/s、°C、K、V、A、Ω、H、T、Nm、W、kW 等单位与符号。

“LOW”显示为“低”，但配套说明继续强调置信度不足不等同于计算失败；“BLOCKED”显示为“暂不可比”，避免误解为软件故障。

温度单位选择器显示标准工程符号 `°C`，内部换算和项目持久化仍使用既有语言无关 token `degC`。

## 字体与布局

界面继续使用 Tk/Windows 系统字体回退，不捆绑专有字体。GUI smoke 检查中文主标题、文件菜单、引导输入标题、置信度选项卡，以及反馈与不确定性对话框标题。

最终视觉验证覆盖 96 DPI 与约 200% 的 192 DPI。高 DPI 初次检查发现置信度操作按钮会被纵向内容挤出；显示层将五项摘要改为双栏排列，并让操作区优先保留底部空间。复测确认操作按钮、说明文字和两个对话框均在 `1920 x 1032` 工作区内可用。

## 边界

本阶段只改变显示层。production 计算、动态/控制方程、advanced AFPM、校准逻辑、默认数值和 legacy baseline 均保持冻结。外部来源文本和用户输入内容不会被自动翻译或改写。
