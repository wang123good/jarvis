"""W1 frozen-snapshot audit. Standard library only; no external retrieval.
Exit 0: audit completed (may contain contract gaps); 2: invalid/missing input.
Semantic conclusions are explicit human-authored audit judgments, not NLP proofs.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('D:/codex-project/JARVIS/experiments/W1')
OUTPUT = ROOT / 'worker-output'
MANIFEST = ROOT / 'input-manifest.json'
NAMES = ('architecture-excerpts.md', 'steward-defaults.json', 'steward-entry.md', 'task-template.md')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def within(path, parent):
    return path.resolve().is_relative_to(parent.resolve())


def save(path, value):
    if not within(path, OUTPUT):
        raise ValueError('Output outside authorized worker-output')
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', type=Path, default=ROOT / 'inputs')
    parser.add_argument('--report-dir', type=Path, default=OUTPUT)
    args = parser.parse_args()
    if not within(args.report_dir, OUTPUT):
        parser.error('report-dir must remain inside worker-output')
    if args.input_dir.resolve() != (ROOT / 'inputs').resolve() and not within(args.input_dir, OUTPUT):
        parser.error('input-dir must be frozen inputs or an output-local fixture')
    args.report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        'audit_id': 'W1-01', 'status': 'running',
        'generated_at_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'Four frozen files and input-manifest.json only; no source-document traversal',
        'input_dir': str(args.input_dir.resolve()),
        'method': {'integrity': 'SHA-256 and byte count; exact expected filename set',
                   'presence': 'Explicit text anchors and JSON parsing',
                   'semantics': 'Authored judgments tied to frozen line evidence; not keyword-inferred sufficiency'},
        'errors': [], 'integrity': [],
        'adopted_execution_limits': {'workers': 1, 'descendants': 0, 'checkpoint_minutes': 10,
                                     'max_additional_retries_same_failure': 1,
                                     'network': False, 'token_usage': None, 'cost': None},
    }
    try:
        raw_manifest = MANIFEST.read_bytes()
        manifest = json.loads(raw_manifest.decode('utf-8-sig'))
        report['manifest'] = {'path': str(MANIFEST), 'sha256': sha(raw_manifest),
                              'source_document_hash_claim': manifest.get('architecture_sha256'),
                              'source_document_verified': False,
                              'note': 'Only excerpt verified; original architecture document is outside allowed inputs'}
        entries = manifest['files']
        mapped = {}
        for entry in entries:
            name = entry['path'].replace('\\', '/').rsplit('/', 1)[-1]
            if name not in NAMES or name in mapped:
                raise ValueError('Unexpected or duplicate manifest filename: ' + name)
            expected_path = (ROOT / 'inputs' / name).resolve()
            if Path(entry['path']).resolve() != expected_path:
                raise ValueError('Manifest path outside frozen allowlist: ' + name)
            mapped[name] = entry
        if set(mapped) != set(NAMES):
            raise ValueError('Manifest does not contain exactly four expected files')
        documents = {}
        for name in NAMES:
            path = args.input_dir / name
            if not within(path, args.input_dir):
                raise ValueError('Resolved input escapes selected input directory: ' + name)
            if not path.is_file():
                report['errors'].append({'code': 'MISSING_INPUT', 'file': name, 'path': str(path),
                                         'message': 'Required frozen input missing; stop without knowledge-base fallback'})
                continue
            data = path.read_bytes()
            entry = mapped[name]
            item = {'file': name, 'manifest_path': entry['path'], 'read_path': str(path),
                    'expected_bytes': entry['bytes'], 'actual_bytes': len(data),
                    'expected_sha256': entry['sha256'], 'actual_sha256': sha(data)}
            item['passed'] = item['actual_sha256'].lower() == item['expected_sha256'].lower() and len(data) == entry['bytes']
            report['integrity'].append(item)
            if not item['passed']:
                report['errors'].append({'code': 'INTEGRITY_MISMATCH', 'file': name})
            documents[name] = data.decode('utf-8-sig')
        if report['errors']:
            report['status'] = 'blocked'
            report['semantic_audit_performed'] = False
            save(args.report_dir / 'audit-report.json', report)
            print(json.dumps({'status': 'blocked', 'errors': report['errors'], 'exit_code': 2}, ensure_ascii=False), file=sys.stderr)
            return 2

        def evidence(name, anchor):
            matches = [{'file': name, 'line': i, 'text': line} for i, line in enumerate(documents[name].splitlines(), 1) if anchor in line]
            if len(matches) != 1:
                raise ValueError('Evidence anchor expected exactly once: ' + name + ': ' + anchor)
            return matches[0]

        entry = lambda anchor: evidence('steward-entry.md', anchor)
        template = lambda anchor: evidence('task-template.md', anchor)
        arch = lambda anchor: evidence('architecture-excerpts.md', anchor)
        defaults = json.loads(documents['steward-defaults.json'])
        report['configuration_actual_values'] = [
            {'json_pointer': '/' + key, 'value': value,
             'evidence': evidence('steward-defaults.json', '"' + key + '"' + ':')}
            for key, value in defaults.items()
        ]
        report['configuration_consistency'] = {
            'passed': all((defaults['default_mode'] == 'direct', defaults['max_workers_total'] == 2,
                           defaults['max_workers_concurrent'] == 2, defaults['max_additional_retries_same_failure'] == 2,
                           defaults['max_exploration_branches'] == 2, defaults['active_work_review_minutes'] == 20,
                           defaults['budget_review_fraction_when_measurable'] == 0.8,
                           defaults['enforcement'] == 'instruction-level-soft-limits')),
            'entry_evidence': [entry('直接模式 Worker 为 0'), entry('约 80%')],
            'note': 'Checks listed frozen defaults against entry wording; does not enforce budgets at runtime'}
        report['dimension_reviews'] = [
            {'dimension': '工作包输入', 'presence': 'present_at_policy_level', 'semantic_sufficiency': 'partial',
             'evidence': [entry('Worker 工作包须含'), template('输入、经验与来源')],
             'assessment': '已要求裁剪背景、来源和版本/哈希，但没有逐 Worker 输入清单、必需性和缺失材料处理字段。'},
            {'dimension': '工作包输出', 'presence': 'present_at_task_level', 'semantic_sufficiency': 'partial',
             'evidence': [template('交付与验收标准'), template('记录实际验证')],
             'assessment': '有任务级交付和产物路径记录，没有逐 Worker 输出文件名、格式与返回结构。'},
            {'dimension': '写入范围', 'presence': 'generic_permissions_only', 'semantic_sufficiency': 'insufficient',
             'evidence': [entry('Worker 工作包须含'), template('范围及不做事项')],
             'assessment': '有权限和范围原则，缺少逐 Worker 允许读取/写入目录、禁止动作及越界处理实例槽位；不代表已有系统隔离。'},
            {'dimension': '预算', 'presence': 'present', 'semantic_sufficiency': 'partial',
             'evidence': [template('本次预算'), entry('这些是可调整')],
             'assessment': '总量与计量未知项已覆盖；未要求逐 Worker 采用值、共享预算记账和到限返回方式。'},
            {'dimension': '状态/阻碍返回', 'presence': 'task_status_and_generic_return_requirement', 'semantic_sufficiency': 'insufficient',
             'evidence': [template('状态：'), entry('返回要求')],
             'assessment': '任务状态不是 Worker 返回协议；未列举完成/部分完成/阻塞/失败、阻碍证据、剩余工作和下一步字段。'},
            {'dimension': '验收责任', 'presence': 'steward_accountability_and_selfcheck_distinction', 'semantic_sufficiency': 'partial',
             'evidence': [entry('对最终成果负责'), template('自检和用户验收分开')],
             'assessment': '管家总责已明确；尚无逐项验收负责人、复核证据以及 Worker 完成到管家验收的交接字段。'},
        ]
        report['findings'] = [
            {'id': 'F1', 'importance': 'high', 'title': '缺少可实例化的逐 Worker 输入/产物清单',
             'evidence': [entry('Worker 工作包须含'), template('输入、经验与来源'), template('交付与验收标准'), arch('把经验摘要、不足和 Skill 版本写入 Context Pack')],
             'impact': '管家任务卡包含信息不代表 Worker 收到完整且冻结的输入；产物可能无法按约定位或复查。',
             'recommendation': '增加 worker_id、objective、inputs[{path,version_or_hash,required}]、context_summary、experience_and_limitations、skills（可明确为空）、outputs[{path,format}]；输入缺失立即返回阻碍，不自行补读。'},
            {'id': 'F2', 'importance': 'high', 'title': '权限原则未落到具体路径与动作边界',
             'evidence': [entry('预算与权限'), template('范围及不做事项'), arch('不直接访问图书管理员或全量 Obsidian')],
             'impact': '不同 Worker 可能重写共享文件，或误把来源路径当成可自行读取的授权。',
             'recommendation': '增加 allowed_read_paths、allowed_write_paths、forbidden_actions、network_policy、may_spawn_children 与 boundary_violation_action；明确这些是指令约束，不能宣称运行时隔离。'},
            {'id': 'F3', 'importance': 'medium', 'title': '任务总预算未明确分配到 Worker',
             'evidence': [template('本次预算'), entry('最多额外重试 2 次'), arch('拆解任务图、依赖、里程碑、预算和并发策略')],
             'impact': '并行 Worker 可能分别采用完整默认值；重试计数和检查点的责任不明确。',
             'recommendation': '增加 effective_worker_budget{checkpoint_minutes,max_additional_retries,deadline_or_stop,token_or_cost_limit_or_unknown}、budget_owner 和 retry_scope；总数/并发由管家汇总。'},
            {'id': 'F4', 'importance': 'high', 'title': 'Worker 状态与阻碍返回结构未定义',
             'evidence': [entry('返回要求'), template('状态：'), arch('调度 Worker，记录状态、工具、结果、耗时和异常')],
             'impact': '管家难以区分部分成功与彻底失败，也难以据证据选择重试、替换或停止。',
             'recommendation': '固定返回 status(completed/partial/blocked/failed)、summary、artifacts、checks、findings、blockers、remaining_risks、changed_files、next_action；未知耗时/费用用 null 并说明。'},
            {'id': 'F5', 'importance': 'medium', 'title': '验收总责明确但逐项交接证据未结构化',
             'evidence': [entry('对最终成果负责'), template('自检和用户验收分开'), arch('检查产物、测试、引用和验收标准')],
             'impact': 'Worker 的 completed 可能被误读成任务已验收；验收标准与测试证据缺少明确映射。',
             'recommendation': '增加 acceptance[{criterion,verification,evidence_path}]、review_owner、handoff_state；Worker 只报告执行/自检，管家复核后单独记录已交付待验收或后续状态。'},
        ]
        report['semantic_audit_performed'] = True
        report['readiness'] = 'Principles support manual delegation; structured reliable dispatch needs five localized contract additions'
        report['status'] = 'completed'
        report['blockers'] = []
        report['remaining_risks'] = [
            '仅针对冻结快照；未检查当前主会话正在修改的职责文档，也未修改任何职责文档。',
            '原架构 DOCX 及图示未读取；manifest 中原文哈希只是声明，不能验证摘录完整性。',
            '缺失输入用例验证本审计脚本的失败行为，不能证明通用 Worker 沙箱、权限或调度系统有效。',
            '语义评价是显式人工判断；字段存在性和哈希通过不等于语义或系统成熟度通过。',
            'token/费用未采集；没有运行时硬预算或系统访问隔离验证。',
        ]
        save(args.report_dir / 'audit-report.json', report)
        lines = ['# W1-01 委派准备审计', '', 'status: completed（审计完成，未代表配置已可直接可靠派发或正式发布）', '',
                 '四个冻结文件的 SHA-256 与字节数均匹配；实际配置值、定位和六维审查见 audit-report.json。', '',
                 '结论：原则层面可支持人工装配委派；可靠派发还需要下面五项局部契约补充。当前任务卡不是独立 Worker 工作包模板。', '',
                 '默认值：direct；Worker 总数/并发 2/2；同类额外重试 2；探索分支 2；主动工作检查点 20 分钟；可计量时 80% 检查。',
                 '这些是被冻结的项目配置。本实验实际采用 1 Worker、不派生后代、10 分钟检查点、同类额外重试最多 1 次；token/费用未知。', '']
        for finding in report['findings']:
            refs = '；'.join(f"{e['file']}:{e['line']}" for e in finding['evidence'])
            lines.extend([f"## {finding['id']} {finding['title']}", '', f"证据：{refs}。", '',
                          '影响：' + finding['impact'], '', '最小建议：' + finding['recommendation'], ''])
        lines.extend(['## 复现与限制', '',
                      '正常运行退出 0 表示审计完成，不表示没有缺口；缺失必需输入退出 2，详细记录见 execution-checks.json。', '',
                      *['- ' + risk for risk in report['remaining_risks']], '',
                      'next_action：管家复核文件和实际退出码，再决定是否补充工作包模板；本 Worker 不批准正式发布。', ''])
        (args.report_dir / 'audit-conclusions.md').write_text('\n'.join(lines), encoding='utf-8')
        print(json.dumps({'status': 'completed', 'hashes_passed': len(report['integrity']),
                          'dimensions_reviewed': len(report['dimension_reviews']), 'findings': len(report['findings']),
                          'report': str(args.report_dir / 'audit-report.json')}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report['status'] = 'blocked'
        report['semantic_audit_performed'] = False
        report['errors'].append({'code': 'INPUT_OR_AUDIT_ERROR', 'message': str(exc)})
        save(args.report_dir / 'audit-report.json', report)
        print(json.dumps({'status': 'blocked', 'errors': report['errors']}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
