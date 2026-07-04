# 教材与参考书候选清单

更新时间：2026-07-04

## 1. 说明

本清单服务于后续公式审阅、术语澄清、worked example 提取和 validation case 设计。

本清单不提供盗版下载链接。

若后续确需使用书中 worked example，请优先通过以下方式获取：

- 用户已有 PDF
- 图书馆电子资源
- 正版纸书
- Google Books / WorldCat / 出版社预览页

## 2. 候选总表

| 书名 | relevance to this project | likely useful chapters | helps PMSM | helps BLDC | helps AFPM | helps loss model | helps thermal model | may include worked examples | user should try to locate PDF / library copy | priority score |
|---|---|---|---|---|---|---|---|---|---|---:|
| *Design of Rotating Electrical Machines* — Pyrhönen, Jokinen, Hrabovcová | 电机设计总参考，适合统一术语和设计变量 | machine sizing, magnetic loading, winding, losses, inductance | 是 | 间接 | 间接 | 是 | 部分 | 是 | 是 | 5 |
| *Brushless Permanent-Magnet Motor Design* — Hanselman | BLDC / PM 电机常数与设计语义很相关 | PM sizing, back EMF, torque constant, commutation | 是 | 是 | 间接 | 部分 | 否 | 是 | 是 | 5 |
| *Design of Brushless Permanent-Magnet Machines* — Hendershot & Miller | 经典 PM machine 设计与实例书 | sizing, winding, magnets, losses, performance maps | 是 | 是 | 间接 | 是 | 部分 | 是 | 是 | 5 |
| *Permanent Magnet Synchronous and Brushless DC Motor Drives* — Ramu Krishnan | PMSM/BLDC 语义、控制边界、Ke/Kt 背景 | PMSM/BLDC models, control, back EMF forms, torque production | 是 | 是 | 间接 | 部分 | 否 | 是 | 是 | 5 |
| *Electric Motor Drives: Modeling, Analysis, and Control* — Ramu Krishnan | 控制与系统层理解强，有助区分控制数据集与电磁 benchmark | drive models, control loops, parameter interpretation | 是 | 是 | 间接 | 部分 | 否 | 部分 | 是 | 4 |
| *Axial Flux Permanent Magnet Brushless Machines* — Gieras, Wang, Kamper | 与 AFPM 目标最贴近 | AFPM topologies, sizing, losses, comparative analysis | 是 | 是 | 是 | 是 | 部分 | 是 | 是 | 5 |
| *The Induction Machines Design Handbook* — Boldea and Nasar | 可用于对照 IM benchmark，但不是主线 | induction machine sizing, losses, equivalent circuits | 否 | 否 | 否 | 是 | 部分 | 是 | 可选 | 3 |
| *Permanent Magnet Motor Technology: Design and Applications* — Jacek F. Gieras | PM 电机综合参考，补足设计与应用背景 | PM materials, design, losses, applications | 是 | 是 | 部分 | 是 | 部分 | 部分 | 是 | 4 |
| *Analysis of Electric Machinery and Drive Systems* — Paul C. Krause et al. | 若后续需要更严格的 machine equations 对照非常有用 | generalized machine theory, dq models, induction/PM equations | 是 | 间接 | 否 | 部分 | 否 | 部分 | 是 | 4 |

## 3. 分项说明

### 3.1 Design of Rotating Electrical Machines

- `relevance to this project`: 适合做统一设计语言底座，特别适合澄清 geometry、winding、loss 和 machine constant 相关术语
- `likely useful chapters`: winding design、magnetic loading、electric loading、loss calculation、inductance estimation、thermal basics
- `whether it helps PMSM`: 是
- `whether it helps BLDC`: 间接帮助，尤其在绕组、磁路和 loss 侧
- `whether it helps AFPM`: 间接，主要用于通用 rotating machine design 口径
- `whether it helps loss model`: 是
- `whether it helps thermal model`: 部分
- `whether it may include worked examples`: 是
- `whether user should try to locate PDF / library copy`: 是
- `priority score from 1 to 5`: `5`

### 3.2 Brushless Permanent-Magnet Motor Design

- `relevance to this project`: 对 BLDC / PMSM 语义和 PM sizing 很直接
- `likely useful chapters`: back EMF waveform、torque constant、magnet design、commutation and performance
- `whether it helps PMSM`: 是
- `whether it helps BLDC`: 是
- `whether it helps AFPM`: 间接
- `whether it helps loss model`: 部分
- `whether it helps thermal model`: 否
- `whether it may include worked examples`: 是
- `whether user should try to locate PDF / library copy`: 是
- `priority score from 1 to 5`: `5`

### 3.3 Design of Brushless Permanent-Magnet Machines

