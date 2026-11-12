import unittest
from app.extraction import parse_transcript, normalize_digits
from app.core import Case, validate

PRISMA_REAL_SHAPE_SYNTHETIC = ('नमस्ते पेशेंट्स का रेफरेंस नंबर १०२४ है पेशेंट्स रामपुर गाँव से हैं '
    'कॉन्टेक्ट नंबर ९८७६५४३२१० है पेशेंट को चेकअप के लिए हॉस्पिटल रेफरल की जरूरत है '
    'कृपया हॉस्पिटल रेफरल अरेंज करें')

class ExtractionTests(unittest.TestCase):
    def test_actual_prisma_response_regression(self):
        result = parse_transcript(PRISMA_REAL_SHAPE_SYNTHETIC)
        self.assertEqual(result, {
            'patient_ref': '1024', 'village': 'रामपुर',
            'contact': '9876543210',
            'referral_reason': 'पेशेंट को चेकअप के लिए हॉस्पिटल रेफरल की जरूरत है'})
        self.assertNotIn('कृपया', result['referral_reason'])

    def test_english_colon_transcript_backwards_compatible(self):
        p = parse_transcript('Patient ID: DEMO-001, village: Rampur, contact: 9999999999, reason: transport coordination requested')
        self.assertEqual(p['patient_ref'], 'DEMO-001')
        self.assertEqual(p['village'], 'Rampur')
        self.assertEqual(p['contact'], '9999999999')
        self.assertEqual(p['referral_reason'], 'transport coordination requested')

    def test_hinglish_latin(self):
        p = parse_transcript('Patient reference 1024 hai village Rampur contact number 9876543210 referral reason: hospital checkup')
        self.assertEqual(p['patient_ref'], '1024')
        self.assertEqual(p['contact'], '9876543210')
        self.assertEqual(p['village'], 'Rampur')
        self.assertEqual(p['referral_reason'], 'hospital checkup')

    def test_unicode_numerals_and_phone_normalization(self):
        self.assertEqual(normalize_digits('०१२३४५६७८९ 123'), '0123456789 123')
        c = Case(); c.update({'patient_ref':'1024','village':'रामपुर', 'contact':'९८७६५ ४३२१०', 'referral_reason':'hospital evaluation'})
        self.assertEqual(c.fields['contact'], '9876543210')
        self.assertEqual(validate(c.fields), {})
        c.confirm(); self.assertTrue(c.can_submit())

    def test_ambiguous_reference_not_guessed(self):
        p = parse_transcript('Patient ID: 1024, Patient ID: 2048, village: Rampur, contact: 9876543210, reason: transfer coordination')
        self.assertEqual(p['patient_ref'], '')

    def test_no_implicit_fields_or_clinical_diagnosis(self):
        self.assertEqual(parse_transcript('कृपया जल्दी आना है, आज एक मरीज है'), dict.fromkeys(('patient_ref','village','contact','referral_reason'), ''))

    def test_contact_with_missing_digit_remains_blank(self):
        p = parse_transcript('contact number 987654321, village: Rampur')
        self.assertEqual(p['contact'], '')

    def test_edit_after_confirmation_invalidates(self):
        c=Case(transcript=PRISMA_REAL_SHAPE_SYNTHETIC)
        c.fields=parse_transcript(c.transcript)
        c.confirm(); self.assertTrue(c.can_submit())
        c.update({**c.fields, 'village':'Other'})
        self.assertFalse(c.can_submit())

    def test_transcript_is_not_changed(self):
        c=Case(transcript=PRISMA_REAL_SHAPE_SYNTHETIC)
        c.fields=parse_transcript(c.transcript)
        self.assertIn('१०२४', c.transcript)

if __name__=='__main__': unittest.main()
