# TASK-ID：三层本地候选复核

- 来源白名单与覆盖：当前任务、指定聊天/卡片/产物；记录哈希、可读来源及压缩、继承、附件和未取得原文的缺口。
- 业务验收：pending / accepted / not_required / returned；用户消息依据或明确无需验收的依据及证据文件。自检不得填 accepted。
- 笔记复核：pending / approved / skipped / returned；用户决定及适用候选版本。接受候选不批准正式写库。
- 当前状态：业务待验收优先用“已交付待验收”；业务已满足而笔记待审用“已交付待笔记复核”。

| 层级 | 本地文件或不生成理由 | 来源与验证证据 | 风险/证据缺口 | 建议结论 |
| --- | --- | --- | --- | --- |
| 任务总结 | 目标、改动、验收、结果与边界 | | | 接受/修改/保留待证据 |
| wiki 候选 | 可复用结论、条件、反例；无新增知识可记无候选 | | | 接受为候选/不采纳/继续验证 |
| 过程归档 | 必要业务要求、决定、发现和失败路径，标明筛选和缺失 | | | 接受覆盖/补来源 |

默认只保存在本任务 closure/；用户明确不整理或限定层级优先，已有旧卡的明确选择沿用。正式写库另提交具体目标、diff、基线、预算和冲突处理；候选复核不触发写库、发布或删除。

可使用 `scripts/task_closure.py TASK-ID` 对 `closure/manifest.json` 做只读核对。manifest 字段：schema_version=1、task_id、contract（file/sha256）、business 和 notes（status；非 pending 状态须 basis、decision 文件引用）、sources（任务内 file/sha256 列表）、coverage、layers（summary/wiki/archive）、risk_review（file/sha256）。引用均为任务目录相对路径。candidate 文件限于 closure/，wiki 可 no_candidate 并附 reason；用户限定的层可 excluded 并附 reason、decision 文件引用。notes=skipped 仍须具体决定证据。此工具不认证用户身份、不代替语义复核，也不生成正式库内容。
