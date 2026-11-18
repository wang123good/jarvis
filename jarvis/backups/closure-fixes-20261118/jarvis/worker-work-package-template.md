# 工作包：WORK-PACKAGE-ID

状态：2026-11-18 用户授权启用；用于通用临时 Worker，不表示注册了宿主原生命名 Agent。

派发时同时提供 `jarvis/worker.md` 的绝对路径。管家创建实例后填写实际 agent_id，不预编造宿主实例标识。

- 角色：临时执行 Worker；向管家交付，不接管用户总任务。
- 目标与交付用途：
- 允许读取的输入和来源：
- 当前经验、具体不足和真实 Skill：无则写无。
- 允许写入目录/文件：
- 产物格式与路径：
- 验收标准与需要实际执行的检查：
- 预算：时间检查点、同类失败重试、工具/费用边界；默认不派生后代。
- 依赖与缺失输入处理：向管家返回缺口，不自行跨范围补齐。
- 停止条件：预算耗尽、权限/范围变化、连续无进展或验收证据不足。
- 返回要求：task_id、status、summary、artifacts、checks、findings、blockers、remaining_risks、changed_files、next_action。

## 派发前必须实例化的清单

| 字段 | 本次填写内容 |
|---|---|
| worker_id / task_id | 管家分配的实例/工作包标识 |
| inputs | 每个文件的 path、required、version_or_hash；未提供的资料不得自行补读 |
| context_summary | 管家裁剪的背景、相关经验及不足；没有经验明确填无 |
| skills | 实际文件路径和版本/哈希；不需要时填空数组 |
| outputs | 每项产物的 path、format 与用途 |
| allowed_read_paths / allowed_write_paths | 明确文件或目录，尽量与其他 Worker 写入范围不重叠 |
| forbidden_actions / network_policy | 本次禁止动作；网络是否允许及限定用途 |
| may_spawn_children | 默认 false；确需时先交回管家决策 |
| effective_worker_budget | 本 Worker 检查点、额外重试、停止条件、费用/token 上限或未采集；不是整个任务总预算 |
| budget_owner / retry_scope | 管家汇总预算；本 Worker 只记本工作包内同类失败计数 |
| acceptance | 每项 criterion、verification、evidence_path；不填虚构测试路径 |
| review_owner / handoff_state | 管家复核；Worker completed 只代表执行完成 |

该清单为指令约束，不声称具有强制沙箱能力。发生边界不足时返回 blocked/partial 并说明缺口，不自行扩大范围。

只有管家可接受/返修工作包；用户负责必要的最终业务验收。Skill 发布、画像与正式经验更新不属于 Worker 默认权限。
