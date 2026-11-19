# JV-20261119-KB-SKILL-UPDATE：知识整理Skill修订

- contract_revision：1；状态：待用户决策（事前复核）。
- 用户要求：根据前面讨论的知识库整理内容，修订完善相应的skill。
- 已做必要只读盘点：读取skill-creator、obsidian-curator真实入口、管理员v0.2、项目默认值及画像读取器。obsidian-curator现为导出会话证据专用；不得把其curate.py误用为任意笔记维护器。
- 判断：中等，采用完整闭环。涉及长期可复用指令、模式分流及原有写入流程兼容，需内容检查与隔离场景验证；不需多Agent。
- 目标：将已讨论的现有笔记整理方法沉淀到现有obsidian-curator，保留会话证据整理流程。
- 交付：修订SKILL.md的触发描述及模式入口，增加按需读取的references/vault-maintenance.md；现有UI元数据若需同步先核对；备份、精确diff、基线及验证报告留在本任务运行目录。必要时仅调整管理员中的Skill使用说明以匹配新模式。
- 内容：范围清单与哈希、报告式巡检、受控标签、语义链接理由与目标解析、三类主题缺口、有据草稿、人工编辑与哈希依赖保护、具体diff批准后备份串行应用、增量与部分失败记录。
- 边界：不将JARVIS十个标签或P3治理规则泛化为全局规定；项目特有约定由本地角色/请求提供。不改codex-memory-sync、obsidian-kb或obsidian-markdown实现；不把curate.py宣称为通用维护写入器；不安装框架、不新增Skill、不整理更多正式笔记。
- 验收：quick_validate通过；原导出会话流程仍可发现且约束不弱化；既有笔记模式不要求伪造source_thread/source_hash映射；缺来源只列缺口；依赖笔记和人工编辑受保护；候选与正式应用权限明确。可用冻结样本在隔离目录做场景回放，禁止写入正式库。
- 执行：管家直接修订→结构及兼容检查→隔离场景验证→有依据修正→复验→交付；不派Worker。最多2类场景，20分钟收敛检查，同类失败额外重试1次，不新增付费服务；费用未计量。
- 停止：基线漂移、无法兼容现有流程或需要扩大目标/脚本实现时停止受影响部分提交决策。必要内部修复在原范围自主完成。
- 当前权限：用户明确要求修订；按项目AGENTS.md事前复核要求，尚待用户确认本次具体范围及组织安排，未修改已安装Skill。

## 事前复核通过

- 用户回复“批准”，认可contract_revision=1的范围、组织及验证安排；当前状态：执行中。上方待复核表述为历史记录。
- 运行目录：jarvis/skill-runs/KB-SKILL-20261119-001；修改前保存Skill入口、UI、原curate.py和管理员角色四份基线及备份。原curate.py只作兼容核对，不修改。
- 使用skill-creator，直接执行，Worker为0；选用已冻结本地样本验证，不联网、不新增付费服务、不向正式库写入。

## 执行与交付检查点

- 当前状态：已交付待验收。已按批准r1修订已安装obsidian-curator的入口、UI及新增vault-maintenance参考，并同步现有管理员预检说明；未修改原curate.py或其他Skill实现。
- 验收映射：quick_validate通过；validation.json的12项检查通过；会话流程正文逐字保留、脚本哈希不变；原渲染器拒绝信任提升及缺来源；冻结笔记标签预览保留正文和非标签元数据；受保护样本及上批36个正式目标哈希不变。
- 语义走查：scenario-review.md区分A/B/C主题缺口、现有页复用、受保护来源与具体diff批准边界；既有笔记模式不伪造会话来源字段、不调用会话写入器。
- 产物：运行目录changes.diff、published-files.json、approval-baseline.json、validation.json、scenario-review.md、run-report.md；before/可作恢复依据，恢复须保护后续编辑。
- 失败账本：fixture首次继承模板占位标签未替换，校验器按预期拒绝；修正fixture后复验通过，追加重试1次已用完。生产Skill和正式库无此失败副作用。
- 限制：管家直接场景走查与隔离样本，非独立Agent前向验证；未做完整导出同步、界面阅读、生产恢复或未来跨会话质量验证。不把指令文件存在视为行为已验证。
