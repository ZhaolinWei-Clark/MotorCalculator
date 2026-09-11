# v1.0.0-rc4 — FEA 案例摘要版本 v3

**状态**：`CASE_HASH_CONTRACT_RESTORED`
**分支**：`release/v1.0.0-rc4`
**应用版本**：`1.0.0-rc3` → `1.0.0-rc4`
**求解器**：FEMM 4.2.0.0，**未重跑**（见 §3，附字节级证明）

> **一句话结论**：rc3 → rc4 这一次纯粹的版本号变更，在旧定义下会让
> **全部** FEA 案例改写 `case_id`，而求解器看到的东西一个字节都没变。
> 这与 Phase 10C 修掉的是同一类缺陷，只是换了一个字段。
> **本次只动 provenance/哈希架构，不动物理，不做任何校准。**

---

## 1. 问题

`hashing.py` 自己写明的契约是：

> `case_id` 覆盖**求解器看得到的一切**：几何、材料、绕组、工作点、
> 网格策略、对称性与 schema 版本。

但 `application_version` 是 `FEAValidationCase` 的顶层字段，且不在
`CASE_HASH_EXCLUDED_FIELDS` 内，因此它进入了求解器可见摘要。

后果（实测，求解器可见输入零变化）：

```
NO_LOAD_BACK_EMF   53fce1b7...  ->  ef6469c3...
AVERAGE_TORQUE     2b4324ca...  ->  840f849d...
COGGING_TORQUE     5a32fe59...  ->  d757f294...
```

`53fce1b7...` 正是 README 中 **+7.15 %** 结论所依据的 Phase 10C 证据所携带的
`case_id`。若放任不管，rc4 打包出来的程序算出的 `case_id` 将与已发布证据
对不上，且**每一次版本号变更都会重演**。

## 2. 修复

只改 provenance/哈希架构：

- `application_version` 移出求解器可见摘要（加入 `CASE_HASH_EXCLUDED_FIELDS`）
- 它本来就已在解析指纹内（`compute_analytical_fingerprint` 硬编码覆盖），
  因为换一个构建版本**可能**合法地改变被比较的解析预测值
- 摘要定义变了，故版本提升为 **`rc4.fea.hash.v3`**，跨版本摘要不可比较

迁移结果：

```
                   v2 (rc3)          v3 (rc4)
AVERAGE_TORQUE     2b4324ca...  ->   357ad054...
COGGING_TORQUE     5a32fe59...  ->   6613e84c...
NO_LOAD_BACK_EMF   53fce1b7...  ->   73adc055...
```

此后版本号变更不再使任何 FEA 证据失效。

## 3. 为什么不需要重跑 FEMM

沿用 Phase 10C 的做法：直接比对 `generate_case_scripts()` 为 Phase 10C 自洽案例
发出的**全部 52 个位置**的 Lua 脚本。归一化两个与本次运行相关的记号
（临时工作目录路径、`case_id` 出处注释）之后：

```
rc3 归一化后 campaign SHA-256: 8fbb95e97f092f59c0384b2a34864b5c8f7e02e2251489352d76a466d9cb96e9
rc4 归一化后 campaign SHA-256: 8fbb95e97f092f59c0384b2a34864b5c8f7e02e2251489352d76a466d9cb96e9
52 个位置全部逐字节相同，差异脚本数 0
```

即几何、材料、绕组、相电流、网格策略、对称性与每一个求解位置均未改变。
**+7.15 % 的结论不受影响**，因为被求解的机器就是同一台。

## 4. 历史证据的处置

`validation_data/fea_results/phase10b_winding_factor_inconsistent/` 与
`phase10c_self_consistent/` **保持原样不动**。它们是 rc3 下真实完成的求解记录，
其中的 `case_id` 属于 `phase10c.fea.hash.v2` 定义，按既有政策
**跨摘要版本不可比较**——这一点与 v1 → v2 那次完全一致。

被重算的只有 `validation_data/fea_cases/phase10a_coreless_ssdr_reference_v1.json`：
它是**当前**的参考案例定义，不是历史求解记录。

## 5. 未触碰的内容

AFPM 磁路方程、漏磁系数、Carter 系数、Br、气隙、磁钢厚度、磁钢极弧、磁通公式、
FEMM 几何、FEMM 材料属性、FEA 网格策略、电压模型、优化器、损耗模型。
未为改善一致性而调整任何参数。
