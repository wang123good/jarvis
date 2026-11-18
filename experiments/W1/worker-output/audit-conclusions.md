# W1-01 委派准备审计

status: completed（审计完成，未代表配置已可直接可靠派发或正式发布）

四个冻结文件的 SHA-256 与字节数均匹配；实际配置值、定位和六维审查见 audit-report.json。

结论：原则层面可支持人工装配委派；可靠派发还需要下面五项局部契约补充。当前任务卡不是独立 Worker 工作包模板。

默认值：direct；Worker 总数/并发 2/2；同类额外重试 2；探索分支 2；主动工作检查点 20 分钟；可计量时 80% 检查。
这些是被冻结的项目配置。本实验实际采用 1 Worker、不派生后代、10 分钟检查点、同类额外重试最多 1 次；token/费用未知。

## F1 缺少可实例化的逐 Worker 输入/产物清单

证据：steward-entry.md:15；task-template.md:8；task-template.md:5；architecture-excerpts.md:53。

影响：管家任务卡包含信息不代表 Worker 收到完整且冻结的输入；产物可能无法按约定位或复查。

最小建议：增加 worker_id、objective、inputs[{path,version_or_hash,required}]、context_summary、experience_and_limitations、skills（可明确为空）、outputs[{path,format}]；输入缺失立即返回阻碍，不自行补读。

## F2 权限原则未落到具体路径与动作边界

证据：steward-entry.md:15；task-template.md:6；architecture-excerpts.md:17。

影响：不同 Worker 可能重写共享文件，或误把来源路径当成可自行读取的授权。

最小建议：增加 allowed_read_paths、allowed_write_paths、forbidden_actions、network_policy、may_spawn_children 与 boundary_violation_action；明确这些是指令约束，不能宣称运行时隔离。

## F3 任务总预算未明确分配到 Worker

证据：task-template.md:9；steward-entry.md:28；architecture-excerpts.md:77。

影响：并行 Worker 可能分别采用完整默认值；重试计数和检查点的责任不明确。

最小建议：增加 effective_worker_budget{checkpoint_minutes,max_additional_retries,deadline_or_stop,token_or_cost_limit_or_unknown}、budget_owner 和 retry_scope；总数/并发由管家汇总。

## F4 Worker 状态与阻碍返回结构未定义

证据：steward-entry.md:15；task-template.md:3；architecture-excerpts.md:85。

影响：管家难以区分部分成功与彻底失败，也难以据证据选择重试、替换或停止。

最小建议：固定返回 status(completed/partial/blocked/failed)、summary、artifacts、checks、findings、blockers、remaining_risks、changed_files、next_action；未知耗时/费用用 null 并说明。

## F5 验收总责明确但逐项交接证据未结构化

证据：steward-entry.md:3；task-template.md:18；architecture-excerpts.md:89。

影响：Worker 的 completed 可能被误读成任务已验收；验收标准与测试证据缺少明确映射。

最小建议：增加 acceptance[{criterion,verification,evidence_path}]、review_owner、handoff_state；Worker 只报告执行/自检，管家复核后单独记录已交付待验收或后续状态。

## 复现与限制

正常运行退出 0 表示审计完成，不表示没有缺口；缺失必需输入退出 2，详细记录见 execution-checks.json。

- 仅针对冻结快照；未检查当前主会话正在修改的职责文档，也未修改任何职责文档。
- 原架构 DOCX 及图示未读取；manifest 中原文哈希只是声明，不能验证摘录完整性。
- 缺失输入用例验证本审计脚本的失败行为，不能证明通用 Worker 沙箱、权限或调度系统有效。
- 语义评价是显式人工判断；字段存在性和哈希通过不等于语义或系统成熟度通过。
- token/费用未采集；没有运行时硬预算或系统访问隔离验证。

next_action：管家复核文件和实际退出码，再决定是否补充工作包模板；本 Worker 不批准正式发布。
