# Phase 7F Back-EMF 阻塞项变化

## 计数口径

计数对象是四个外部来源进入径向切片 back-EMF 预测前的独立 gate 字段。Phase 7E 为 `20` 个，Phase 7F 为 `18` 个。语义上不可直接比较的非正弦波形另行统计，不与输入字段重复计数。

| 类别 | Phase 7E | Phase 7F | 变化 | 说明 |
|---|---:|---:|---:|---|
| turns / effective series turns | 2 | 2 | 0 | Hosseini、Abdelli 仍无法得到有效串联匝数 |
| winding factor | 4 | 4 | 0 | 四个来源均无可安全使用的标量 `kw` |
| connection | 1 | 1 | 0 | Abdelli 双定子连接仍未知；其他可用连接已显式化 |
| topology / pole count | 1 | 0 | -1 | Price 由线圈/磁极重复关系安全得到 12 极、6 极对 |
| geometry / coverage / effective gap | 6 | 5 | -1 | Price 的两点径向磁体覆盖轮廓已由尺寸恢复 |
| material | 5 | 5 | 0 | Price 的 NdFeB 名称不能替代 `Br`/相对磁导率 |
| external scalar reference | 1 | 1 | 0 | Abdelli 仍只有图形，无权威标量 |
| **输入 gate 总计** | **20** | **18** | **-2** | 仅移除可追溯且数学安全的两项 |

## 来源级变化

| 来源 | Phase 7E gate blockers | Phase 7F gate blockers | 已移除 | 关键剩余项 |
|---|---:|---:|---|---|
| Price 2009 | 5 | 3 | `pole_pairs`、径向磁体覆盖 | `Br`、磁体相对磁导率、`kw` |
| Parviainen 2005 | 4 | 4 | 无，但绕组/定子网络已从隐含语义变为显式 | 有效气隙、磁体覆盖、磁导率、`kw` |
| Hosseini 2008 | 3 | 3 | 无 | 磁体覆盖、有效串联匝数、`kw` |
| Abdelli 2026 | 8 | 8 | 无 | 气隙/覆盖、材料、有效匝数、`kw`、定子连接、标量 reference |

## 波形阻塞

- Parviainen 的 phase RMS 波形呈平顶特征，不能直接按正弦基波比较。
- Hosseini 报告 harmonic phase peak-to-peak，不能用 `sqrt(2)` 转换。
- Abdelli 只有图形且波形语义不完整。
- Price 的 measured sinusoidal phase peak 可在输入完整后执行 `phase RMS * sqrt(2)` 的 `SAFE_TRANSFORM`。

因此波形/谐波阻塞保持 `3 -> 3`；Price 不属于波形阻塞，而是材料和绕组因数阻塞。

## Phase 7G 决策

1. 新解锁外部 back-EMF 行：`0`。
2. 最接近可比较的来源：Price 2009，已从 5 个输入 blocker 降至 3 个。
3. 其余主要阻塞已清楚分为材料/几何参数、波形/谐波语义和来源访问/完整性；不再是 winding-network 软件表示能力本身。
4. Phase 7G 首选 **D. benchmark acquisition**，目标是取得带数值磁体参数和可审计 `kw`/线圈布局的 Price 补充资料或另一完整 AFPM benchmark。
5. 若无法取得更完整 benchmark，次选 **A. harmonic/non-sinusoidal back-EMF**，但只能用于 Parviainen/Hosseini 的语义能力建设，不能补齐其未知物理输入。

不推荐目前进入 correction-factor fitting 或 calibration，因为仍没有真实 AFPM electromagnetic error 行。
