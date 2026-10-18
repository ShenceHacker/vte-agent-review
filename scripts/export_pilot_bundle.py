"""Build a matched, complete pilot without changing saved clinical results."""
from copy import deepcopy
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from vte_review.comparison import digest, extract_initial
from vte_review.rating_rubric import VERSION
from vte_review.rating_methods import METHODS


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def build(reviewed,comparison,out,case_ids):
    reviewed=Path(reviewed);comparison=Path(comparison);out=Path(out)
    original=read(reviewed)
    cases=[deepcopy(c) for c in original['cases'] if c['id'] in case_ids]
    if len(cases)!=len(set(case_ids)):raise ValueError('Missing pilot cases')
    audit=[];assets=set()
    for case in cases:
        if len(case['outputs'])!=case['timepoints']:raise ValueError('Incomplete reviewed case '+case['id'])
        extra=[]
        for item in case['outputs']:
            folder=comparison/'nodes'/item['id'];frozen=read(folder/'input.json')
            meta=frozen['metadata'];source=Path(meta['source_run'])
            raw=read(source/'result.json')['recommendation']
            if raw['shared_plan']!=item['answer']:raise ValueError('Reviewed wording changed or non-native Chinese source')
            if meta['case_id']!=case['id'] or meta['position']!=item['position'] or meta['language']!='zh':raise ValueError('Pairing mismatch')
            if digest(read(source/'case.json'))!=meta['original_case_hash']:raise ValueError('Input source changed')
            for method in ('baseline','rag','synthesis'):
                result=read(folder/method/'result.json')
                if result['output_hash']!=digest(result['output']):raise ValueError('Output hash mismatch')
                if result['metadata']!=meta:raise ValueError('Unpaired comparison')
                if method=='synthesis':
                    events=[json.loads(line) for line in (source/'events.jsonl').read_text(encoding='utf-8').splitlines()]
                    initial,_,_=extract_initial(events)
                    if initial['output']!=result['output']:raise ValueError('Initial draft was rewritten')
                else:
                    request=read(folder/method/'request.json')
                    if digest(request)!=result['request_hash']:raise ValueError('Request changed')
                variant=deepcopy(item)
                variant.update(id=method.upper()+'-'+item['id'],method_id=method,answer=result['output']['shared_plan'],
                    assumptions=result['output'].get('assumptions',[]),information_requests=result['output'].get('information_requests',[]))
                variant['evidence']=[] if method=='baseline' else [{'title':e['id']+' · '+e['title'],'text':e['text'],'url':e.get('source','')} for e in frozen['evidence']]
                extra.append(variant)
                audit.append({'id':variant['id'],'method':method,'source':str((folder/method/'result.json').resolve()),'output_hash':result['output_hash']})
            audit.append({'id':item['id'],'method':'reviewed','source':str((source/'result.json').resolve()),'answer_sha256':hashlib.sha256(item['answer'].encode()).hexdigest()})
        case['outputs']+=extra
        for data in [case.get('baseline',{}),*case['outputs']]:
            assets.update(a['id'] for a in data.get('images',[]))
            assets.update(a['id'] for a in data.get('reference',{}).get('images',[]))
    out.mkdir(parents=True,exist_ok=True);(out/'assets').mkdir(exist_ok=True)
    for name in sorted(assets):
        source=reviewed.parent/'assets'/name
        if hashlib.sha256(source.read_bytes()).hexdigest()+'.png'!=name:raise ValueError('Image hash mismatch')
        shutil.copyfile(source,out/'assets'/name)
    bundle={'schema_version':1,'study':'VTE','rubric_version':VERSION,'cases':cases}
    scope={'rubric_version':VERSION,'case_ids':sorted(case_ids),'methods':list(METHODS),'complete_follow_up':True}
    (out/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False),encoding='utf-8')
    (out/'active-study.json').write_text(json.dumps(scope,ensure_ascii=False,indent=2),encoding='utf-8')
    report={'cases':len(cases),'timepoints_per_method':sum(c['timepoints'] for c in cases),'outputs':len(audit),'assets':len(assets),'source_audit':audit}
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with tarfile.open(out/'pilot.tar.gz','w:gz') as archive:
        for name in ('bundle.json','active-study.json'):archive.add(out/name,arcname=name)
        for name in sorted(assets):archive.add(out/'assets'/name,arcname='assets/'+name)
    return {k:v for k,v in report.items() if k!='source_audit'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--reviewed',type=Path,required=True);p.add_argument('--comparison',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--cases',nargs='+',required=True)
    args=p.parse_args();print(json.dumps(build(args.reviewed,args.comparison,args.out,args.cases)))
