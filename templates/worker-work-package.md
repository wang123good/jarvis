# 工作包：WORK-PACKAGE-ID

状态：2026-11-18 用户授权启用；用于通用临时 Worker，不表示注册了宿主原生命名 Agent。

角色：临时执行 Worker，向管家交付，不接管用户总任务。派发消息提供 `agents/worker.md` 和本次工作包的绝对路径。

## 派发前必须实例化的清单

| 字段 | 本次填写内容 |
|---|---|
| worker_id / task_id | 管家分配的实例/工作包标识 |
| parent_task_id / contract_revision / work_package_id / agent_id | 父任务及契约修订、稳定工作包 ID、实际宿主实例 ID；未创建不虚构 |
| plan_revision / step_ids / value_review | 绑定计划修订与步骤；每步目的、对应验收、产出使用者及管家价值审查结论；无收益不派发 |
| goal | 本包目标与交付用途 |
| revision_change_policy | 契约变化暂停受影响工作并交回管家；旧结果重验后才可复用 |
| inputs | 每个文件的 path、required、version_or_hash；未提供的资料不得自行补读 |
| dependencies | 执行依赖；缺失输入向管家返回缺口，不自行跨范围补齐 |
| context_summary | 管家裁剪的背景、相关经验及不足；没有经验明确填无 |
| skills | 实际文件路径和版本/哈希；不需要时填空数组 |
| outputs | 每项产物的 path、format 与用途；优先独立工作包目录，复核后由管家整合，避免旧执行覆盖新产物 |
| allowed_read_paths / allowed_write_paths | 明确文件或目录，尽量与其他 Worker 写入范围不重叠 |
| forbidden_actions / network_policy | 本次禁止动作；网络是否允许及限定用途 |
| may_spawn_children | 默认 false；确需时先交回管家决策 |
| effective_worker_budget | 本 Worker 检查点、同类失败额外重试、工具/费用边界及费用/token 上限或未采集；不是父任务总预算。预算耗尽、权限/范围变化、连续无进展或验收证据不足时停止 |
| budget_owner / retry_scope | 管家维护父任务 failure_key 账本；提供已用/预留/剩余额度，子包额度不超过总剩余；换包/返修不清零 |
| acceptance | 每项 criterion、verification、evidence_path；不填虚构测试路径 |
| review_owner / handoff_state | 管家复核；Worker completed 只代表执行完成 |
| recovery / action_records | 记录位置、输入基线、step_id/attempt_id、执行前意图、动作状态、产物/回执/验证、旧执行状态、已用/剩余额度、下一安全动作；未知副作用不重放，恢复不重置额度 |

返回结构按 `agents/worker.md` 的“返回格式”，包含父任务、契约修订、工作包及实际实例标识、failure_events、actions、结果、产物、检查证据和剩余事项。

该清单为指令约束，不声称具有强制沙箱能力。发生边界不足时返回 blocked/partial 并说明缺口，不自行扩大范围。

只有管家可接受/返修工作包；用户负责必要的最终业务验收。Skill 发布、画像与正式经验更新不属于 Worker 默认权限。
