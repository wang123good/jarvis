# JARVIS 使用与操作入口

JARVIS 在本项目主会话中理解意图、维护任务契约、组织执行并复核交付。项目发布版本及规则以根目录 `AGENTS.md` 为准；角色初版 v0.1 不等于项目发布版本。当前实现依靠指令、模板和本地文件，宿主提供实际工具。

## 提出任务

直接说明问题和预期成果，例如：“JARVIS，请评审这份技术方案，给出实施建议、验证方法和不确定性。”

实质任务分别判断复杂度、完整闭环与委派收益，提交理由和契约摘要，经用户事前复核后执行。简单任务可简记，复杂任务先建带修订号任务卡；已复核范围内连续执行、检查及修复。具体关卡、例外、停止和验收规则见 `AGENTS.md`，不在此重复维护。默认直接执行，按需采用委派或探索模式；不必为普通任务新建 Agent 或输入角色长提示。

## 按需读取

| 文件 | 用途与触发条件 |
| --- | --- |
| `AGENTS.md` | 管家身份、事前复核、权限、清理保护及读取路由 |
| `config/defaults.json` | 本次预算和路径的软默认值；不是 Codex 原生配置 |
| `templates/task.md`、`.local/tasks/` | 复杂任务或需要完整闭环时记录契约、修订、检查点与验收 |
| `agents/worker.md`、`templates/worker-work-package.md` | 有明确委派收益且宿主支持时，定义角色与本次工作包 |
| `agents/knowledge-administrator.md`、`templates/knowledge-run-request.json` | 用户手动要求整理时，限定来源、目标、读写范围及预算；占位模板不能执行 |
| `docs/user-profile.md`、`up.example.json` | 画像读取和安全维护；实际数据仅在根目录 `up.json`，不提交 Git |
| `.codex/obsidian-kb.json` | 本项目知识库定位；检索范围及正式经验要求见入口规则 |
| `docs/environment.md` | 环境准备、现行目录、命名、模板、初始化及迁移 |

画像首次仅询问昵称，可跳过；明确保存的偏好按画像规则维护，观察候选确认后生效，旧画像不自动迁移。

## 手动整理知识

例如：“知识库管理员，请整理当前任务的方案决策与验证结论，生成候选草稿供我复核。”

管家明确本次来源和目标；可从当前任务唯一确定的范围直接列明，确有歧义才询问。运行请求和报告保存在 `.local/knowledge-runs/RUN-ID/`。默认先交候选及 diff，正式写入需对应批准与基线核对，角色启用授权不能代替变更批准。

当前采用草稿／工作记录／wiki 布局，对话为 `06 归档` 下的扁平 Markdown；详细规则见环境说明。历史 `50_图书管理员` 名称仅保留来源与链接含义。整理不自动触发全库扫描、定时任务或向 Worker 提供实时检索；“清理聊天且不整理笔记”按入口清理规则执行。

## 接入检查与回退

在完成本机路径、知识库及真实 Skill 配置后，运行：

```powershell
python scripts/verify_installation.py
```

脚本在 `.local/verification-runs/` 排他创建独立目录，保存报告和被测哈希；可用 `--run-id` 指定新 ID，已存在则拒绝。它检查资源与限定检索接入，不验证意图理解、完整恢复、跨会话复用质量或所有规则行为。

历史证据已迁往仓库外，路径映射见 [归档索引](archive-index.md)。以下均为原归档路径：首轮试用见 `jarvis/tasks/JV-20261118-001.md` 及同名 `-verification.json`；单 Worker 链路见 `experiments/W1/steward-recheck.json`。这些结果仅对当时输入有效，不证明多 Worker 并行、硬隔离或成本优势。

回退前保留当前差异，核对后续人工修改；以下备份按归档索引定位，原入口见 `jarvis/backups/initial-deployment/AGENTS.pre-deployment.md`，管理员接入前备份见 `jarvis/backups/knowledge-administrator-deployment/`。不覆盖后续修改、不触碰知识库正文或原始来源。

## 实现边界

Worker 和管理员按需运行，依赖宿主实际能力；收尾按工具完成或停止，无销毁工具不声称已销毁。未注册长期命名子代理，不增加常驻进程、调度器或付费 API，不更改宿主沙箱、模型或审批。软预算、职责分工和恢复规程不构成系统级限额或隔离。

新会话自动加载和实际遵循效果须另行观察；文件存在、接入检查通过不等于行为已验证。机制参考：[官方 AGENTS.md 文档](https://learn.chatgpt.com/docs/agent-configuration/agents-md)，不能据此推断未实现能力。
