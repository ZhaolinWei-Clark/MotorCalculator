# Phase 7B.1 外部精度结果解释

## 四个证据层次

1. Internal mathematical consistency：独立公式或 fixture 与实现一致，只证明代数、单位或 solver 行为，不是外部 accuracy evidence。
2. External metric validation：一个明确 metric 在一个明确 operating point 与外部测量/规格直接比较；结论必须限定到该 metric 和 operating point。
3. Full-machine validation：多个关键 metric families、多个 operating points 和匹配 topology 共同支持整机判断；Phase 7B.1 尚未达到。
4. Calibration：使用外部数据选择或拟合模型参数；本阶段禁止，也没有发生。

## 可以声称什么

Parviainen 原型表 3.1 同时给出 5 kW、300 rpm 和 159 Nm。项目既有 strict-SI helper 计算 `T=P/(2*pi*n/60)=159.154943091895 Nm`，相对绝对误差约 `0.097448%`。因此可以声称：公开 AFPM 原型额定点支持该轴端功率-转速-转矩 SI 关系，且在 Phase 7A torque tolerance 下为 PASS。

## 不能声称什么

该关系不使用 magnet geometry、air gap、Br、turns、winding factor、current、Ke/Kt 或 loss model。因此不能由此声称：

- AFPM magnetic circuit 已验证；
- back-EMF、Ke、Kt 或 torque-current accuracy 已验证；
- production default 已通过实验验证；
- 参数已经校准或效率已经优化。

Price 和 Hosseini 虽然 topology 更接近默认 SSDR，但缺少生产计算所需的完整语义。Parviainen 和 Abdelli 的电磁数据较完整，但都是 single-rotor/double-stator。Bumby 数值全文尚不可复现访问。这些是 blocker，不是 model FAIL。

## 误差与 blocker 的解释

- `PASS=1`：只对应 strict-SI rated shaft torque identity。
- `WARNING=0`、`FAIL=0`：不是因为电磁模型已准确，而是目前没有第二个合法 prediction/reference pair。
- `BLOCKED=14`：来源有值或图，但缺少安全模型映射。
- `UNAVAILABLE=6`：来源没有数值或只取得摘要；未知值保持 `None`。

## 后续建议

Phase 7C 可继续做证据获取与语义桥审批，但不应开始 calibration。最有价值的新证据是同一 SSDR 样机在明确 Br 温度、series turns/phase、connection、winding factor/leakage 定义下的 tabulated no-load phase waveform/RMS/peak，以及匹配 operating point 的 torque-current 数据。
