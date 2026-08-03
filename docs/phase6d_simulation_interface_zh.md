# Phase 6D：面向用户的动态仿真接口

## 1. 阶段边界

Phase 6D 在已验证的 PMSM dynamic engine 上增加配置、自动求解器选择、状态信息和显式静态 fallback。它不增加电机物理方程，不执行 calibration，不修改 production calculation chain、默认参数、GUI calculation behavior 或 legacy baseline。

低层 `SimulationRunner` 继续保留显式 timestep，供数值验证和开发测试使用。面向用户的新入口是 `UserSimulationRunner` 或 `run_user_simulation()`；它们只接收 `SimulationConfig`，用户不需要也不能通过该接口提供 timestep。

## 2. SimulationConfig

公开配置包含：

- `simulation_time`：总仿真时间，单位 s，必须是有限正数。
- `accuracy_level`：`FAST`、`BALANCED` 或 `HIGH_ACCURACY`。
- `solver_preference`：`AUTO`、`EULER` 或 `RK4`。
- `fallback_policy`：`STATIC` 或 `FAIL`。

字符串值也会被规范化为对应 enum；非法值会被明确拒绝。

## 3. Accuracy preset

| Accuracy | AUTO solver | Internal timestep | Numerical confidence | Intended use |
|---|---|---:|---|---|
| `FAST` | Euler | `5e-3 s` | low | 快速预览；结果总是带 warning |
| `BALANCED` | RK4 | `1e-3 s` | medium | 推荐的默认动态仿真 |
| `HIGH_ACCURACY` | RK4 | `1e-4 s` | high | 更细步长的内部数值设置 |

confidence 只描述当前 preset 的数值设置，不代表电机参数、模型物理或实机预测已经获得相同等级的验证。

## 4. Solver selection

`solver_preference=AUTO` 时使用上表映射。用户可以显式选择 Euler 或 RK4，但在 `BALANCED`/`HIGH_ACCURACY` 下强制 Euler 会返回 warning，并把 numerical confidence 降为 low。

自动选择不会修改 integrator、dq 模型或 production 默认值。内部 timestep 仅由 immutable preset 解析，不写回 `SimulationConfig`。

示例：

```python
from dynamics import (
    InputState,
    SimulationAccuracy,
    SimulationConfig,
    UserSimulationRunner,
)

config = SimulationConfig(
    simulation_time=1.0,
    accuracy_level=SimulationAccuracy.BALANCED,
)

result = UserSimulationRunner().run(
    initial_state=initial_state,
    motor_parameters=dynamic_parameters,
    input_profile=InputState(Vd=0.0, Vq=24.0, load_torque=1.0),
    config=config,
    static_fallback_provider=static_provider,
)
```

## 5. Simulation status

`SimulationResult` 增加以下元数据：

- `status`：`SUCCESS`、`WARNING`、`FALLBACK_STATIC` 或 `FAILED`。
- `warning_messages`：所有用户可见 warning，永不静默丢弃。
- `solver_used`：实际使用的 `Euler` 或 `RK4`。
- `confidence_level`：low、medium、high、unspecified 或 unavailable。
- `fallback_reason`：动态失败或 fallback 失败原因。
- `steady_state_result`：仅在静态 fallback 成功时存在。
- `transient_response_available`：明确标识 transient arrays 是否可用。

低层 runner 的直接结果使用 `confidence_level=unspecified`，因为它绕过了用户 accuracy preset。

## 6. Static fallback

dynamic sandbox 不自行构造静态结果，也不导入 production calculator。调用者通过 `static_fallback_provider(reason)` 显式提供可信的 steady-state result。

当动态仿真抛出数值或输入异常且 `fallback_policy=STATIC` 时：

1. 调用 provider，并把动态失败原因传给它。
2. 返回 `status=FALLBACK_STATIC`。
3. `steady_state_result` 原样保存 provider 返回对象，不转换、不校准、不修改。
4. transient arrays 保持为空，`transient_response_available=False`。
5. warning 明确说明 transient response unavailable。

如果未提供 provider、provider 自身失败或返回 `None`，结果为 `FAILED`，不会伪造静态结果。`fallback_policy=FAIL` 时动态失败也直接返回 `FAILED`。

## 7. Limitations

- accuracy preset 是固定 numerical policy，不是自适应误差控制。
- `FAST` 不能保证适用于所有电机时间常数；它只是带 warning 的快速预览。
- 尚无自动重试、solver escalation、刚性求解器或 convergence estimator。
- 静态 fallback 依赖调用者提供的结果，本层不验证其物理来源或准确度。
- 尚未实现 FOC、current controller、inverter switching、PWM、磁饱和、铁耗、热模型、BLDC dynamic model 或 parameter calibration。
- 本层尚未接入现有 GUI；因此 existing GUI calculation behavior 保持不变。

## 8. Conclusion

Phase 6D 把 Phase 6C 的数值引擎包装为不要求用户选择 timestep、不会静默 fallback、并携带明确状态和置信信息的安全接口。它是 simulation usability layer，不是 physics expansion 或 calibration layer。
