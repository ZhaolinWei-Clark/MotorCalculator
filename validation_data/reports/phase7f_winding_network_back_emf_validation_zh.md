# Phase 7F AFPM 绕组网络 Back-EMF 验证

## Sandbox Boundary

本报告只评估 `motor_calculator/advanced_afpm/` sandbox。没有修改 production 公式、默认参数、GUI 或 legacy baseline；没有拟合绕组因数、磁体参数或 correction factor。只有 `DIRECT` 或批准的 `SAFE_TRANSFORM` 行才允许输出 predicted/error。

径向积分使用 Phase 7E 推荐的确定性切片数 `N = 100`。

## Winding-Network Reconstruction

| source | topology | explicit network | effective series turns/phase | stator aggregation | phase connection | winding factor provenance |
|---|---|---|---:|---|---|---|
| Price 2009 | SSDR | 36 turns/coil; 3 coils/phase; 3 series; 1 branch; concentrated | 108 | one stator, no aggregation | Y | unavailable; short-pitch geometry is not converted to `kw` |
| Parviainen 2005 | DSSR | 140 turns/coil; 6 coils/phase/stator; 6 series; 1 branch; distributed | 840 per stator | 2 identical stators in parallel; terminal EMF not doubled | Y | ambiguous; exact coil span required by source equation |
| Hosseini 2008 | SSDR | 6 coils/phase recovered; 50 conductors/coil not treated as turns | BLOCKED | one stator, no aggregation | unknown | unavailable; source symbol has no prototype value |
| Abdelli 2026 | DSSR | 48 turns/coil; 3 parallel grouping; series count unknown; concentrated | BLOCKED | 2 stators, connection unknown | unknown | unavailable; no generic concentrated-winding value used |

串联线圈增加有效匝数；并联支路不增加串联匝数或端电压。相同双定子串联时相电势相加，并联时端电势保持单定子值，独立定子不形成一个自动合并的端电压。

## External Re-evaluation

| source | N | radial-slice prediction | external reference | comparability | error | remaining blockers |
|---|---:|---:|---:|---|---:|---|
| Price 2009 | 100 | BLOCKED | 37 V phase peak, measured sinusoidal | BLOCKED; future SAFE_TRANSFORM candidate | N/A | `Br`; magnet relative permeability; `kw` |
| Parviainen 2005 | 100 | BLOCKED | 211 V phase RMS, flattened waveform | BLOCKED | N/A | effective nonmagnetic gap; magnet coverage; magnet relative permeability; `kw`; waveform mismatch |
| Hosseini 2008 | 100 | BLOCKED | 160 V phase peak-to-peak, harmonic | BLOCKED | N/A | magnet coverage; effective series turns; `kw`; waveform mismatch |
| Abdelli 2026 | 100 | BLOCKED | scalar unavailable, graph only | BLOCKED | N/A | effective gap; coverage; `Br`; permeability; effective turns; `kw`; stator connection; scalar reference |

## Provenance

- Price 2009: [official issue PDF](https://ijme.us/issues/spring2009/ijme_sp_09.pdf), winding paragraph/Table 1/Figure 12, article pp. 63--65.
- Parviainen 2005: [LUT dissertation record](https://urn.fi/URN:ISBN:952-214-030-9), winding-factor equation and prototype tables, pp. 46--47 and 73--77.
- Hosseini 2008: [article PDF](https://dl.icdst.org/pdfs/files3/4c8ab132b2439e719f68989a63c59837.pdf), winding description and Tables 1/3, pp. 192--201.
- Abdelli 2026: [DOI record](https://doi.org/10.2516/stet/2026004), topology/design/prototype sections and Figures 10--11.

字段级页面、位置、推导和状态保存在 `validation_data/source_recovery/phase7f_winding_recovery.json`。

## Result

- `DIRECT = 0`
- `SAFE_TRANSFORM = 0`
- `APPROXIMATE = 0`
- `BLOCKED = 4`
- 新增可比较外部行：`0`
- 第一条真实 AFPM back-EMF error：尚不可合法计算

Phase 7F 改进了物理表示并减少了 Price 的输入歧义，但没有用假设填补材料或绕组因数。结果保持 `BLOCKED`，而不是输出看似更好的数字。
