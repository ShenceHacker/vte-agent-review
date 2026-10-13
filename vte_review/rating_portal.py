"""Private physician ratings portal, isolated from the model execution service."""
from __future__ import annotations
import argparse,base64,csv,hashlib,hmac,io,json,os,re,secrets,smtplib,sqlite3,ssl,time
from contextlib import contextmanager
from email.message import EmailMessage
from datetime import datetime,timezone,timedelta
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse,unquote
from .rating_rubric import VERSION,DIMENSIONS,ERRORS,OVERALL,CONSEQUENCES,SEVERITY,rubric

WEB=Path(__file__).with_name('rating_web')
EMAIL=re.compile(r'^[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
ID=re.compile(r'^[A-Za-z0-9_-]{1,90}$')

class PortalError(Exception):
    def __init__(self,status,message):self.status=status;self.message=message

class Store:
    def __init__(self,root,allowed,secret,mailer=None,clock=time.time):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'ratings.sqlite3';self.allowed={e.strip().lower() for e in allowed if e.strip()}
        self.secret=secret.encode();self.mailer=mailer;self.clock=clock
        if len(self.secret)<32:raise ValueError('A random secret of at least 32 characters is required')
        with self.db() as c:c.executescript('''
        CREATE TABLE IF NOT EXISTS challenges(id TEXT PRIMARY KEY,email TEXT NOT NULL,code_hash TEXT,expires REAL,attempts INTEGER DEFAULT 0,used INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,email TEXT,csrf TEXT,expires REAL);
        CREATE TABLE IF NOT EXISTS limits(bucket TEXT PRIMARY KEY,start REAL,count INTEGER);
        CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY,summary TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS outputs(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,position INTEGER NOT NULL,content_hash TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(case_id,position));
        CREATE TABLE IF NOT EXISTS ratings(email TEXT,output_id TEXT,content_hash TEXT,rubric_version TEXT,payload TEXT,status TEXT,revision INTEGER,opened_at REAL,updated_at REAL,submitted_at REAL,PRIMARY KEY(email,output_id));
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,email TEXT,event TEXT,target TEXT,at REAL);
        ''')
        try:self.path.chmod(0o600)
        except OSError:pass

    @contextmanager
    def db(self):
        c=sqlite3.connect(self.path,timeout=15);c.row_factory=sqlite3.Row
        try:
            c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=15000')
            yield c;c.commit()
        except Exception:c.rollback();raise
        finally:c.close()

    def hashed(self,value):return hmac.new(self.secret,value.encode(),hashlib.sha256).hexdigest()

    def limit(self,bucket,maximum,window):
        now=self.clock();bucket=self.hashed(bucket)
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM limits WHERE bucket=?',(bucket,)).fetchone()
            if not r or now-r['start']>=window:c.execute('INSERT OR REPLACE INTO limits VALUES(?,?,1)',(bucket,now));return
            if r['count']>=maximum:raise PortalError(429,'操作过于频繁，请稍后再试。')
            c.execute('UPDATE limits SET count=count+1 WHERE bucket=?',(bucket,))

    def request_code(self,email,ip):
        email=str(email).strip().lower()
        if len(email)>254 or not EMAIL.fullmatch(email):raise PortalError(400,'请输入有效邮箱。')
        self.limit('send-ip:'+ip,12,3600);self.limit('send-email:'+email,1,60)
        self.limit('send-day:'+email,20,86400)
        cid=secrets.token_urlsafe(24);code=f'{secrets.randbelow(1000000):06d}'
        if email in self.allowed:
            if self.mailer is None:raise PortalError(503,'邮件服务尚未配置，请联系研究管理员。')
            with self.db() as c:
                c.execute('UPDATE challenges SET used=1 WHERE email=?',(email,))
                c.execute('INSERT INTO challenges(id,email,code_hash,expires) VALUES(?,?,?,?)',(cid,email,self.hashed(cid+':'+code),self.clock()+600))
            try:self.mailer(email,code)
            except Exception:
                with self.db() as c:c.execute('UPDATE challenges SET used=1 WHERE id=?',(cid,))
                raise PortalError(503,'验证码暂未发出，请稍后重试。') from None
        return {'challenge_id':cid,'message':'如果该邮箱在医生名单中，将收到10分钟有效的验证码。'}

    def verify(self,cid,email,code,ip):
        email=str(email).strip().lower();self.limit('verify:'+ip,40,600)
        if not re.fullmatch(r'\d{6}',str(code)):raise PortalError(400,'请输入6位验证码。')
        error=False
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE');r=c.execute('SELECT * FROM challenges WHERE id=?',(cid,)).fetchone()
            if not r or r['email']!=email or email not in self.allowed or r['used'] or r['expires']<self.clock() or r['attempts']>=5:error=True
            elif not hmac.compare_digest(r['code_hash'],self.hashed(cid+':'+str(code))):
                c.execute('UPDATE challenges SET attempts=attempts+1 WHERE id=?',(cid,));error=True
            else:
                c.execute('UPDATE challenges SET used=1 WHERE id=?',(cid,));token=secrets.token_urlsafe(40);csrf=secrets.token_urlsafe(32)
                c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(self.hashed(token),email,csrf,self.clock()+8*3600))
                c.execute('INSERT INTO events(email,event,target,at) VALUES(?,?,?,?)',(email,'login','',self.clock()))
        if error:raise PortalError(401,'验证码无效、已使用或已过期。')
        return token,{'email':email,'csrf':csrf}

    def session(self,token):
        with self.db() as c:r=c.execute('SELECT * FROM sessions WHERE token_hash=?',(self.hashed(token or ''),)).fetchone()
        if not r or r['expires']<self.clock() or r['email'] not in self.allowed:raise PortalError(401,'请先登录。')
        return dict(r)

    def logout(self,token):
        with self.db() as c:c.execute('DELETE FROM sessions WHERE token_hash=?',(self.hashed(token),))

    def import_bundle(self,bundle):
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            for case in bundle['cases']:
                if not ID.fullmatch(case['id']):raise ValueError('Invalid case ID')
                summary={k:v for k,v in case.items() if k!='outputs'}
                c.execute('INSERT INTO cases VALUES(?,?) ON CONFLICT(id) DO UPDATE SET summary=excluded.summary',(case['id'],json.dumps(summary,ensure_ascii=False)))
                for output in case['outputs']:
                    if not ID.fullmatch(output['id']):raise ValueError('Invalid output ID')
                    encoded=json.dumps(output,sort_keys=True,ensure_ascii=False);sha=hashlib.sha256(encoded.encode()).hexdigest()
                    old=c.execute('SELECT content_hash FROM outputs WHERE id=?',(output['id'],)).fetchone()
                    if old and old['content_hash']!=sha:raise ValueError('A released output is immutable; create a new study version')
                    occupied=c.execute('SELECT id FROM outputs WHERE case_id=? AND position=?',(case['id'],output['position'])).fetchone()
                    if occupied and occupied['id']!=output['id']:raise ValueError('Timeline position already has a released output')
                    c.execute('INSERT OR IGNORE INTO outputs VALUES(?,?,?,?,?)',(output['id'],case['id'],output['position'],sha,encoded))

    def list_cases(self,email):
        with self.db() as c:
            cases=[]
            for row in c.execute('SELECT * FROM cases'):
                item=json.loads(row['summary']);item.pop('baseline',None);outputs=[]
                for o in c.execute('SELECT o.id,o.position,o.payload,r.status FROM outputs o LEFT JOIN ratings r ON r.output_id=o.id AND r.email=? WHERE o.case_id=? ORDER BY o.position',(email,row['id'])):
                    payload=json.loads(o['payload']);outputs.append({'id':o['id'],'position':o['position'],'label':payload['label'],'status':o['status'] or 'not_started'})
                unlocked=True
                for o in outputs:
                    o['locked']=not unlocked
                    if o['status']!='submitted':unlocked=False
                item['outputs']=outputs;item['done']=sum(o['status']=='submitted' for o in outputs);cases.append(item)
        cases.sort(key=lambda x:self.hashed(email+':'+x['id']))
        return cases

    def preview(self,email,cid):
        if email not in self.allowed:raise PortalError(401,'请先登录。')
        if not ID.fullmatch(cid):raise PortalError(404,'病例不存在。')
        with self.db() as c:r=c.execute('SELECT summary FROM cases WHERE id=?',(cid,)).fetchone()
        if not r:raise PortalError(404,'病例不存在。')
        d=json.loads(r['summary']);return {'case_id':cid,**d.get('baseline',{})}

    def preview_asset(self,email,cid,aid):
        d=self.preview(email,cid)
        if aid not in {a['id'] for a in d.get('images',[])} or not re.fullmatch(r'[a-f0-9]{64}\.png',aid):raise PortalError(404,'图片不存在。')
        f=self.root/'assets'/aid
        if not f.is_file():raise PortalError(404,'图片不存在。')
        return f.read_bytes()

    def output(self,email,oid):
        if not ID.fullmatch(oid):raise PortalError(404,'记录不存在。')
        with self.db() as c:
            row=c.execute('SELECT * FROM outputs WHERE id=?',(oid,)).fetchone()
            if not row:raise PortalError(404,'记录不存在。')
            unfinished=c.execute("SELECT COUNT(*) FROM outputs o LEFT JOIN ratings r ON r.output_id=o.id AND r.email=? WHERE o.case_id=? AND o.position<? AND COALESCE(r.status,'')!='submitted'",(email,row['case_id'],row['position'])).fetchone()[0]
            if unfinished:raise PortalError(403,'请先完成此前时间点的评分。')
            rating=c.execute('SELECT * FROM ratings WHERE email=? AND output_id=?',(email,oid)).fetchone()
            if rating and rating['rubric_version']!=VERSION:raise PortalError(409,'评分标准已更新，请联系研究管理员处理旧草稿。')
            if not rating:
                c.execute('INSERT OR IGNORE INTO ratings VALUES(?,?,?,?,?,?,?,?,?,NULL)',(email,oid,row['content_hash'],VERSION,'{}','draft',0,self.clock(),self.clock()))
                rating=c.execute('SELECT * FROM ratings WHERE email=? AND output_id=?',(email,oid)).fetchone()
        data=json.loads(row['payload'])
        if rating['status']!='submitted':data.pop('reference',None)
        # Only explicit client fields are exported: never model metadata or internal ratings.
        allowed=['id','case_id','position','label','patient','context','images','answer','answer_original','report_language','assumptions','information_requests','evidence','reference','source_issues']
        data={k:v for k,v in data.items() if k in allowed}
        data.update(content_hash=row['content_hash'],rubric_version=VERSION,rating=json.loads(rating['payload']),rating_status=rating['status'],revision=rating['revision'])
        return data

    def save_rating(self,email,oid,payload,revision,submit=False,rubric_version=VERSION):
        if rubric_version!=VERSION:raise PortalError(409,'评分标准已更新为R2，请刷新页面后重新评分。')
        output=self.output(email,oid);validate_rating(payload,submit)
        if type(revision) is not int:raise PortalError(400,'评分版本无效。')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM ratings WHERE email=? AND output_id=?',(email,oid)).fetchone()
            if row['status']=='submitted':raise PortalError(409,'已提交评分锁定，原始评价保持不变。')
            if row['revision']!=revision:raise PortalError(409,'评分已在其他页面更新，请刷新后重试。')
            if row['content_hash']!=output['content_hash'] or row['rubric_version']!=VERSION:raise PortalError(409,'研究版本已变更。')
            now=self.clock();status='submitted' if submit else 'draft'
            c.execute('UPDATE ratings SET payload=?,status=?,revision=revision+1,updated_at=?,submitted_at=? WHERE email=? AND output_id=?',(json.dumps(payload,ensure_ascii=False),status,now,now if submit else None,email,oid))
            if submit:c.execute('INSERT INTO events(email,event,target,at) VALUES(?,?,?,?)',(email,'submitted',oid,now))
        return {'revision':revision+1,'status':status}

    def asset(self,email,oid,asset_id):
        data=self.output(email,oid)
        ids={a['id'] for a in data.get('images',[])}
        if data.get('reference'):ids.update(a['id'] for a in data['reference'].get('images',[]))
        if asset_id not in ids or not re.fullmatch(r'[0-9a-f]{64}\.png',asset_id):raise PortalError(404,'图片不存在。')
        path=self.root/'assets'/asset_id
        if not path.is_file():raise PortalError(404,'图片不存在。')
        return path.read_bytes()

    def export(self,email):
        buf=io.StringIO();w=csv.writer(buf);keys=[k for k,*_ in DIMENSIONS]
        w.writerow(['病例编号','时间点ID','评分标准版本','回答哈希',*[d[1] for d in DIMENSIONS],*[d[1]+'说明' for d in DIMENSIONS],'安全关键错误','安全错误事件数','安全错误事件_JSON','安全评分不一致说明','待仲裁','总体可接受性','最小必要修改','评审意见','页面活跃秒数','提交时间_北京时间'])
        with self.db() as c:
            for r in c.execute("SELECT r.*,o.case_id FROM ratings r JOIN outputs o ON o.id=r.output_id WHERE r.email=? AND r.status='submitted' AND r.rubric_version=? ORDER BY o.case_id,o.position",(email,VERSION)):
                p=json.loads(r['payload']);events=[{**e,'category':ERRORS[e['category']],'severity':SEVERITY[e['severity']],'consequences':[CONSEQUENCES[x] for x in e['consequences']]} for e in p.get('safety_events',[])]
                values=[r['case_id'],r['output_id'],r['rubric_version'],r['content_hash'],*[p['scores'][k] for k in keys],*[p.get('dimension_notes',{}).get(k,'') for k in keys],{'yes':'有','no':'未发现','uncertain':'无法判断'}[p['critical_error']],len(events),json.dumps(events,ensure_ascii=False),p.get('safety_score_explanation',''),'是' if needs_adjudication(p) else '否',OVERALL[p['overall']],p.get('minimum_change',''),p.get('comment',''),p.get('active_seconds',0),datetime.fromtimestamp(r['submitted_at'],timezone(timedelta(hours=8))).isoformat()]
                w.writerow([("'"+str(v)) if str(v).lstrip('\ufeff \t\r\n').startswith(('=','+','-','@')) else v for v in values])
        return ('\ufeff'+buf.getvalue()).encode('utf-8')

