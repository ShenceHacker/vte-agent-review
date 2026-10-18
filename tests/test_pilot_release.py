from copy import deepcopy
import unittest
import tempfile,json
from scripts.deploy_rating_pilot_remote import validate_pilot,prune_to_pilot,VERSION
from vte_review.rating_portal import Store
from tests.test_rating_portal import bundle,rating


class PilotReleaseTests(unittest.TestCase):
    def setUp(self):
        self.study={'rubric_version':VERSION,'case_ids':['CASE'+str(i) for i in range(41,51)]}
        self.bundle={'cases':[{'id':cid,'timepoints':3,'outputs':[{'case_id':cid,'method_id':m,'position':p} for m in ('baseline','rag','synthesis','reviewed') for p in range(3)]} for cid in self.study['case_ids']]}

    def test_full_followup_and_all_four_methods_required(self):
        validate_pilot(self.bundle,self.study)
        for index in (0,3,6,9):
            missing=deepcopy(self.bundle);missing['cases'][0]['outputs'].pop(index)
            with self.assertRaises(ValueError):validate_pilot(missing,self.study)

    def test_duplicate_timepoint_cannot_replace_missing_followup(self):
        self.bundle['cases'][0]['outputs'][1]['position']=0
        with self.assertRaises(ValueError):validate_pilot(self.bundle,self.study)

    def test_scope_cannot_silently_expand_or_change_version(self):
        expanded=deepcopy(self.bundle);expanded['cases'].append(deepcopy(expanded['cases'][0]))
        with self.assertRaises(ValueError):validate_pilot(expanded,self.study)
        self.study['rubric_version']='old'
        with self.assertRaises(ValueError):validate_pilot(self.bundle,self.study)

    def test_archived_cohort_removal_keeps_pilot_ratings_and_accounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            s=Store(tmp,['doctor@example.com'],'test-only-secret-'*3)
            s.import_bundle(bundle());s.import_bundle(json.loads(json.dumps(bundle()).replace('CASE01','CASE41')))
            for case in ('CASE01','CASE41'):s.save_rating('doctor@example.com',case+'-T1',rating(),0,True)
            s.create_account('doctor1','synthetic-only-password')
            with s.db() as c:
                pilot=tuple(c.execute("SELECT * FROM ratings WHERE output_id='CASE41-T1'").fetchone())
                accounts=[tuple(r) for r in c.execute('SELECT * FROM accounts')]
            prune_to_pilot(s,['CASE41'])
            with s.db() as c:
                self.assertEqual([r[0] for r in c.execute('SELECT id FROM cases')],['CASE41'])
                self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM ratings')],[pilot])
                self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM accounts')],accounts)
                self.assertEqual(c.execute('PRAGMA freelist_count').fetchone()[0],0)
                self.assertEqual(c.execute('PRAGMA quick_check').fetchone()[0],'ok')
