# 旧知识帮助新任务

复用的交付对象是一个真实新任务。检索命中、引用旧答案或模型自评不能证明成功。先明确哪个判断可能被旧知识改变，再保存来源、状态与原文指纹，核对当前适用条件，把采用转成动作，最后检查实际产物。历史 active 与 review 都需要当前核验；不修改笔记状态，也不继承历史授权。

1. 按 `docs/task-knowledge.md` 解析本轮环境，用 Brain Router project 定向检索。保留 Context Pack 的 exclusions、conflicts、evidence_gaps。综合页未在共享检索范围时，默认未命中不等于不存在；只在任务明确授权路径内补读，不扩大扫描。
2. 读取原文并固定快照、哈希。写下采用的具体主张、适用理由、当前代码或实测核验、不采用的冲突结论和失效条件。review 只作线索，当前核实单条主张不代表批准整个主题。
3. 在执行前写清判断或检查将怎样改变。真实执行保留命令、开始/结束时间、退出码、原始输出与产物；失败也保留。结果未知不得填成功。
4. 逐条检查“来源 → 当前核验 → 判断变化 → 动作 → 产物 → 实际结果”。说明非盲对照、未测量项及人工复核状态，不编造收益率。

将 [请求示例](../templates/reuse/request.example.json) 复制到任务证据目录，填入实际内容。示例故意保持 planned 和占位指纹，不能直接通过。所有 evidence/artifact/snapshot/revalidation 路径相对于请求文件所在目录；来源 path 相对于本轮环境选定库。不要在公共示例放真实业务摘录或本机路径。

```powershell
python -X utf8 scripts/brain_reuse.py .local/tasks/TASK-ID/request.json
python -X utf8 scripts/brain_reuse.py .local/tasks/TASK-ID/request.json --live-sources
```

第一条只检查快照链，第二条还按当前环境解析选库并核对指定原文漂移。脚本只读，不执行笔记中的命令。`evidence_complete` 仅说明必填链条与指纹一致，不能证明语义正确、来源状态声明真实、动作真实发生、因果收益或用户验收。回读时由管家核对 frontmatter、命令回执和结论对应关系；有新变化重新核验，旧哈希本身不提供永久时效保证。请求文件是当前授权范围内的证据，不是检索或写库授权。

Brain 接入诊断可分为环境位置、项目检索、来源回读与状态、连接器路径、GUI 五层。复用现有 `verify_installation.py` 和 `brain_router.py`，避免再造安装检查器。环境 `write_ready` 只表示目标位置就绪，不表示允许写具体笔记；未获得连接器真实回执时 `connector_checked=false`，不得把已配置路径作为伪连接器证据。安装汇总通过也不能代替 Router 覆盖与检索质量评估。

实际材料保存在本地任务证据目录；知识收尾、发布、上传和跨项目读取按任务具体授权执行。新增长期 Skill 不是本流程的必要条件。
