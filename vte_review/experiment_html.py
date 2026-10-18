"""Local HTML reading entry for VTE experiment records; raw audit files stay intact."""
from datetime import datetime, timedelta, timezone
from html import escape
import os
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from .longitudinal import load


def render_value(value):
    if isinstance(value, dict):
        return '<table class="record-table"><tbody>'+''.join('<tr><th scope="row">'+escape(str(k))+'</th><td>'+render_value(v)+'</td></tr>' for k,v in value.items())+'</tbody></table>'
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            return ''.join('<details class="record-item"><summary>'+escape(str(item.get('id') or item.get('case') or item.get('case_id') or ('记录 '+str(i+1))))+'</summary>'+render_value(item)+'</details>' for i,item in enumerate(value))
        return '<ul>'+''.join('<li>'+render_value(v)+'</li>' for v in value)+'</ul>' if value else '<span class="muted">无</span>'
    return escape(str(value)) if value is not None else '<span class="muted">未记录</span>'


def write_experiment_html(out):
    out = Path(out)
    dataset = out.parent
    repo = dataset.parents[1]
    timestamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S 北京时间')
    manifest = load(dataset/'manifest.json', {})
    expected = sum(c.get('timepoints', 0) for c in manifest.get('cases', []))
    progress = load(out/'progress.json', {})
    final = load(out/'final-status.json', {})
    # A frozen comparison cohort must not grow when a later reviewed batch arrives.
    expected = final.get('target_nodes') or progress.get('prepared_nodes') or expected
    names = {'baseline':'基础模型', 'rag':'单模型 RAG', 'synthesis':'审核前首次汇总'}
    def link(path, label):
        if not path.exists():
            return '<span class="muted">'+escape(label)+'（待生成）</span>'
        relative = os.path.relpath(path, dataset).replace('\\', '/')
        return '<a href="'+quote(relative, safe='/')+'">'+escape(label)+'</a>'
    rows = ''
    for key, label in names.items():
        completed = progress.get('methods', {}).get(key, {}).get('completed', 0)
        rows += '<tr><td>'+label+'</td><td>'+str(completed)+'</td><td>'+str(expected or '待确定')+'</td><td>'+str(max(0, expected-completed))+'</td></tr>'
    state = {'complete':'全部完成', 'failed_outputs':'运行结束，存在输出失败', 'source_wait_timeout':'等待源数据超时'}.get(final.get('status'), '尚无完成记录；以当前进度为准')
    sections = '<section><h2>本次对照实验</h2><p>'+escape(state)+'</p><table><thead><tr><th>组别</th><th>已完成</th><th>目标时间点</th><th>尚缺</th></tr></thead><tbody>'+rows+'</tbody></table><p>'+link(out/'clinical_results.html','查看各组完整回答（可搜索、筛选）')+'</p><p>第三组原样提取原流程审核前首次汇总。对照程序不重跑完整审核修订系统；完整系统的批次进度见下方。运行完成不代表临床评审通过。</p></section>'
    for previous in sorted(dataset.glob('comparison-*')):
        if previous.is_dir() and previous.resolve()!=out.resolve() and (previous/'progress.json').exists():
            old=load(previous/'progress.json',{})
            counts='；'.join(names.get(k,k)+' '+str(v.get('completed',0))+' 份' for k,v in old.get('methods',{}).items())
            sections+='<section><h2>'+escape(previous.name)+'</h2><p>'+escape(counts)+'</p><p>'+link(previous/'clinical_results.html','查看该批原始报告')+'</p></section>'
    sources = [(out/'protocol.json', '本次对照：实验设置与比较边界'),
               (out/'verification.json', '本次对照：文件与来源核验'),
               (out/'final-status.json', '本次对照：最终执行状态')]
    for batch in sorted((dataset/'processing').glob('*')):
        if not batch.is_dir(): continue
        if (batch/'实验记录.html').exists():
            sections += '<section><h2>'+escape(batch.name)+'：完整审核修订系统</h2><p>'+link(batch/'实验记录.html','查看本批进度与报告')+'</p></section>'
        sources += [(batch/'protocol.json', batch.name+'：实验方案'),
                    (batch/'progress.json', batch.name+'：完整方法进度'),
                    (batch/'input-verification.json', batch.name+'：输入核验')]
    for path, title in sources:
        value = load(path)
        if value is not None:
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
            sections += '<section><details><summary>'+escape(title)+'</summary><p class="muted">来源更新：'+modified+' 北京时间</p>'+render_value(value)+'</details></section>'
    sections += '<section><h2>历史实验</h2><ul><li>'+link(dataset/'private/history/evaluation-20261009/VTE_10例医生与系统对照.html','2026-10-09：10例医生记录与完整系统回答对照')+'</li><li>'+link(repo/'runs/case-example-private/panel-comparison/VTE_case_responses_panels_a-e.html','2026-10-04：单病例 a–e 面板原始回答')+'</li></ul></section>'
    failures = []
    for path in sorted((out/'nodes').glob('*/*/attempts.json')):
        failures.append({'时间点': path.parent.parent.name, '方法': names.get(path.parent.name, path.parent.name),
                         '已恢复': (path.parent/'result.json').exists(), '尝试记录': load(path, [])})
    if failures:
        sections += '<section><details><summary>技术失败与重试记录（'+str(len(failures))+'个请求）</summary>'+render_value(failures)+'</details></section>'
    page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>VTE 实验记录</title><style>body{font:16px/1.65 system-ui,sans-serif;margin:0 auto;max-width:1040px;padding:28px;background:#f4f7fb;color:#17283d}h1{font-size:30px}h2{font-size:22px}section{background:white;border:1px solid #dbe4ed;border-radius:12px;padding:22px;margin:20px 0}table{border-collapse:collapse;width:100%}th,td{padding:12px;text-align:left;border-bottom:1px solid #dbe4ed}a{color:#075daf}summary{cursor:pointer;font-weight:650}dt{font-weight:650;margin-top:12px}dd{margin-left:18px;overflow-wrap:anywhere;white-space:pre-wrap}li{margin:8px 0}.muted{color:#627387}dl dl{border-left:2px solid #dbe4ed;padding-left:12px}@media(max-width:600px){body{padding:12px}section{padding:14px}th,td{padding:7px}}</style></head><body><h1>VTE 实验记录</h1><p class="muted">页面生成：'''+timestamp+'''</p><p>实验记录统一通过 HTML 阅读；论文中的结果仍整理成表格。原始数据与程序日志保留用于复现。</p>'''+sections+'</body></html>'
    from .report_display import enhance_report_html
    page = enhance_report_html(page)
    destination = dataset/'实验记录.html'
    temporary = destination.with_suffix('.'+uuid4().hex+'.tmp')
    temporary.write_text(page, encoding='utf-8')
    temporary.replace(destination)
    return destination