- `relevance to this project`: 很适合提取 PM 机设计 worked examples，补足 Ke/Kt 与 performance interpretation
- `likely useful chapters`: magnetic circuit, winding, losses, performance prediction, examples
- `whether it helps PMSM`: 是
- `whether it helps BLDC`: 是
- `whether it helps AFPM`: 间接
- `whether it helps loss model`: 是
- `whether it helps thermal model`: 部分
- `whether it may include worked examples`: 是
- `whether user should try to locate PDF / library copy`: 是
- `priority score from 1 to 5`: `5`

### 3.4 Permanent Magnet Synchronous and Brushless DC Motor Drives

- `relevance to this project`: 非常适合继续澄清 PMSM 与 BLDC 的语义边界
- `likely useful chapters`: PMSM/BLDC modeling, torque production, control assumptions, machine constants
- `whether it helps PMSM`: 是
- `whether it helps BLDC`: 是
- `whether it helps AFPM`: 间接
- `whether it helps loss model`: 部分
- `whether it helps thermal model`: 否
- `whether it may include worked examples`: 是
- `whether user should try to locate PDF / library copy`: 是
- `priority score from 1 to 5`: `5`

### 3.5 Electric Motor Drives: Modeling, Analysis, and Control

- `relevance to this project`: 更偏 drive / control，适合判断某些大学数据集到底是不是“控制数据”而非“电磁 benchmark”
- `likely useful chapters`: drive modeling, state equations, control interpretation, thermal estimation context
- `whether it helps PMSM`: 是
- `whether it helps BLDC`: 是
- `whether it helps AFPM`: 间接
- `whether it helps loss model`: 部分
- `whether it helps thermal model`: 否
- `whether it may include worked examples`: 部分
- `whether user should try to locate PDF / library copy`: 是
- `priority score from 1 to 5`: `4`

### 3.6 Axial Flux Permanent Magnet Brushless Machines

- `relevance to this project`: 与 AFPM 目标最直接相关的书之一
- `likely useful chapters`: AFPM topologies, sizing, magnetic circuit, losses, cooling considerations, comparative examples
- `whether it helps PMSM`: 是
- `whether it helps BLDC`: 是
- `whether it helps AFPM`: 是
- `whether it helps loss model`: 是
- `whether it helps thermal model`: 部分
- `whether it may include worked examples`: 是
- `whether user should try to locate PDF / library copy`: 是
- `priority score from 1 to 5`: `5`

### 3.7 The Induction Machines Design Handbook

- `relevance to this project`: 不是主线，但若未来要把 CREATOR IM data 用作 schema 对照，它会有帮助
- `likely useful chapters`: equivalent circuits, induction machine losses, thermal and design tradeoffs
- `whether it helps PMSM`: 否
- `whether it helps BLDC`: 否
- `whether it helps AFPM`: 否
- `whether it helps loss model`: 是
- `whether it helps thermal model`: 部分
- `whether it may include worked examples`: 是
- `whether user should try to locate PDF / library copy`: 可选
- `priority score from 1 to 5`: `3`

### 3.8 Permanent Magnet Motor Technology: Design and Applications

- `relevance to this project`: 适合作 PM machine 综合补充参考
- `likely useful chapters`: PM materials, machine design, applications, loss mechanisms
- `whether it helps PMSM`: 是
- `whether it helps BLDC`: 是
- `whether it helps AFPM`: 部分
- `whether it helps loss model`: 是
- `whether it helps thermal model`: 部分
- `whether it may include worked examples`: 部分
- `whether user should try to locate PDF / library copy`: 是
- `priority score from 1 to 5`: `4`

### 3.9 Analysis of Electric Machinery and Drive Systems

- `relevance to this project`: 若后续要对等效模型、dq 模型和 machine equations 做更严格复核，它会很有帮助
- `likely useful chapters`: generalized machine equations, induction/PM machine models, dynamic states
- `whether it helps PMSM`: 是
- `whether it helps BLDC`: 间接
- `whether it helps AFPM`: 否
- `whether it helps loss model`: 部分
- `whether it helps thermal model`: 否
- `whether it may include worked examples`: 部分
- `whether user should try to locate PDF / library copy`: 是
- `priority score from 1 to 5`: `4`

## 4. 当前建议的补源顺序

### 第一优先级

- *Axial Flux Permanent Magnet Brushless Machines*
- *Brushless Permanent-Magnet Motor Design*
- *Design of Brushless Permanent-Magnet Machines*
- *Design of Rotating Electrical Machines*

原因：

- 与 AFPM / PMSM / BLDC 主线最贴近
- 最有机会提供可解释 Ke/Kt、loss、geometry、winding 的 worked examples

### 第二优先级

- *Permanent Magnet Synchronous and Brushless DC Motor Drives*
- *Electric Motor Drives: Modeling, Analysis, and Control*

原因：

- 更适合帮助判断控制数据集边界
- 也适合继续澄清 PMSM vs BLDC 语义

### 第三优先级

- *The Induction Machines Design Handbook*
- *Analysis of Electric Machinery and Drive Systems*

原因：

- 偏辅助
- 对当前 AFPM PMSM/BLDC 主线不是第一批必需
