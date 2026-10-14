"""Local, idempotent collection of clinical DOCX files; never publishes originals."""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import posixpath
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET

NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def docx_identity(data: bytes) -> tuple[str, str]:
    if len(data) > 32 * 1024 * 1024:
        raise ValueError('DOCX exceeds collection limit')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        if sum(i.file_size for i in z.infolist()) > 120 * 1024 * 1024:
            raise ValueError('DOCX expanded size exceeds limit')
        tree = ET.fromstring(z.read('word/document.xml'))
        lines = [''.join(t.text or '' for t in p.findall('.//w:t', NS))
                 for p in tree.findall('.//w:p', NS)]
        text = '\n'.join(x for x in lines if x.strip())
        normalized = re.sub(r'\s+', '', text)
        media = sorted(digest(z.read(n)) for n in z.namelist() if n.startswith('word/media/') and not n.endswith('/'))
        rels={}
        if 'word/_rels/document.xml.rels' in z.namelist():
            for rel in ET.fromstring(z.read('word/_rels/document.xml.rels')):
                target=posixpath.normpath('word/'+rel.attrib.get('Target',''))
                if target in z.namelist() and target.startswith('word/media/'):
                    rels[rel.attrib.get('Id')]=digest(z.read(target))
        sequence=[];buffer=[]
        for node in tree.iter():
            if node.tag=='{'+NS['w']+'}t':buffer.append(re.sub(r'\s+','',node.text or ''))
            for attribute in ['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed','{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']:
                if node.attrib.get(attribute) in rels:
                    sequence.append(''.join(buffer));buffer=[];sequence.append({'image':rels[node.attrib[attribute]]})
        sequence.append(''.join(buffer))
        fingerprint = digest(json.dumps([normalized, sequence, media], ensure_ascii=False).encode())
        return fingerprint, text

def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def processing_directory(dataset: Path, case: dict) -> Path:
    """Resolve a case's recorded batch without mixing separate cohort runs."""
    default = 'private/history/evaluation-20261009' if int(case['case_id'][4:]) <= 10 else 'processing/sol-20261012'
    relative = PurePosixPath(str(case.get('processing_dir', default)).replace('\\', '/'))
    if relative.is_absolute() or '..' in relative.parts or ':' in str(relative):
        raise ValueError('Invalid processing directory')
    target = (dataset / relative).resolve()
    target.relative_to(dataset.resolve())
    return target

def collect(incoming: Path, dataset: Path, prior_cases: Path, prior_results: Path) -> dict:
    dataset.mkdir(parents=True, exist_ok=True)
    manifest_path = dataset/'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {
        'schema_version': 1, 'cases': [], 'imports': [], 'duplicates': []}
    for c in manifest['cases']:
        c['content_sha256'] = docx_identity((dataset/c['source']).read_bytes())[0]
    fingerprints = {c['content_sha256']: c for c in manifest['cases']}
    file_hashes = {c['file_sha256']: c for c in manifest['cases']}
    by_id = {c['case_id']: c for c in manifest['cases']}

    def register(data, provenance, existing_id=None):
        file_hash = digest(data); fingerprint, text = docx_identity(data)
        existing = file_hashes.get(file_hash) or fingerprints.get(fingerprint)
        if existing:
            if provenance not in existing['sources']:
                existing['sources'].append(provenance)
                manifest['duplicates'].append({'case_id': existing['case_id'], **provenance,
                    'match': 'identical_file' if file_hash == existing['file_sha256'] else 'identical_text_and_media'})
            return existing, False
        case_id = existing_id or f'CASE{max([int(k[4:]) for k in by_id] or [0])+1:02d}'
        if case_id in by_id:
            raise ValueError('Conflicting existing case ID; refusing overwrite')
        folder = dataset/'private'/'cases'/case_id; folder.mkdir(parents=True, exist_ok=True)
        (folder/'source.docx').write_bytes(data)
        (folder/'source-text.txt').write_text(text, encoding='utf-8')
        case = {'case_id': case_id, 'file_sha256': file_hash, 'content_sha256': fingerprint,
                'sources': [provenance], 'source': f'private/cases/{case_id}/source.docx',
                'processing_status': 'new', 'created_at': datetime.now(timezone.utc).isoformat()}
        by_id[case_id]=case; fingerprints[fingerprint]=case; file_hashes[file_hash]=case
        manifest['cases'].append(case)
        return case, True

    previous = json.loads(prior_results.read_text(encoding='utf-8')) if prior_results.exists() else {'cases': []}
    result_by_case = {c['case']: c for c in previous['cases']}
    for folder in sorted(prior_cases.glob('CASE*')):
        if not (folder/'source.docx').exists(): continue
        case, _ = register((folder/'source.docx').read_bytes(), {'kind':'previous_evaluation','case':folder.name}, folder.name)
        if folder.name in result_by_case:
            target = dataset/'results'/'evaluation-20261009'/f'{case["case_id"]}.json'
            if not target.exists(): write_json(target, result_by_case[folder.name])
            case.update(processing_status='completed_reused', result=str(target.relative_to(dataset)).replace('\\','/'),
                        timepoints=len(result_by_case[folder.name]['nodes']))

    for archive in sorted(incoming.rglob('*.zip')):
        archive_hash = digest(archive.read_bytes())
        if any(a['sha256']==archive_hash for a in manifest['imports']): continue
        dest=dataset/'private'/'archives'/f'{archive_hash[:12]}.zip';dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(archive,dest)
        added=0;duplicate=0
        with zipfile.ZipFile(archive) as z:
            if sum(i.file_size for i in z.infolist()) > 512*1024*1024: raise ValueError('Archive too large')
            for info in sorted(z.infolist(),key=lambda i:i.filename):
                if info.is_dir():continue
                name=PurePosixPath(info.filename.replace('\\','/'))
                if name.is_absolute() or '..' in name.parts or ':' in info.filename: raise ValueError('Unsafe archive entry')
                if name.suffix.lower()!='.docx' or name.name.startswith('~$'):continue
                case,is_new=register(z.read(info),{'kind':'archive','archive_sha256':archive_hash,'archive_name':archive.name,'entry':info.filename})
                added+=is_new;duplicate+=not is_new
        manifest['imports'].append({'name':archive.name,'sha256':archive_hash,'new':added,'duplicates':duplicate})
    manifest['updated_at']=datetime.now(timezone.utc).isoformat()
    write_json(manifest_path,manifest)
    previous_count=sum(any(s['kind']=='previous_evaluation' for s in c['sources']) for c in manifest['cases'])
    summary={'unique_cases':len(manifest['cases']),'completed_reused':sum(c['processing_status']=='completed_reused' for c in manifest['cases']),
             'new_cases':len(manifest['cases'])-previous_count,'duplicates':len(manifest['duplicates']),
             'imports':[{'name':a['name'],'new':a['new'],'duplicates':a['duplicates']} for a in manifest['imports']]}
    write_json(dataset/'collection_summary.json',summary)
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('incoming',type=Path);p.add_argument('--dataset',type=Path,default=Path('data/vte_dataset'))
    p.add_argument('--prior-cases',type=Path,default=Path('runs/pharmacist-review-20261007'))
    p.add_argument('--prior-results',type=Path,default=Path('runs/evaluation-20261009/comparison_results.json'))
    a=p.parse_args();print(json.dumps(collect(a.incoming,a.dataset,a.prior_cases,a.prior_results),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
