import base64,csv,gzip,io,json,tempfile,threading,unittest,zipfile
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from vte_review.rating_portal import Store,PortalError,handler,validate_rating
from vte_review.rating_rubric import DIMENSIONS,VERSION
from vte_review.dataset import docx_identity,collect
from vte_review.intake import SourceStore
from vte_review.longitudinal import stage_heading

def bundle():
    return {'cases':[{'id':'CASE01','demographics':'合成病例','timepoints':2,'outputs':[
      {'id':'CASE01-T1','case_id':'CASE01','position':0,'label':'入院','context':'SYNTHETIC CURRENT','answer':'SYNTHETIC ANSWER','images':[],
       'model':'HIDDEN MODEL','reference':{'text':'HIDDEN REFERENCE','images':[{'id':'a'*64+'.png'}]}},
      {'id':'CASE01-T2','case_id':'CASE01','position':1,'label':'随访','context':'FUTURE FACT','answer':'FUTURE ANSWER','images':[],'reference':{'text':'FUTURE GOLD','images':[]}}]}]}

def rating():return {'scores':{k:4 for k,*_ in DIMENSIONS},'critical_error':'no','overall':'minor','minimum_change':'Clarify follow-up details (synthetic).','dimension_notes':{},'safety_events':[],'comment':'','active_seconds':12}

def safety_event():return {'id':'synthetic-event-1','category':'regimen','severity':'major','consequences':['bleeding'],'dimensions':['medication','safety'],'problem':'Synthetic erroneous instruction','case_evidence':'Synthetic case evidence','clinical_rule':'Synthetic reference rule','potential_consequence':'Synthetic potential bleeding consequence'}

class PortalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.now=1000;self.sent=[]
        self.store=Store(self.tmp.name,['doctor@example.com','second@example.com'],'test-only-secret-'*3,lambda e,c:self.sent.append((e,c)),clock=lambda:self.now)
        self.store.import_bundle(bundle())
    def tearDown(self):self.tmp.cleanup()
    def test_pilot_scope_preserves_old_ratings_and_blocks_all_access_paths(self):
        self.store.save_rating('doctor@example.com','CASE01-T1',rating(),0,True)
        with self.store.db() as c:
            c.execute("UPDATE ratings SET rubric_version='VTE-R2-2026-10-13'")
            before=[tuple(r) for r in c.execute('SELECT * FROM ratings')]
        other=json.loads(json.dumps(bundle()).replace('CASE01','CASE41'))
        self.store.import_bundle(other)
        Path(self.tmp.name,'active-study.json').write_text(json.dumps({'rubric_version':VERSION,'case_ids':['CASE41']}))
        scoped=Store(self.tmp.name,['doctor@example.com'],'test-only-secret-'*3)
        self.assertEqual([c['id'] for c in scoped.list_cases('doctor@example.com')],['CASE41'])
        self.assertEqual(scoped.list_methods('doctor@example.com')[-1]['total'],2)
        for call in [lambda:scoped.output('doctor@example.com','CASE01-T1'),lambda:scoped.preview('doctor@example.com','CASE01'),lambda:scoped.asset('doctor@example.com','CASE01-T1','a'*64+'.png')]:
            with self.assertRaises(PortalError) as err:call()
            self.assertEqual(err.exception.status,404)
        self.assertNotIn('CASE01',scoped.export('doctor@example.com').decode('utf-8'))
        with scoped.db() as c:self.assertEqual(before,[tuple(r) for r in c.execute('SELECT * FROM ratings')])
    def test_scope_configuration_fails_closed(self):
        Path(self.tmp.name,'active-study.json').write_text(json.dumps({'rubric_version':'old','case_ids':[]}))
        with self.assertRaises(ValueError):Store(self.tmp.name,[],'test-only-secret-'*3)
    def login(self,email='doctor@example.com'):
        d=self.store.request_code(email,'test-ip');code=self.sent[-1][1]
        return self.store.verify(d['challenge_id'],email,code,'test-ip')
    def test_allowlist_unknown_does_not_send(self):
        self.store.request_code('stranger@example.com','test-ip');self.assertEqual(self.sent,[])
    def test_otp_not_stored_plaintext(self):
        d=self.store.request_code('doctor@example.com','test-ip');code=self.sent[-1][1]
        with self.store.db() as c:r=c.execute('select code_hash from challenges').fetchone()
        self.assertNotEqual(r[0],code);self.assertNotIn('code',d)
    def test_expiry_and_replay(self):
        d=self.store.request_code('doctor@example.com','test-ip');code=self.sent[-1][1]
        self.store.verify(d['challenge_id'],'doctor@example.com',code,'test-ip')
        with self.assertRaises(PortalError):self.store.verify(d['challenge_id'],'doctor@example.com',code,'test-ip')
        self.now+=61;d=self.store.request_code('doctor@example.com','test-ip');code=self.sent[-1][1];self.now+=601
        with self.assertRaises(PortalError):self.store.verify(d['challenge_id'],'doctor@example.com',code,'test-ip')
    def test_wrong_codes_lock_challenge(self):
        d=self.store.request_code('doctor@example.com','test-ip');code=self.sent[-1][1]
        wrong='000000' if code!='000000' else '000001'
        for _ in range(5):
            with self.assertRaises(PortalError):self.store.verify(d['challenge_id'],'doctor@example.com',wrong,'test-ip')
        with self.assertRaises(PortalError):self.store.verify(d['challenge_id'],'doctor@example.com',code,'test-ip')
    def test_rate_limit(self):
        self.store.request_code('doctor@example.com','test-ip')
        with self.assertRaises(PortalError) as e:self.store.request_code('doctor@example.com','test-ip')
        self.assertEqual(e.exception.status,429)
    def test_sessions_expire_and_revocation_is_immediate(self):
        token,who=self.login();self.assertEqual(self.store.session(token)['email'],who['email'])
        self.store.allowed.clear()
        with self.assertRaises(PortalError):self.store.session(token)
        self.store.allowed.add('doctor@example.com');self.now+=28801
        with self.assertRaises(PortalError):self.store.session(token)
    def test_log_out(self):
        token,_=self.login();self.store.logout(token)
        with self.assertRaises(PortalError):self.store.session(token)
    def test_password_accounts_are_salted_and_isolated(self):
        password='synthetic-review-password'
        for username in ['doctor1','doctor2']:self.store.create_account(username,password)
        token,who=self.store.password_login('DOCTOR1',password,'test-ip')
        self.assertEqual(who['email'],'doctor1');self.assertEqual(self.store.session(token)['email'],'doctor1')
        with self.store.db() as c:rows=c.execute('SELECT salt,password_hash FROM accounts ORDER BY username').fetchall()
        self.assertNotEqual(rows[0]['salt'],rows[1]['salt']);self.assertNotEqual(rows[0]['password_hash'],rows[1]['password_hash'])
        self.assertNotIn(password,str([tuple(r) for r in rows]))
        r=rating();r['scores']['dose']=4.25
        self.store.save_rating('doctor1','CASE01-T1',r,0,True)
        self.assertEqual(self.store.output('doctor2','CASE01-T1')['rating'],{})
        self.assertNotIn('4.25',self.store.export('doctor2').decode('utf-8'))
        self.assertEqual(self.store.list_methods('doctor1')[-1]['done'],1)
        self.assertEqual(self.store.list_methods('doctor2')[-1]['done'],0)
        self.store.preview('doctor1','CASE01')
    def test_password_disabled_account_revokes_session_and_login_is_limited(self):
        self.store.create_account('doctor1','synthetic-review-password')
        token,_=self.store.password_login('doctor1','synthetic-review-password','test-ip')
        with self.store.db() as c:c.execute("UPDATE accounts SET enabled=0 WHERE username='doctor1'")
        with self.assertRaises(PortalError):self.store.session(token)
        with self.assertRaises(PortalError):self.store.password_login('doctor1','synthetic-review-password','test-ip')
        for _ in range(8):
            with self.assertRaises(PortalError) as error:self.store.password_login('doctor1','wrong','test-ip')
            self.assertEqual(error.exception.status,401)
        with self.assertRaises(PortalError) as error:self.store.password_login('doctor1','wrong','test-ip')
        self.assertEqual(error.exception.status,429)
    def test_unknown_password_account_and_bad_input_are_generic(self):
        for username,password in [('missing','anything'),('doctor1',None),('invalid name','anything')]:
            with self.assertRaises(PortalError) as error:self.store.password_login(username,password,'test-ip')
            self.assertEqual(error.exception.status,401)
        with self.store.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0],0)
    def baseline_bundle(self):
        b=bundle();b['method_id']='baseline'
        for o in b['cases'][0]['outputs']:o['id']='BASE-'+o['id'];o['answer']='SYNTHETIC BASELINE '+o['answer']
        return b
    def test_method_groups_do_not_duplicate_missing_reports(self):
        groups=self.store.list_methods('doctor@example.com')
        self.assertEqual([g['total'] for g in groups],[0,0,0,2])
        self.assertEqual(self.store.list_cases('doctor@example.com','baseline')[0]['outputs'],[])
        with self.assertRaises(PortalError):self.store.list_cases('doctor@example.com','unknown')
    def test_method_ratings_timeline_and_exports_are_separate(self):
        self.store.import_bundle(self.baseline_bundle())
        self.store.save_rating('doctor@example.com','CASE01-T1',rating(),0,True)
        self.store.output('doctor@example.com','CASE01-T2')
        with self.assertRaises(PortalError):self.store.output('doctor@example.com','BASE-CASE01-T2')
        base=self.store.output('doctor@example.com','BASE-CASE01-T1')
        self.assertEqual(base['rating'],{});self.assertEqual(base['method_id'],'baseline');self.assertNotIn('reference',base)
        self.assertEqual(self.store.list_cases('doctor@example.com','baseline')[0]['done'],0)
        self.store.save_rating('doctor@example.com','BASE-CASE01-T1',rating(),0,True)
        for method,oid in [('baseline','BASE-CASE01-T1'),('reviewed','CASE01-T1')]:
            rows=list(csv.DictReader(io.StringIO(self.store.export('doctor@example.com',method).decode('utf-8-sig'))))
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['方法编号'],method);self.assertEqual(rows[0]['时间点ID'],oid)
        self.assertEqual(len(list(csv.DictReader(io.StringIO(self.store.export('doctor@example.com').decode('utf-8-sig'))))),2)
    def test_published_output_cannot_change_method(self):
        b=bundle();b['method_id']='baseline'
        with self.assertRaises(ValueError):self.store.import_bundle(b)
    def test_method_schema_migration_preserves_outputs_and_ratings(self):
        self.store.save_rating('doctor@example.com','CASE01-T1',rating(),0,True)
        with self.store.db() as c:
            original_outputs=[tuple(r) for r in c.execute('SELECT id,case_id,position,content_hash,payload FROM outputs ORDER BY id')]
            original_ratings=[tuple(r) for r in c.execute('SELECT * FROM ratings')]
            c.executescript('''ALTER TABLE outputs RENAME TO outputs_new;
                CREATE TABLE outputs(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,position INTEGER NOT NULL,content_hash TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(case_id,position));
                INSERT INTO outputs SELECT id,case_id,position,content_hash,payload FROM outputs_new;
                DROP TABLE outputs_new;''')
        migrated=Store(self.tmp.name,self.store.allowed,'test-only-secret-'*3,clock=lambda:self.now)
        with migrated.db() as c:
            self.assertEqual([tuple(r) for r in c.execute('SELECT id,case_id,position,content_hash,payload FROM outputs ORDER BY id')],original_outputs)
            self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM ratings')],original_ratings)
            self.assertEqual({r[0] for r in c.execute('SELECT method_id FROM outputs')},{'reviewed'})
        migrated.import_bundle(self.baseline_bundle())
        self.assertEqual([g['total'] for g in migrated.list_methods('doctor@example.com')],[2,0,0,2])
    def test_reference_and_future_are_not_exported(self):
        o=self.store.output('doctor@example.com','CASE01-T1')
        self.assertNotIn('reference',o);self.assertNotIn('model',o);self.assertNotIn('FUTURE',json.dumps(o))
        with self.assertRaises(PortalError):self.store.output('doctor@example.com','CASE01-T2')
    def test_reference_assets_locked_before_submission(self):
        with self.assertRaises(PortalError):self.store.asset('doctor@example.com','CASE01-T1','a'*64+'.png')
    def test_submit_unlocks_only_current_reference_and_next_visit(self):
        self.store.save_rating('doctor@example.com','CASE01-T1',rating(),0,True)
        self.assertEqual(self.store.output('doctor@example.com','CASE01-T1')['reference']['text'],'HIDDEN REFERENCE')
        self.assertNotIn('reference',self.store.output('doctor@example.com','CASE01-T2'))
    def test_drafts_resume_and_stale_writes_rejected(self):
        r=rating();self.store.save_rating('doctor@example.com','CASE01-T1',r,0)
        self.assertEqual(self.store.output('doctor@example.com','CASE01-T1')['rating'],r)
        with self.assertRaises(PortalError):self.store.save_rating('doctor@example.com','CASE01-T1',rating(),0)
    def test_submitted_ratings_immutable_and_independent(self):
        self.store.save_rating('doctor@example.com','CASE01-T1',rating(),0,True)
        with self.assertRaises(PortalError):self.store.save_rating('doctor@example.com','CASE01-T1',rating(),1)
        o=self.store.output('second@example.com','CASE01-T1');self.assertEqual(o['rating'],{});self.assertNotIn('reference',o)
    def test_changed_model_output_refused(self):
        b=bundle();b['cases'][0]['outputs'][0]['answer']='CHANGED'
        with self.assertRaises(ValueError):self.store.import_bundle(b)
    def test_idempotent_import_preserves_rating(self):
        self.store.save_rating('doctor@example.com','CASE01-T1',rating(),0,True);self.store.import_bundle(bundle())
        self.assertEqual(self.store.output('doctor@example.com','CASE01-T1')['rating_status'],'submitted')
    def test_pending_preview_contains_only_baseline(self):
        b={'cases':[{'id':'CASE02','demographics':'Synthetic','timepoints':2,'baseline':{'context':'INITIAL ONLY','images':[]},'outputs':[]}]}
        self.store.import_bundle(b)
        self.assertEqual(self.store.preview('doctor@example.com','CASE02')['context'],'INITIAL ONLY')
        self.assertNotIn('baseline',next(c for c in self.store.list_cases('doctor@example.com') if c['id']=='CASE02'))
        with self.assertRaises(PortalError):self.store.preview('stranger@example.com','CASE02')
    def test_timeline_position_cannot_be_silently_replaced(self):
        b=bundle();b['cases'][0]['outputs'][0]['id']='OTHER'
        with self.assertRaises(ValueError):self.store.import_bundle(b)
    def test_required_safety_and_na_explanations(self):
        r=rating();r['critical_error']='yes'
        with self.assertRaises(PortalError):validate_rating(r,True)
        r.update(safety_events=[safety_event()],overall='major');r['scores']['safety']=2;r['dimension_notes']['safety']='Synthetic risk';validate_rating(r,True)
        for value in ['NA','NE']:
            r=rating();r['scores']['dose']=value
            with self.assertRaises(PortalError):validate_rating(r,True)
            r['dimension_notes']['dose']='Reason specific to this dimension';validate_rating(r,True)
    def test_each_low_score_needs_its_own_note(self):
        for score in [1,2,3]:
            r=rating();r['scores']['dose']=score;r['comment']='General comment'
            with self.assertRaises(PortalError):validate_rating(r,True)
            r['dimension_notes']['dose']='Specific deficiency';validate_rating(r,True)
    def test_critical_error_cannot_be_accepted_and_mismatch_needs_reason(self):
        r=rating();r.update(critical_error='yes',safety_events=[safety_event()],safety_score_explanation='Needs adjudication')
        for overall in ['accept','minor']:
            r['overall']=overall
            with self.assertRaises(PortalError):validate_rating(r,True)
        r['overall']='major';r.pop('safety_score_explanation')
        with self.assertRaises(PortalError):validate_rating(r,True)
        r['safety_score_explanation']='Explanation for adjudication';validate_rating(r,True)
        self.store.save_rating('doctor@example.com','CASE01-T1',r,0,True)
        row=list(csv.DictReader(io.StringIO(self.store.export('doctor@example.com').decode('utf-8-sig'))))[0]
        self.assertEqual(row['待仲裁'],'是');self.assertEqual(row['安全错误事件数'],'1')
        self.assertEqual(json.loads(row['安全错误事件_JSON'])[0]['id'],'synthetic-event-1')
    def test_event_evidence_completeness_and_duplicate_ids(self):
        r=rating();r.update(critical_error='yes',overall='major',safety_events=[safety_event()],safety_score_explanation='Explain')
        for key in ['case_evidence','clinical_rule','potential_consequence','problem','category','severity','consequences','dimensions']:
            changed=json.loads(json.dumps(r));changed['safety_events'][0].pop(key)
            validate_rating(changed,False)
            with self.assertRaises(PortalError):validate_rating(changed,True)
        r['safety_events'].append(safety_event())
        with self.assertRaises(PortalError):validate_rating(r,False)
    def test_uncertain_is_not_forced_into_an_error_event(self):
        r=rating();r.update(critical_error='uncertain',overall='unable')
        with self.assertRaises(PortalError):validate_rating(r,True)
        r['comment']='Missing review materials';validate_rating(r,True)
    def test_no_error_cannot_contain_confirmed_event(self):
        r=rating();r['safety_events']=[safety_event()]
        with self.assertRaises(PortalError):validate_rating(r,True)
    def test_version_guard_prevents_old_browser_writes(self):
        for version in [None,'VTE-R1-2026-10-12']:
            with self.assertRaises(PortalError) as e:self.store.save_rating('doctor@example.com','CASE01-T1',rating(),0,True,version)
            self.assertEqual(e.exception.status,409)
        with self.store.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM ratings').fetchone()[0],0)
    def test_r2_csv_preserves_na_ne_and_notes(self):
        r=rating();r['scores'].update(dose='NA',timeline='NE');r['dimension_notes'].update(dose='Not applicable',timeline='Insufficient materials')
        self.store.save_rating('doctor@example.com','CASE01-T1',r,0,True)
        row=list(csv.DictReader(io.StringIO(self.store.export('doctor@example.com').decode('utf-8-sig'))))[0]
        self.assertEqual(row['评分标准版本'],VERSION);self.assertEqual(row['剂量准确性'],'NA');self.assertEqual(row['疗程决策'],'NE');self.assertEqual(row['疗程决策说明'],'Insufficient materials')
    def test_decimal_scores_survive_save_reload_submit_and_csv(self):
        r=rating();r['scores'].update(dose=3.5,medication=4.25,timeline=1.5);r['dimension_notes']['timeline']='Synthetic missing timeline detail'
        self.store.save_rating('doctor@example.com','CASE01-T1',r,0)
        self.assertEqual(self.store.output('doctor@example.com','CASE01-T1')['rating']['scores'],r['scores'])
        self.store.save_rating('doctor@example.com','CASE01-T1',r,1,True)
        row=list(csv.DictReader(io.StringIO(self.store.export('doctor@example.com').decode('utf-8-sig'))))[0]
        self.assertEqual(row['剂量准确性'],'3.5');self.assertEqual(row['药物选择适宜性'],'4.25');self.assertEqual(row['疗程决策'],'1.5')
    def test_decimal_low_notes_and_safety_thresholds(self):
        r=rating();r['scores']['safety']=2.5
        with self.assertRaises(PortalError):validate_rating(r,True)
        r['dimension_notes']['safety']='Synthetic deficiency';validate_rating(r,True)
        r.update(critical_error='yes',overall='major',safety_events=[safety_event()])
        with self.assertRaises(PortalError):validate_rating(r,True)
        r['scores']['safety']=1.5;validate_rating(r,True)
        r['scores']['safety']=2.5;r['safety_score_explanation']='Explanation for adjudication';validate_rating(r,True)
    def test_invalid_scores_and_low_score_comment(self):
        for v in [0,6,True,False,0.9,5.01,float('nan'),float('inf'),float('-inf'),'4.5']:
            r=rating();r['scores']['safety']=v
            with self.assertRaises(PortalError):validate_rating(r,True)
        r=rating();r['scores']['safety']=1
        with self.assertRaises(PortalError):validate_rating(r,True)
    def test_csv_neutralizes_formula(self):
        r=rating();r['comment']='=1+1';self.store.save_rating('doctor@example.com','CASE01-T1',r,0,True)
        self.assertIn("'=1+1",self.store.export('doctor@example.com').decode('utf-8'))
        self.assertNotIn("'=1+1",self.store.export('second@example.com').decode('utf-8'))
    def test_http_auth_origin_csrf_and_private_files(self):
        srv=ThreadingHTTPServer(('127.0.0.1',0),handler(self.store,'http://127.0.0.1:1','/vte-review'))
        origin=f'http://127.0.0.1:{srv.server_port}';srv.RequestHandlerClass=handler(self.store,origin,'/vte-review')
        thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        def get(path,headers=None,data=None):
            req=Request(origin+'/vte-review/'+path,headers=headers or {},data=json.dumps(data).encode() if data is not None else None)
            try:
                with urlopen(req) as r:return r.status,r.read(),r.headers
            except HTTPError as e:return e.code,e.read(),e.headers
        try:
            self.assertEqual(get('api/cases')[0],401);self.assertEqual(get('private/source.docx')[0],401)
            self.assertEqual(get('api/methods')[0],401)
            self.store.create_account('doctor1','synthetic-review-password')
            password_headers={'Content-Type':'application/json','Origin':'https://untrusted.example'}
            credentials={'username':'doctor1','password':'synthetic-review-password'}
            self.assertEqual(get('api/auth/password',password_headers,credentials)[0],403)
            password_headers['Origin']=origin
            password_status,password_raw,password_response=get('api/auth/password',password_headers,credentials)
            self.assertEqual(password_status,200);self.assertNotIn(b'synthetic-review-password',password_raw)
            self.assertIn('HttpOnly',password_response['Set-Cookie'])
            account_header={'Cookie':password_response['Set-Cookie'].split(';')[0]}
            self.assertEqual(get('api/methods',account_header)[0],200)
            self.assertEqual(json.loads(get('api/cases?method=baseline',account_header)[1])['cases'][0]['outputs'],[])
            self.assertEqual(get('api/export?method=invalid',account_header)[0],400)
            token,who=self.login();h={'Cookie':'vte_review_session='+token}
            plain=get('api/rubric',h)[1]
            status,packed,headers=get('api/rubric',{**h,'Accept-Encoding':'gzip, deflate, br'})
            self.assertEqual(status,200);self.assertEqual(headers['Content-Encoding'],'gzip')
            self.assertEqual(gzip.decompress(packed),plain);self.assertLess(len(packed),len(plain))
            self.assertEqual(headers['Cache-Control'],'no-store')
            self.assertNotIn('Content-Encoding',get('api/rubric',{**h,'Accept-Encoding':'gzip;q=0'})[2])
            status,raw,_=get('api/outputs/CASE01-T1',h);self.assertEqual(status,200);self.assertNotIn(b'HIDDEN REFERENCE',raw)
            self.assertEqual(get('api/outputs/CASE01-T2',h)[0],403)
            h.update({'Content-Type':'application/json','Origin':'https://untrusted.example'})
            self.assertEqual(get('api/auth/logout',h,{})[0],403)
            h['Origin']=origin;self.assertEqual(get('api/auth/logout',h,{})[0],403)
            h['X-CSRF-Token']=who['csrf']
            body={'rating':rating(),'revision':0,'submit':True}
            self.assertEqual(get('api/outputs/CASE01-T1/ratings',h,body)[0],409)
            body['rubric_version']=VERSION
            self.assertEqual(get('api/outputs/CASE01-T1/ratings',h,body)[0],200)
            self.assertEqual(get('api/auth/logout',h,{})[0],200)
            self.assertEqual(get('api/cases',h)[0],401)
        finally:srv.shutdown();srv.server_close();thread.join()

