# JARVIS 环境说明

本说明面向 Windows 用户。当前支持在 Codex 中打开项目，并使用仓库脚本创建 Brain v1 的目录、Markdown 种子、九份空白模板、Brain 索引、运行规则与四个 Bases 视图。Obsidian 自动下载安装和首次呼叫全流程仍是设计，尚未实现；不要将知识库初始化等同于软件安装、插件接入或检索质量验收。

## 现在如何开始

1. 下载并解压项目，或按 [README](../README.md#开始使用) 克隆仓库。在 Codex 中打开包含 `AGENTS.md` 的目录，然后呼叫「JARVIS」。
2. Python 用于读取本地用户画像和运行安装检查。昵称保存在项目根目录的 `up.json`，首次交流可以跳过称呼设置。需要浏览和编辑知识库时，使用 [Obsidian](https://obsidian.md/download)。JARVIS 还需要可用的本地检索工具来查找笔记。临时 Worker 取决于宿主提供的 Agent 工具。
3. 手动接入知识库时，按下节创建本机配置。仓库不保存活动知识库的绝对路径；目录层级和相对规则共享，本机位置单独保存。先检查环境，再按需检查注册表和检索接入。[共享层级](../.codex/obsidian-kb.json) · [本机配置示例](../config/environment.example.json) · [检查脚本](../scripts/verify_installation.py)

## 共享配置与本机路径

唯一的本机路径入口为 `.local/environment.json`，整个 `.local/` 已被 Git 忽略。先在 Obsidian 中打开或创建知识库，再使用当前连接工具实际报告的知识库根目录完成首次配置：

```powershell
python scripts/setup_environment.py --connector-vault "工具报告的知识库绝对路径"
```

脚本会校验目录、共享层级与项目相对路径，原子写入 `.local/environment.json`，并生成 `.local/obsidian-kb.resolved.json`。它不修改 `up.json`；已有不同路径时拒绝覆盖，用户明确要求更换后再使用 `--replace`。成功结果中的 `next` 给出下一步安装检查命令。

仓库同时分发 `config/environment.example.json`，供人工审查或无法运行脚本时使用。示例中的占位值必须替换，不能直接用于执行；以下路径仅为示例，不是默认位置：

```json
{
  "version": 1,
  "vault_root": "C:/path/to/your/vault",
  "skill_roots": []
}
```

`skill_roots` 留空时从当前用户目录推导 `.codex/skills`、`.agents/skills`；有实际安装在其他位置的 Skill 时，只在本机文件填写其绝对目录。项目根目录由脚本自身位置确定，不依赖终端当前目录。

- `.codex/obsidian-kb.json`：共享项目目录和知识分层，库内路径相对于 `vault_root`。
- `config/defaults.json`：`registry`、`agreement` 相对于知识库；其他项目资源路径相对于仓库根。
- `scripts/resolve_environment.py`：读取共享和本机配置，拼接实际路径，校验库内路径不越界；缺失或无效配置不猜测、不自动覆盖。

先由当前 Obsidian 连接工具读取实际库根目录（例如 `obsidian_info` 返回的 `vaultRoot`），再将该值传入校验。不能从本机配置抄出一个值冒充连接结果：

```powershell
python scripts/resolve_environment.py
python scripts/resolve_environment.py --connector-vault "工具报告的知识库绝对路径" --require-write-ready
python scripts/verify_installation.py --environment-only --connector-vault "工具报告的知识库绝对路径"
```

第一条只解析配置，未核验连接时输出 `write_ready: false`。写库前须通过第二条；目标不存在或两侧路径不同会返回失败。校验只代表当次检查，写入前仍需核对目标；它不是系统锁，也不改变宿主工具权限。初始化命令内置同一校验；其他知识库工具由管家按 AGENTS.md I01 执行写前检查。

需要旧版 `obsidian-kb` 格式时，可加 `--write-runtime-pointer`，在 `.local/obsidian-kb.resolved.json` 生成本机解析结果，不改共享配置。外部检索工具必须明确支持传入这份配置。当前这台机器的已安装 `obsidian-kb` Skill 已实测可解析 `.codex/obsidian-kb.json` 的 `environment_file` 引用；Skill 升级后若再次提示缺少 vault，先重新运行首次配置入口和 `doctor`，不要改把绝对路径写入共享配置或画像。

完整接入检查使用仓库查询入口验证真实注册表及项目约定的检索：

```powershell
python scripts/verify_installation.py --connector-vault "工具报告的知识库绝对路径"
```

环境检查通过不表示经验注册表存在或完整检索可用。`.codex/obsidian-links.json`、`.codex/knowledge-index.md` 及归档文档中的旧绝对路径是已停用的历史来源记录，不作为本机配置，不批量改写或重新启用其操作文字。换电脑只需配置新机器的 `.local/environment.json` 及宿主连接；无需修改共享目录规划，也不自动搬迁笔记。

## 人格表达开关

同一 `.local/environment.json` 可增加 `"persona": {"enabled": true}`。这是整个人格功能唯一开关；false 时在装载模块、匹配和读写适配状态之前返回，基础身份和任务治理继续生效。新建环境配置默认 true；已有配置缺字段保持关闭，重复 setup 不擅自启用。setup 保留其他用户字段和已有开关，resolver 校验严格布尔值。

人格入口不依赖 vault 连接；尚未配置环境时保守关闭，不为启用人格伪造知识库路径。正常环境可手动只增加 persona 字段；关闭后不删除画像或适配记录。运行 `python -X utf8 scripts/persona.py --persist` 可装载当前策略，新用户不需要选型；模块、状态、防抖、故障和恢复细节见[人格规程](persona.md)。

## 首次呼叫与自动准备（设计）

1. **先检查本机。** JARVIS 读取 `up.json` 判断是否已有称呼，并独立检查 Python、Obsidian、库路径和检索配置。即使用户已有昵称，也会检查尚未完成的准备。基础环境或知识库分别报告就绪状态。
2. **一轮说明并收集选择。** 缺少昵称时一并询问。知识库有三种选项，新建、接入已有库、先开工。新建时默认用 Windows 实际的「文档」目录，在其中创建 `JARVIS知识库`，并向用户显示解析后的完整路径。用户可指定盘符或完整路径。「先开工」进入基础对话与任务，之后说「准备知识库」即可继续。
3. **验证位置并取得同意。** 清楚列出缺少的软件和会写入的位置。用户回复「按默认位置准备」或「放 D 盘」可确认已说明的准备事项。盘符用于存放笔记，例如 `D:\JARVIS知识库`，Obsidian 应用按常规方式安装。若盘符不存在、位置不可写或目录用途不明确，说明原因，提供已检查的可用位置，请用户重新指定。已有库按用户确认的范围接入。
4. **自行准备。** 确认后告诉用户「好，我来准备，稍等一下」。复用已装软件，从官方来源下载并安装缺少的 Obsidian；目录和模板通过下述初始化入口创建。按已确认库位置配置检索与检查，保护已有笔记。安装中断后，下次重新检查并从缺失步骤接着做。
5. **验证后打招呼。** 实际在目标范围内检索一篇初始化笔记。成功时告诉用户知识库路径，并说「准备好了，咱们开工吧」。如检索或安装失败，说明已完成部分与下一步，用户仍可开始基础工作。

默认位置可用时，首次准备通常只需回复一次。

> 嗨，我是 JARVIS！我怎么称呼你？我可以帮你准备 Obsidian，并在你的「文档」目录下建一个 JARVIS 知识库。你可以回「叫我小林，按默认位置准备」，也可以指定盘符、用已有的库，或说「先开工」。

## 知识库目录与模板（已提供初始化入口）

| 目录 | 内容 |
| --- | --- |
| `01 草稿` | `历史收件箱`、`迁移待分类` 与草稿说明；新材料先保留来源，不自动升级为 active |
| `02 工作记录/任务总结` | JARVIS 与历史项目的任务目标、做法、结果、验证、问题和后续 |
| `02 工作记录/日报/YYYY`、`周报/YYYY` | 仅在用户明确触发时生成，沿用北京时间、ISO 周和具体起止日期规则 |
| `02 工作记录/Brain运行日志` | 摄入、整合、迁移、健康检查、复审、替代和治理事件 |
| `03 wiki/主题` | 经核验的概念、实践和稳定主题内容 |
| `03 wiki/参考资料` | 外部资料与快照，保留来源和适用范围 |
| `03 wiki/综合` | 逐条列明来源的跨笔记结论；冲突分别保留 |
| `03 wiki/索引` | 首页之外的 Brain 索引与主题 MOC |
| `03 wiki/视图` | 待复核、需要复审、主题地图和证据缺口四个核心 Bases |
| `04 模板` | 草稿、任务总结、任务契约、决策、日报、周报、wiki主题、规则、业务对话共 9 个空白模板；模板属性统一为 `type: template`、`status: active` |
| `05 规则` | JARVIS 运行与治理规则，以及按适用范围记录的历史决策 |
| `06 归档` | 仅可读业务对话 Markdown，直接放文件，不建项目、年份、会话 ID 或哈希子目录 |
| `99 附件` | 笔记实际引用的附件；对话归档不自动复制附件 |

先在 Obsidian 创建或接入目标库，完成本机配置并取得连接工具报告的路径后，在仓库根目录执行：

```powershell
python scripts/init_vault.py --connector-vault "工具报告的知识库绝对路径"
```

模板源位于 [templates/vault](../templates/vault/)，Brain v1 的首页、索引、运行规则、日志和 Bases 种子位于 [templates/brain](../templates/brain/)，随 ZIP 或仓库一起分发。脚本校验本机与连接路径一致后，只补缺失目录、Markdown 种子、模板和 `.base` 文件；使用排他创建保护已有同名文件，重复运行报告保留项，不自动迁移已有库、不改插件配置、不生成假日报。初始化出的空库不虚构业务主题或结论。Obsidian 内可将核心模板功能的模板目录设为 `04 模板`；不依赖第三方模板插件。模板中的日期、标题可由核心模板替换，其余说明按实际任务填写。

任务跨天时更新同一篇总结，记录完成日期；日报按北京时间命名 `YYYY-MM-DD_日报.md`，没有工作记录时不生成空日报。周报按周一至周日，使用 ISO 周所属年与周号 `YYYY-Www_周报.md`，正文必须标具体起止日期；跨年归入 ISO 周所属年目录。日报、周报均由用户明确触发，不自动设置定时任务或扫描其他项目。

业务对话命名为 `06 归档/YYYY-MM-DD_任务名称_对话名.md`。日期取北京时间的对话开始日期；名称重复追加 `_02`、`_03`；任务名称与对话名重复可合并。正文按发言顺序保留用户与助手业务内容，注明起止时间和缺失；不保存 `来源.json`、原始日志、宿主指令、内部推理及工具日志副本，不自动复制附件。可阅读对话不冒充完整运行档案。

旧库迁移须先盘点文件、固定哈希、生成路径映射，保护状态与人工内容，更新笔记链接、检索配置及必要插件路径。旧第二层任务经验进入任务总结；旧领域知识及参考资料进入 wiki；未复核候选仍保持草稿。迁移验证包括覆盖、冲突、内容保留、链接和检索；回退材料置于知识库外，不混入归档。历史记录里描述旧目录的文字属于历史事实，不机械改写为新规则。

初始化验收覆盖完整 Brain v1 目录与种子、模板属性、四个 Bases 文件、重复运行、用户文件保护及错误连接阻止写入；基础库应通过 `scripts/brain_health.py` 的核心属性和链接检查。检索质量、Bases GUI 和自动下载安装另在完成本机配置后实测。首次呼叫与安装恢复全流程仍须另行实现验证。

## 生成日报与周报

在 JARVIS 会话中说「生成昨天的日报」或「生成本周周报」，也可以从仓库根目录预览。省略 `--date` 时使用北京时间当天，周报覆盖指定日期所在的 ISO 周。

```powershell
python -X utf8 scripts/work_report.py daily --date 2026-11-21
python -X utf8 scripts/work_report.py weekly --date 2026-11-22
```

日报按项目任务总结的业务日期汇总，优先使用 `completed_on`，其次使用 `date`。跨天任务在结束时补记 `completed_on`，格式为 `YYYY-MM-DD`。旧笔记缺少这两个字段时，仅兼容文件名开头的 `YYYY-MM-DD`；此类记录进入预览的 `date_fallbacks`，报表正文明确标注“日期取自文件名”。无法从字段或文件名确定日期的笔记进入 `undated`，不根据正文、目录名或文件修改时间猜测。周报也按 frontmatter 的 `period_start` 或 `date` 发现周期内同一项目的日报，兼容 `YYYY-MM-DD 日报.md` 等旧命名，并通过 `project` 或 `project/<项目名小写>` 标签核对项目。

预览返回目标文件、来源、Markdown 和 `baseline`。取得该报表的写入授权后，从连接工具确认实际 Obsidian 库根路径，把预览的 `baseline` 传给 `--write`，并在写入后回读文件。

```powershell
python -X utf8 scripts/work_report.py daily --date 2026-11-21 --connector-vault '<连接工具报告的实际库路径>' --write '<已批准预览的 baseline>'
```

已有同名报表时保留原件，返回 `exists`。周期无可用记录时预览返回 `no_records`。来源或预览变化后需重新预览。
