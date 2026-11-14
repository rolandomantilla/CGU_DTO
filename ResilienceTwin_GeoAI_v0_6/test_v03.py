import unittest
from decision_engine import load,evaluate,compare,ACTIONS

class DecisionTests(unittest.TestCase):
    def test_data(self):
        d=load(); self.assertEqual(len(d['shipments']),40); self.assertGreater(len(d['route_segments']),0)
    def test_all_scenarios(self):
        for sc in load()['scenario_definitions']:
            for action in ACTIONS:
                with self.subTest(sc=sc['scenario_id'],action=action):
                    r=evaluate(sc['scenario_id'],action)
                    self.assertEqual(r['metrics']['shipments'],40)
                    self.assertGreaterEqual(r['metrics']['cost_usd'],0)
                    self.assertEqual(len(r['shipments']),40)
    def test_closure_not_passable(self):
        x=evaluate('SCN-CLOSE','Stay on primary')
        self.assertTrue(any(r['blocked'] for r in x['shipments']))
        self.assertTrue(all(not r['on_time'] for r in x['shipments'] if r['blocked']))
    def test_alternate_route_changes(self):
        a=evaluate('SCN-SLOW','Stay on primary')
        b=evaluate('SCN-SLOW','Use alternate route')
        self.assertGreaterEqual(b['metrics']['miles'],a['metrics']['miles'])
    def test_reschedule_not_real_booking(self):
        r=evaluate('SCN-SLOW','Request reschedule')
        self.assertTrue(any(x['reschedule_requested'] for x in r['shipments']))
        self.assertTrue(any('hypothetical' in w for x in r['shipments'] for w in x['warnings']))
    def test_guardrails(self):
        with self.assertRaises(ValueError): evaluate(severity=-1)
        with self.assertRaises(ValueError): evaluate(action='Send truck')
    def test_normal_repeatable(self):
        self.assertEqual(evaluate('SCN-NORMAL')['metrics'],evaluate('SCN-NORMAL')['metrics'])
if __name__=='__main__':unittest.main(verbosity=2)
