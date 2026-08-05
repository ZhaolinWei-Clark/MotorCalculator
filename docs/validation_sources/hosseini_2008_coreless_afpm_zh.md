# Hosseini 2008 Coreless AFPM Generator 来源提取记录

## 来源

- 公开全文：[Design, Prototyping and Analysis of a Low-Cost Disk Permanent Magnet Generator with Rectangular Flat-Shaped Magnets](https://dl.icdst.org/pdfs/files3/4c8ab132b2439e719f68989a63c59837.pdf)
- Iranian Journal of Science & Technology, Transaction B, 32(B3), 191-203, 2008。

## 拓扑与参数

- dual-rotor/single-coreless-stator AFPM，24 poles / 12 pole pairs，18 single-layer coils。
- Table 1（p.197）：25 x 10 x 3 mm magnets、Br 1.2 T、relative permeability 1.045、3000 rpm、rotor thickness 10 mm、air gap each side 1 mm、35/60 mm radii、0.4 mm wire、50 conductors/coil。
- winding connection、series turns per phase、production leakage/winding-factor semantics 未明确。

## 外部输出

- Table 3（p.201）明确区分：no-load phase voltage peak-to-peak、full-load phase voltage peak-to-peak、loaded output waveform fundamental peak-to-peak。
- 3000 rpm：上述三列分别为 160 V、120 V、102 V。论文同时说明 output waveform has harmonics。
- Figure 14 / Table 4（pp.201-202）：3000 rpm measured efficiency 78.1%，nominal phase voltage 40 V、phase current 3.6 A、frequency 300 Hz、`Xsd=Xsq=2.1 ohm`。

## 可比性结论

该来源 topology 最接近项目默认 AFPM，但 peak-to-peak harmonic/load voltage 不能擅自转换为 production back-EMF RMS/peak；`Xsd/Xsq` 也不能未经批准转换为 scalar phase inductance。五个已提取输出均保留为 `BLOCKED`，没有推断缺失字段。
