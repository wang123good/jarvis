import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VAULT = Path('D:/个人知识库')
NOTE = '01_项目/JARVIS/50_图书管理员/candidates/2026-11-18 F1 真实Skill核验与经验清理草稿.md'


def main():
    e = json.loads((ROOT / 'source-evidence.json').read_text(encoding='utf-8'))
    skill = next(s for s in e['skills'] if s['skill_id'] == 'report-analysis-loop')
    raw = e['source_raw']
    refs = '\n'.join(f"- source.jsonl 第 {r['record']} 行：{r['text'].strip()}" for r in e['selected_user_records'])
    sections = {
        '目标': '防止把候选 Skill 名称或示例版本当成真实能力写入正式经验注册表。',
        '成功标准': '无真实对应 Skill 的条目退出正式注册表；备份可核对；历史复核保留；不把结构校验通过等同于复用成功。',
        '交付物': '清理清单、隔离备份、清理校验，以及本条待复核经验草稿。',
        '业务背景': 'JARVIS 单用户试用阶段，用户要求减少数据污染并明确接受清理建议。',
        '技术背景': '原 7 条样本引用的 Skill ID 未找到对应本地文件；实际可用的 report-analysis-loop 要求基于证据区分事实、判断与建议。',
        '输入资料': f'[[{raw}]]；experiments/R1/evidence-audit.json；experiments/R2/cleanup-manifest.json 与 cleanup-check.json。',
        '时间、成本与权限约束': '仅本项目与指定 Skill 文件；用户批准移除旧条目，不自动批准新经验、长期 Skill 或全局画像。',
        '初始假设': '先前样本中的 Skill 映射被当成可用能力；R1 核查未发现同名文件，因此该假设不能保留。',
        '实际步骤': '1. 按注册 ID 核对本地技能目录及缓存。\n2. 报告文件存在性与版本证据缺口。\n3. 用户要求移除后，先做字节备份并核对哈希。\n4. 移除 7 条正式记录、隔离 9 份 Markdown，保留历史复核。\n5. 检查查询为 0、备份匹配以及未批准恢复被拒绝。',
        '关键转折': '用户明确要求去除无对应 Skill 的经验；因此没有通过删除 skill_links 来保留正式记录。',
        '关键决策': '选择移除并隔离，保留原 ID 与历史证据。相似功能的其他 Skill 只能重新核对后提出新映射，不能自动替代。代价是当前正式经验为 0，暂时没有正式复用样本。',
        '结果与评价': '已有磁盘产物证明清理执行完成；用户“建议可行”和后续 R2 确认是接受范围的证据；本草稿未获单独入库批准。',
        '最终效果': '7 条无对应 Skill 的旧样本已退出正式注册表；清理检查 9 项通过。当前整理为真实 Skill 关联草稿，尚未成为正式可复用经验。',
        '未解决项': '正式经验仍为 0；本草稿需人工复核；新会话真实任务复用、版本兼容和长期收益未验证。',
        '残余风险': '同名文件或内容哈希只能识别 Skill 文件，不证明能力匹配、整个支持目录一致或执行质量。来源导出存在压缩、附件及独立事务覆盖限制。',
        '下次应该怎么做': '先查正式经验；无匹配则明确说明；核实 Skill 文件及版本或哈希后，才提出有来源的候选；入库必须得到人工复核。',
        '不应该怎么做': '不凭名称创造 Skill 版本，不凭 approved 认定已复用成功，不自动恢复被隔离记录，不把所有普通知识笔记都强制绑定 Skill。',
        '可复用步骤': '登记任务与范围 → 定位实际 Skill 文件 → 固定来源与内容哈希 → 核对适用性 → 草稿与差异 → 人工复核 → 新任务验证。',
        '失败与坑': '原结构校验未覆盖 Skill 存在性与全部更新时间；空注册表校验通过只代表结构一致，不能宣称复用成功。',
        '可进入领域层的知识': '本次不写领域层；规则的普适性仍需其他任务检验。',
        '可进入资源层的资料': '本次不新增资源层；实际 Skill 文件为本地工具依据，记录路径与内容哈希即可。',
        '仅适用于当前项目的知识': 'JARVIS 正式任务经验需真实 Skill 关联；普通知识笔记不受此强制约束。',
        '证据与来源': f'原始对话：[[{raw}]]\n{refs}\n- 本地执行证据：D:/codex-project/JARVIS/experiments/R2/cleanup-check.json（9 项检查均为 true）。\n- 真实 Skill：{skill["path"]}\n- SKILL.md SHA-256：{skill["sha256"]}；未发现语义版本，不编造版本号。\n- 该 Skill 支撑证据评审方法，不单独提供注册表清理工具。',
        '相关笔记': '[[01_项目/JARVIS/00_项目索引|项目索引]]\n[[01_项目/JARVIS/30_实验记录/2026-11-18 R2 注册表清理与复用准备|原清理记录]]\n[[01_项目/JARVIS/10_设计笔记/JARVIS 项目协作约定|已确认约定]]',
        '复核记录': '2026-11-18：按真实来源生成草稿。历史清理获接受不等于本条新经验已获入库批准。'
    }
    fields = {'title': '真实 Skill 核验与无效经验清理', 'type': 'task-experience', 'task_id': 'jarvis-task-008', 'project': 'jarvis', 'status': 'draft', 'created': '2026-11-18', 'updated': '2026-11-18', 'confidence': 'medium', 'source_thread': e['thread'], 'source_raw': raw, 'source_hash': e['source_hash'], 'topics': ['skill-verification', 'experience-registry', 'evidence-review'], 'tags': ['project/jarvis', 'task-experience', 'draft'], 'skill_links': [{'skill_id': skill['skill_id'], 'skill_path': skill['path'], 'skill_content_sha256': skill['sha256'], 'semantic_version': None}], 'formal_registry_member': False}
    batch = {'project_dir': 'D:/codex-project/JARVIS', 'notes': [{'path': NOTE, 'template': 'Codex任务经验模板.md', 'fields': fields, 'sections': sections}], 'tasks': {e['thread']: [{'task_id': 'jarvis-task-008', 'note': NOTE, 'status': 'draft', 'source_hash': e['source_hash']}]}}
    (ROOT / 'candidate-batch.json').write_text(json.dumps(batch, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    manifest = {'note': NOTE, 'status': 'draft', 'source_hash': e['source_hash'], 'skill': skill, 'formal_registry_member': False}
    (ROOT / 'candidate-proposal.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == '__main__':
    main()
