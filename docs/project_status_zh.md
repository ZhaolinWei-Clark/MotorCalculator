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

已完成：

- 审查原始单文件程序结构
- 识别 GUI、计算逻辑、依赖和打包风险
- 列出单位、相线值、峰值/有效值、极数/极对数等关键风险

### 第二阶段：安全基线、核心拆分、输入校验

已完成：

- 初始化 Git 仓库
- 保留原始单文件版本
- 创建 baseline 提交
- 保存 3 组 `legacy baseline`
- 创建 `motor_core/` 纯计算内核
- 创建 `gui/` GUI 包装层
- 集中单位转换、常量、模型假设和输入校验
- 建立回归测试、单位测试和输入校验测试

### Phase 3A：电气语义澄清与标准 pytest

已完成：

- 启用标准 `pytest`
- 标准测试命令固定为 `python -m pytest -v`
- 引入明确的速度、频率、电压、电流和控制模式语义
- 隔离 PMSM 与 BLDC 的电气语义边界
- 保留 legacy 输出字段并新增明确语义字段
- 编写 `docs/electrical_quantity_definitions_zh.md`

Phase 3A 验收状态：

- 测试结果：`25 passed`
- `legacy_baseline.json` 未修改
- 3 组 legacy baseline、18 个输出字段均未发现数值漂移

### Phase 3B：legacy 与 strict SI 额定转矩并行比较

已完成：

- 新增 `legacy_rated_torque_nm` 与 `revised_rated_torque_nm` 并行输出
- 新增额定转矩差异字段和状态字段
- revised 额定转矩只用于比较、测试和报告
- 下游仍继续使用 legacy 额定转矩
- 生成 `docs/phase3_formula_change_report_zh.md`

Phase 3B 验收状态：

- 测试结果：`35 passed`
- `legacy_baseline.json` 未修改
- revised 额定转矩未传播到额定电流、损耗、效率或 `required_voltage_v`

### Phase 3C：PMSM revised `Ke` / `Kt` 定义与隔离

已完成：

- 新增 revised PMSM `Ke` 四种显式定义
- 新增 revised PMSM `Kt` 两种显式定义
- 新增 `ke_model_status`、`kt_model_status`、`pmsm_power_consistency_status`
- 保持 revised `Ke` / `Kt` 只进入输出、测试和报告
- 保持 BLDC `Ke` / `Kt` 为 legacy / provisional

Phase 3C 验收状态：

- 测试结果：`63 passed`
- `legacy_baseline.json` 未修改
- 现有 3 组 legacy baseline 全部为 BLDC 路径
- revised PMSM `Ke` / `Kt` 当时仅通过单位换算、三相功率平衡和下游隔离测试
- 当时尚未通过独立 PMSM reference case 验证

### Phase 3D：独立 PMSM analytical reference cases

已完成：

- 新增独立 fixture：`motor_calculator/tests/fixtures/pmsm_reference_cases.json`
- fixture 与 `legacy_baseline.json` 分离保存
- 当前 4 个案例全部明确标记为 `analytical_reference`
- 新增独立 reference builder：`motor_calculator/tests/reference_case_builder.py`
- builder 只使用 fixture 原始输入、`json`、`math`、`pathlib`
- 新增测试：
  - `motor_calculator/tests/test_pmsm_reference_cases.py`
  - `motor_calculator/tests/test_pmsm_reference_power_balance.py`
  - `motor_calculator/tests/test_pmsm_reference_independence.py`
- 验证了以下关系在 4 个 PMSM 正弦案例中数值一致：
  - `rpm -> mechanical_angular_speed_rad_s`
  - `E_phase_peak -> E_phase_rms -> E_line_rms`
  - `I_phase_peak -> I_phase_rms`
  - 四种 revised `Ke`
  - 两种 revised `Kt`
  - `P_electromagnetic = (3/2) * E_phase_peak * I_phase_peak`
  - `T = P_electromagnetic / omega_m`
  - `T = Kt_phase_peak * I_phase_peak`
  - `T = Kt_phase_rms * I_phase_rms`
- 明确证明 reference expected 值不依赖 production calculation modules 生成
- 明确保留 legacy 下游链路不变

Phase 3D 验收状态：