class DatasetTests(unittest.TestCase):
    def docx(self,directory=False,variant='a'):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Synthetic case '+variant+'</w:t></w:r></w:p></w:body></w:document>')
            if directory:z.writestr('word/media/','')
        return out.getvalue()
    def test_semantic_dedup_ignores_zip_directory_entries(self):
        self.assertEqual(docx_identity(self.docx())[0],docx_identity(self.docx(True))[0])
    def test_image_position_changes_are_not_duplicates(self):
        def make(reverse):
            out=io.BytesIO();ids=['r2','r1'] if reverse else ['r1','r2']
            with zipfile.ZipFile(out,'w') as z:
                z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:a="urn:drawing"><w:p><w:t>Visit 1</w:t><a:blip r:embed="'+ids[0]+'"/></w:p><w:p><w:t>Visit 2</w:t><a:blip r:embed="'+ids[1]+'"/></w:p></w:document>')
                z.writestr('word/_rels/document.xml.rels','<Relationships><Relationship Id="r1" Target="media/a.png"/><Relationship Id="r2" Target="media/b.png"/></Relationships>')
                z.writestr('word/media/a.png',b'image A');z.writestr('word/media/b.png',b'image B')
            return out.getvalue()
        self.assertNotEqual(docx_identity(make(False))[0],docx_identity(make(True))[0])
    def test_empty_media_directory_is_not_an_image(self):
        with tempfile.TemporaryDirectory() as d:
            s=SourceStore(Path(d));r=s.ingest('synthetic.docx',base64.b64encode(self.docx(True)).decode());self.assertEqual(r['images'],[])
    def test_chinese_relative_headings(self):
        self.assertEqual(stage_heading('日期：术后三周'),('postoperative-3-week','3 weeks postoperative','relative'))
        self.assertEqual(stage_heading('随访十二个月')[0],'follow-up-12-month')
        self.assertIsNone(stage_heading('患者三周前开始治疗'))
    def test_collection_reuses_old_cases_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);prior=p/'prior/CASE01';prior.mkdir(parents=True);(prior/'source.docx').write_bytes(self.docx())
            inc=p/'incoming';inc.mkdir()
            with zipfile.ZipFile(inc/'batch.zip','w') as z:z.writestr('old.docx',self.docx(True));z.writestr('new.docx',self.docx(variant='b'))
            gold=p/'results.json';gold.write_text(json.dumps({'cases':[{'case':'CASE01','nodes':[{'answer':'old'}]}]}))
            a=collect(inc,p/'data',p/'prior',gold);b=collect(inc,p/'data',p/'prior',gold)
            self.assertEqual(a,b);self.assertEqual(a['unique_cases'],2);self.assertEqual(a['duplicates'],1);self.assertEqual(a['completed_reused'],1)
    def test_zip_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);inc=p/'incoming';inc.mkdir()
            with zipfile.ZipFile(inc/'bad.zip','w') as z:z.writestr('../escape.docx',self.docx())
            with self.assertRaises(ValueError):collect(inc,p/'data',p/'prior',p/'none.json')
            self.assertFalse((p/'escape.docx').exists())

if __name__=='__main__':unittest.main()
