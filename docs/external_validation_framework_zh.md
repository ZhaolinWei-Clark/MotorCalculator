# 外部验证框架说明

更新时间：2026-07-04

## 1. 为什么 analytical validation 不足以证明真实准确度

analytical validation 只能说明：

- 程序实现和一组明确数学定义是一致的
- 单位、相/线值、RMS/peak、功率平衡等内部语义是自洽的

它不能说明：

- 电机真实样机一定满足这些理想化假设
- legacy 经验公式已经被真实实验验证
- 材料、几何、槽型、端部效应、热限制、控制策略与损耗链路已经准确

因此：

- PMSM analytical reference
- BLDC analytical reference
- synthetic example

都不能被当作真实准确度证据。

## 2. 六种数据来源类型

`ValidationSourceType`：

- `analytical_reference`
- `published_benchmark`
- `fea_simulation`
- `bench_measurement`
- `manufacturer_data`
- `user_supplied_data`

规则：

- `analytical_reference` 只能表示独立数学参考
- `published_benchmark` 必须可追溯到文献或公开资料
- `fea_simulation` 必须可追溯到仿真文件、报告或工程编号
- `bench_measurement` 必须可追溯到实验记录
- `manufacturer_data` 不能冒充台架实测
- `user_supplied_data` 必须可追溯到用户提供的文件或记录

## 3. 五个证据等级

`ValidationEvidenceLevel`：

- `LEVEL_0_INTERNAL_REGRESSION`
- `LEVEL_1_ANALYTICAL`
- `LEVEL_2_PUBLISHED_OR_FEA`
- `LEVEL_3_CONTROLLED_MEASUREMENT`
- `LEVEL_4_MULTI_SOURCE_VALIDATION`

建议解释：

- `LEVEL_0`：内部回归或结构化占位数据，不可作准确度声明
- `LEVEL_1`：独立 analytical verification
- `LEVEL_2`：公开 benchmark 或 FEA 级别的外部参考
- `LEVEL_3`：受控台架实测
- `LEVEL_4`：多来源交叉验证

## 4. 数据 schema

Phase 4A 新增核心结构：

- `motor_core/validation_records.py`
- `motor_core/validation_loader.py`
- `motor_core/validation_comparison.py`

每条验证记录至少包含：

- `validation_id`
- `source_type`
- `evidence_level`
- `motor_type`
- `control_mode`
- `topology`
- `source_title`
- `source_author_or_organization`
- `source_year`
- `source_identifier`
- `source_file`
- `source_page_or_section`
- `license_or_usage_note`
- `data_quality_notes`
- `model_assumptions`
- `input_parameters`
- `expected_outputs`
- `uncertainty`
- `tolerances`
- `excluded_comparisons`
- `created_at`

字段值必须通过状态记录可用性：

- `provided`
- `inferred`
- `unavailable`
- `not_applicable`

未知值不得写成 `0`。

## 5. 单位和语义兼容规则

比较前必须同时满足：

- 控制模式兼容
- 拓扑兼容
- 绕组连接兼容
- 波形语义兼容
- 相值/线值兼容
- RMS/peak/flat-top 兼容
- 电流基准兼容

只有 `directly_comparable` 的字段才能计算模型误差。

Phase 4A 当前支持的 comparability 状态：

- `directly_comparable`
- `unit_conversion_required`
- `semantics_mismatch`
- `insufficient_input_data`
- `waveform_mismatch`
- `control_strategy_mismatch`
- `topology_mismatch`
- `not_available`

示例：

- `phase` 不能直接和 `line` 比
- `RMS` 不能直接和 `peak` 比
- PMSM 正弦结果不能直接和 BLDC 120°记录比
- `Y` 连接不能直接和 `Delta` 连接比
- 未知 current basis 的 `Nm/A` 不能直接比

## 6. 不确定度与误差的区别

`uncertainty` 用于记录外部数据本身的测量/仿真不确定度。

`model error` 用于记录程序预测值与 external expected value 的差异。

两者必须分开保存，不能混成一个数。

例如：

- 传感器误差或文献误差带属于 `uncertainty`
- legacy / revised 相对 expected 的偏差属于 `absolute_error_*` 和 `relative_error_*`

## 7. legacy / revised 比较方式

当前比较引擎同时输出：

- `predicted_legacy_value`
- `predicted_revised_value`

并分别给出：

- `absolute_error_legacy`
- `relative_error_legacy`
- `absolute_error_revised`
- `relative_error_revised`

这允许在不切默认值的前提下评估：

- legacy 路径
- revised 路径

但 Phase 4A 不会让外部验证结果回写 production。