- 4 个 analytical PMSM reference cases 全部通过
- revised PMSM `Ke` / `Kt` 已通过 analytical reference validation
- `legacy_baseline.json` SHA-256 固定值未变
- legacy regression 继续通过
- revised `Ke` / `Kt` 仍未设为默认值
- revised `Ke` / `Kt` 仍未传播到额定电流、损耗、效率、`required_voltage_v` 或 GUI 默认链路

## 4. 当前 Git 状态

- Phase 3C 状态固化提交：`941551d` `docs: record phase 3C completion and phase 3D scope`
- 当前 Phase 3D 工作分支：`test/pmsm-reference-cases`

关键历史提交：

- `d2f9f67`：`baseline: preserve original single-file motor calculator`
- `aaeb2d7`：`refactor: split motor core and add validation baseline`
- `c2d0039`：`docs: freeze project context and approved assumptions`

## 5. 当前测试体系

正式测试命令：

```text
python -m pytest -v
```

当前完整测试结果：

```text
84 passed
```

兼容测试入口仍保留：

```text
python work/run_pytest_style.py
```

但它只用于临时兼容环境，不再作为正式测试入口。

## 6. baseline 与 reference fixture 的角色

`motor_calculator/tests/fixtures/legacy_baseline.json` 的作用是：

- 固化重构前程序行为
- 作为 regression baseline
- 防止结构重构无意改变 legacy 输出

它不是：

- 物理真值
- PMSM revised `Ke` / `Kt` 的数值参考
- 实验验证结果

`motor_calculator/tests/fixtures/pmsm_reference_cases.json` 的作用是：

- 为 PMSM 正弦模式提供独立、可追溯、可手算的 analytical reference cases
- 验证 revised `Ke` / `Kt`、功率和转矩关系
- 与 legacy baseline 分开保存和解释

它当前不是：

- FEA 验证
- 台架实验验证
- 公开论文 benchmark
- 完整材料与几何驱动的电机样机验证

## 7. 当前公式状态

当前已经明确但仍保持并行、不切默认的内容包括：

- strict SI 额定转矩
- PMSM revised `Ke`
- PMSM revised `Kt`

当前仍保持 legacy 或未修正的内容包括：

- `9.55 * P / n` 的下游默认链路
- BLDC `Ke` / `Kt`
- `required_voltage_v`
- 铁损、机械损耗、涡流损耗模型
- 电感模型
- 槽满率代理模型

## 8. Phase 3D 结论

- PMSM revised `Ke` / `Kt` 已通过独立 analytical reference validation
- 这意味着 revised 定义在当前三相、Y 接、正弦稳态假设下可独立手算、可独立复核、可由 production results 数值重现
- 这不意味着 revised `Ke` / `Kt` 已获批准成为默认值
- 这也不意味着整套电机模型已经获得实验验证
- BLDC `Ke` / `Kt` 仍未进入本阶段

## 9. 下一阶段状态

当前 Phase 3D 已完成。

当前可考虑但必须单独审批的下一阶段候选是：

- 独立 BLDC `Ke` / `Kt` 阶段

当前仍不允许：

- 未经批准把 revised PMSM `Ke` / `Kt` 切换为默认值
- 未经批准把 revised rated torque 切换为默认值
- 在 BLDC 阶段混入 `required_voltage_v` 修正
- 在 BLDC 阶段混入损耗模型、电感模型或 GUI 重设计

## 10. 当前未解决问题

- BLDC 120°导通下的严格 RMS、peak、`Ke`、`Kt` 关系仍未建立
- `9.55 * P / n` 是否应从 legacy 默认值切换为严格 SI 默认值，尚未批准
- PMSM revised `Ke` / `Kt` 仍未成为默认值
- `required_voltage_v` 仍是 legacy 简化模型
- 缺少 FEA reference cases
- 缺少台架实验测量
- 缺少公开论文 benchmark
- 缺少材料、几何、磁路和绕组参数完整闭环的 PMSM reference cases

当前建议：

- 暂不将 revised 额定转矩设为默认值
- 暂不将 revised `Ke` / `Kt` 设为默认值
- 若继续推进，下一阶段应作为独立 BLDC `Ke` / `Kt` 工作包单独审批