def numeric_score(value):
    return type(value) in (int,float) and 1<=value<=5


def low_safety_score(value):
    return numeric_score(value) and value<=2


def needs_adjudication(p):
    return p.get('critical_error')=='uncertain' or (any(e.get('severity')=='major' for e in p.get('safety_events',[])) and not low_safety_score(p.get('scores',{}).get('safety')))


def validate_rating(p,submit=False):
    allowed={'scores','dimension_notes','critical_error','overall','safety_events','safety_score_explanation','minimum_change','comment','active_seconds'}
    if not isinstance(p,dict) or set(p)-allowed:raise PortalError(400,'评分字段无效，请刷新R2页面。')
    scores=p.get('scores',{});keys={k for k,*_ in DIMENSIONS}
    if not isinstance(scores,dict) or set(scores)-keys or any(not (v in ('NA','NE') or numeric_score(v)) for v in scores.values()):raise PortalError(400,'评分应为1–5之间的数字（可含小数）、NA或NE。')
    def valid_text(value):return isinstance(value,str) and len(value)<=2000
    for k in ['comment','minimum_change','safety_score_explanation']:
        if not valid_text(p.get(k,'')):raise PortalError(400,'说明须为文字且不超过2000字。')
    notes=p.get('dimension_notes',{})
    if not isinstance(notes,dict) or set(notes)-keys or not all(valid_text(v) for v in notes.values()):raise PortalError(400,'逐项说明无效。')
    if p.get('critical_error') not in (None,'yes','no','uncertain') or p.get('overall') not in (None,*OVERALL):raise PortalError(400,'选择项无效。')
    seconds=p.get('active_seconds',0)
    if type(seconds) not in (float,int) or not 0<=seconds<=86400:raise PortalError(400,'计时无效。')
    events=p.get('safety_events',[]);ids=set()
    if not isinstance(events,list) or len(events)>20:raise PortalError(400,'安全事件最多20项。')
    for e in events:
        fields={'id','category','severity','consequences','dimensions','problem','case_evidence','clinical_rule','potential_consequence'}
        if not isinstance(e,dict) or set(e)-fields or not isinstance(e.get('id'),str) or not ID.fullmatch(e['id']) or e['id'] in ids:raise PortalError(400,'安全事件编号无效或重复。')
        ids.add(e['id'])
        for field,choices in [('category',ERRORS),('severity',SEVERITY)]:
            if e.get(field) not in ('',None,*choices):raise PortalError(400,'安全事件类别或严重度无效。')
        for field,choices in [('dimensions',keys),('consequences',CONSEQUENCES)]:
            values=e.get(field,[])
            if not isinstance(values,list) or any(not isinstance(v,str) or v not in choices for v in values) or len(set(values))!=len(values):raise PortalError(400,'安全事件关联项无效。')
        for field in ['problem','case_evidence','clinical_rule','potential_consequence']:
            if not valid_text(e.get(field,'')):raise PortalError(400,'安全事件说明过长或格式无效。')
        if submit and (not e.get('category') or not e.get('severity') or not e.get('consequences') or not e.get('dimensions') or any(not e.get(k,'').strip() for k in ['problem','case_evidence','clinical_rule','potential_consequence'])):raise PortalError(400,'请补全每个安全事件的原文/遗漏、病例证据、临床规则、后果、严重度及关联维度。')
    if submit:
        if set(scores)!=keys or not p.get('overall') or not p.get('critical_error'):raise PortalError(400,'请完成7项评分、总体判断和安全错误判断。')
        for key,label,*_ in DIMENSIONS:
            v=scores[key]
            if (v in ('NA','NE') or numeric_score(v) and v<=3) and not notes.get(key,'').strip():raise PortalError(400,f'请说明“{label}”的欠缺或NA/NE理由。')
        if p['overall'] in ('minor','major','reject') and not p.get('minimum_change','').strip():raise PortalError(400,'请用一句话填写最小必要修改。')
        if (p['overall']=='unable' or p['critical_error']=='uncertain') and not p.get('comment','').strip():raise PortalError(400,'请说明无法判断的原因。')
        if p['critical_error']=='yes':
            if not events:raise PortalError(400,'请至少记录一个安全关键错误事件。')
            if p['overall'] in ('accept','minor'):raise PortalError(400,'确认安全关键错误时，总体不能评为无需实质修改或小幅修改后可用。')
        elif events:raise PortalError(400,'已记录安全错误事件，请确认“有”，或移除事件并说明无法判断的原因。')
        if any(e['severity']=='major' for e in events) and not low_safety_score(scores['safety']) and not p.get('safety_score_explanation','').strip():raise PortalError(400,'重大安全错误与安全维度评分不一致，请说明理由，提交后标记待仲裁。')

