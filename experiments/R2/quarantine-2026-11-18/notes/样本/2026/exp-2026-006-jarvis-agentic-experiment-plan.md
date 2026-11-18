---
title: JARVIS Agentic 闭环实验计划设计
type: task-experience-sample
project: jarvis
experience_id: exp-2026-006
task_signature: jarvis-agentic-experiment-plan
status: 已闭环
human_review: approved
call_frequency: 2
created: 2026-11-17
updated: 2026-11-18
last_verified: 2026-11-18
confidence: high
tags:
  - project/jarvis
  - task-experience
---

# JARVIS Agentic 闭环实验计划设计

## 目标

把 JARVIS 架构转化为分层、可确认、可验收的实验步骤。

## 结果

形成 E0 至 E5 分层实验、G0 至 G5 确认门和状态流转机制；G0 已确认并进入 E1。

## 状态建议

**已闭环**：计划已落地到 Obsidian，状态机制、基线任务和 E0 结果已通过 G0。

## 可复用经验

- 每层先定义产物和验收，再执行。
- 状态只能按“待确认、已确认、执行中、待复核、已完成、阻塞”流转。
- 不允许跳过确认门。

## 证据

- note:JARVIS Agentic 闭环实验计划 v0.2
- note:2026-11-17 E0 闭环定义与基线
- note:2026-11-18 G1 注册表阶段确认
- note:2026-11-18 E2-02 Session主题与经验提取
- note:2026-11-18 E2-04 人工复核决策

## 适用边界

适用于当前单用户、本地 Codex 和 Obsidian 环境。

## 复核

- [x] 人工复核状态与证据

