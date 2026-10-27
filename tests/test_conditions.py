import unittest
from agentic_rag.catalog import Catalog
from agentic_rag.tools import AcademicTools

class RecordedConditionTests(unittest.TestCase):
    def setUp(self): self.tools = AcademicTools(Catalog())
    def test_chain_and_bare_codes(self):
        r = self.tools.conditions('IT320', 'K37', depth=2)
        self.assertEqual([n['course_code'] for n in r['nodes']], ['IT320','CS122','CS121'])
        self.assertEqual(r['nodes'][0]['components'][0]['kind'], 'COURSE_CODE')
        self.assertTrue(all(c['workbook_row'] for c in r['citations']))
    def test_multiple_explicit_components(self):
        r = self.tools.conditions('IT499','K37')
        self.assertEqual(sorted(c['threshold'] for c in r['nodes'][0]['components']), [4,7,100])
        self.assertEqual(r['status'],'recorded_conditions')
    def test_missing_reference_and_blank(self):
        r = self.tools.conditions('AD219','K37',depth=2)
        self.assertIn('AD213',r['missing_references'])
        self.assertEqual(r['status'],'insufficient_data')
        r = self.tools.conditions('CS121','K37')
        self.assertEqual(r['status'],'insufficient_data')
        self.assertEqual(r['nodes'][0]['prerequisite_status'],'SOURCE_BLANK')
