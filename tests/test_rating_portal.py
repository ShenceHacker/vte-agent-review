import base64,io,json,tempfile,threading,unittest,zipfile
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from vte_review.rating_portal import Store,PortalError,handler,validate_rating
from vte_review.rating_rubric import DIMENSIONS
from vte_review.dataset import docx_identity,collect
from vte_review.intake import SourceStore
from vte_review.longitudinal import stage_heading

def bundle():
    return {'cases':[{'id':'CASE01','demographics':'合成病例','timepoints':2,'outputs':[
      {'id':'CASE01-T1','case_id':'CASE01','position':0,'label':'入院','context':'SYNTHETIC CURRENT','answer':'SYNTHETIC ANSWER','images':[],
       'model':'HIDDEN MODEL','reference':{'text':'HIDDEN REFERENCE','images':[{'id':'a'*64+'.png'}]}},
      {'id':'CASE01-T2','case_id':'CASE01','position':1,'label':'随访','context':'FUTURE FACT','answer':'FUTURE ANSWER','images':[],'reference':{'text':'FUTURE GOLD','images':[]}}]}]}

def rating():return {'scores':{k:4 for k,*_ in DIMENSIONS},'critical_error':'no','overall':'minor','error_types':[],'comment':'','active_seconds':12}

class PortalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.now=1000;self.sent=[]
        self.store=Store(self.tmp.name,['doctor@example.com','second@example.com'],'test-only-secret-'*3,lambda e,c:self.sent.append((e,c)),clock=lambda:self.now)
        self.store.import_bundle(bundle())
    def tearDown(self):self.tmp.cleanup()
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
        r.update(potential_harm='major',error_types=['wrong_drug'],comment='Wrong drug');validate_rating(r,True)
        r=rating();r['scores']['diagnosis']='NA'
        with self.assertRaises(PortalError):validate_rating(r,True)
        r['na_reason']='Insufficient supporting data';validate_rating(r,True)
    def test_invalid_scores_and_low_score_comment(self):
        for v in [0,6,True,3.5]:
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
            token,who=self.login();h={'Cookie':'vte_review_session='+token}
            status,raw,_=get('api/outputs/CASE01-T1',h);self.assertEqual(status,200);self.assertNotIn(b'HIDDEN REFERENCE',raw)
            self.assertEqual(get('api/outputs/CASE01-T2',h)[0],403)
            h.update({'Content-Type':'application/json','Origin':'https://untrusted.example'})
            self.assertEqual(get('api/auth/logout',h,{})[0],403)
            h['Origin']=origin;self.assertEqual(get('api/auth/logout',h,{})[0],403)
            h['X-CSRF-Token']=who['csrf'];self.assertEqual(get('api/auth/logout',h,{})[0],200)
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
