# Abdelli 2026 AFPM 来源提取记录

## 来源

- 论文：[Design and manufacturing of axial flux permanent magnet machines for electric vehicle applications](https://doi.org/10.2516/stet/2026004)
- 期刊：Science and Technology for Energy Transition, 2026, 81:8。
- 许可：来源页面标示 CC BY 4.0。
- 访问状态：开放全文页面可读；本活动未把图像曲线人工数字化。

## 拓扑与参数

- double-stator/single-rotor，open-slot，18 slots / 12 poles，tooth coils。
- Table 1：最大 8000 rpm、350 Nm、140 kW，active OD 245 mm、ID 140 mm。
- Table 2（article p.3）：air gap 1 mm、magnet thickness 10 mm、magnet fill factor 0.67、3 parallel coils、初始 27 turns/winding、495 A RMS。
- 样机制造说明（article p.5）：实际 1.5 mm wire、42% fill、48 turns/coil；必须保留“设计值”和“样机值”的区别。

## 外部输出

- Figures 10/11（article p.6）：1000 rpm measured/FEA phase back-EMF；曲线有 even/odd harmonics，无权威数值表。
- Figure 12（article p.6）：1000 rpm、20-400 A torque sweep；文字声明测量与 FEA 最大偏差 3.5%，但没有逐点表。
- Table 4：6500 rpm、250 A FEA operating point；这是 FEA，不是测量。

## 可比性结论

back-EMF 和 torque 都为 `BLOCKED`：DSSR 与项目默认 SSDR 不同，且主要 measured outputs 只有图。R/L 为 `UNAVAILABLE`。不得以摘要中的偏差或读图值替代项目模型比较。
