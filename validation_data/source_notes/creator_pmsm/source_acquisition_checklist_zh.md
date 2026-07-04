# CREATOR PMSM 原始文件获取清单

更新时间：2026-07-04

## 1. 当前状态

本轮已完成：

- 仓库页核验
- README 预览核验
- 配套论文元数据核验

本轮未完成：

- 下载并审阅 `PM_synchronous_motor.zip`
- 下载并审阅 `CREATOR_Machine_Data_2024-11-04.pdf`
- 字段级手工抽取

## 2. 为创建正式 record 仍需的文件

优先级从高到低：

1. `CREATOR_Machine_Data_2024-11-04.pdf`
   - 仓库页标示大小：`2.1 MB`
   - 用途：表/页/节导航，定位 geometry、material、electrical、winding、equivalent parameters、measurement sections
2. `PM_synchronous_motor.zip`
   - 仓库页标示大小：`12.6 MB`
   - 用途：原始 PMSM 数据包，预计包含字段级数据文件

## 3. 下一步人工动作

1. 批准是否允许下载并本地保存 `2.1 MB` 的 PDF。
2. 批准是否允许下载并本地保存 `12.6 MB` 的 ZIP。
3. 若不批准下载，请手动提供以下任一项：
   - `CREATOR_Machine_Data_2024-11-04.pdf`
   - `PM_synchronous_motor.zip`
   - 或 PDF 中包含 PMSM 参数表/测量表的关键页截图
4. 在拿到原始文件后，逐项抽取：
   - `topology`
   - `winding_connection`
   - `control_mode` 相关语义
   - 额定参数表
   - 低频等效参数表
   - 至少一个可直接比较的 torque / back-EMF / loss / efficiency 指标

## 4. 当前不能做的事

- 不能伪造数值字段
- 不能用 `0` 代替未知值
- 不能在未确认 `topology` 前把该来源写成 AFPM benchmark
- 不能在未确认 `control_mode` / `back_emf_waveform` 前强行创建正式 PMSM comparison record
