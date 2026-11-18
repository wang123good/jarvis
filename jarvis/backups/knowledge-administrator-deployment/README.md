# JARVIS 管家 v0.1 使用说明

本版是 `D:/codex-project/JARVIS` 项目主会话的角色指令配置。2026-11-18 用户授权“按建议落地”，入口为项目根目录 `AGENTS.md`；详细职责保留在 `架构方案/JARVIS 管家Agent职责定义 v0.1.md`。

## 如何使用

在本项目中直接提出工作任务即可，例如：“JARVIS，请评审这份技术方案，给出实施建议和不确定性。”简单任务直接完成，复杂任务由管家维护一份任务卡。无需为普通任务新建 Agent 或输入角色长提示。

建议下一次在此工作目录启动新会话，并先要求其说明读取了哪些项目指令，再给出真实任务。本次已明确读取新入口并执行首项试用；新会话自动加载及行为效果仍需实际观察，不能以文件存在替代验证。

## 文件分工

- `jarvis/worker.md`：已启用的通用临时 Worker 角色与管家派发规程。

- `jarvis/worker-work-package-template.md`：逐 Worker 输入、产物、范围、子预算和验收交接。

- `AGENTS.md`：身份、工作顺序、权限和交付约定。

- `jarvis/defaults.json`：供管家读取的项目软默认值，不是 Codex 原生配置，不会自行执行限时或控费。

- `jarvis/task-template.md`、`jarvis/tasks/`：单份轻量任务记录与实际交付。

- `.codex/obsidian-kb.json`：现有知识库入口；正式经验与草稿保持区分。

当前采用直接/委派/探索三种模式，默认直接；临时 Worker 仅在实际可调用且已授权时按需使用。未注册命名子代理，不增加常驻进程、调度器或付费 API，不更改宿主沙箱、模型和审批设置。

2026-11-18 用户授权落地通用 Worker。你只需继续向管家提出任务；管家判断是否需要委派，组织工作包、派发、复核及关闭实例。W1 已验证单个临时 Worker 执行链路，本次接入可复用指令与模板；多 Worker 并行、硬隔离和成本收益仍未验证。

## 首次验证与回退

首项任务 `jarvis/tasks/JV-20261118-001.md` 评估本版试用准备情况；校验报告为 `jarvis/tasks/JV-20261118-001-verification.json`。

原入口备份在 `jarvis/backups/initial-deployment/AGENTS.pre-deployment.md`。需回退时先保留当前差异，再恢复该入口；不覆盖后续人工修改，不触碰知识库数据。原 v1.5 DOCX 未修改。

官方机制依据：https://learn.chatgpt.com/docs/agent-configuration/agents-md 。其支持项目指令加载，不保证此角色已经具备常驻、硬预算、Worker 权限隔离或跨会话学习能力。