## 8. 为什么不能自动校准公式

当前项目仍处于受控重构与语义澄清阶段。

因此明确禁止：

- 根据单个 benchmark 自动修改公式
- 根据误差自动改经验系数
- 根据 FEA 或实验差异自动切换默认值
- 把验证框架变成自动校准器

原因：

- 单个来源可能存在波形、连接或工况语义不一致
- 许多 downstream 量仍是 legacy/provisional
- 自动回写会破坏 regression baseline 和审查可追溯性

## 9. 如何导入公开论文数据

在 `validation_data/imported/` 中放入真实文献摘录或数据文件后：

1. 使用 `published_benchmark_template.json` 建立记录。
2. 填写标题、作者/机构、年份、DOI/URL/编号。
3. 填写页码或章节。
4. 明确单位、波形、连接、工况、输入参数。
5. 对不可比较字段写入 `excluded_comparisons`。

若论文只给图表而无明确语义：

- 可以记录来源
- 不得直接宣称“模型准确”

## 10. 如何导入 FEA 数据

使用 `fea_simulation_template.json`。

建议至少记录：

- 网格或求解精度说明
- 材料参数
- 几何边界
- 绕组连接
- 控制模式
- 求解器与边界条件
- 导出字段的单位与语义

如果 FEA 输出是 `phase peak` 而程序对比量是 `line rms`：

- 要么显式证明可转换
- 要么标记为 `semantics_mismatch`

## 11. 如何导入台架测量数据

使用 `bench_measurement_template.json`。

建议至少记录：

- 台架编号
- 测量日期
- 传感器型号
- 校准信息
- 采样方式
- 工况点
- 数据文件
- 处理方法

没有这些信息时：

- 可以降级为 `user_supplied_data`
- 不应直接称为 `LEVEL_3_CONTROLLED_MEASUREMENT`

## 12. 如何记录测量仪器和不确定度

不确定度应记录在 `uncertainty` 中，建议包含：

- `absolute`
- `relative`
- `coverage_factor`
- `notes`

仪器和采样细节应写入：

- `data_quality_notes`
- `source_file`
- `source_page_or_section`

## 13. 如何避免数据泄漏和循环验证

禁止把以下内容混为“外部验证”：

- production 结果导出的 synthetic expected
- 直接从 production 公式复制出的“独立 benchmark”
- 为了让测试通过而手工改写 expected 值

因此：

- synthetic example 只能标记为 `analytical_reference`
- `legacy_baseline.json` 不是 external benchmark
- reference builders 必须保持独立于 production 计算链

## 14. 如何判断字段是否可比较

一个字段只有同时满足以下条件，才是 `directly_comparable`：

- expected value 可用
- 来源与证据等级合法
- control mode 一致
- topology 一致
- connection 一致
- waveform 一致
- phase/line 一致
- RMS/peak/flat-top 一致
- current basis 一致
- 单位相同或已显式转换
- 不在 `excluded_comparisons` 内

否则应输出：

- `semantics_mismatch`
- `waveform_mismatch`
- `control_strategy_mismatch`
- `topology_mismatch`
- `insufficient_input_data`
- `not_available`

## 15. 当前哪些量已经具备 revised 定义

当前已经具备 revised 并行语义的量：

- strict SI `rated_torque_nm`
- PMSM revised `Ke`
- PMSM revised `Kt`
- BLDC revised `Ke`
- BLDC revised `Kt`

这些量可以在 comparability 条件满足时与 external expected 并行比较。

## 16. 哪些量仍属于 legacy / provisional

当前仍属于 legacy / provisional 的量包括：

- `phase_inductance_h`
- `rated_current_a` 默认链路
- `iron_loss_w`
- `mechanical_loss_w`
- `efficiency`
- `required_voltage_v`
- 槽满率
- thermal limits
- demagnetization limits

因此 schema 支持这些字段，不等于程序已经对这些字段建立成熟 revised 物理模型。

## 17. 当前不能做出的准确度声明

截至 Phase 4A 完成，当前不能宣称：

- 程序已经通过真实公开 benchmark 验证
- 程序已经通过 FEA 验证
- 程序已经通过台架实验验证
- `required_voltage_v`、损耗、效率、电感等已经得到 external validation
- 任何 revised 结果已经自动成为默认值
- synthetic example、legacy baseline 或 analytical reference 足以证明真实准确度

当前能宣称的是：

- 已建立可追溯外部验证框架
- 已建立 provenance、comparability、误差与不确定度分离结构
- 当前尚未导入真实外部 benchmark、FEA 或实测数据
