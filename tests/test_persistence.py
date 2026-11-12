import tempfile
import unittest
from pathlib import Path
from app.storage import SQLiteCaseStore, StaleCase
from app.core import Case

GOOD={'patient_ref':'1024','village':'रामपुर','contact':'९८७६५४३२१०','referral_reason':'Hospital checkup referral'}

class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'cases.sqlite3'
        self.store=SQLiteCaseStore(self.path)
    def tearDown(self):self.temp.cleanup()
    def test_case_survives_new_store_instance(self):
        c=Case(transcript='dummy sample');c.update(GOOD);self.store.create(c)
        new_process_like_store=SQLiteCaseStore(self.path)
        restored=new_process_like_store.get(c.id)
        self.assertEqual(restored.fields['contact'],'9876543210')
        self.assertEqual(restored.fields['village'],'रामपुर')
    def test_confirmation_and_demo_submission_survive_restart(self):
        c=Case();c.update(GOOD);c.confirm();c.submitted=True;c.referral_id='DEMO-ABC';self.store.create(c)
        restored=SQLiteCaseStore(self.path).get(c.id)
        self.assertTrue(restored.can_submit())
        self.assertTrue(restored.submitted)
        self.assertEqual(restored.referral_id,'DEMO-ABC')
    def test_stale_edit_cannot_overwrite_newer_version(self):
        c=Case();c.update(GOOD);self.store.create(c)
        self.store.mutate(c.id,lambda v:v.update({**GOOD,'village':'B'}),expected_version=1)
        with self.assertRaises(StaleCase):
            self.store.mutate(c.id,lambda v:v.update({**GOOD,'village':'C'}),expected_version=1)
        self.assertEqual(self.store.get(c.id).fields['village'],'B')
    def test_failed_operation_rolls_back(self):
        c=Case();self.store.create(c)
        def invalid(x):
            x.update(GOOD)
            raise ValueError('abort')
        with self.assertRaises(ValueError):self.store.mutate(c.id,invalid)
        self.assertEqual(self.store.get(c.id).version,0)
    def test_submitted_case_rejects_corrections(self):
        c=Case();c.update(GOOD);c.confirm();c.submitted=True;self.store.create(c)
        with self.assertRaises(ValueError):self.store.mutate(c.id,lambda x:x.update(GOOD))
        self.assertEqual(self.store.get(c.id).version,1)

if __name__=='__main__':unittest.main()
