# 项目状态

更新时间：2026-07-03

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

Phase 3A 验收状态：

- 测试结果：`25 passed`
- `legacy_baseline.json` 未修改

### Phase 3B：legacy 与 strict SI 额定转矩并行比较

已完成。

Phase 3B 验收状态：

- 测试结果：`35 passed`
- `legacy_baseline.json` 未修改
- revised 额定转矩未传播到额定电流、损耗、效率或 `required_voltage_v`

### Phase 3C：PMSM revised `Ke` / `Kt` 定义与隔离

已完成。

Phase 3C 验收状态：

- 测试结果：`63 passed`
- `legacy_baseline.json` 未修改
- 现有 3 组 legacy baseline 全部为 BLDC 路径

### Phase 3D：独立 PMSM analytical reference cases

已完成。

Phase 3D 验收状态：

- 测试结果：`84 passed`
- 4 个 analytical PMSM reference cases 全部通过
- revised PMSM `Ke` / `Kt` 已通过 analytical reference validation
- `legacy_baseline.json` SHA-256 固定值未变
- revised PMSM `Ke` / `Kt` 仍未传播到额定电流、损耗、效率、`required_voltage_v` 或 GUI 默认链路

### Phase 3E：BLDC revised `Ke` / `Kt` 语义、功率平衡与独立 analytical reference cases

已完成。

已完成内容：

- 建立理想 BLDC 三相、Y 接、梯形相反电势、120°六步换相 revised 波形语义
- 明确区分：
  - `phase_flat_top`
  - `phase_peak`
  - `phase_rms`
  - `line_to_line_peak`
  - `line_to_line_rms`
- 新增归一化纯函数：
  - `normalized_bldc_phase_back_emf(electrical_angle_rad)`
  - `normalized_bldc_phase_current(electrical_angle_rad)`
- 建立 BLDC revised `Ke` 字段：
  - `revised_bldc_back_emf_constant_phase_flat_top_v_per_rad_s`
  - `revised_bldc_back_emf_constant_phase_peak_v_per_rad_s`
  - `revised_bldc_back_emf_constant_phase_rms_v_per_rad_s`
  - `revised_bldc_back_emf_constant_line_rms_v_per_rad_s`
  - `revised_bldc_back_emf_constant_line_rms_v_per_krpm`
- 建立 BLDC revised `Kt` 字段：
  - `revised_bldc_torque_constant_nm_per_conduction_a`
  - `revised_bldc_torque_constant_nm_per_phase_rms_a`
- 新增状态字段：
  - `bldc_waveform_semantics_status`
  - `bldc_power_balance_status`
  - `bldc_ke_semantics_status`
  - `bldc_kt_semantics_status`
- 新增 4 个独立 BLDC analytical reference cases
- 新增独立 builder：`motor_calculator/tests/bldc_reference_case_builder.py`
- 新增并行输出与隔离验证测试

Phase 3E 验收状态：

- 完整测试结果：`117 passed`
- `legacy_baseline.json` 未修改
- `legacy_baseline.json` SHA-256：`15598fb1529e6f7707c80b6665597ab07bd148b087b59991b8038e3b508c17b9`
- 4 个 BLDC analytical reference cases 全部通过
- BLDC revised `Ke` / `Kt` 已通过 piecewise waveform、numeric integration、independent analytical reference 与 downstream-isolation validation
- revised BLDC `Ke` / `Kt` 未传播到额定电流、损耗、效率、`required_voltage_v`、转矩波形或 GUI 默认链路
- PMSM revised 结果保持不变
- 3 组 legacy baseline 继续全部通过

## 4. 当前 Git 状态

- Phase 3D 状态固化提交：`958dc23` `docs: record phase 3D completion and phase 3E scope`
- 当前 Phase 3E 工作分支：`feature/bldc-ke-kt-semantics`

关键历史提交：

- `d2f9f67`：`baseline: preserve original single-file motor calculator`
- `aaeb2d7`：`refactor: split motor core and add validation baseline`
- `c2d0039`：`docs: freeze project context and approved assumptions`

已记录的 Phase 3E 实现提交：

- `52373c6` `feat: define ideal BLDC waveform semantics`
- `3168ad2` `feat: derive BLDC Ke Kt from 120 degree power balance`
- `2d28905` `test: add independent BLDC analytical reference cases`
- `9716cb0` `test: validate BLDC Ke Kt semantics and isolation`

## 5. 当前测试体系

正式测试命令：

```text
.venv\Scripts\python.exe -m pytest -v
```

当前完整测试结果：

```text
117 passed
```

兼容测试入口仍保留：

```text
python work/run_pytest_style.py
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

`motor_calculator/tests/fixtures/pmsm_reference_cases.json` 的作用是：

- 为 PMSM 正弦模式提供独立、可追溯、可手算的 analytical reference cases

`motor_calculator/tests/fixtures/bldc_reference_cases.json` 的作用是：

- 为 ideal BLDC 120°导通模式提供独立、可追溯、可手算的 analytical reference cases
- 验证 revised BLDC `Ke` / `Kt`、相/线电压量、电流量、功率和转矩关系

当前这些 fixture 都不是：

- FEA 验证
- 台架实验验证
- 公开论文 benchmark
- 完整样机验证

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
- 因此 revised BLDC 模型被实现为与 legacy 并行的独立语义层，而不是对 legacy 波形做静默重解释
- revised BLDC `Ke` / `Kt` 已通过解析推导、数值积分、独立 reference fixture 和生产结果交叉验证
- 这不意味着 revised BLDC `Ke` / `Kt` 已获批准成为默认值
- 这也不意味着整套电机模型已经获得实验验证

## 9. 下一阶段状态

当前 Phase 3E 已完成。

当前尚未批准任何下一阶段。若继续推进，建议作为单独工作包审批：

- 是否引入更高层级验证来源：
  - FEA
  - 台架测试
  - 公开 benchmark
- 是否批准 revised PMSM `Ke` / `Kt` 成为默认值
- 是否批准 revised BLDC `Ke` / `Kt` 成为默认值
- 是否单独进入 `required_voltage_v` 语义修正阶段

## 10. 当前未解决问题

- revised PMSM `Ke` / `Kt` 仍未成为默认值
- revised BLDC `Ke` / `Kt` 仍未成为默认值
- `9.55 * P / n` 是否应切换为严格 SI 默认值，尚未批准
- `required_voltage_v` 仍是 legacy 简化模型
- 缺少 FEA reference cases
- 缺少台架实验测量
- 缺少公开论文 benchmark
- 缺少材料、几何、磁路和绕组参数完整闭环的样机验证
