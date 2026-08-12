# Phase 8C：自动保存、崩溃恢复与项目兼容性基础

## 1. 阶段边界

Phase 8C 是本地软件可靠性层，不修改电机计算公式、AFPM 高级模型、动态/控制方程、验证数学或默认输出。恢复文件是非可信 JSON 数据，只做结构、版本和 SHA-256 完整性校验，不执行文件内容，也不使用 pickle、动态导入或 `eval`。

本阶段完全离线：无遥测、上传、云同步、账户或网络调用。恢复数据只写入 Windows 用户数据目录：

```text
%LOCALAPPDATA%\MotorCalculator\recovery\
```

`MOTOR_CALCULATOR_USER_DATA` 仅用于已有的可测试/可部署用户目录覆盖机制。

## 2. Autosave 与 Save 的区别

- **Save / Save As**：由用户明确触发，写入用户选择的 `.motorproj`，并保留一份 `.motorproj.bak`。
- **Autosave**：只保护 dirty 状态，写入 LocalAppData 下的独立恢复 JSON，绝不覆盖正式 `.motorproj`。
- 恢复快照不等同于正式保存；GUI 状态明确显示“Unsaved changes”或“Recovery snapshot”。

输入、项目说明、不确定性假设、关联验证记录 ID、项目 UUID、原路径、dirty 状态、应用/项目 schema 版本、恢复时间、输入哈希和完整可恢复项目文档都包含在恢复记录中。

## 3. 触发、写入与轮换

默认自动恢复间隔为 **60 秒**。字段、项目说明、不确定性假设或验证记录关联改变后：

1. 保留 Phase 8B dirty 标记；
2. 重置 60 秒防抖计时器；
3. 只有项目仍为 dirty 且当前状态可通过项目 schema 验证时才写快照；
4. 写盘失败只记录状态和日志，不中断计算、显式保存或 GUI 使用。

恢复写入采用同目录临时文件、flush/fsync、`os.replace` 原子替换。每个项目 UUID 最多保留 `latest` 与 `previous` 两份快照；若 `latest` 损坏，扫描会隔离它并尝试有效的 `previous`。新项目创建时立即拥有 UUID，因此从未正式保存的项目也可恢复。

## 4. 会话与崩溃检测

启动时创建带 UUID 的 active session marker，初始 `clean_shutdown=false`。正常退出在保留 Phase 8B Save/Discard/Cancel 决策后写入 clean marker；异常进程终止不会执行该步骤。扫描不会只依赖时间戳，而会同时使用会话状态、正式项目兼容性、恢复/正式状态哈希和修改时间。

正常退出或成功正式保存只清理当前项目相关且已被用户处理/保存的恢复文件，不删除其他项目的恢复记录。

## 5. 候选规则

- 未保存项目的 dirty 快照：`RECOVERABLE`。
- 恢复状态与正式项目状态哈希相同：`IDENTICAL_TO_OFFICIAL`，默认不提示。
- 状态不同且恢复时间晚于正式项目 `modified_at`：`RECOVERABLE` / `AUTOSAVE_NEWER`。
- 状态不同但恢复更旧：`STALE`，默认不提升为候选。
- 原会话已 clean：`CLEAN_SESSION`，默认不提升为候选。
- 正式文件无效但恢复有效：保留恢复候选；若 `.bak` 有效，同时报告 `CORRUPT_OFFICIAL_WITH_VALID_BACKUP` 和 `BACKUP`。

这里的“状态哈希”忽略正常保存时间和派生缓存，但覆盖模型、全部输入、不确定性假设、UI 偏好、说明与验证引用，避免把只有时间戳变化的文件误判为新工作。

## 6. Restore、Discard 与 `.bak`

File 菜单新增 **Recover Unsaved Work...**。浏览器显示项目名、恢复时间、原路径、状态和是否晚于正式保存，并提供 Restore、Discard、Details、Later。

- **Restore**：载入内存为 `Recovered Project *`，清除正式文件路径并保持 dirty；不会覆盖原 `.motorproj`，用户必须显式 Save / Save As。
- **Discard**：确认后只删除选中的恢复记录，不删除正式项目或其他项目记录。
- **`.bak`**：若正式项目损坏但同名 `.bak` 通过完整性和兼容性检查，Open 流程明确询问是否打开备份；不自动替换损坏文件。

损坏恢复文件不会阻止启动，而会移动到 `recovery\corrupt\` 并记录可读警告，从而避免每次启动重复触发同一错误。

## 7. 项目兼容性策略

只读 inspector 在打开前报告：

- `COMPATIBLE`：当前 schema、完整性与模型族可用；
- `MIGRATION_AVAILABLE`：存在逐版本、已批准的内存迁移链；
- `NEWER_SCHEMA_UNSUPPORTED`：项目来自未知未来 schema，绝不静默降级；
- `CORRUPT`：SHA-256 不匹配或完整性元数据损坏；
- `INVALID`：不是有效 UTF-8 JSON、根结构/必要版本字段无效，或无法按 schema 解释。

显式 `PROJECT_MIGRATIONS` 注册表当前为空，因为生产 schema 仍为 v1。本阶段只通过测试注入的 synthetic v0 adapter 验证顺序迁移基础，不虚构 v2。应用版本不同本身不等同于 schema 不兼容；schema、完整性、必要字段和 calculation model family 才是打开门槛。未来迁移函数应在可行范围内保留未知扩展数据，但不得静默打开或降级未知未来 schema。

## 8. 已验证场景

- 未保存新项目可在模拟崩溃后精确恢复全部输入；
- 已保存项目修改后的 autosave 比正式文件更新，恢复不改写正式文件；
- 损坏正式文件、有效 `.bak` 与更新 autosave 会同时暴露来源优先级；
- 恢复外层和内嵌项目双重完整性校验有效；
- latest/previous 原子轮换在强制替换失败时保留旧有效快照；
- 无权限/磁盘写入错误降级为非破坏性 warning；
- source GUI 与 one-folder packaged GUI 使用同一用户数据和恢复接口。

## 9. 当前限制

- 恢复周期固定为 60 秒，尚无用户配置 UI；最后一次编辑到意外断电之间可能存在至多约一个间隔的未捕获窗口。
- 只保留每项目 latest + previous，不提供时间线式版本历史。
- SHA-256 用于意外损坏检测，不是数字签名，也不防范拥有本机写权限的恶意修改者。
- 无跨设备同步、云备份、加密或多人合并。
- schema v1 尚无真实历史迁移；首个真实 schema 升级必须单独审查迁移与数据保留政策。
