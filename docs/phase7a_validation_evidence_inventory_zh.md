# Phase 7A：验证证据清单

## 1. 审计边界

本清单冻结 Phase 7A 可见的证据，不改变模型、参数或 validation schema。`experimental`、`analytical`、`FEA`、`manufacturer` 与 `synthetic` 必须分开解释。内部单元测试、解析夹具和数值收敛只证明实现一致性，不能作为外部精度声明。

## 2. 证据清单

| source_id | source_type / evidence | topology / waveform | quantities / operating points | provenance | topology compatibility | accuracy claim | calibration | blockers |
|---|---|---|---|---|---|---|---|---|
| `creator_pmsm_initial_record` | published benchmark；包含测量与部分 FEA 来源字段，LEVEL_2 | 径向气隙 PMSM，4 极 6 槽，正弦 | 2000 rpm；额定转矩、相基波反电势峰值、相电阻、相 RMS 电流；Ld/Lq 仅在来源说明中 | DOI、PDF 表格、CSV 文件、页/节与转换日志均已记录 | Track A 语义研究为 partial；与 Track B AFPM 不兼容 | partial，仅能说明来源字段和比较门禁工作；不能给出 AFPM error | no，当前记录标明 `not_for_accuracy_claims` 且拓扑不匹配 | 无 AFPM 几何映射；若干字段 unavailable；无不确定度 |
| `creator_pmsm_initial_comparison` | Phase 4 comparison report | CREATOR radial PMSM vs project AFPM gate | 对所有已导入输出执行 comparability 检查 | 由正式导入记录和现有比较引擎生成 | 明确 `TOPOLOGY_MISMATCH` / `NOT_AVAILABLE` | no，证明阻断正确，不证明模型准确 | no | 没有 directly comparable metric |
| `pmsm_reference_cases` | analytical / synthetic，LEVEL_1 | 三相 Y 接正弦 PMSM 语义 | 4 个手工工况；phase peak/RMS、line RMS、Ke、Kt、功率、转矩 | 仓库 JSON 夹具，公式假设显式 | Track A 内部语义兼容 | no external claim；仅 internal consistency | no | 非测量、非 FEA、非独立软件预测 |
| `bldc_reference_cases` | analytical / synthetic，LEVEL_1 | 三相 Y 接、理想梯形反电势、120 度六步 | 4 个工况；波形 RMS、Ke、Kt、电流、功率、转矩 | 仓库 JSON 夹具与独立分段/数值积分 | Track C 内部语义兼容 | no external claim；仅 internal consistency | no | 无真实换相、PWM、逆变器压降或外部 BLDC 数据 |
| `example_synthetic_record` | synthetic analytical template | 模板，不代表真实电机 | schema 示例字段 | 明确标注 synthetic | 不适合作任何拓扑准确度比较 | no | no | 仅用于验证 loader/schema |
| Phase 5 governance / calibration sandbox | governance + synthetic proposal evaluation | 强制区分径向 PMSM 与 AFPM | compatibility、proposal、risk、sensitivity 边界 | 项目状态、CREATOR 记录说明、`calibration_sandbox` 只读实现 | 结论是 CREATOR 可辅助 PMSM-side thinking，不能校准 AFPM 默认模型 | no | no execution；只允许治理讨论 | 仓库无独立 Phase 5 benchmark 或测量记录 |
| `phase6a_sensitivity_preview` | synthetic perturbation | production 输入副本上的局部扰动 | +/-1%、+/-5% 参数敏感性 | 可重复 sandbox runner | 只描述当前公式响应 | no | no | 不是外部真值，不回答参数应取何值 |
| `phase6c_dynamic_validation_report` | numerical / analytical | synthetic PMSM dq plant | Euler/RK4、dt 收敛、稳态力矩平衡、功率趋势 | 固定合成参数与可复现测试 | Track D 数值实现兼容 | no physical claim | no | 无实测电流/速度/转矩时间序列；粗步长 Euler 可不稳定 |
| Phase 6D-6L control reports | numerical / synthetic control tests | PMSM dq + controller/inverter/FOC skeleton | 配置、限压、PI、变换、FOC、anti-windup、速度环、MTPA/弱磁 | 单元测试与 sandbox examples | Track D 内部架构兼容 | no physical claim | no | 理想化反馈/平均模型；无控制器硬件 benchmark |
| `phase6m_sensor_nonideality_report` | numerical / synthetic | 可选传感器/编码器非理想层 | 偏置、噪声、量化、延迟类行为 | 固定随机种子/测试配置 | Track D only | no physical claim | no | 无具体传感器标定数据与实测噪声谱 |
| `phase6n_svpwm_average_modulation` | numerical / analytical average model | 平均 SVPWM/PWM envelope | 调制度、限幅、平均电压 | 解析关系和测试 | Track D only | no switching accuracy claim | no | 无开关波形、dead time、器件压降、硬件采样 |
| `phase6o_dynamic_loss_thermal_foundation` | analytical / synthetic | PMSM dq loss monitor + 单节点热 RC | 铜耗、可选 provisional 铁耗、阻尼损耗、温升与时间常数 | 方程、合成加热/冷却实验和测试 | Track E internal only | no physical claim | no | 默认铁耗 unavailable；无热参数辨识、冷却条件或温度测量 |
| `PARVIAINEN-AFPM` | published dissertation candidate；尚未入库 | 高相关 AFPM PMSM | 预计有几何、设计与性能示例；具体字段未核验 | 仅有候选引用，全文需用户提供/合法获取 | 潜在 Track B 兼容，尚未证明 | no, currently blocked | no | 源文件、页码、工况、定义和数值均未导入 |
| `FEMM-SPM` / outrunner example | FEA tutorial candidate | RFPM SPM 或 RFPM outrunner BLDC | 部分反电势/损耗/几何示例 | 外部候选页，未形成正式 record | 与 AFPM 不兼容；Track A/C 也需语义审查 | no | no | 非 AFPM；字段不完整；强依赖仿真 workflow |
| Paderborn electrical / thermal candidates | university bench dataset candidate | PMSM system，非 AFPM-specific | 电流、电压、速度、温度时间序列可能可用 | 候选清单，未导入 | 潜在 Track D/E，Track B 不兼容 | no, currently blocked | no | 输入、负载、惯量、参数与采样语义尚未映射 |
| `EMRAX` public data | manufacturer data candidate | AFPM product family | 产品级额定值，内部几何/工况通常不足 | 厂家公开页面，未导入 | 仅 topology relevant | no direct model claim | no | 无完整输入参数、测量方法、不确定度和可复现工况 |

