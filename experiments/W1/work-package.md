# W1-01：管家配置的委派准备审计

## 目标

独立审计所给管家入口、默认值与任务模板，判断是否足以可靠派发给临时 Worker，找出最小需要补充的契约字段；不判断整体系统是否成熟。

## 输入与上下文

只使用 `D:/codex-project/JARVIS/experiments/W1/inputs/` 四个冻结文件及 `input-manifest.json`。其中 architecture-excerpts.md 是管家从 v1.5 摘录的相关正文。正式经验当前为空，无可用经验或专用 Skill 注入；任务可直接用 Python 标准库和材料分析完成，不得虚构 Skill。

## 执行与写入范围

读取输入；在 `D:/codex-project/JARVIS/experiments/W1/worker-output/` 创建并实际运行一个审计脚本，产出机器报告 JSON 和面向管家的短 Markdown 结论。不改其他文件；不读取 Obsidian、历史聊天、隔离目录、API 密钥或外部网络。允许读取本工作包和必要工具/系统说明。

## 验收标准

1. 核对冻结输入哈希，并提供配置实际值及定位。
2. 区分“字段/文件存在性”和“语义是否足够”；至少审查工作包输入输出、写入范围、预算、状态/阻碍返回、验收责任。
3. 对比架构，列最多 5 项重要缺口，含证据位置、影响、建议；不存在缺口就如实说明，不凑数。
4. 实际运行脚本正常输入场景；另在 worker-output 内创建缺失输入场景，返回清晰错误、非零退出码，不尝试访问知识库补齐。不得故意破坏冻结输入。
5. 除 output 范围外不做项目业务写入；报告自述只作为证据之一，管家将复核真实文件和执行结果。

## 预算与停止

本工作包 1 个 Worker、不派生后代；约 10 分钟检查点，同类失败最多额外重试 1 次。不启用新增付费服务；token/费用未知不编造。缺少关键材料或范围不够时以 blocked/partial 返回管家，不自行扩大访问范围。

## 返回契约

最终回复包含 status（completed / partial / blocked / failed）、summary、artifacts、checks、findings、blockers、remaining_risks、changed_files、next_action。不要向用户请求审批，由管家汇总决策；不要自行批准正式发布。
