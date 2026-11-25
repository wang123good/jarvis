## 知识检索

- 回顾跨聊天任务或按一段时间汇总项目工作时，读取 [任务回顾规程](../task-knowledge.md#任务回顾)。

- **I06** 任务上下文默认使用 JARVIS Brain Router 的 `project` 模式，不再把通用
  `kb.py context` 当作项目隔离保证。先运行 `python scripts/resolve_environment.py`
  解析本机路径。注册表变化后先运行 `python -X utf8 scripts/brain_router.py
  check-config`，核对项目根、共享层和项目索引；根或共享层缺失时不得继续把
  Router 结果当作完整上下文。检查通过后执行：

  ```powershell
  python -X utf8 scripts/brain_router.py project --query "<任务目标与关键词>" --limit 8
  ```

  `project` 只扫描当前项目根、当前项目规则和共享主题/资料层；默认阻止其他项目、
  `inbox`、`archive`、`draft`、`archived`、`superseded`、`rejected`、`deprecated`
  与 `expired`。项目识别以注册表中的 vault 相对路径为主，frontmatter 不能覆盖路径
  边界。返回 Context Pack 的 `write_allowed` 必须为 `false`。

- **I07** 只有任务明确需要跨项目研究时才使用 `research`。指定项目：

  ```powershell
  python -X utf8 scripts/brain_router.py research --query "<研究问题>" --projects "<project-id-1>,<project-id-2>" --limit 8
  ```

  省略 `--projects` 时只搜索注册表中 `researchable=true` 的自动候选。没有具体任务
  授权或明确用途时，不以自动候选替代当前项目上下文。研究结果必须显示
  `source_project`、`selection_reason` 和 `current`；共享层标为 `shared`。

- **I08** `archived`、`superseded` 和 `draft` 只能分别通过
  `--include-archived`、`--include-superseded`、`--include-drafts` 显式纳入；
  纳入后仍须保留 `status_warning=non_current`，不能作为现行事实使用。跨范围链接
  只可扩展到本次允许的项目和共享层，不能借链接进入其他项目或归档路径。

- **I09** Router 只读且不写 Obsidian。命中项只是待读线索；正式采用前按 I02 读取
  原文、核对状态、版本、适用条件和冲突。`conflicts`、`evidence_gaps` 与
  `exclusions` 必须随 Context Pack 交付，不得静默合并。通用 `kb.py context`
  仅用于兼容排障；其 hub 可能越层且链接结果可能超出请求上限，不得用于默认项目
  上下文。当前排序是确定性词法检索，不是语义相关性保证；`conflicts` 主要识别
  重名及现行/非现行状态冲突，不能替代阅读原文后的语义矛盾判断。

- **I05** 回顾回答的覆盖与相关记忆提示：说明本次覆盖的项目、时间或资料范围。问题可能包含更广历史，且已有经核实的相关索引或历史资产线索时，回答后简短提示并询问是否展开；不为提示默认扫描其他项目正文，不扩大跨项目敏感读取授权。数量未经本次核对不报精确数，历史快照标明日期。同一议题已提示、待回复或用户已拒绝时不重复提醒，除非用户重新要求或范围有实质变化。用户明确要求全局回顾时按其授权范围查询；缺少权限、入口或范围不明则说明并澄清，不先交付明知不足的局部答案再追问。操作步骤见任务回顾规程。

- **I01** 知识库根路径仅保存在 `.local/environment.json`，共享层级见 `.codex/obsidian-kb.json`。涉及知识库操作时先运行 `python scripts/resolve_environment.py`；缺失配置时先向用户取得连接工具报告的实际库路径，再运行 `python scripts/setup_environment.py --connector-vault <实际路径>`，不得从账号或示例猜路径，也不得改写画像。写入前须由连接工具报告实际库路径，再用 `--connector-vault <实际路径> --require-write-ready` 校验，不得猜测路径或在不一致时写入。正式注册表位于 `<vault_root>/05 规则/JARVIS/任务经验注册表/experience-registry.json`；缺失时如实报告，不伪造或自动初始化。按任务名称、签名、目标及适用范围筛选，再按调用频率降序、更新时间降序、稳定 ID 升序排序，不得编造频率。
- **I02** 使用前核对证据、人工复核、具体不足及真实 Skill 文件、版本/内容哈希。草稿仅作线索；无匹配正式经验则说明并继续，不恢复隔离样本。正式经验须关联真实 Skill，普通知识笔记不强制关联。
- **I03** 外部检索工具须明确支持显式配置，并使用解析器生成的 `.local/obsidian-kb.resolved.json`；不支持时停止对应接入，不回写共享绝对路径。本项目经验可继续使用 obsidian-kb 的 `search ... --project-only` 做窄范围补查；仅 `--layers project` 不保证项目隔离，不能用未限定的 `context` 替代 Router Context Pack。领域/参考资料仅按授权需要读取，不读无关项目敏感内容。资产数量按需查询，不以历史快照代表现状。