## 3. 五条验证轨道

| Track | 被验证模型 | 明确不验证 | 当前 benchmark | 现在能否进行 |
|---|---|---|---|---|
| A | PMSM 共享电气语义、dq 方程和 Ke/Kt 定义 | AFPM 几何预测、控制器硬件、损耗 | CREATOR 为 primary candidate；PMSM 解析夹具为 internal secondary | PARTIAL：可审查语义/参数定义，尚无兼容完整预测比较 |
| B | AFPM production/default 电磁模型 | 径向 PMSM、BLDC 波形、动态控制 | 无 primary；Parviainen 2005 为 leading blocked candidate | BLOCKED |
| C | BLDC 特定反电势/电流/Ke/Kt 语义 | PMSM 正弦与 AFPM 几何准确度 | BLDC 解析夹具（internal only）；无 external primary | INTERNAL_ONLY / external BLOCKED |
| D | PMSM 动态 plant、求解器和控制链 | 静态 AFPM 几何精度、真实硬件开关 | Phase 6 数值报告（internal only）；Paderborn 为 blocked candidate | INTERNAL_ONLY / physical BLOCKED |
| E | 动态损耗监测与单节点热 RC | 多节点热路、已校准铁耗、实机效率 | Phase 6O（internal only）；Paderborn thermal 为 blocked candidate | INTERNAL_ONLY / physical BLOCKED |

## 4. Benchmark 优先级锁定

- PRIMARY：Track A 使用 CREATOR PMSM 作为来源和语义审查的首选外部记录，但当前不能形成 AFPM 数值误差；Track B 没有可用 primary；Track C/D/E 没有可用 external primary。
- SECONDARY：PMSM/BLDC 解析夹具与 Phase 6 数值报告仅作为内部一致性 secondary，不提升 evidence level。
- BLOCKED/FUTURE：Track B 优先补 Parviainen 2005 完整来源；Track D/E 可继续审查 Paderborn 数据；FEMM 与 EMRAX 只能在字段、拓扑和工况完整后另建 record。

结论：CREATOR radial PMSM 不得用于声明 AFPM topology accuracy。
