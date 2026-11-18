---
title: Skill Subagent Agent集群与编排层边界
type: task-experience-sample
project: jarvis
experience_id: exp-2026-007
task_signature: skill-subagent-cluster-orchestrator-boundary
status: 已闭环
human_review: approved
call_frequency: 2
created: 2026-11-17
updated: 2026-11-17
last_verified: 2026-11-17
confidence: high
tags:
  - project/jarvis
  - task-experience
---

# Skill Subagent Agent集群与编排层边界

## 目标

澄清 Skill、Subagent、Agent 集群、Orchestrator 和 Scheduler 的关系。

## 结果

确定 Skill 是方法，Subagent 是临时执行实例，Orchestrator 是目标与责任层，Scheduler 是执行资源层。

## 状态建议

**已闭环**：用户采纳“Worker 可直接协作、管家定义边界和检查点、Scheduler 延后”的建议，并据此开始实验。

## 可复用经验

- 小任务优先点对点协作。
- 复杂任务需要目标拆解、检查点和最终责任人。
- 共享工作区优先于私聊作为事实来源。

## 证据

- session:01a1e893-ce4d-7ff2-bf55-00845bf74786
- docx:JARVIS 管家 Worker Skill 与图书管理员架构设计 v1.5

## 适用边界

适用于多 Agent 协作和编排设计，不强制所有任务采用 Orchestrator。

## 复核

- [x] 人工复核状态与证据

