"""Resume only the newly collected cohort; retain unresolved clinical reviews."""
from pathlib import Path
import sys,json,time,asyncio,hashlib,threading,os,argparse
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.serve_fe import configure_fe
from vte_review.server import App
from vte_review.longitudinal import load,save
from vte_review.vector import VectorStore
from vte_review.providers import ChatCompletionsModel,ProviderError
from vte_review.reviewed_experiment_html import write_reviewed_html
OUT=ROOT/'data/vte_dataset/processing/sol-20261012'
QUESTION=('Using only information available at this time point, state the working VTE diagnosis '
 '(DVT/PE, laterality, anatomical extent, uncertainty and competing diagnoses), then recommend '
 'anticoagulation choices, doses, duration, monitoring and changes. The current physician decision '
 'is withheld for independent comparison. Previously documented treatment is historical fact, '
 'not necessarily the preferred treatment. No new symptoms or labs supplied at follow-up does '
 'not establish recovery or normal results. Give useful conditional recommendations. '
 'Include the diagnosis explicitly in the coordinator shared_plan.')
class EvaluationApp(App):
    def start(self,body):
        body=deepcopy(body);body['case']['question']=QUESTION
        return super().start(body)

def run(max_attempts=6):
    configure_fe(Path.home()/'.claude/settings.json','gpt-5.6-sol')
    if '--ssh-tunnel' in sys.argv:os.environ['VTE_BASE_URL']='http://127.0.0.1:18880/v1'
    os.environ['VTE_OUTPUT_LANGUAGE']='zh'
    original=ChatCompletionsModel._post;lock=threading.Lock()
    async def post(self,endpoint,body):
        for i in range(3):
            try:return await original(self,endpoint,body)
            except ProviderError as exc:
                reason=str(exc)
                if i==2 or not any(s in reason for s in ['RemoteProtocolError','ReadError','HTTP 429','HTTP 502','HTTP 503','HTTP 504','model response stream failed']):raise
                with lock:
                    with (OUT/'transport-retries.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'time':time.time(),'reason':reason,'request_hash':hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()})+'\n')
                await asyncio.sleep([5,15][i])
    ChatCompletionsModel._post=post
    app=EvaluationApp(OUT/'workspace');app.vectors=VectorStore(ROOT/'runs');state=load(OUT/'batch.json',{})
    for record in load(OUT/'protocol.json')['records']:
        key=record['case']
        if key not in state:state[key]={'series_id':app.start_series({'source_ids':[record['source_id']]}),'attempts':1}
        elif app.series_detail(state[key]['series_id'])['status']!='complete' and state[key]['attempts']<max_attempts:
            app.retry_series(state[key]['series_id'],{});state[key]['attempts']+=1
        save(OUT/'batch.json',state)
    previous=None
    while True:
        active=False;summary=[]
        for key,record in state.items():
            detail=app.series_detail(record['series_id']);job=app.series_jobs.get(record['series_id'])
            if job and not job.done:active=True
            elif detail['status']=='failed' and record['attempts']<max_attempts:
                app.retry_series(detail['id'],{});record['attempts']+=1;save(OUT/'batch.json',state);active=True
            summary.append({'case':key,'status':detail['status'],'done':detail.get('completed_nodes',0),'total':detail['node_count'],'attempts':record['attempts']})
        save(OUT/'progress.json',summary);current=json.dumps(summary)
        if current!=previous:
            write_reviewed_html(OUT)
            print(current,flush=True);previous=current
        if not active:break
        time.sleep(5)
    print('BATCH_FINISHED',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--batch-dir',type=Path,default=OUT)
    parser.add_argument('--ssh-tunnel',action='store_true')
    parser.add_argument('--max-attempts',type=int,choices=range(1,13),default=6,
                        help='Finite cumulative case-resume limit, including earlier attempts')
    args=parser.parse_args();OUT=args.batch_dir.resolve()
    OUT.relative_to((ROOT/'data/vte_dataset/processing').resolve())
    run(args.max_attempts)
