# v1.5 相关正文摘录

仅为原文文本摘录，不包含图示或整份文档。

二 角色边界
角色或资产
生命周期
职责
边界
管家 Agent
长期
任务闭环所有者；目标、闭环定义、任务图、能力规划、Context Pack、调度、证据评估和重规划
不包办执行；不自行扩大权限、修改规则或发布长期能力
执行 Worker
临时
完成有边界的工作包并返回证据
不直接访问图书管理员或全量 Obsidian
Skill
长期复用
封装流程、脚本、样例和验收
不管理任务生命周期
图书管理员 Agent
长期离线
整理 Session、主题知识、经验状态、证据和 Skill 映射
不参与实时任务，不直接服务 Worker
任务经验注册表
长期结构化
记录任务签名、状态、频率、证据、适用范围和 Skill 版本
不替代 Obsidian 原文

Worker 与 Skill 规则
重复流程、固定步骤和验收标准优先沉淀为 Skill。
只有在上下文隔离、并行执行、独立复核或单独生命周期成立时才派生 Worker。
Worker 通过管家获得裁剪后的 Context Pack，不自行检索图书管理员。
六 规划与检索流程
Worker 不直接查询 Obsidian 或图书管理员。管家根据当前任务名称、任务签名和目标，读取注册表中的候选经验，再按调用频率降序选择，并把适用经验写入 Context Pack。
步骤
管家动作
输出
识别
提取当前任务名称、签名、目标和约束
经验查询条件
读取
扫描经验注册表，匹配任务名称或签名
候选经验列表
排序
按调用频率降序，频率相同按更新时间降序
经验优先级
筛选
检查已闭环或有待完善状态及适用范围
可用经验
装配
把经验摘要、不足和 Skill 版本写入 Context Pack
Worker 输入

附录 A 管家 Agent 控制面职责
管家 JARVIS 是长期任务闭环所有者与控制面。它接收人类伙伴的任务，定义目标、验收标准、证据要求和停止条件，规划所需 Skill、Worker 和上下文，组织执行并依据证据决定继续、重试、重规划或停止。
管家拥有规划和调度权，但不包办所有执行。它不能自行扩大权限、修改长期规则、批准自己的长期能力变更，也不能把候选经验直接升级为可信知识。
职责边界
职责
具体内容
关键产物
决策权限
人类伙伴接口
接收任务，澄清目标、优先级、约束、风险和时间
任务意图卡
可自主整理，关键目标需确认
闭环设计
定义成功、证据、停止条件、审批门和失败处理
Loop Contract
可提出，高风险任务需确认
能力规划
选择 Skill、已有 Worker、角色模板或新 Skill 候选
Capability Plan
可派生临时 Worker；长期能力需确认
任务规划
拆解任务图、依赖、里程碑、预算和并发策略
Task Graph
可自主规划，超预算需升级
上下文治理
读取经验注册表，选择知识、画像、Skill 和证据
Context Pack
可自主检索和裁剪
执行与观察
调度 Worker，记录状态、工具、结果、耗时和异常
Execution Trace
可在授权范围内调度
证据评估
检查产物、测试、引用和验收标准
Evaluation Record
可判定失败并有限重试
自主探索
生成假设、探索分支、预算和收敛条件
Exploration Plan
仅在明确预算和停止条件下自主进行
重规划
重试、替换 Worker、拆分任务或请求人工决策
Revised Plan
可在预算内重规划
演进提议
提出 Skill、经验和画像候选
Evolution Candidate
只能提议，不能自行发布

三档闭环
闭环模式
适用场景
执行方式
停止边界
直接闭环
简单、低风险、流程明确
目标 → Skill → 验证 → 交付
验收通过或确认无法完成
委派闭环
需要隔离、并行或独立复核
计划 → Context Pack → Worker → 汇总
Worker 失败或证据不足
探索闭环
路径不确定、需要假设和多分支研究
假设 → 探索计划 → 多 Worker → 收敛
预算耗尽、证据达标或风险升级

Loop Contract
管家为每个任务生成轻量闭环契约。简单任务可只填写核心字段，复杂和探索任务需完整填写。
loop_id: loop-2026-001owner: JARVIShuman_partner: userobjective: 完成可验收的任务目标value: 为什么值得做success_criteria: [可验证标准]evidence_requirements: [产物, 测试, 引用]deliverables: [docx, code, report, decision]constraints: [time, cost, tools, data, permissions]risk_level: low | medium | highloop_type: direct | delegated | exploratorycapability_plan:  skills: []  workers: []  librarian_inputs: []budget: {time_minutes, token_budget, max_workers}approval_gates: [目标确认, 高风险动作, 长期能力发布]stop_conditions: [验收通过, 预算耗尽, 证据不足, 连续失败, 风险升级]learning_targets: [Skill候选, 任务经验, 画像候选]
能力规划
管家的能力规划不是任意创建 Agent，而是在已有能力和候选能力之间做最小充分选择。
已有 Skill 能完成时，不派生 Worker。
需要上下文隔离、并行、独立复核或独立生命周期时，派生临时 Worker。
Worker 角色优先级为：通用角色模板 → 项目角色配置 → 新角色候选。
新 Skill 或长期 Agent 只生成候选，必须经过回放、人工确认和版本发布。
图书管理员经验作为规划输入；Worker 不直接访问图书管理员。
决策权限
权限级别
管家可以做什么
可自主执行
澄清后形成计划；查询经验；选择已有 Skill；派生临时 Worker；预算内重试；保存任务证据和候选经验
必须确认
新增长期 Skill/Agent；修改目标或验收标准；扩大范围；超预算探索；不可逆操作；跨项目敏感读取
绝对禁止
自行扩权；修改审批和沙箱规则；自行发布可信知识；删除原始证据；批准自己的长期能力变更

自主探索约束
自主探索不是无限制试错，而是围绕明确假设和证据阈值推进。管家必须记录探索假设、分支、预算、证据和收敛判断；当分支没有新增信息、超出预算或触碰高风险边界时，应停止并请求人工决策。
架构定义
管家 JARVIS 是长期任务闭环所有者与控制面。它接收人类伙伴的任务，负责澄清目标、定义验收与停止条件、设计任务图、选择或提出所需 Skill 与 Worker、装配 Context Pack、组织执行、观察证据、决定继续或重规划，并将任务经验提交给记忆与演进流程。管家不包办所有执行，也不拥有自行扩大权限、修改长期规则或发布可信知识的权力。