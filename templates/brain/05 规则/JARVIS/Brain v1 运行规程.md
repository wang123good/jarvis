---
title: "Brain v1 运行规程"
type: "rule"
status: "active"
updated: "2026-11-22"
updated_source: "migration"
topics: ["Brain", "知识管理"]
confidence: "high"
authority: "personal"
source: "JARVIS Brain v1 设计"
---
# Brain v1 运行规程

## 摄入

1. 新材料先进入 `01 草稿`，保留来源、捕获日期和原文哈希；缺少依据时保持 `inbox` 或 `review`。
2. 未经人工复核，不把来源摘要提升为 `active` 规则或跨来源结论。
3. 模板进入 `04 模板`，不进入业务知识 MOC。

## 查询

1. 从 [[首页|知识库首页]] 进入 Brain 索引或主题 MOC。
2. 用 `status`、`topics`、`confidence`、`updated`、`review_after` 缩小范围。
3. 对时间敏感答案核对来源和快照日期；历史中的“已验证”只在该任务范围有效。
4. 找不到证据时明确拒答，并区分“没有来源”和“检索未命中”。

## 每周整合（仅明确触发）

1. 读取本周任务总结和新增草稿。
2. 生成待合并、待复核、可转主题或参考资料的候选。
3. 给出差异和冲突清单；人工编辑冲突时停止覆盖。
4. 获批后更新 MOC、Brain 索引和 [[02 工作记录/Brain运行日志/log|运行日志]]。

## 每月健康检查

检查核心属性、合法类型与状态、active 缺来源、过期 `review_after`、未解析或歧义链接、替代关系、孤立项和模板误检索。报告只产生维护候选，不自动改内容。

## 过期、替代与归档

- 时间敏感 active 知识应设 `review_after`。
- 被替代内容保留原文，标 `status: superseded` 并指向 `superseded_by`。
- 历史留存标 `status: archived`，不作为默认现行答案。
- 无证据内容可退回 `review`；不得静默删除。

## 写入权限

- 用户确认规则、正式经验、长期能力和跨来源 active 结论。
- JARVIS 在明确任务内维护草稿、属性、索引、日志和验证报告。
- 知识库管理员只在指定来源和批准差异范围内整理。
- Worker 没有知识库直接写入权。
