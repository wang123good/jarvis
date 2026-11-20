# 历史证据归档索引

2026-11-20 经用户确认，历史实验、任务附件和运行证据迁往仓库外：

`D:/codex-archives/JARVIS/2026-11-20`

原项目相对路径统一映射为归档根下的 `project/<原路径>`。完整逐文件清单、SHA-256、迁移日志和核验结果位于归档根的 `_cleanup/`；原件保持不变。新克隆或其他电脑不会自动获得这些本地归档。

| 原路径 | 内容 |
| --- | --- |
| `experiments/` | E2-06、F1、R1、R2、W1 历史实验及核验原件 |
| `jarvis/tasks/` | 历史任务卡、附件与执行证据；当前清理任务卡仍留在本地 |
| `jarvis/backups/` | 初始部署及管理员接入前备份 |
| `jarvis/knowledge-runs/` | 历史知识整理、迁移及复核记录 |
| `jarvis/skill-runs/`、`jarvis/reviews/`、`jarvis/research/` | 历史技能运行、评审及研究材料 |
| `jarvis/verification-runs/` | 历史接入与架构检查结果 |
| `jarvis/user-profile/` 中旧 JSON/JSONL | 已停用画像、批准及验证记录；当前入口仍为根目录 `up.json` |
| `AWB/`、根目录 ZIP、缓存及 `$null` | 业务附件、本地打包文件及运行残留 |

重要来源（以下均为原路径，读取时加归档根及 `project/`）：

- 首轮试用：`jarvis/tasks/JV-20261118-001.md` 及同名 `-verification.json`。
- 真实单 Worker 链路：`experiments/W1/dispatch-receipt.json`、`experiments/W1/steward-recheck.json`。
- 原入口：`jarvis/backups/initial-deployment/AGENTS.pre-deployment.md`；管理员接入前备份：`jarvis/backups/knowledge-administrator-deployment/`。
- 首批标签词表与复核：`jarvis/knowledge-runs/KB-20261119-ORG-001/worker/tag-vocabulary.json`、同运行的 `review-summary.md`。
- 管理员修订研究：`jarvis/research/obsidian-skills-20261119/report.md`。
- 架构检查：`jarvis/verification-runs/arch-20261120/run-report.md`。
- 知识库迁移：`jarvis/knowledge-runs/VAULT-20261120/`。

架构历史文档中的上述路径保留原始来源含义，按本映射查找，不作为现行运行依赖。历史结论只对当时输入有效。

源码、角色、模板、技能及文档留在仓库；新任务卡、运行报告、业务附件和个人画像仅保存在本地并由忽略规则排除。此次迁移不改写 Git 历史，旧提交可能仍含历史文件；未提交、推送或递增发布版本。同盘迁移不代表释放磁盘空间。
