# Phase 7F AFPM 绕组来源恢复记录

## 边界

本轮只把来源中明确给出或可由整数关系安全推导的绕组网络信息写入 `validation_data/source_recovery/phase7f_winding_recovery.json`。原 Phase 7C 重建记录、production 参数和 legacy baseline 均未修改。`NdFeB` 材料名称不等价于数值 `Br` 或磁体相对磁导率，未知量不使用通用默认值替代。

状态语义：`source_provided` 为来源直接给出；`safely_derived` 为公式和输入均明确的推导；`ambiguous` 为存在多种合理解释；`unavailable` 为来源未报告。

## Price 2009

来源：[A Low Speed Generator for Energy Harvesting Applications](https://ijme.us/issues/spring2009/ijme_sp_09.pdf)，文章第 60--65 页。

- 直接恢复：单定子/双转子、每线圈 36 串联匝、每相 3 个串联线圈、Y 接、短距集中绕组、内外磁体宽度均为 `0.0254 m`。
- 安全推导：`9 coils / 3 coils per group * 4 poles = 12 poles`，因此 `pole_pairs = 6`；每相总计 3 个线圈且全部串联，因此并联支路数为 1，有效串联匝数为 `36 * 3 = 108 turn/phase`。
- 安全恢复的径向轮廓：用来源表格的内外半径、磁体宽度及 12 极计算两个半径端点的磁体覆盖率；这不是常数磁弧比拟合。
- 仍未知：数值 `Br`、磁体相对磁导率、`kw`、`kp`、`kd`。来源只写明 NdFeB，未给牌号或数值。

## Parviainen 2005

来源：[Design of Axial-Flux Permanent-Magnet Low-Speed Machines and Performance Comparison Between Radial-Flux and Axial-Flux Machines](https://urn.fi/URN:ISBN:952-214-030-9)，论文第 46--47、73--75 页。

- 直接恢复：每线圈 140 匝、双定子/单转子、默认两定子并联、星形连接、传统双层叠绕组。
- 安全推导：每定子每相 840 串联匝除以每线圈 140 匝，得到每相 6 个串联线圈、1 条定子内并联支路。
- 仍未知：来源的绕组因数公式需要精确线圈跨度，但原型参数表未提供足够数据；因此不生成 `kw`。

## Hosseini 2008

来源：[Design, Prototyping, and Analysis of a Low Cost Axial-Flux Coreless Permanent-Magnet Generator](https://dl.icdst.org/pdfs/files3/4c8ab132b2439e719f68989a63c59837.pdf)，文章第 191--203 页。

- 直接恢复：单定子/双转子、单层梯形三相绕组。
- 安全推导：18 个线圈除以 3 相，得到每相 6 个线圈。
- 保持歧义：来源给出的是每线圈 50 根导体，不是匝数；相内串并联、Y/Delta 和数值绕组因数均未报告。

## Abdelli 2026

来源：[STET 2026 AFPM article](https://doi.org/10.2516/stet/2026004)，文章第 2--6 页。

- 直接恢复：制造原型每线圈 48 匝、3 个并联线圈分组、双定子/单转子、18 槽齿绕集中绕组。
- 保持歧义：设计值与制造值不同，来源不足以确定每相每支路串联线圈数。
- 仍未知：两定子电气串联/并联关系、Y/Delta、`kw` 和可直接比较的标量 back-EMF。

## 恢复结论

Price 的极对数、径向磁体覆盖轮廓和完整相绕组串联匝数已恢复；Parviainen 的定子内支路与定子间并联语义已显式化。Hosseini 与 Abdelli 的关键匝数/连接歧义仍不能安全消除。所有恢复值均保留字段级 provenance，且没有使用 production default。
