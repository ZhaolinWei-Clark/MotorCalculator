# Parviainen 2005 AFPM Dissertation 来源提取记录

## 来源

- LUT 正式记录：[Design of axial-flux permanent-magnet low-speed machines and performance comparison between radial-flux and axial-flux machines](https://lutpub.lut.fi/handle/10024/31185)
- 作者：Asko Parviainen；Lappeenranta University of Technology doctoral dissertation, 2005。
- 正式永久标识：`URN:ISBN:952-214-030-9`；全文已检查。

## 拓扑与额定点

- one-rotor/two-stators AFPM；两个 stators 默认 electrically in parallel，和项目默认 dual-rotor/single-stator 不同。
- Table 3.1（p.73）：5 kW output、300 rpm、159 Nm、230 V rated phase voltage、211 V PM-induced phase voltage、8.4 A phase current、6 pole pairs、36 slots。
- 同表：magnet 4 mm、Br 1.05 T at 100 C、air gap per stator 1.5 mm、OD 328 mm、ID 197 mm、840 series turns/phase。
- p.74：conventional double-layer lap winding，star connection；两 stators 的电气并联必须在任何 R/L/voltage 映射中显式处理。

## 测量结果

- Table 3.3（p.77）：`Ld=0.055 H`、`Lq=0.060 H`（inverter estimate）、phase DC resistance `3.7 ohm`、PM-induced phase RMS voltage `211 V`。
- Figure 3.6（p.78）：PM 温度约 95 C 时 measured PM-induced voltage waveform。
- p.79：natural-cooling steady-state measured efficiency 89.2%，calculated 89.6%。

## 可比性结论

5 kW / 300 rpm / 159 Nm 在同一表内，单位和 quantity scope 明确，可用既有 strict-SI `T=P/omega` 做 `DIRECT` 轴端一致性检查。其余 E/R/L/efficiency 因 topology、parallel-stator、dq/scalar 或 loss/cooling 语义保持 `BLOCKED`。唯一 PASS 不得描述为 AFPM electromagnetic model validation。
