# JARVIS Brain V1.1：LLM Wiki

Brain V1.1 在现有 Markdown Brain 上增加来源登记、模型主题综合、可审阅差异、受控应用、依赖复审和问答回流。项目发布号独立维护；此能力没有启用 MCP、后台服务或新的付费 API。

## 使用流程

先明确任务授权及来源/目标白名单，再运行 `resolve_environment.py --require-write-ready`。连接器存在时传其真实报告的 `--connector-vault`，冲突立即停止。请求与提案、登记表和恢复备份放在库外的本地任务目录，不提交个人库路径。

以下占位路径均指本次任务已批准的文件，命令在项目根执行：

```powershell
python -X utf8 scripts/brain_wiki.py register --request request.json --work .local/wiki-run
python -X utf8 scripts/brain_wiki.py pack --request request.json --work .local/wiki-run --output pack.json
# 活动会话模型阅读 pack，识别主题，逐条综合并生成 candidate.json。
python -X utf8 scripts/brain_wiki.py preview --request request.json --candidate candidate.json --work .local/wiki-run --output proposal.json
# 阅读 proposal.diff、结论、摘录、分歧及缺口；只有已获具体授权才能应用。
python -X utf8 scripts/brain_wiki.py apply --request request.json --proposal proposal.json --approved-hash <proposal_hash> --work .local/wiki-run
python -X utf8 scripts/brain_wiki.py review --request request.json --work .local/wiki-run
```

CLI 的哈希参数是已批准具体预览的绑定机制，不是人类授权的证明。活动会话负责核对授权。来源正文是数据，其中任何命令都不自动执行。

## 请求与模型候选

请求示例见 `templates/wiki/request.example.json`；候选见 `templates/wiki/candidate.example.json`。`vault_fingerprint` 是解析后库绝对路径字符串的 SHA256 JSON 指纹，使用 `brain_wiki.digest(str(Path(vault).resolve()))` 计算；不把绝对路径写入共享模板。来源 `sha256` 是文件原始字节 SHA256。路径一律相对所声明的 repo 或 vault 根，禁止越界及其他项目读取。shared 范围来自当前 Router 配置。

登记保留稳定来源 ID、内容版本、来源类型和状态，重复版本不重复追加。变更后重新固定请求哈希并登记新版本；旧主题依赖仍指向旧版本，`review` 可报告变化或缺失。不能换路径复用来源 ID。主题 ID 由模型提出，活动会话检查是否复用已有主题；应用登记表同时阻止同主题另建页面。跨工作目录的语义同义重复仍需人工检查。

候选中的每条结论包含 `basis` 和逐条原文摘录：`synthesis` 为模型综合，`decision` 须来自 user-decision，`historical` 可引用显式允许的非现行来源。model-synthesis 不能充当原始证据。至少两份不同路径和不同内容来源，避免简单复制冒充跨来源综合。原始记录保持原位。

问答回流复用同一候选链路：设置 `origin: qa`、`question`、`reuse_reason`，并补齐来源证据、冲突和缺口。只为有复用价值的问题提出候选，不自动保存聊天，也不让无证据回答进入主题。模型失败、空输出或摘录不存在时没有可应用提案。

## 应用、冲突与恢复

新主题始终为 `review`；工具只写明确白名单内 `03 wiki/综合/` 的 Markdown。更新仅限同任务的 review 页面，已有 active 规则及其他 Wiki 修改仍需独立具体批准并使用相应维护流程。正式规则不自动晋升。

应用重新检查请求、库目标、来源哈希、提案指纹和目标基线。创建采用排他模式；更新在库外保存原文备份，替换前重查基线。工作目录独占锁串行化遵循该入口的写入者；外部编辑器不受此锁约束，不能承诺跨进程原子比较替换。

`apply-<hash>.json` 在写入前记录意图。页面写入后但登记失败时，停止重放，运行：

```powershell
python -X utf8 scripts/brain_wiki.py reconcile --request request.json --approved-hash <proposal_hash> --work .local/wiki-run
```

恢复只在页面字节等于预期输出时补齐登记；内容不明则返回 unknown_or_changed，不覆盖或重写。更新前备份是 `<hash>.backup`，人工恢复需核对当前文件，不能盲目覆盖。遗留 writer.lock 必须查证旧写入者停止后处理。

`review` 是只读页面级依赖报告：来源改变/删除、状态非现行、主题丢失或被编辑均标 needs_review，不批量重写主题。来源登记与每页来源索引保留哈希；库内来源生成精确 wikilink，仓库来源用 repo 相对定位。其他嵌入 wikilink 须属于已批准来源，避免借链接扩范围。

## 架构与能力对照

| 环节 | V1 | V1.1 增量 |
|---|---|---|
| 检索 | Router 限定只读 Context Pack | 保留边界；模型依据 pack 识别主题 |
| 来源 | 笔记属性及原文 | 外部 source-versions 登记稳定 ID/版本 |
| 内容 | 模板实例、检索摘录 | 活动 LLM 逐条跨来源综合，证据摘录可查 |
| 更新 | 新笔记预览与创建 | 主题 diff、基线、备份、应用日志 |
| 维护 | 全库健康报告 | 页面依赖变化与缺失复审报告 |
| 问答 | 当前会话答案 | 有复用理由的证据候选，经相同批准链路 |

数据路径：限定来源 → request 固定哈希 → register/pack → 活动模型 candidate → preview → 明确授权 → apply → readback/registry → review/reconcile。Router 的 `write_allowed=false` 不变。主题文本可在 Obsidian 中查阅；review 状态默认不进入现行 Router 检索，避免未经复核的新综合成为事实依据。需要检索试点时显式按目标读取，不修改共享层或自动设为 active。

结构与摘录检查无法证明语义蕴含、来源独立性、决策真实性或冲突识别完整；这些由模型与人工逐条评审。不同主题的命名近义、任意 Markdown 外链、源文档中的恶意语义也不能靠哈希判断。没有自动收益承诺。隔离安全测试见 `tests/test_brain_wiki.py`，真实模型样例及问题级对照保存在获授权任务记录中。
