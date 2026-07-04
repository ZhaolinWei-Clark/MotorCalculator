# 项目状态

更新时间：2026-07-04

## 1. 当前项目目标

当前项目目标仍然是：

- 冻结已批准的模型定义
- 保持 legacy 行为稳定
- 提升结构可维护性、可测试性和语义清晰度
- 在任何会改变结果的公式修改前，先建立并行输出、测试和差异报告

当前项目目标不包括：

- 未经批准直接替换 legacy 电磁经验公式
- 重做 GUI 布局或视觉样式
- 删除 `matplotlib`
- 打包 EXE
- 在未批准前直接启用新的物理默认值

## 2. 项目对象

- 目标电机：三相轴向磁通永磁无刷电机 AFPM PMSM/BLDC
- 默认拓扑：双转子、单定子、双气隙
- 默认连接：Y 接

## 3. 已完成阶段

### 第一阶段：审查与问题识别

已完成。

### 第二阶段：安全基线、核心拆分、输入校验

已完成。

### Phase 3A：电气语义澄清与标准 pytest

已完成。

### Phase 3B：legacy 与 strict SI 额定转矩并行比较

已完成。

### Phase 3C：PMSM revised `Ke` / `Kt` 定义与隔离

已完成。

### Phase 3D：独立 PMSM analytical reference cases

已完成。

Phase 3D 验收状态：

- 测试结果：`84 passed`
- Phase 3D 状态固化提交：`958dc23`
- `legacy_baseline.json` SHA-256 固定值未变
- revised PMSM `Ke` / `Kt` 已通过 analytical reference validation

### Phase 3E：BLDC revised `Ke` / `Kt` 语义、功率平衡与独立 analytical reference cases

已完成并通过验收。

Phase 3E 分支：

- `feature/bldc-ke-kt-semantics`

Phase 3E 提交：

- `52373c6` `feat: define ideal BLDC waveform semantics`
- `3168ad2` `feat: derive BLDC Ke Kt from 120 degree power balance`
- `2d28905` `test: add independent BLDC analytical reference cases`
- `9716cb0` `test: validate BLDC Ke Kt semantics and isolation`
- `3bba27d` `docs: document BLDC Ke Kt analytical validation`

Phase 3E 验收状态：

- 修改前完整测试结果：`84 passed`
- 修改后完整测试结果：`117 passed`
- `legacy_baseline.json` 未修改
- `legacy_baseline.json` SHA-256：`15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9`
- BLDC revised `Ke` / `Kt` 已通过：
  - 分段解析推导
  - 独立数值积分
  - 独立 analytical reference cases
  - production/reference 交叉验证
  - downstream isolation
- revised BLDC line RMS `Ke` 与 legacy 相差约 `2.4695%`
- legacy BLDC `Kt` 语义仍不完整，不应强制计算误差
- revised PMSM 和 revised BLDC 均未设为默认值
- `required_voltage_v`、额定电流、损耗、效率、GUI 默认链路均未修改
- analytical validation 不等于 FEA、实验或公开 benchmark 验证

## 4. 当前 Git 状态

- 当前分支：`feature/bldc-ke-kt-semantics`
- Phase 3D 状态固化提交：`958dc23` `docs: record phase 3D completion and phase 3E scope`

## 5. 当前测试体系

正式测试命令：

```text
.venv\Scripts\python.exe -m pytest -v
```

当前完整测试结果：

```text
117 passed
```

## 6. baseline 与 reference fixture 的角色

`motor_calculator/tests/fixtures/legacy_baseline.json` 的作用是：

- 固化重构前程序行为
- 作为 regression baseline
- 防止结构重构无意改变 legacy 输出

它不是：

- 物理真值
- PMSM revised `Ke` / `Kt` 的数值参考
- BLDC revised `Ke` / `Kt` 的数值参考
- 实验验证结果

## 7. 当前公式状态

当前已经明确但仍保持并行、不切默认的内容包括：

- strict SI 额定转矩
- PMSM revised `Ke`
- PMSM revised `Kt`
- BLDC revised `Ke`
- BLDC revised `Kt`

当前仍保持 legacy 或未修正的内容包括：

- `9.55 * P / n` 的下游默认链路
- `required_voltage_v`
- 铁损、机械损耗、涡流损耗模型
- 电感模型
- 槽满率代理模型
- 退磁与温升模型

## 8. Phase 3E 结论

- 现有 legacy BLDC 示意波形不等于本阶段固定的 ideal 120°平顶梯形 revised 模型
- revised BLDC `Ke` / `Kt` 已通过解析推导、数值积分、独立 reference fixture 和 production/reference 交叉验证
- 这不意味着 revised BLDC `Ke` / `Kt` 已获批准成为默认值
- 这也不意味着整套电机模型已经获得实验验证

## 9. 下一阶段状态

Phase 3E 已完成并验收通过。

下一阶段已批准为 Phase 4A，但当前只做状态固化，尚未开始实施。

Phase 4A 只允许：

- 建立外部验证数据框架
- 建立数据来源追踪与 provenance 结构

Phase 4A 不允许：

- 切换任何默认链路
- 修改任何计算公式

## 10. 当前未解决问题

- revised PMSM `Ke` / `Kt` 仍未成为默认值
- revised BLDC `Ke` / `Kt` 仍未成为默认值
- `required_voltage_v` 仍是 legacy 简化模型
- 缺少 FEA reference cases
- 缺少台架实验测量
- 缺少公开论文 benchmark
- 缺少材料、几何、磁路和绕组参数完整闭环的样机验证
