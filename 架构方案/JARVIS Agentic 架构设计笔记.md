---
title: JARVIS Agentic 架构设计笔记
date: 2026-11-17
type: design-note
project: jarvis
status: draft
last_verified: null
confidence: medium
tags:
  - project/jarvis
  - agentic-ai
  - codex
aliases:
  - JARVIS 设计笔记
---

# JARVIS Agentic 架构设计笔记

## 定位

JARVIS 是“长期管家 Agent + 临时执行 Worker + Skill 能力库 + 离线图书管理员 + 任务经验注册表”的个人 Agentic 工作系统。

长期主体只有管家 Agent；Worker 为具体任务临时派生；Skill 负责复用方法；图书管理员负责离线整理知识，不参与实时任务。

## 关键决策

| 组件 | 定位 | 边界 |
|---|---|---|
| 管家 Agent | 长期规划与决策主体 | 负责目标、计划、上下文、调度、观察、重规划和交付 |
| Worker | 临时执行实例 | 只承接有边界的工作包，不持有长期记忆 |
| Skill | 可复用能力包 | 负责流程、脚本、样例和验收，不管理任务状态 |
| 图书管理员 Agent | 独立离线整理主体 | 手动触发，整理 Session、主题知识、经验和 Skill 映射 |
| 经验注册表 | 规划输入 | 管家读取后写入 Worker Context Pack |
| Obsidian | 人类可读知识库 | Worker 不直接访问，避免越权和上下文污染 |

## 运行闭环

```text
目标
→ 查询任务经验注册表
→ 生成计划与任务图
→ 装配 Context Pack
→ 管家执行或派生 Worker
→ 观察结果与证据
→ 验收、重试或重规划
→ 保存任务证据
```

## 自进化

**能力进化**

```text
任务证据 → 复盘 → Skill / 知识候选 → 回放验证 → 人工确认 → 版本发布
```

**用户认知进化**

```text
纠正与反馈 → 画像候选 → 明确确认或一致证据 → 分层用户模型
```

长期资产必须保留来源、置信度、适用范围、版本和回滚指针。

## 任务经验注册表

首版状态采用：

- **已闭环**：结果与目标基本一致，可重复复用对应 Skill。
- **有待完善**：结果可接受，但存在明确不足，需在新任务中继续完善。

状态由图书管理员建议，人工复核确认。首版按任务调用频率降序排列，频率相同时按最近更新时间降序。

稳定字段至少包括：

```yaml
experience_id: exp-2026-001
task_name: Agent架构评审
task_signature: review-agent-architecture
objective: 评审架构方案的可实施性和风险
status: 已闭环 | 有待完善
status_suggestion: 图书管理员建议
human_review: approved | needs_changes
call_frequency: 8
last_updated: 2026-11-17
evidence_refs: [session_id, artifact_path, test_result]
applicability: [JARVIS, 本地Codex, 架构评审]
skill_links:
  - skill_id: architecture-review
    skill_version: 1.2.0
```

注册表承担间接接口职责。Worker 不直接调用图书管理员，也不直接读取全量 Obsidian；由管家筛选后写入 Context Pack。

## Agentic 特性

- 显式目标、验收标准和风险等级。
- 任务图、依赖、状态机、检查点和停止条件。
- Worker 输入输出契约及结构化返回。
- 工具注册、权限、副作用和幂等性。
- 执行轨迹、人工审批、失败重试和重规划。
- 结果评测与轨迹评测并行。

## 安全边界

- 图书管理员默认只读历史证据，写 Obsidian 和注册表前输出 diff。
- 管家不能自行扩大 Worker 权限。
- Worker 不跨项目读取经验。
- 用户画像和专业背景只按明确确认或一致证据更新。
- 自动归档、自动画像和自动 Skill 发布均在验证后启用。

## 待验证技术点

- 独立 Agent 自动读取完整 Session。
- 命名 TOML Agent 的发现和调用。
- Worker 权限、工作区和审批隔离。
- Hooks 或 Automations 的幂等触发。
- 大规模 Obsidian 检索和索引性能。
- 图书管理员状态建议的准确率。
- 频率排序对任务质量的长期影响。

## 可继续完善

1. 从单频排序扩展到“相关度、状态、时效性、成功率、频率”综合排序。
2. 增加经验完备度评分和具体不足分类。
3. 建立 Experience-Skill 多对多映射和版本约束。
4. 增加经验去重、冲突检测、过期和回滚。
5. 增加图书管理员运行游标、批处理日志和人工复核界面。
6. 增加 Worker 轨迹评测、成本预算和失败恢复指标。
7. 定义项目级访问控制和敏感信息保留策略。
8. 验证自动读取、定时触发和常驻运行后再减少人工步骤。

## 下一步

1. 手动建立 5 至 10 条任务经验，验证注册表字段。
2. 跑通“图书管理员整理 → 人工复核 → 管家查询 → Worker Context Pack”的闭环。
3. 用历史高频任务验证频率排序和经验复用收益。
4. 通过 PoC 后再决定自动读取、自动排序和自动发布。

## 相关文档

- [[JARVIS 管家 Worker Skill 与图书管理员架构设计 v1.5]]
- [[JARVIS 管家Agent 执行Worker 与Skill 架构设计 v1.3]]
