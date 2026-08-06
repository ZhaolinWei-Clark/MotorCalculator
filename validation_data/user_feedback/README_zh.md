# Phase 7J 本地验证反馈库

默认数据库路径为 `validation_data/user_feedback/feedback_records.jsonl`，格式为 UTF-8 JSONL，每行一个带 schema version、输入快照哈希和记录内容哈希的证据记录。

该文件默认被 Git 忽略，原因是用户测量、测试报告和运行配置可能包含私有信息。系统不会上传、同步或自动导出这些数据。需要分享时，应由用户主动审查内容、支持文件和来源许可后显式导出。

Phase 7J 只追加证据：

- 不覆盖同 ID 记录；
- 可能重复的记录标记为 `POSSIBLE_DUPLICATE`，但不删除；
- 语义不兼容的记录仍保存，但不计算误差；
- 不校准、不训练、不修改生产参数。
