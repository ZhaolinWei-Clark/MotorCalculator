# CREATOR PMSM 原始文件获取清单

更新时间：2026-07-04

## 1. 当前状态

本轮已完成：

- 仓库页核验
- README 下载与审阅
- `CREATOR_Machine_Data_2024-11-04.pdf` 下载与审阅
- `PM_synchronous_motor.zip` 下载、解包与字段级人工抽取

本轮未做：

- 未把原始 PDF / ZIP 写入 Git 仓库
- 未把 drive-cycle 大量时序数据整体导入为正式 record

## 2. 已下载文件

下载位置：

- 临时目录，仅用于本轮人工抽取与核验

文件列表：

1. `README.md`
   - 大小：`892 B`
   - 用途：数据集简介、许可说明、ZIP 内容概览
2. `CREATOR_Machine_Data_2024-11-04.pdf`
   - 大小：`2,088,845 B`
   - 用途：字段导航、表格页码、PMSM 控制/等效参数说明
3. `PM_synchronous_motor.zip`
   - 大小：`12,555,471 B`
   - 用途：PMSM 设计参数、材料、绕组、等效参数、反电势、drive-cycle 数据

## 3. 已用于正式 record 的关键文件

- `PMSM_general_specification.csv`
- `Design_parameters/Electrical_parameters/Electrical_properties_of_PMSM.csv`
- `Design_parameters/Motor_geometry/Geometry_parameters_PMSM.csv`
- `Design_parameters/Material_properties/Motor_parts_material.csv`
- `Design_parameters/Material_properties/Ferrite/Ferrite_properties.csv`
- `Measurement_results/Equivalent_circuit_parameters/Equivalent_circuit_parameters_PMSM.csv`
- `CREATOR_Machine_Data_2024-11-04.pdf`

## 4. 后续若继续深挖仍需人工动作

1. 若要导入损耗或效率字段，需要从 drive-cycle / no-load 文件中选定具体工况点并建立单独可追溯引用。
2. 若要导入 `phase_inductance_h`，需要先确认 `Ld/Lq` 到单一 schema 字段的允许语义。
3. 若要导入 `turns_per_phase`，需要先确认 `turns per slot` 是否能安全映射。

## 5. 当前不应做的事

- 不伪造缺失字段
- 不用 `0` 代替未知值
- 不把 raw PDF / ZIP 提交进 Git
- 不把该径向 PMSM record 夸大成 AFPM 或 BLDC 的准确度验证
