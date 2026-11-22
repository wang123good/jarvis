---
title: "Brain v1 治理规范"
type: "rule"
status: "active"
updated: "2026-11-22"
updated_source: "migration"
topics: ["Brain", "知识管理", "治理"]
confidence: "high"
authority: "personal"
source: "JARVIS Brain v1 设计"
---
# Brain v1 治理规范

## 单一事实源

Markdown 正文与 frontmatter 是知识事实源；Bases、搜索和日志视图只用于读取与审计，不形成第二份事实。

## 状态升级

- `inbox → review`：完成来源捕获和基础属性。
- `review → active`：结论有来源或明确个人决策依据，适用范围清楚。
- `active → superseded/archived`：有替代关系或不再适用。
- 迁移、自动整理和模板生成都不能凭“文件存在”把内容升级为 active。

## 冲突

- 新旧说法并存时，分别保留并标注适用时间、来源和冲突。
- 较新、更高频或标题更完整都不自动胜出。
- 无法判定时交用户决策，不静默合并。

## 来源与证据

- 重要外部资料保留 `source`、`source_url`、`captured_at` 或 `source_hash`。
- 任务证据指向可重复读取的运行目录、文件或消息定位。
- 历史快照中的“已验证”不自动延伸到当前状态。

## 人工编辑保护

- 写入前校验输入基线；人工内容变化时停止受影响批次。
- 合并或移动保留来源哈希和恢复入口。
- 永久删除、公开分享、插件安装和跨项目敏感读取均需单独授权。

## Brain 日志

每次迁移、整合、健康检查和状态决策记录日期、任务/运行 ID、结果和证据。日志不保存密钥、原始工具日志或内部推理。
