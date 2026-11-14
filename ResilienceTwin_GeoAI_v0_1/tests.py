import unittest
from engine import evaluate,compare
class SimulationTests(unittest.TestCase):
 def test_database_and_normal(self):
  r=evaluate('Normal');self.assertEqual(r['metrics']['shipments'],40)
 def test_changes_under_disruption(self):
  a=evaluate('Normal');b=evaluate('Highway closure');self.assertGreaterEqual(b['metrics']['at_risk'],a['metrics']['at_risk'])
 def test_alternative_changes_mileage(self):
  a=evaluate('Highway slowdown','Stay on primary');b=evaluate('Highway slowdown','Use alternate route');self.assertGreater(b['metrics']['total_miles'],a['metrics']['total_miles'])
 def test_compare(self):
  base,opts=compare();self.assertEqual(len(opts),3);self.assertEqual(base['scenario'],'Normal')
if __name__=='__main__':unittest.main()
