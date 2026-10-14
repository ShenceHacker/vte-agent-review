"""Readable local record for a reviewed cohort; preserves raw model wording."""
from datetime import datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path
from uuid import uuid4

from .longitudinal import load


def write_reviewed_html(batch_dir):
    batch_dir = Path(batch_dir)
    protocol = load(batch_dir / 'protocol.json', {})
    batch = load(batch_dir / 'batch.json', {})
    input_check = load(batch_dir / 'input-verification.json', {})
    state_names = {'complete': '完成', 'reviewing': '审核中', 'extracting': '资料提取中',
                   'queued': '等待处理', 'failed': '技术失败'}
    outcome_names = {'conditional': '内部审核完成（带条件）', 'approved': '内部审核通过',
                     'needs_human_review': '保留审核分歧'}
    rows, reports, done, total = [], [], 0, 0
    for record in protocol.get('records', []):
        cid = record['case']; ref = batch.get(cid, {})
        series = load(batch_dir / 'workspace/series' / ref.get('series_id', 'pending') / 'series.json', {})
        count = series.get('completed_nodes', 0); expected = record['nodes']
        done += count; total += expected
        rows.append('<tr><td><a href="#'+escape(cid)+'">'+escape(cid)+'</a></td><td>'+str(count)+' / '+str(expected)+'</td><td>'+escape(state_names.get(series.get('status'), series.get('status', '未启动')))+'</td><td>'+str(ref.get('attempts', 0))+'</td></tr>')
        nodes = []
        for pos, node in enumerate(series.get('nodes', []), 1):
            if node.get('status') not in {'complete', 'review_required'}: continue
            result = load(batch_dir / 'workspace' / node.get('run_id', 'pending') / 'result.json', {})
            recommendation = result.get('recommendation') or {}
            text = recommendation.get('shared_plan', '')
            if not text: continue
            label = node.get('key', str(pos)).replace('admission', '入院').replace('discharge', '出院').replace('postoperative-', '术后').replace('-week', '周').replace('-month', '月')
            extras = ''.join('<h4>'+title+'</h4><ul>'+''.join('<li>'+escape(str(x))+'</li>' for x in recommendation.get(key, []))+'</ul>' for key, title in [('assumptions', '原始假设'), ('information_requests', '原始补充资料请求')] if recommendation.get(key))
            nodes.append('<details><summary>T'+str(pos)+' · '+escape(label)+' · '+escape(outcome_names.get(result.get('status'), result.get('status', '')))+'</summary><div class="answer">'+escape(text)+'</div>'+extras+'</details>')
        reports.append('<section id="'+escape(cid)+'"><h2>'+escape(cid)+' · '+str(count)+' / '+str(expected)+'</h2>'+(''.join(nodes) or '<p class="muted">尚无完整报告。</p>')+'</section>')
    retry_file = batch_dir / 'transport-retries.jsonl'
    retries = len(retry_file.read_text(encoding='utf-8').splitlines()) if retry_file.exists() else 0
    publication = load(batch_dir / 'publication-verification.json')
    published = '<section><h2>上线核验</h2><pre>'+escape(json.dumps(publication, ensure_ascii=False, indent=2))+'</pre></section>' if publication else '<p class="muted">本批尚无上线完成记录。</p>'
    timestamp = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S 北京时间')
    page = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>新病例完整审核流程实验记录</title><style>body{font:16px/1.65 system-ui,sans-serif;max-width:1080px;margin:auto;padding:26px;background:#f5f7fb;color:#1c2f45}section{background:white;border:1px solid #dbe3ec;border-radius:12px;padding:22px;margin:20px 0}h1{font-size:29px}h2{font-size:21px}table{border-collapse:collapse;width:100%}th,td{text-align:left;border-bottom:1px solid #e2e8f0;padding:10px}summary{cursor:pointer;font-weight:650;padding:12px 0}details+details{border-top:1px solid #e2e8f0}.answer,pre{white-space:pre-wrap;overflow-wrap:anywhere}.muted{color:#64748b}a{color:#075daf}.stat{font-size:27px;font-weight:700}progress{width:100%;height:14px}@media(max-width:600px){body{padding:12px}section{padding:14px}}</style></head><body><h1>新病例完整审核流程实验记录</h1><p class="muted">更新：'''+timestamp+'''</p><p><a href="../../实验记录.html">返回全部实验记录</a> · <a href="https://api.forceeasyai.com/vte-review/">打开医生评分站</a></p><section><h2>运行进度</h2><div class="stat">'''+str(done)+' / '+str(total)+''' 个时间点</div><progress value="'''+str(done)+'" max="'+str(total or 1)+'''"></progress><p>本批'''+str(len(protocol.get('records', [])))+'''例；采用完整审核修订系统，模型 '''+escape(str(protocol.get('model', '未记录')))+'''，中文生成。沿用此前知识库内容；当前处方留出，既往真实治疗随时间线带入。报告以下列原始结果呈现，待医生独立评分。</p><p>请求级传输重试：'''+str(retries)+''' 次。下表的运行尝试次数按病例恢复计算，两者不同。</p><table><thead><tr><th>病例</th><th>完成时间点</th><th>当前状态</th><th>运行尝试</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></section><section><h2>输入与来源核验</h2><p>'''+escape(input_check.get('summary', '已冻结输入；详细核验见下方记录。'))+'''</p><details><summary>查看冻结输入核验记录</summary><pre>'''+escape(json.dumps(input_check, ensure_ascii=False, indent=2))+'''</pre></details><details><summary>查看本批实验设置</summary><pre>'''+escape(json.dumps(protocol, ensure_ascii=False, indent=2))+'''</pre></details></section>'''+published+''.join(reports)+'''</body></html>'''
    destination = batch_dir / '实验记录.html'
    temporary = destination.with_suffix('.'+uuid4().hex+'.tmp')
    temporary.write_text(page, encoding='utf-8'); temporary.replace(destination)
    return destination


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('batch_dir', type=Path)
    print(write_reviewed_html(parser.parse_args().batch_dir))
