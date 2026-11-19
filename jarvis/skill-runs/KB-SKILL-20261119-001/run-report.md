# 知识整理Skill修订报告

任务JV-20261119-KB-SKILL-UPDATE，契约r1。用户批准后执行；状态：已交付待验收。Skill修订已落地，技术自检通过；未升级任何知识信任状态。

## 变更

- 修改已安装obsidian-curator/SKILL.md的触发描述及模式分流，逐字保留原会话整理流程。
- 新增references/vault-maintenance.md：来源白名单与快照、报告式巡检、受控标签、语义理由与唯一目标、三类主题缺口、有据草稿、哈希/人工编辑保护、集中diff复核、备份串行应用及增量/部分失败边界。
- 同步agents/openai.yaml现有描述与示例提示，保留自动调用策略。
- 同步JARVIS知识库管理员预检中的Skill模式说明。没有增加新Skill、修改curate.py或其他Skill实现，也未新增通用写入脚本。
- 项目特有标签、正式经验规则及预算由本地角色和任务提供，不写成全局要求。

## 验证与证据

quick_validate输出Skill is valid。validation.json记录12项检查通过：原导出流程和脚本保全、引用可发现、调用策略不变、真实原渲染器正反例、现有笔记样本保全，以及正式笔记仍匹配上一批批准哈希。scenario-review.md说明两类场景的实际检查、语义走查和限制。

approval-baseline.json保存用户批准、四份原文件基线与备份位置；changes.diff保存精确修订；published-files.json记录四个已修改/新增目标及未改脚本的SHA-256。before/为修改前副本。恢复前先核对当前文件仍匹配发布哈希，避免覆盖后续人工编辑；新增参考文件需要单独处理。

测试fixture最初有未替换的模板标签，被原校验器拒绝；只修正fixture后复验通过。同类额外重试1次已消耗；没有Skill生产运行失败、正式笔记写入或未知副作用。没有开启Worker，费用未计量。

未做独立Agent行为测试、完整导出/sync写入、Obsidian阅读视图或生产恢复演练。结构与样本检查不代表长期质量已验证。后续真实管理员运行应使用新入口并保留实际效果证据。
