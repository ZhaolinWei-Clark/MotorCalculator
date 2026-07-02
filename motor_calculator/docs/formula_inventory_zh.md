# 公式清单与状态

说明：

- A：基本物理关系
- B：解析近似模型
- C：经验系数模型
- D：示意波形或仅用于展示
- E：待确认或可能存在问题

## A 类：基本物理关系

| 分类 | 公式 | 代码位置 | 输入 | 输出 | 单位 | 模型假设 | 是否影响设计精度 |
|---|---|---|---|---|---|---|---|
| A | `R_gap = g_eff * k_c / (μ0 * A_pole)` | `motor_core/calculations.py :: calculate_magnetic_circuit` | `g_eff, k_c, A_pole` | 气隙磁阻 | A/Wb | 双气隙 AFPM，等效 Carter 系数 | 高 |
| A | `R_mag = 2 * h_mag / (μ0 * μr * A_pole)` | 同上 | `h_mag, μr, A_pole` | 磁钢磁阻 | A/Wb | 双转子双磁钢路径 | 高 |
| A | `Fm = 2 * (Br / μ0) * h_mag / μr` | 同上 | `Br, h_mag, μr` | 磁动势 | A | 双侧磁钢 | 高 |
| A | `Φ = Fm / (R_gap + σm * R_mag)` | 同上 | `Fm, R_gap, R_mag, σm` | 每极磁通 | Wb | 漏磁系数集中处理 | 高 |
| A | `E_line_rms = sqrt(3) * E_phase_rms` | `motor_core/calculations.py :: calculate_electrical_parameters` | 相反电势 | 线反电势 | V | Y 接 | 高 |
| A | `P_cu = 3 * I_rms^2 * R_phase` | `motor_core/calculations.py :: calculate_losses` | `I_rms, R_phase` | 铜损 | W | 三相平衡 | 高 |

## B 类：解析近似模型

| 分类 | 公式 | 代码位置 | 输入 | 输出 | 单位 | 模型假设 | 是否影响设计精度 |
|---|---|---|---|---|---|---|---|
| B | `A_pole = (π / (2 * pole_pairs)) * (Ro^2 - Ri^2) * αp` | `calculate_magnetic_circuit` | 几何尺寸、极弧系数 | 极面面积 | m² | 轴向磁通盘式结构 | 高 |
| B | `Bg_peak = Φ / A_pole` | `calculate_magnetic_circuit` | `Φ, A_pole` | 峰值气隙磁密 | T | 极面均匀等效 | 高 |
| B | `L_gap = μ0 * N^2 * A / g_eff` | `calculate_electrical_parameters` | 匝数、面积、气隙 | 气隙电感 | H | 无铁芯主导气隙电感 | 高 |
| B | `delta = sqrt(2 * ρ / (μ0 * 2πf))` | `calculate_losses` | `ρ, f` | 趋肤深度 | m | 交流导体近似 | 中 |
| B | `P_windage = 0.5 * Cm * ρ_air * ω^3 * (Ro^5 - Ri^5) * 2` | `calculate_losses` | `Cm, ρ_air, ω, Ro, Ri` | 风阻损耗 | W | 双盘式转子 | 中 |

## C 类：经验系数模型

| 分类 | 公式 | 代码位置 | 输入 | 输出 | 单位 | 模型假设 | 是否影响设计精度 |
|---|---|---|---|---|---|---|---|
| C | `E_phase_rms = 4.44 * f * N * Φ * kw` | `calculate_electrical_parameters` | `f, N, Φ, kw` | PMSM 相反电势有效值 | V | 正弦反电势 | 高 |
| C | `E_phase_rms = 4.0 * f * N * Φ * kw` | 同上 | `f, N, Φ, kw` | BLDC 相反电势有效值 | V | 梯形反电势 | 高 |
| C | `L_end = tau_p * 1.3` | `calculate_electrical_parameters` | 极距 | 端部长度 | m | legacy 端部绕组经验系数 | 中 |
| C | `L_end_ind = 0.15 * L_gap` | 同上 | `L_gap` | 端部电感 | H | legacy 经验比例 | 中 |
| C | `M = -0.5 * L_phase * 0.3` | 同上 | `L_phase` | 互感 | H | 平衡三相 + AFPM 耦合削弱 | 中 |
| C | `P_core = 0.01 * P_rated` | `calculate_losses` | `P_rated` | 铁损 | W | 粗略比例估计 | 高 |
| C | `P_bearing = 0.005 * P_rated * (n / 3000)` | `calculate_losses` | `P_rated, n` | 轴承损耗 | W | legacy 经验比例 | 中 |
| C | `K_fill = (3 * N * 2 * n_parallel * d_wire) / (π * D_in)` | `run_full_analysis` | 匝数、线径、内径 | 填充系数 | - | 并非真实槽满率，只是 legacy 占比指标 | 高 |

## D 类：示意波形或仅用于展示

| 分类 | 公式 | 代码位置 | 输入 | 输出 | 单位 | 模型假设 | 是否影响设计精度 |
|---|---|---|---|---|---|---|---|
| D | 梯形反电势分段函数 | `motor_core/calculations.py :: _trapezoidal_back_emf` | `θ, E_peak, αp` | 相反电势波形 | V | 示意性梯形波 | 中 |
| D | `T_inst = T_avg * (1 + k6*cos(6θ) + k12*cos(12θ))` | `calculate_torque_waveform` | `T_avg, k6, k12` | 瞬时转矩 | Nm | legacy 谐波示意模型 | 中 |
| D | `Bg(θ)` 的准方波空间分布 | `calculate_flux_distribution` | `Bg_peak, αp` | 空间磁密曲线 | T | 示意性空间分布 | 中 |
| D | FFT 频谱展示 | `calculate_flux_distribution` / legacy GUI 图形方法 | 波形数组 | 谐波图 | - | 仅用于展示 | 低 |

## E 类：待确认或可能存在问题

| 分类 | 公式 | 代码位置 | 输入 | 输出 | 单位 | 模型假设 | 是否影响设计精度 |
|---|---|---|---|---|---|---|---|
| E | `Kt = (3 * E_phase_rms) / (sqrt(2) * ωm)` 再换算 RMS | `calculate_electrical_parameters` | `E_phase_rms, ωm` | 转矩常数 | Nm/A | 相值/线值、峰值/有效值、PMSM/BLDC 驱动关系需进一步确认 | 高 |
| E | `T_rated = 9.55 * P / n` | `calculate_cogging_torque`, `calculate_torque_waveform`, `run_full_analysis` | `P, n` | 额定转矩 | Nm | legacy rpm 形式保留，尚未替换为严格 SI 形式以避免未批准回归漂移 | 中 |
| E | `V_req = sqrt(E^2 + (IR)^2 + (ωe L I)^2) * 1.05` | `run_full_analysis` | `E, I, R, L, ωe` | 所需电压 | V | 忽略控制策略、调制度和相位角 | 高 |
| E | `P_eddy = (π^2 / 24) * (f * B * d)^2 / ρ * V * k_skin` | `calculate_losses` | `f, B, d, ρ, V` | 涡流损耗 | W | 近似于导体局部交变磁场模型，适用边界待确认 | 高 |
