"""Prepare new, de-identified, time-scoped inputs and hold current orders out."""
from pathlib import Path
import sys,json,re,base64,io,sqlite3
from copy import deepcopy
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from vte_review.intake import SourceStore
from vte_review.longitudinal import plan_sources,stage_heading
from vte_review.dataset import write_json

DATA=ROOT/'data/vte_dataset'
OUT=DATA/'processing/sol-20261012'
CURATION={}

def deidentify(text):
    text=re.sub(r'(?m)^\s*(?:编\s*号|姓\s*名|住院号|病案号|身份证号|联系电话|手机|地址)\s*[:：].*$', '',text)
    # Preserve smoking/drinking and other clinical social history, remove location fields.
    text=re.sub(r'(?:出生于|生于|长期居住生活在|久居|后居于)[^，,。；;\n]+[，,。；;]?', '',text)
    for hospital in CURATION.get('hospital_names',[]):text=text.replace(hospital,'外院')
    return text.strip()

def blind(text):
    text=deidentify(text)
    text=re.sub(r'(?:门诊|急诊)?拟(?:以)?[“\"][^”\"]+[”\"](?:收住|收入|收治|收)?入?院[。；]?','',text)
    text=re.sub(r'(?:我科|门诊|急诊)[^。\n]{0,12}以[“\"][^”\"]+[”\"](?:收入院|收住院|收入我科)[。；]?','',text)
    return text

def prepare():
    global CURATION
    CURATION=json.loads((DATA/'private/curation.json').read_text(encoding='utf-8'))
    OUT.mkdir(parents=True,exist_ok=True);work=OUT/'workspace';work.mkdir(exist_ok=True)
    if not (work/'knowledge.sqlite3').exists():
        with sqlite3.connect(ROOT/'runs/knowledge.sqlite3') as a,sqlite3.connect(work/'knowledge.sqlite3') as b:a.backup(b)
    original=SourceStore(DATA/'private/parsed');store=SourceStore(work/'sources')
    manifest=json.loads((DATA/'manifest.json').read_text());records=[]
    for case in manifest['cases']:
        if case['processing_status']=='completed_reused':continue
        cid=case['case_id'];profile=CURATION['cases'][cid];src=original.get(case['source_id'])
        image_map={};rx_ids=set()
        for i,sid in enumerate(src['images'],1):
            raw=(original.root/sid/'source.bin').read_bytes()
            # Remove only clipped non-clinical headers in these inspected report copies.
            crop=profile.get('image_crops',{}).get(str(i))
            if crop:
                im=Image.open(io.BytesIO(raw));im=im.crop((0,crop[0],im.width,im.height-crop[1]));buf=io.BytesIO();im.save(buf,'PNG');raw=buf.getvalue()
            image_map[sid]=store._image(f'{cid}-image-{i}.png',raw)['id']
            if i in profile['prescription_image_indices']:rx_ids.add(sid)
        nodes=plan_sources(original,[src['id']]);blocks=[];gold=[];previous_rx='';previous_rx_images=[]
        issues=profile.get('issues',[])
        # The post-intervention comparison report is not available at admission.
        delayed_index=profile.get('defer_image_to_second_visit')
        delayed_report=src['images'][delayed_index-1] if delayed_index else None
        for ni,node in enumerate(nodes):
            texts=[];order_text=[];clinical_images=[];order_images=[]
            for chunk in node['chunks']:
                text=chunk['text'];parts=re.split(r'开药\s*[:：]',text,maxsplit=1)
                texts.append(parts[0])
                if len(parts)>1:order_text.append(parts[1])
                for sid in chunk['images']:
                    if sid in rx_ids:order_images.append(image_map[sid])
                    elif sid!=delayed_report:clinical_images.append(image_map[sid])
            text='\n'.join(t for t in '\n'.join(texts).splitlines() if not stage_heading(t))
            text=blind(text)
            if ni==1 and delayed_report:clinical_images.append(image_map[delayed_report])
            heading=node['key']
            if heading.startswith('postoperative-'):heading=heading.replace('postoperative-','术后').replace('-week','周').replace('-month','月')
            elif heading=='admission':heading='入院'
            elif heading=='discharge':heading='出院'
            blocks.append({'text':heading,'images':[],'location':node['key']})
            fact=text or '本时间点未提供新的症状、检查或检验。'
            if ni>0:fact+='\n此前实际治疗（'+nodes[ni-1]['label']+'，不是本次新处方）：\n'+(previous_rx or '见既往医嘱截图，文字未给出。')
            if issues:fact+='\n原始资料核对提示：'+'；'.join(issues)
            blocks.append({'text':fact,'images':list(dict.fromkeys(clinical_images+previous_rx_images)),'location':node['key']+' facts'})
            rx=deidentify('\n'.join(order_text))
            gold.append({'node_key':node['key'],'label':node['label'],'physician_prescription':rx or '此时间点未给出可读的文字处方；如有医嘱图，以图为准。',
                         'prescription_images':list(dict.fromkeys(order_images)), 'diagnosis_reference':None,
                         'reference_source':'原病例记录；尚未由独立专家形成共识金标准'})
            previous_rx=rx;previous_rx_images=list(dict.fromkeys(order_images))
        payload=json.dumps(blocks,ensure_ascii=False).encode()
        clean=store._save(cid+'-blinded.txt',payload,'text/plain','\n'.join(b['text'] for b in blocks),list(dict.fromkeys(i for b in blocks for i in b['images'])),blocks)
        planned=plan_sources(store,[clean['id']]);assert len(planned)==len(nodes),(cid,len(planned),len(nodes))
        write_json(OUT/(cid+'-input.json'),blocks);write_json(OUT/(cid+'-gold.json'),gold)
        case.update(timepoints=len(nodes),processing_status='prepared',data_issues=issues)
        records.append({'case':cid,'source_id':clean['id'],'nodes':len(nodes),'gold':cid+'-gold.json'})
    write_json(DATA/'manifest.json',manifest)
    write_json(OUT/'protocol.json',{'version':'2026-10-12.r1','model':'gpt-5.6-sol','records':records,
       'input_policy':'Contemporaneous physician order held out; prior actual prescriptions retained; imaging reports retained; no independent diagnostic gold yet.',
       'old_cases':'CASE01-10 reused verbatim, not rerun','parser_changes':'Recognize Chinese relative headings; ignore ZIP media directory entries; retry transient Windows file sharing errors.',
       'max_series_attempts':5,'patient_concurrency':2,'known_source_issues':'Private curation.json preserves per-case date and image-assignment notes.'})
    print(json.dumps({'new_cases':len(records),'timepoints':sum(r['nodes'] for r in records)},ensure_ascii=False))

if __name__=='__main__':prepare()
