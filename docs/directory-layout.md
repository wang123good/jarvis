# 目录职责与扩展约定

仓库根目录保留项目入口、发布说明及用户画像空白模板；可分发资产按职责存放，本地执行数据集中隔离。

| 路径 | 职责 |
| --- | --- |
| `AGENTS.md` | 项目主会话入口与读取路由 |
| `agents/` | Worker、知识库管理员等角色定义 |
| `config/` | 项目默认配置；宿主相关配置仍在 `.codex/` |
| `templates/` | 任务、工作包、整理请求及 `vault/` 知识库模板 |
| `scripts/` | 初始化、画像读取、接入检查、制图等辅助程序 |
| `tests/` | 辅助程序测试 |
| `skills/` | 随项目维护的技能资产 |
| `docs/` | 操作、环境、画像、目录和归档说明；`images/`、`diagrams/` 保存图示 |
| `架构方案/` | 架构设计、职责依据和历史设计文档 |
| `.local/` | 任务卡、工作包、运行请求、报告及临时文件；不提交 Git |
| `up.json` | 唯一活动用户画像；不提交 Git |

新增功能沿用上述职责；只有形成独立模块时再增加子目录，不为每个功能复制一套顶层结构。脚本以自身位置定位仓库资源，配置中的相对路径以仓库根为基准。新运行使用独立 ID，不覆盖已有证据。

常用入口：

```powershell
python scripts/read_profile.py
python scripts/init_vault.py --vault "D:\JARVIS知识库"
python scripts/verify_installation.py
python -B -m unittest discover -s tests
```

2026-11-20 经用户批准将原 `jarvis/` 按职责拆分；旧路径不提供兼容转发，当前调用按本结构执行。外部自动化或人工保存的旧命令需同步调整。库外归档原件、历史哈希和来源路径不改写，映射见 [归档索引](archive-index.md)。历史 DOCX 保留原件，其内嵌旧路径按归档和本说明理解。本地运行材料分别位于 `.local/tasks/`、`.local/knowledge-runs/`、`.local/skill-runs/`、`.local/verification-runs/`。
