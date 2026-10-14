"""Check a complete review export against its frozen clinical run records."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import sys
import tarfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from vte_review.rating_rubric import VERSION
from vte_review.dataset import processing_directory


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(value):
    return hashlib.sha256(value).hexdigest()


def verify(previous_archive):
    data = ROOT / 'data/vte_dataset'
    portal = data / 'portal'
    manifest = read(data / 'manifest.json')
    bundle = read(portal / 'bundle.json')
    records = {c['case_id']: c for c in manifest['cases']}
    cases = {c['id']: c for c in bundle['cases']}
    assert len(cases) == len(bundle['cases']) == len(records)
    assert set(cases) == set(records)
    outputs = {}
    assets = set()
    status_counts = Counter()
    audit = []
    forbidden = re.compile(r'编\s*号\s*[:：]|出生于|长期居住生活在')
    headings = [('Current assessment', '当前判断'),
                ('Changes since previous visit', '与上次相比的变化'),
                ('Changes since the previous visit', '与上次相比的变化'),
                ('Recommended actions', '建议措施'),
                ('Rationale and conditions', '依据与适用条件')]
    for cid, case in cases.items():
        legacy = int(cid[4:]) <= 10
        source = processing_directory(data, records[cid])
        batch = read(source / 'batch.json')
        series = read(source / 'workspace/series' / batch[cid]['series_id'] / 'series.json')
        assert series['status'] == 'complete', cid
        assert len(case['outputs']) == len(series['nodes']) == records[cid]['timepoints'], cid
        assert not forbidden.search(case['baseline']['context']), cid
        assets.update(a['id'] for a in case['baseline']['images'])
        allowed = set()
        for pos, (item, node) in enumerate(zip(case['outputs'], series['nodes'])):
            oid = f'{cid}-T{pos+1}'
            assert item['id'] == oid and item['case_id'] == cid and item['position'] == pos
            assert oid not in outputs
            outputs[oid] = item
            allowed.update(chunk['source_id'] for chunk in node['chunks'])
            folder = source / 'workspace' / node['run_id']
            clinical = read(folder / 'case.json')
            result = read(folder / 'result.json')
            assert result['status'] in {'approved', 'conditional', 'needs_human_review'}, oid
            assert set(clinical['source_ids']) <= allowed, oid
            events = clinical['longitudinal']['prior_events'] + clinical['longitudinal']['new_information']
            assert {event['source_id'] for event in events} <= allowed, oid
            rec = result['recommendation']
            if legacy:
                translation = read(data / 'translations' / f'{oid}.json')
                original = {'coordinator_answer': rec['shared_plan'],
                            'assumptions': rec.get('assumptions', []),
                            'information_requests': rec.get('information_requests', [])}
                assert translation['numeric_check'] == 'passed', oid
                assert translation['source_hash'] == sha(json.dumps(original, sort_keys=True, ensure_ascii=False).encode()), oid
                assert item['answer_original'] == rec['shared_plan'], oid
                expected = translation['translated']['coordinator_answer']
                assert item['report_language'] == '中文译文'
            else:
                expected = rec['shared_plan']
                assert item['report_language'] == '中文原文'
            for en, zh in headings:
                expected = expected.replace(en, zh)
            assert item['answer'] == expected, oid
            assert len(re.findall(r'[\u4e00-\u9fff]', item['answer'])) > 50, oid
            assert not forbidden.search(item['context']), oid
            assets.update(a['id'] for a in item['images'] + item['reference']['images'])
            status_counts[result['status']] += 1
            audit.append({'output_id': oid, 'run_id': node['run_id'], 'status': result['status'],
                          'source': source.relative_to(ROOT).as_posix(),
                          'result_sha256': sha((folder / 'result.json').read_bytes()),
                          'content_hash': sha(json.dumps(item, sort_keys=True, ensure_ascii=False).encode())})
    for aid in assets:
        assert re.fullmatch(r'[a-f0-9]{64}\.png', aid), aid
        path = portal / 'assets' / aid
        raw = path.read_bytes()
        assert raw.startswith(b'\x89PNG\r\n\x1a\n') and sha(raw) + '.png' == aid, aid
        with Image.open(path) as im:
            im.verify()
    with tarfile.open(previous_archive) as archive:
        old = json.load(archive.extractfile('bundle/bundle.json'))
    published = {o['id']: o for c in old['cases'] for o in c['outputs']}
    assert all(outputs.get(oid) == item for oid, item in published.items()), 'Released output changed'
    summary = {'checked_at': datetime.now(timezone.utc).isoformat(), 'rubric_version': VERSION,
               'cases': len(cases), 'outputs': len(outputs), 'assets': len(assets),
               'legacy_translations': sum(o['report_language'] == '中文译文' for o in outputs.values()),
               'native_chinese_outputs': sum(o['report_language'] == '中文原文' for o in outputs.values()),
               'unchanged_published_outputs': len(published), 'internal_status_counts': dict(status_counts),
               'bundle_sha256': sha((portal / 'bundle.json').read_bytes()),
               'time_scoped_sources_checked': len(audit),
               'limitations': 'Technical provenance and known identifier-pattern checks; not a clinical correctness or complete privacy audit.'}
    report = {**summary, 'referenced_assets': sorted(assets), 'outputs_audit': audit}
    (data / 'final-verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--previous-archive', type=Path, required=True)
    verify(parser.parse_args().previous_archive)