def smtp_mailer(config):
    def send(email,code):
        msg=EmailMessage();msg['Subject']='[FE VTE] 医生评审登录验证码';msg['From']=config['sender'];msg['To']=email
        msg.set_content(f'您的VTE医生评审验证码为：{code}\n\n10分钟内有效，仅用于登录。请勿转发。若不是您本人操作，请忽略。')
        context=ssl.create_default_context()
        if int(config['port'])==465:client=smtplib.SMTP_SSL(config['host'],int(config['port']),context=context,timeout=20)
        else:
            client=smtplib.SMTP(config['host'],int(config['port']),timeout=20);client.starttls(context=context)
        with client:client.login(config['username'],config['password']);client.send_message(msg)
    return send

def handler(store,origin,prefix):
    parsed=urlparse(origin);secure=parsed.scheme=='https';base=prefix.rstrip('/')
    class Handler(BaseHTTPRequestHandler):
        server_version='VTEPortal';sys_version=''
        def log_message(self,*args):pass
        def headers_out(self,status,ctype='application/json; charset=utf-8',cookie=None):
            self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer')
            self.send_header('X-Frame-Options','DENY');self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'")
            if cookie:self.send_header('Set-Cookie',cookie)
            self.end_headers()
        def json(self,data,status=200,cookie=None):
            self.headers_out(status,cookie=cookie);self.wfile.write(json.dumps(data,ensure_ascii=False).encode())
        def token(self):
            c=SimpleCookie()
            try:c.load(self.headers.get('Cookie',''))
            except Exception:return ''
            return c['vte_review_session'].value if 'vte_review_session' in c else ''
        def cookie(self,value,clear=False):return f'vte_review_session={value}; Path={base}/; HttpOnly; SameSite=Strict; Max-Age={0 if clear else 28800}'+('; Secure' if secure else '')
        def route(self):
            if self.headers.get('Host','')!=parsed.netloc:raise PortalError(400,'Host无效。')
            path=unquote(urlparse(self.path).path)
            if not path.startswith(base+'/'):raise PortalError(404,'页面不存在。')
            return path[len(base):]
        def do_GET(self):
            try:
                path=self.route()
                if path in {'/','/portal.js','/portal.css','/logo.svg'}:
                    f=WEB/('index.html' if path=='/' else path[1:]);types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml'}
                    self.headers_out(200,types[f.suffix]);self.wfile.write(f.read_bytes());return
                if path=='/api/health':self.json({'status':'ok','rubric_version':VERSION});return
                who=store.session(self.token());email=who['email']
                if path=='/api/me':self.json({'email':email,'csrf':who['csrf']});return
                if path=='/api/rubric':self.json(rubric());return
                if path=='/api/cases':self.json({'cases':store.list_cases(email)});return
                m=re.fullmatch(r'/api/cases/([A-Za-z0-9_-]+)/preview',path)
                if m:self.json(store.preview(email,m[1]));return
                m=re.fullmatch(r'/api/cases/([A-Za-z0-9_-]+)/preview/assets/([a-f0-9]{64}\.png)',path)
                if m:
                    raw=store.preview_asset(email,m[1],m[2]);self.headers_out(200,'image/png');self.wfile.write(raw);return
                if path=='/api/export':self.headers_out(200,'text/csv; charset=utf-8');self.wfile.write(store.export(email));return
                m=re.fullmatch(r'/api/outputs/([A-Za-z0-9_-]+)',path)
                if m:self.json(store.output(email,m[1]));return
                m=re.fullmatch(r'/api/outputs/([A-Za-z0-9_-]+)/assets/([a-f0-9]{64}\.png)',path)
                if m:
                    raw=store.asset(email,m[1],m[2]);self.headers_out(200,'image/png');self.wfile.write(raw);return
                raise PortalError(404,'记录不存在。')
            except PortalError as e:self.json({'error':e.message},e.status)
            except (BrokenPipeError,ConnectionResetError):pass
            except Exception:self.json({'error':'服务暂时不可用。'},500)
        def do_POST(self):
            try:
                path=self.route()
                if self.headers.get('Origin')!=origin:raise PortalError(403,'请求来源无效。')
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise PortalError(415,'需要JSON请求。')
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=60000:raise PortalError(413,'请求过大，请精简说明。')
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):raise PortalError(400,'请求格式无效。')
                ip=self.headers.get('X-Real-IP',self.client_address[0]) if self.client_address[0] in {'127.0.0.1','::1'} else self.client_address[0]
                if path=='/api/auth/request':self.json(store.request_code(body.get('email',''),ip));return
                if path=='/api/auth/verify':
                    token,who=store.verify(body.get('challenge_id',''),body.get('email',''),body.get('code',''),ip);self.json(who,cookie=self.cookie(token));return
                who=store.session(self.token())
                if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),who['csrf']):raise PortalError(403,'请求验证失败，请刷新。')
                if path=='/api/auth/logout':store.logout(self.token());self.json({'ok':True},cookie=self.cookie('',True));return
                m=re.fullmatch(r'/api/outputs/([A-Za-z0-9_-]+)/ratings',path)
                if m:self.json(store.save_rating(who['email'],m[1],body.get('rating'),body.get('revision'),body.get('submit') is True,body.get('rubric_version')));return
                raise PortalError(404,'操作不存在。')
            except PortalError as e:self.json({'error':e.message},e.status)
            except (ValueError,TypeError,json.JSONDecodeError):self.json({'error':'请求格式无效。'},400)
            except (BrokenPipeError,ConnectionResetError):pass
            except Exception:self.json({'error':'服务暂时不可用。'},500)
    return Handler

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--port',type=int,default=8792)
    p.add_argument('--origin',default=os.environ.get('VTE_PORTAL_ORIGIN','http://127.0.0.1:8792'));p.add_argument('--prefix',default='/vte-review')
    p.add_argument('--import-bundle',type=Path);p.add_argument('--import-only',action='store_true');a=p.parse_args()
    smtp_path=os.environ.get('VTE_SMTP_CONFIG');mailer=smtp_mailer(json.loads(Path(smtp_path).read_text())) if smtp_path else None
    store=Store(a.root,os.environ.get('VTE_REVIEWERS','').split(','),os.environ.get('VTE_PORTAL_SECRET',''),mailer)
    if a.import_bundle:store.import_bundle(json.loads(a.import_bundle.read_text(encoding='utf-8')))
    if not a.import_only:ThreadingHTTPServer(('127.0.0.1',a.port),handler(store,a.origin,a.prefix)).serve_forever()

if __name__=='__main__':main()
