# validation_data 数据源侦察说明

更新时间：2026-07-04

## 1. 当前状态

Phase 4B 只进行外部数据源侦察，不导入真实外部数据。

因此当前状态是：

- `validation_data/imported/` 仍然保持空目录语义
- 当前目录中只有占位文件 `.gitkeep`
- 尚未创建任何真实 `validation_data/imported/*.json`

## 2. Phase 4B 本轮明确未做

- 未导入 published benchmark
- 未导入真实 FEA record
- 未导入真实 bench measurement record
- 未导入 manufacturer data record
- 未导入任何用户提供数据

## 3. 为什么目前仍保持 imported 为空

真实外部数据进入 `imported/` 之前，必须逐项通过以下检查：

1. `license` 是否允许保存与后续使用
2. `source provenance` 是否可追溯到 DOI、论文、仓库、数据页、实验记录或用户文件
3. `field completeness` 是否足以支撑目标验证用途
4. `comparability` 是否与当前项目的 control mode、拓扑、相/线、RMS/peak 语义兼容
5. `missing fields` 是否会导致该记录只能做弱参考而不能算模型误差

## 4. 允许的下一步

后续若单独批准进入 Phase 4C，才允许：

- 在 `validation_data/imported/` 中放入真实外部原始文件或整理后的引用文件
- 创建与之对应的 validation record JSON
- 生成结构化 comparison report

## 5. 导入前必须再次确认的红线

- 不得伪造 published benchmark、FEA 或实验数据
- 不得把工具输出冒充实验实测
- 不得把厂家宣传参数冒充 controlled measurement
- 不得把 analytical reference 或 synthetic example 回写为真实 external validation
- 不得让外部验证结果直接修改 production 默认计算链

## 6. 关联文档

- `docs/external_data_source_candidates_zh.md`
- `docs/external_data_field_mapping_matrix_zh.md`
- `docs/validation_data_import_plan_zh.md`
- `docs/textbook_reference_candidates_zh.md`
