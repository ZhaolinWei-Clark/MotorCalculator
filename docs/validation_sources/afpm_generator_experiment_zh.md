# Price 2009 AFPM Generator 实验来源提取记录

## 来源

- 论文：[Design and Testing of a Permanent Magnet Axial Flux Wind Power Generator](https://ijme.us/issues/spring2009/ijme_sp_09.pdf)
- 作者：Garrison F. Price, Todd D. Batzel, Mihai Comanescu, Bruce A. Muller。
- 期刊整期 PDF 中 article pp.59-66；全文可复现访问。

## 拓扑与绕组

- two rotor discs / one ironless stator，属于项目默认 topology class 的候选。
- 9 identical coils，36 turns/coil；每相 3 coils series；Y connection。
- short-pitch concentrated coils；NdFeB，但未给 numeric Br 或磁体 grade。
- Table 1（article p.63）：`lm=0.0127 m`、`lg=0.01905 m`、`ly=0.00635 m`、`ro=0.1524 m`、`ri=0.1016 m` 等 geometry。

## 外部输出

- article p.65 / issue PDF p.67：600 rpm no-load measured single-phase back-EMF peak = 37 V；论文自身 trapezoidal-coil analytical prediction = 35.5 V。
- 同页：500 rpm rated load current 下 measured average shaft torque = 12.6 Nm；论文自身 prediction = 12.8 Nm。

## 可比性结论

两个测量值都保留为 field-level evidence，但项目预测为 `BLOCKED`。原因是 numeric Br、leakage factor、winding factor 和 rated-current basis 不足，不能用论文自身预测冒充项目预测。R/L 未报告，标为 `UNAVAILABLE`。
