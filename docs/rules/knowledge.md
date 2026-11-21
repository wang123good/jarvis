## 知识检索

- 回顾跨聊天任务或按一段时间汇总项目工作时，读取 [任务回顾规程](../task-knowledge.md#任务回顾)。

- **I01** 知识库根路径仅保存在 `.local/environment.json`，共享层级见 `.codex/obsidian-kb.json`。涉及知识库操作时先运行 `python scripts/resolve_environment.py`；写入前须由连接工具报告实际库路径，再用 `--connector-vault <实际路径> --require-write-ready` 校验，不得猜测路径或在不一致时写入。正式注册表位于 `<vault_root>/05 规则/JARVIS/任务经验注册表/experience-registry.json`；缺失时如实报告，不伪造或自动初始化。按任务名称、签名、目标及适用范围筛选，再按调用频率降序、更新时间降序、稳定 ID 升序排序，不得编造频率。
- **I02** 使用前核对证据、人工复核、具体不足及真实 Skill 文件、版本/内容哈希。草稿仅作线索；无匹配正式经验则说明并继续，不恢复隔离样本。正式经验须关联真实 Skill，普通知识笔记不强制关联。
- **I03** 外部检索工具须明确支持显式配置，并使用解析器生成的 `.local/obsidian-kb.resolved.json`；不支持时停止对应接入，不回写共享绝对路径。本项目经验使用 obsidian-kb 的 `search ... --project-only`；仅 `--layers project` 不保证项目隔离，不能用未限定的 context 替代。领域/参考资料仅按授权需要读取，不读无关项目敏感内容。资产数量按需查询，不以历史快照代表现状。
