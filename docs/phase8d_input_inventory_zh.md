# Phase 8D 输入清单

## 审计边界

本清单覆盖当前 `.motorproj` schema 和 legacy GUI 的全部 41 个输入。所有字段在当前 schema 中均为必填；“模式”仅改变 GUI 可见性，不改变 schema、默认值或计算链。`B/A` 表示 Basic 和 Advanced 均可见，`A` 表示仅 Advanced 显示。软提示复用现有 production validator，不能替代详细设计审查。

## 完整清单

| 字段 | GUI 标签 | 模型含义 | 规范单位 / 默认值 | 模型族 | 当前校验 | 控件 | 模式 / preset | Tooltip / 易错点 |
|---|---|---|---|---|---|---|---|---|
| `V_dc` | 直流母线电压 | 静态工作点母线电压 | V / 48 | 共用 | 数值、正值 | slider 候选 + 精确输入 | B/A；工作点 | 不是相电压；当前 quick panel 未设滑块 |
| `P_rated` | 额定输出功率 | 额定轴输出功率 | W / 800 | 共用 | 数值、正值 | `TEXT_NUMERIC` | B/A；工作点 | 与输入电功率不同 |
| `n_rated` | 额定转速 | 机械转速 | rpm / 2500 | 共用 | 数值、正值 | slider + 精确输入 | B/A；工作点 | 不是电角速度 |
| `Temp_coil` | 绕组温度 | 电阻计算温度 | degC / 80 | 共用 | 数值；软异常提示 | slider 候选 + 精确输入 | B/A；工作点 | 非环境温度 |
| `D_out` | 电机外径 | 有效电机外径 | mm / 140 | AFPM | 必须大于内径 | slider 候选 + 精确输入 | B/A；设计示例 | 外径/半径不可混用 |
| `D_in` | 电机内径 | 有效电机内径 | mm / 70 | AFPM | 必须小于外径 | slider 候选 + 精确输入 | B/A；设计示例 | 内径/半径不可混用 |
| `g_side` | 机械气隙（单侧） | 单侧机械气隙 | mm / 1 | AFPM SSDR | 正值；大于 5 mm 为软提示 | slider + 精确输入 | B/A；设计示例 | 不应输入双气隙总和 |
| `D_stator_out` | 定子外径 | 定子有效外径 | mm / 138 | AFPM | 几何关系 | `TEXT_NUMERIC` | A | 应与电机外径一致解释 |
| `D_stator_in` | 定子内径 | 定子有效内径 | mm / 72 | AFPM | 几何关系 | `TEXT_NUMERIC` | A | 应与定子外径配套 |
| `h_stator` | 定子叠厚/厚度 | 轴向定子厚度 | mm / 20 | AFPM | 正值 | `TEXT_NUMERIC` | A | 无铁芯/有铁芯语义不同 |
| `h_coil` | 定子盘厚度 | 线圈轴向厚度 | mm / 5 | AFPM | 正值 | `TEXT_NUMERIC` | A | 不是单根导线直径 |
| `h_yoke` | 定子轭部高度 | legacy 轭部尺寸 | mm / 5 | AFPM | 正值 | `TEXT_NUMERIC` | A | 对无铁芯路径意义有限 |
| `slots` | 槽数 | 总定子槽数 | count / 24 | AFPM | 正整数 | `SPINBOX_INTEGER` 候选 | A；拓扑 | 不等于每相槽数 |
| `slot_type` | 槽形类型 | 有限槽形枚举 | enum / 无槽 | AFPM | 已知枚举 | `DROPDOWN_ENUM` | A；拓扑 | 避免拼写型自由文本 |
| `h_slot` | 槽深 | 槽几何深度 | mm / 15 | AFPM slotted | 正值 | `TEXT_NUMERIC` | A | 无槽时仍保存但可能不适用 |
| `w_slot_top` | 槽口宽度 | 槽上部宽度 | mm / 8 | AFPM slotted | 正值 | `TEXT_NUMERIC` | A | 与槽开口宽度不同 |
| `w_slot_bottom` | 槽底宽度 | 槽底部宽度 | mm / 6 | AFPM slotted | 正值 | `TEXT_NUMERIC` | A | 与槽顶宽度不同 |
| `h_slot_opening` | 槽口高度 | 槽口几何高度 | mm / 1 | AFPM slotted | 正值 | `TEXT_NUMERIC` | A | 仅槽形路径使用 |
| `w_slot_opening` | 槽口开口宽度 | 槽口实际开口宽度 | mm / 3 | AFPM slotted | 正值 | `TEXT_NUMERIC` | A | 不等于 `w_slot_top` |
| `h_wedge` | 槽楔高度 | 槽楔几何高度 | mm / 2 | AFPM slotted | 正值 | `TEXT_NUMERIC` | A | 无槽时不适用 |
| `h_mag` | 永磁体厚度 | 充磁方向厚度 | mm / 5 | AFPM | 正值 | slider 候选 + 精确输入 | B/A；设计示例 | 必须按现有充磁方向语义输入 |
| `w_magnet` | 永磁体宽度 | 周向磁体宽度 | mm / 20 | AFPM | 正值 | `TEXT_NUMERIC` | A | 周向，不是径向长度 |
| `L_magnet` | 永磁体长度 | 径向磁体跨度 | mm / 30 | AFPM | 正值 | `TEXT_NUMERIC` | A | 径向，不是周向宽度 |
| `magnet_type` | 永磁体类型 | 表贴/内置枚举 | enum / 表贴式 | 共用 | 已知枚举 | `DROPDOWN_ENUM` | B/A；拓扑 | 仅选择既有模型分支 |
| `magnetization` | 充磁方式 | 充磁方向/阵列枚举 | enum / 径向充磁 | 共用 | 已知枚举 | `DROPDOWN_ENUM` | A；拓扑 | 不应以自由文本输入 |
| `p` | 极对数 | 机械到电角度倍数 | pole pairs / 8 | 共用 | 正整数 | spinbox + 精确输入 | B/A；设计示例 | 总极数为 `2*p` |
| `magnet_grade` | 永磁体牌号 | 磁材名义牌号 | enum / N42 | 共用 | 支持枚举或 Custom | preset dropdown | B/A；磁材 | 选择 preset 前必须预览 |
| `Br` | 剩磁 | 名义剩余磁通密度 | T / 1.28 | 共用 | 数值、正值 | `TEXT_NUMERIC` | B/A；磁材 | 强依赖厂家与温度，可覆盖 preset |
| `alpha_p` | 极弧系数 | 磁体极弧覆盖比例 | ratio / 0.70 | AFPM | ratio 校验 | slider 候选 + 精确输入 | A；设计示例 | 不是机械角度 |
| `sigma_m` | 漏磁系数 | legacy 经验磁路系数 | ratio / 1.15 | AFPM legacy | 数值、正值 | `ADVANCED_CUSTOM` | A | 不是通用材料常数 |
| `mu_r_mag` | 永磁体相对磁导率 | 回线相对磁导率 | ratio / 1.05 | 共用 | 数值、正值 | `TEXT_NUMERIC` | A；磁材可选 | 数据表定义需一致 |
| `N_ph_turns` | 每相匝数 | 有效每相串联匝数 | turns/phase / 50 | 共用 | 正整数 | `SPINBOX_INTEGER` 候选 | B/A；设计示例 | 不是每线圈匝数 |
| `d_wire` | 导线直径 | legacy 绕组导线直径 | mm / 0.9 | 共用 | 正值 | slider 候选 + 精确输入 | B/A | 裸线/含绝缘语义需核对 |
| `n_parallel` | 并联根数 | 绕组并联路径数 | count / 2 | 共用 | 正整数 | `SPINBOX_INTEGER` 候选 | B/A | 不应输入相数 |
| `k_w` | 绕组系数 | 节距与分布综合系数 | ratio / 0.93 | 共用 | 模型 validator；低值软提示 | slider + 精确输入 | B/A；设计示例 | 无依据时不要假定 1.0 |
| `fill_limit` | 填充系数限制 | legacy 允许填充比例 | ratio / 0.65 | 共用 | ratio 校验 | slider 候选 + 精确输入 | A | 是上限输入，不是实测填充率 |
| `waveform` | 反电势波形 | PMSM/BLDC 电量语义开关 | enum / 正弦波 | PMSM/BLDC | 已知枚举 | dropdown/radio | B/A；拓扑 | 影响 RMS/peak、phase/line 解释 |
| `k_cogging` | 齿槽转矩系数 | legacy 经验系数 | ratio / 0.02 | legacy | 数值 | `ADVANCED_CUSTOM` | A | 不代表实测齿槽转矩 |
| `k_ripple_6` | 6 次谐波转矩系数 | legacy 经验系数 | ratio / 0.05 | legacy | 数值 | `ADVANCED_CUSTOM` | A | 非通用谐波模型参数 |
| `k_ripple_12` | 12 次谐波转矩系数 | legacy 经验系数 | ratio / 0.02 | legacy | 数值 | `ADVANCED_CUSTOM` | A | 非通用谐波模型参数 |
| `coreless` | 无铁芯定子设计 | 选择既有无铁芯分支 | boolean / true | AFPM | 布尔 | `TOGGLE_BOOLEAN` | B/A；拓扑 | 不会自动重构其他几何 |

## 主要歧义与风险

- 当前 GUI 同时存在 overall、stator 和 magnet 几何，最易发生直径/半径、周向/径向和单侧/双侧气隙混用。
- `N_ph_turns` 是有效每相串联匝数；来源若仅给每线圈匝数，不能直接填入。
- `waveform` 实际承担 PMSM/BLDC 电气语义选择；它不是仅用于绘图。
- `Br`、`sigma_m`、`k_cogging`、`k_ripple_*` 的证据性质不同，不应都理解成材料常数。
- DSSR、显式 Y/Delta、显式 `Ld/Lq` 等当前 production schema 无法完整表达，因此 preset 不得伪造这些字段。

## 实现取舍

Phase 8D 没有把所有字段都改成滑块。首批 quick-adjust 仅覆盖气隙、转速和绕组系数，并保留精确文本框；极对数使用 spinbox，波形和 magnet grade 使用枚举选择。其它已分类为 slider 候选的字段暂保留精确输入，避免在缺少可靠显示范围时施加误导。
