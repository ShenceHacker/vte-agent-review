"""Export only de-identified time-scoped review materials, never source DOCX files."""
from pathlib import Path
import sys,json,hashlib,re,io
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vte_review.dataset import write_json,processing_directory
from vte_review.longitudinal import load
DATA=ROOT/'data/vte_dataset';DEST=DATA/'portal';ASSETS=DEST/'assets'

def image_asset(path,label):
    with Image.open(path) as im:
        out=io.BytesIO();im.convert('RGB').save(out,'PNG');raw=out.getvalue()
    name=hashlib.sha256(raw).hexdigest()+'.png';(ASSETS/name).write_bytes(raw)
    return {'id':name,'label':label}

def info(text):
    age=re.search(r'年\s*龄\s*[:：]\s*(\d+)',text);sex=re.search(r'性\s*别\s*[:：]\s*([男女])',text)
    weight=re.search(r'体重\s*[:：]?\s*([\d.]+)',text)
    return ([sex[1]] if sex else [])+([age[1]+'岁'] if age else [])+([weight[1]+' kg'] if weight else [])

def time_label(key,label):
    return {'admission':'入院','discharge':'出院','postoperative-3-week':'术后3周','postoperative-3-month':'术后3个月','postoperative-6-month':'术后6个月'}.get(key,label)

def export():
    ASSETS.mkdir(parents=True,exist_ok=True);manifest=load(DATA/'manifest.json');cases=[];audit=[]
    old=DATA/'private/history/evaluation-20261009'
    if not old.exists():old=ROOT/'runs/evaluation-20261009'
    for record in manifest['cases']:
        cid=record['case_id'];source=processing_directory(DATA,record)
        if int(cid[4:])<=10 and not source.exists():source=old
        batch=load(source/'batch.json',{});state=batch.get(cid);series=load(source/'workspace/series'/state['series_id']/'series.json',{}) if state else {}
        gold=load(source/(cid+'-gold.json'),[]);input_blocks=load(source/(cid+'-input.json'),[])
        basic=info('\n'.join(b['text'] for b in input_blocks[:2]));items=[];allowed=set()
        for pos,node in enumerate(series.get('nodes',[])):
            allowed.update(c['source_id'] for c in node['chunks'])
            rid=node.get('run_id');folder=source/'workspace'/str(rid);result=load(folder/'result.json',{})
            if result.get('status') not in {'conditional','needs_human_review','approved'} or not result.get('recommendation'):break
            rec=result['recommendation'];translation=None
            if int(cid[4:])<=10:
                translation=load(DATA/'translations'/f'{cid}-T{pos+1}.json')
                if not translation or translation.get('numeric_check')!='passed':break
                original={'coordinator_answer':rec['shared_plan'],'assumptions':rec.get('assumptions',[]),'information_requests':rec.get('information_requests',[])}
                sha=hashlib.sha256(json.dumps(original,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                if translation.get('source_hash')!=sha:raise ValueError('Translation source hash mismatch')
            clinical=load(folder/'case.json');assert set(clinical['source_ids'])<=allowed
            events=clinical['longitudinal']['prior_events']+clinical['longitudinal']['new_information']
            context=[];images=[];seen=set()
            for event in events:
                key=(event['source_id'],event['time_label'])
                if key in seen:continue
                seen.add(key)
                label=event['time_label'].replace('Admission','入院').replace('Discharge','出院')
                label=re.sub(r'(\d+) weeks? postoperative',r'术后\1周',label)
                label=re.sub(r'(\d+) months? postoperative',r'术后\1个月',label)
                context.append('【'+label+'】\n'+event['text'].replace('Admission','入院').replace('Discharge','出院'))
                meta=load(source/'workspace/sources'/event['source_id']/'meta.json',{})
                for i,sid in enumerate(meta.get('images',[])):
                    a=image_asset(source/'workspace/sources'/sid/'source.bin',label+' · 资料图 '+str(i+1))
                    if not any(x['id']==a['id'] for x in images):images.append(a)
            reference={'text':gold[pos]['physician_prescription'],'images':[]}
            if gold[pos].get('diagnosis_reference'):reference['text']='诊断记录参照：'+gold[pos]['diagnosis_reference']+'\n\n'+reference['text']
            if int(cid[4:])<=10 and pos==0:
                order=DATA/'private/cases'/cid/'image4.png'
                if not order.exists():order=ROOT/'runs/pharmacist-review-20261007'/cid/'image4.png'
                reference['images'].append(image_asset(order,'本次住院医嘱'))
            for sid in gold[pos].get('prescription_images',[]):reference['images'].append(image_asset(source/'workspace/sources'/sid/'source.bin','本次医生医嘱'))
            encoded=json.dumps(rec);ids=set(re.findall(r'KB-[A-Za-z0-9-]+',encoded))
            trace=load(folder/'retrieval_trace.json',[])
            for t in trace:ids.update(t.get('selected_ids',[]))
            evidence=[{'title':e['id']+' · '+e['title'],'text':e['text'],'url':e.get('source','')} for e in load(folder/'evidence.json',[]) if e['id'] in ids]
            item={'id':cid+'-T'+str(pos+1),'case_id':cid,'position':pos,'label':time_label(node['key'],node['label']),
                  'patient':basic,'context':'\n\n'.join(context),'images':images,'answer':rec['shared_plan'],
                  'assumptions':rec.get('assumptions',[]),'information_requests':rec.get('information_requests',[]),
                  'evidence':evidence,'reference':reference,'source_issues':record.get('data_issues',[])}
            if translation:
                item['answer_original']=item['answer'];item['answer']=translation['translated']['coordinator_answer']
                item['assumptions']=translation['translated']['assumptions'];item['information_requests']=translation['translated']['information_requests']
                item['report_language']='中文译文';item['translation_version']=translation['translation_version']
            else:item['report_language']='中文原文'
            for en,zh in [('Current assessment','当前判断'),('Changes since previous visit','与上次相比的变化'),('Changes since the previous visit','与上次相比的变化'),('Recommended actions','建议措施'),('Rationale and conditions','依据与适用条件')]:
                item['answer']=item['answer'].replace(en,zh)
            if len(re.findall(r'[\u4e00-\u9fff]',item['answer']))<50:raise ValueError('Chinese clinical report required')
            items.append(item);audit.append({'id':item['id'],'run_id':rid,'source':str(source.relative_to(ROOT)),'answer_sha256':hashlib.sha256(item['answer'].encode()).hexdigest()})
        baseline={'patient':basic,'context':input_blocks[1]['text'] if len(input_blocks)>1 else '',
                  'images':[],'source_issues':record.get('data_issues',[])}
        if len(input_blocks)>1:
            for i,sid in enumerate(input_blocks[1]['images']):
                baseline['images'].append(image_asset(source/'workspace/sources'/sid/'source.bin','初始资料图 '+str(i+1)))
        cases.append({'id':cid,'demographics':' · '.join(basic),'timepoints':record.get('timepoints',len(gold)),'baseline':baseline,'outputs':items})
    bundle={'schema_version':1,'study':'VTE-R1','cases':cases};write_json(DEST/'bundle.json',bundle)
    write_json(DATA/'portal-export-audit.json',audit)
    print(json.dumps({'cases':len(cases),'outputs':sum(len(c['outputs']) for c in cases),'assets':len(list(ASSETS.glob('*.png')))},ensure_ascii=False))

if __name__=='__main__':export()
