# 外部验证数据目录说明

本目录用于 Phase 4A 外部验证框架的数据组织，不直接参与 production 默认计算链。

## 目录结构

- `templates/`：验证记录模板与一个仅用于测试导入器/比较器的 synthetic 示例
- `imported/`：未来导入的真实外部数据
- `reports/`：结构化验证报告输出

## 强制规则

1. 不得在 `imported/` 中放入虚构 benchmark、虚构 FEA 或虚构台架数据。
2. 所有真实外部数据都必须保留可追溯来源：
   - 文件
   - 文献
   - 实验记录
   - 用户输入
3. analytical reference 只能标记为 `analytical_reference`，不能伪装成实验验证。
4. 厂家参数只能标记为 `manufacturer_data`，不能伪装成 `bench_measurement`。
5. 缺失值必须使用字段状态：
   - `provided`
   - `inferred`
   - `unavailable`
   - `not_applicable`
6. 未知值不得用 `0` 代替。
7. 模板支持某个字段，不代表当前程序已经对该字段建立了成熟 revised 物理语义。

## 当前成熟度边界

已具备 revised 并行语义：

- strict SI `rated_torque_nm`
- PMSM revised `Ke` / `Kt`
- BLDC revised `Ke` / `Kt`

仍为 legacy / provisional：

- `phase_inductance_h`
- `rated_current_a`
- `iron_loss_w`
- `mechanical_loss_w`
- `efficiency`
- `required_voltage_v`
- 槽满率、热限制、退磁限制等下游链路

## synthetic 示例

`templates/example_synthetic_record.json` 只用于：

- 测试 schema
- 测试导入器
- 测试比较引擎

它必须始终保持：

- `source_type = analytical_reference`
- `evidence_level = LEVEL_1_ANALYTICAL`
- `synthetic = true`
- `not_for_accuracy_claims = true`

它不能被用来宣称程序已经获得公开 benchmark、FEA 或实测验证。
