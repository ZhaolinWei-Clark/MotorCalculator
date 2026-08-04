# Phase 7A：AFPM 外部验证缺口

## 1. 当前结论

**AFPM production-model accuracy validation is BLOCKED.** 当前仓库没有一条与默认双转子、单定子、双气隙 AFPM 拓扑直接兼容且字段完整的外部 benchmark。CREATOR 是径向磁通 PMSM，不能替代 AFPM 来源。

## 2. 已验证、内部一致与未验证

- externally validated AFPM quantities：无。
- internally consistent：PMSM/BLDC 的 phase/line、peak/RMS、Ke/Kt、三相功率关系；legacy regression；Phase 6 求解器和动态方程内部关系。
- unvalidated AFPM quantities：AFPM 反电势、Ke、Kt、额定转矩、电阻、感应参数、所需电压、铜耗、铁耗、效率、动态响应和绕组温度的真实精度。
- CREATOR 提供的额定转矩、相反电势峰值、相电阻和额定电流只属于 radial PMSM 来源字段；它们不改变上述 AFPM 结论。

## 3. 需要的 AFPM benchmark

至少需要以下可追溯字段；未知项必须保持 unavailable，不能以 0 或推测代替：

- topology description：轴向磁通方向、转子/定子数量、气隙数量与磁路布置。
- rotor/stator geometry：内外径、有效半径、叠厚/盘厚、槽数与关键尺寸。
- pole count / pole pairs、winding configuration、相数、Y/Delta、turns per phase、winding factor。
- air gap、magnet dimensions、magnet material、Br 与可用的 B-H/退磁信息、温度。
- phase resistance 及测量温度；phase inductance 或 Ld/Lq 及频率/电流条件。
- speed、current（phase/line 与 peak/RMS）、voltage、load torque 和 shaft/electromagnetic torque 位置。
- back EMF 的 phase/line、peak/RMS、基波/总波形定义与测量速度。
- copper/iron/mechanical loss、input/output power、efficiency 及相同 operating point。
- operating temperature、cooling condition、measurement/FEA provenance、网格/求解设置或仪器不确定度。

一个来源不必覆盖全部字段，但每个被比较指标必须具备足够输入和同一工况。

## 4. Parviainen 2005 状态

基于当前仓库的候选源审计，Parviainen 2005 仍是 Track B 最领先的补源候选之一，因为主题直接覆盖 AFPM 设计与径向/轴向比较。它目前仍是 `needs_user_supplied_source`：全文、页码、案例拓扑、输入字段、输出定义与 evidence type 尚未导入。因此它是 **leading candidate，不是已批准 benchmark**。

建议 Phase 7B 前先取得可合法使用的全文，逐页抽取至少一个完整 AFPM operating point，再通过现有 schema 和 comparability gate 导入。若案例只有 analytical/FEA 数据，应如实标注，不能称为 bench validation。

## 5. 动态验证 readiness

Phase 6 已提供 numerical validation：Euler/RK4 行为、步长收敛、稳态 torque balance 和若干控制链单元测试。physical/external validation 仍不可用。

| Quantity | 当前状态 | 外部数据要求 |
|---|---|---|
| current transient | INTERNAL_ONLY | 三相或 dq 电压/调制输入、DC bus、采样同步的相电流、传感器比例/偏置、Rs/Ld/Lq/psi_f、sample rate/timestamps |
| speed transient | INTERNAL_ONLY | voltage/current input profile、load torque profile、J、B、初始速度、编码器速度/位置时间序列与采样时基 |
| torque transient | INTERNAL_ONLY | 同步电流/速度、load/shaft torque time series、转矩测点与带宽、惯量和损耗边界 |
| startup / load step | BLOCKED | 明确的 step timing、幅值、控制模式、限流/限压、负载切换、完整时间序列和测试温度 |

没有输入 profile、load torque、inertia、motor parameters、time-series measurement 与 sample rate/timing，就不能把曲线差异归因于模型。

## 6. 热验证 readiness

当前热模型是 first-order lumped single-node RC，只表示一个绕组温度状态。外部验证至少需要 ambient temperature、current、speed、torque/operating point、总损耗或可分离损耗、温度随时间、Rth/Cth 或足够长的加热/冷却数据、冷却方式/流量/安装边界，以及 winding temperature measurement location 与传感器方法。

在这些字段缺失时，不验证铁耗，不将 `UnavailableIronLossModel` 解释为 0 W，也不从温升反推 calibrated parameters。
