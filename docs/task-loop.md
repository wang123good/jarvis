# 长路径执行

明确执行任务默认完整闭环，但不强制调用本运行器。已批准的任务有多步依赖、各步可以验证，且适合由 JARVIS 在本地串行推进时，可选用长路径模式。用户复核任务目标、验收、范围和预算后，JARVIS 连续执行并修复失败。运行器依据任务记录决定下一步是否可领用。任务卡和专属对话仍按任务生命周期管理。

## 启动

在 `.local/tasks/<task_id>/contract.md` 保留获批的契约修订，将执行计划写成 JSON。契约文件是本轮固定基线，过程记录和计划文件另存。绑定和接收确认应在 init 前落卡；运行中状态及标题回执写 checkpoint.md 等独立记录，避免仅更新进展就改变契约指纹。ready_to_deliver 仅表示计划证据齐全，不代表用户业务验收或笔记复核通过。运行器检查契约的文件指纹，批准来源及计划与契约的一致性由 JARVIS 复核。

```json
{
  "contract_revision": 1,
  "plan_revision": 1,
  "approval": "用户批准消息的定位",
  "expires_at": "2030-01-01T10:00:00+08:00",
  "max_attempts": 6,
  "max_additional_retries": 2,
  "acceptance": {"tests": "目标回归用例通过"},
  "steps": [
    {"id": "baseline", "depends_on": [], "acceptance": [], "action": "复核基线",
     "verify": "记录待改文件及可复现证据", "failure_key": "baseline"},
    {"id": "fix", "depends_on": ["baseline"], "acceptance": ["tests"], "action": "修复并运行回归用例",
     "verify": "保存回归测试退出码和输出", "failure_key": "regression"}
  ]
}
```

将示例时间和预算换成实际获批值。到期时间限制领用新步骤，所有领用都计入总次数。JARVIS 还需检查契约中的主动执行时间、费用和探索分支预算。步骤按依赖顺序列出，全部验收项须被覆盖。

```powershell
python scripts/task_loop.py TASK-ID init .local/tasks/TASK-ID/plan.json
python scripts/task_loop.py TASK-ID next
python scripts/task_loop.py TASK-ID record <attempt-id> passed --evidence checks/attempt-1.txt
```

## 推进和恢复

1. 每轮先调用 `next`。返回 `execute` 时保存尝试 ID，按指定动作执行、核验实际结果，并把证据保存到任务目录中的独立文件。涉及外部动作时按任务规程额外落盘对象、授权及核对方法。
2. 用 `record` 提交 `passed`、`failed`、`unknown` 或 `not-run`。步骤通过后检查后继。失败后读证据，预算允许时修正并重验。需要改计划时用 `replan <plan.json> --evidence <理由文件>`，递增计划修订号并提交完整步骤列表。运行器保留仍有有效证据且输入步骤有效的成果，重用原失败账本。
3. 中断后按任务 ID 调用 `status`。在途尝试得到 `reconcile` 时，先核实旧执行是否仍活动，再查阅产物或外部回执。仍无法确认时记录 `unknown` 并等待查证。只有证据表明旧动作未发生时才记 `not-run`。数据库在领用前持久化尝试，防止新进程重复领用。
4. 在检查点用 `pause` 和 `resume` 控制继续执行。预算耗尽、连续两次验证失败而无步骤通过、证据变化或契约变化都由 JARVIS 按任务规程处置。契约变化后先复核影响和剩余预算，再由管家按恢复规程处理。运行器会卡住旧批准的执行入口。
5. `ready_to_deliver` 返回每项验收的证据位置和文件指纹。JARVIS 核对当前产物和整体结果，然后按任务卡交付或提交用户验收。

运行数据存于任务目录的 `loop.sqlite3`。每次领用与结果都提交到同一数据库，证据文件应按尝试独立保留。运行器校验结构、预算、依赖和证据文件，证据内容及外部事实由 JARVIS 验证。首版由活动对话驱动，停止对话后可从检查点人工唤起。到期时运行器拦截新步骤，已在途的进程由执行者按宿主能力处理。
