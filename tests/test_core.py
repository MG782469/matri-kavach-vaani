import unittest
from app.core import Case, validate, parse_transcript

GOOD={'patient_ref':'DEMO001','village':'Rampur','contact':'9999999999','referral_reason':'Clinician-requested transfer'}
class CaseTests(unittest.TestCase):
    def test_incomplete_cannot_confirm(self):
        c=Case()
        with self.assertRaises(ValueError):c.confirm()
    def test_confirmation_and_edit_invalidation(self):
        c=Case(); c.update(GOOD);c.confirm();self.assertTrue(c.can_submit())
        changed={**GOOD,'village':'Rampura'};c.update(changed)
        self.assertFalse(c.can_submit())
    def test_critical_contact_format(self):
        self.assertIn('contact',validate({**GOOD,'contact':'999'}))
    def test_parse_conservative(self):
        v=parse_transcript('Patient ID: DEMO001, village: Rampur, contact: 9999999999, reason: transport coordination')
        self.assertEqual(v['patient_ref'],'DEMO001')
        self.assertEqual(v['contact'],'9999999999')
    def test_external_field_mutation_detected(self):
        c=Case();c.update(GOOD);c.confirm();c.fields['village']='Different'
        self.assertFalse(c.can_submit())
if __name__=='__main__':unittest.main()
