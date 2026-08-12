# Phase 8D 输入 UX、工程 Preset 与引导输入

## 目标与边界

Phase 8D 只降低录入成本和语义误用风险，不改变电磁、动态、控制、uncertainty 或 calibration 数学。所有计算仍由既有 production chain 显式触发；滑块移动不会自动运行分析、Monte Carlo、动态仿真或参数扫描。

## Basic / Advanced

- 默认 `ADVANCED`，保持既有工作流和全部字段可见。
- `BASIC` 保留常用工作点、主几何、磁材、绕组和波形字段；高级值只隐藏、不清空。
- 模式属于 `ui_preferences`，项目和 recovery 可恢复；实际 41 个 canonical 输入始终完整保存。

## Interaction-first 控件

- 气隙、转速、绕组系数使用“slider + 精确输入”；两者同步。
- slider 范围只是 quick-adjust display range，不是 validator limit。手工输入超范围的合法值时不钳位，并显示 `Outside quick-adjust range`。
- 极对数使用可键盘输入的 spinbox；波形使用有限枚举 dropdown；磁材使用 `Custom/N35/N42/N48/N52` selector。
- 所有数值仍可键盘精确输入。显示格式清除机器级浮点噪声，但保留有意义的自定义位数。
- 250 ms guidance debounce 和现有 recovery debounce 会取消前一次定时器；拖动期间不会连续写 recovery snapshot。

## Preset 架构与政策

Preset 位于 `motor_calculator/presets/data/presets.json`，由只读 registry/loader 加载。每项记录 ID、版本、类别、证据类型、provenance、assumptions、notes 和适用温度（如有关）。

当前内容：

- `AFPM SSDR Starting Template`：仅选择现有可表达 SSDR/无铁芯/正弦配置。
- `AFPM DSSR (Not Representable)`：明确 unavailable，不填补 schema 缺口。
- `PMSM Starting Template` / `BLDC Starting Template`：仅切换既有 waveform semantic。
- `N35/N42/N48/N52`：仅写入牌号和已有 constants 中的 nominal `Br`；提示厂家与温度依赖，仍允许手工覆盖。
- Application Default Example / Operating Point：明确为 demonstration starting values，不是优化结果或安全限值。

允许措辞包括“Starting template”“Typical reference value”“Manufacturer/source nominal value”。禁止无证据使用“best”“optimized”“guaranteed”。

## 安全应用与重置

Preset 应用前列出且仅列出变化字段，并显示证据、来源和假设；用户可 Apply 或 Cancel。Partial preset 不会修改无关几何、绕组或工作点。应用后项目标记 dirty 并进入 Phase 8C autosave 调度。

提供单字段 reset、quick section reset 和全量 Application Defaults reset。全量 reset 必须确认；Application Defaults 与 Engineering Preset 在文字和行为上分离。

## 单位层

GUI 支持：长度 `mm/m`、速度 `rpm/rad/s`、温度 `degC/K`；角度转换 API 支持 `degree/rad`，但当前 41 个 GUI 输入没有独立角度数值字段，因此未显示角度 selector。

单位只改变显示值与 slider 标签/范围。`.motorproj` 和 recovery 继续保存原 canonical 单位 `mm/rpm/degC`。长度和温度使用十进制转换路径避免可避免的显示往返漂移；速度按 `2*pi/60` 转换并按浮点精度比较。

## Guidance 与 Validation

- `ERROR / INVALID`：现有 parser/validator 判定无法计算，例如内径不小于外径。
- `WARNING / CHECK`：仍可计算，但应复核，例如超出引导转速范围。
- `INFO / UNUSUAL`：软工程提示，例如 7 mm 气隙超出 quick-adjust 范围但仍被保留。
- `INFO / NORMAL`：通过既有 validator 且没有触发软阈值。

软阈值不是工程保证或硬物理定律。真正 calculation blocking 仍由 production validation 负责。

## 项目、恢复与离线打包

项目文件保存 canonical values，并可附带 `input_mode`、显示单位、`preset_id/version`。加载不依赖 preset registry：即使未来 registry 变化，项目仍使用已保存的实际值。recovery 使用同一 document 构建路径，保留超 slider 范围精确值和显示偏好。

PyInstaller one-folder spec 显式打包 `presets.json`。运行时不需要网络；preset 读取不依赖 repository working directory。

## 已知限制

- 首批 quick-adjust slider 只覆盖气隙、转速和绕组系数；其余候选字段暂保留文本输入。
- 当前 schema 不提供显式 DSSR、绕组连接、`Ld/Lq` 或独立 angle 输入，因此不创建虚假控件或值。
- Tooltip 使用本地简短说明；Help 为本地主题摘要，不是完整电机设计教材。
- Guidance 不评价结构、绝缘、退磁、热或制造安全，也不声称 preset 具备最优效率。

## 验收记录

- 环境：CPython 3.12.10、Tcl/Tk 8.6.15、PyInstaller 6.16.0。
- Phase 8D dedicated tests：30 passed；完整 regression：564 passed。
- source real-GUI smoke：PASS，15/15 Phase 8D interaction gates 通过。
- packaged real-GUI smoke：PASS，包含计算、Confidence & Validation、preset、单位、项目、recovery、feedback、export、log、restart 与 clean close。
- strict no-source-.venv：PASS；`.venv` 在 packaged process 整个生命周期内改名不可见，working directory 为 Windows Temp，未设置 `TCL_LIBRARY/TK_LIBRARY`。
- one-folder：`dist/MotorCalculator`，约 85.90 MiB / 1243 files；包含 `_tcl_data`、`_tk_data` 与 `motor_calculator/presets/data/presets.json`。
- 截图检查：guided panel、超范围提示、Confidence & Validation 均可用，无关键控件裁切。
- `motor_core/calculations.py` SHA-256 保持 `416330175f2c770cd6e4c5c6e0df98e22eb7c290e3b5825926cc124642b87a2d`。
- `legacy_baseline.json` SHA-256 保持 `15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9`。
