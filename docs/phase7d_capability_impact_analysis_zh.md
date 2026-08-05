# Phase 7D Capability Impact Analysis

## 计数口径

“Affected rows”表示该能力是解除 blocker 的必要条件；不同能力覆盖会重叠，不能相加。“Potential unlock”表示与其他必要能力和完整 source data 共同实现后，理论上可比较的最大行数。“Immediate unlock in proposal/Phase 7E schema-only”均为 0，因为本阶段不实现 physics。

## Priority 与影响

| priority | capability | affected blocked rows | max potential unlock | immediate unlock | expected modules/files | formulas eventually affected | regression risk | validation benefit |
|---|---|---:|---:|---:|---|---|---|---|
| P0 | explicit topology + stator interconnection schema | 7 | 7 | 0 | new sandbox schema; later `motor_core/models.py`, `validation.py`, `units.py` | magnetic flux-path routing、winding terminal aggregation | high if production-routed; low sandbox-only | makes Parviainen/Abdelli mismatch machine-readable |
| P0 | explicit winding/coil/branch/connection schema | 7 | 6 | 0 | new sandbox schema; later `models.py`, winding helper, `calculations.py` | turns aggregation、resistance network、kw derivation | medium-high | separates missing source turns from unsupported winding physics |
| P0 | annulus + radius-dependent magnet geometry schema | 5 | 4 | 0 | new geometry schema; later `models.py`, magnetic helper | pole area、reluctance/flux integration、waveform geometry | high | required for Price/Hosseini/Parviainen native geometry |
| P0 | source-native back-EMF quantity/waveform semantics | 4 | 4 | 0 | validation-side result schema; later `models.py`, `electrical_semantics.py` | RMS/peak/fundamental/waveform extraction, not flux physics by itself | low schema, medium output routing | prevents invalid sqrt(2)/sqrt(3) conversions |
| P0 | completeness gate and comparability planner | 14 | 0 | 0 | validation package only | none | low | guarantees no defaults or hidden factors enter external cases |
| P1 | topology-aware, radial-slice magnetic/back-EMF sandbox solver | 5 | 4 | 0 | new sandbox solver; later magnetic sections of `calculations.py` only after approval | pole flux、gap reluctance、radius integration、EMF | high | first path to actual electromagnetic back-EMF evidence |
| P1 | winding-factor derivation and multi-stator winding network | 6 | 5 | 0 | new sandbox winding module; later `calculations.py` R/EMF paths | pitch/distribution factor、series/parallel phase quantities | high | removes hidden kw and topology multipliers |
| P1 | optional Ld/Lq sandbox model and result | 4 | 4 | 0 | new sandbox inductance module; later `models.py`/`calculations.py` | dq inductance physics; scalar path remains unchanged | medium-high | may compare Parviainen and Hosseini axis quantities directly |
| P1 | explicit torque boundary/result decomposition | 2 | 1 | 0 | result schema, mechanical-loss adapter | shaft/electromagnetic conversion only with explicit loss torque | medium | prevents Price shaft torque from becoming false Kt evidence |
| P2 | resistance temperature + multi-stator terminal network | 1 | 1 | 0 | sandbox resistance module; later resistance path | copper temperature and series/parallel terminal resistance | medium | enables Parviainen R only if measurement temperature is recovered |
| P2 | generator terminal/load and efficiency boundary | 3 | 2 | 0 | future generator operating-point/loss sandbox | loaded terminal voltage、power flow、loss aggregation | high | addresses Hosseini loaded voltage/efficiency and Parviainen efficiency |
| P2 | mutual-inductance matrix and single-sided refinements | 0 current rows | 0 | 0 | future extended inductance/topology modules | matrix inductance and one-gap return path | high | future coverage, not justified by current blockers |

## Blocked Row Mapping

- Topology proposal affects Abdelli E/T and all five Parviainen blocked rows: 7 rows.
- Radius-dependent/native back-EMF stack affects Abdelli E、Price E、Parviainen E、Hosseini two voltage rows: 5 rows, but loaded terminal voltage additionally needs a generator circuit.
- Optional Ld/Lq affects Parviainen Ld/Lq and Hosseini Xsd/Xsq: 4 rows.
- Torque boundary affects Abdelli torque and Price shaft torque: 2 rows.
- Loss/resistance boundary affects Parviainen R/efficiency and Hosseini efficiency: 3 rows.

这些是 overlapping candidate counts，不是 `14 -> 0` 的承诺。Price 仍缺 Br/pole data，Hosseini 仍缺 turns/connection，Abdelli outputs 仍主要是 plots；model upgrade 不能修复这些 source-data limitations。

## Production Files Eventually Affected

只有未来经过 formula-change approval 后，advanced capability 才可能涉及：

- `motor_calculator/motor_core/models.py`：optional topology/geometry/winding/extended-result types。
- `motor_calculator/motor_core/calculations.py`：magnetic circuit、back-EMF、R/L、loss/torque boundary；本阶段绝不修改。
- `motor_calculator/motor_core/electrical_semantics.py`：native waveform quantity semantics。
- `motor_calculator/motor_core/validation.py`：advanced input validation。
- `motor_calculator/motor_core/units.py`：仅显式 advanced adapter；不得改变 legacy mapping。
- GUI files：只有未来独立批准 opt-in UI 时才可能增加入口；默认 GUI 永远继续 legacy path。

## Backward Compatibility Plan

1. 保持 `MotorAnalysisInput`、`AnalysisResult` 和现有 engine API 不变。
2. Phase 7E 在 validation/sandbox namespace 新增 `AdvancedAFPMRequest` 和 extended dataclasses，不加入 production imports。
3. advanced request 必须显式 opt-in；禁止根据字段存在自动切换模式。
4. advanced result 与 `AnalysisResult` 分离，不覆盖同名 legacy fields。
5. source adapter 只接受 `source_provided`/`safely_derived`，缺字段返回 structured blocker，不回退 default。
6. 未来若需要 production integration，采用 additive optional adapter；旧 GUI/legacy params 继续构造原 `MotorAnalysisInput`。
7. 每个后续 physics step 都必须保留 3 个 legacy baseline cases、现有 formula isolation tests 和 frozen SHA-256。

`legacy_mode + advanced_afpm_mode` 不应表现为一个会自动分支的 boolean。建议使用不同 request/result types 和不同 runner，降低误路由风险。

## Risk Gate

- Schema-only sandbox：低风险，可进入 Phase 7E。
- Sandbox physics：中高风险，必须有独立 analytical tests 与 external-case completeness tests。
- Production formula routing：高风险，需逐公式审批、数值影响报告和 parallel-output period。
- Default switch/calibration：当前禁止且证据不足。
