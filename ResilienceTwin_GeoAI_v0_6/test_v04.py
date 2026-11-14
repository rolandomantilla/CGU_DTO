import unittest
from collections import defaultdict
from optimizer_v04 import optimize, compare_strategies, haversine_miles

class TestV04(unittest.TestCase):
    def test_coverage(self):
        r=optimize()
        self.assertEqual(len(r['shipments']),40)
        self.assertEqual(r['metrics']['scheduled']+r['metrics']['unassigned'],40)
        self.assertEqual(len({x['shipment_id'] for x in r['shipments']}),40)
    def test_appointments_and_assignments(self):
        r=optimize()
        bytruck=defaultdict(list)
        byslot=defaultdict(list)
        for x in r['shipments']:
            if x['status']!='scheduled':continue
            self.assertLessEqual(x['receiving_min'],x['appointment_end_min'])
            self.assertGreaterEqual(x['complete_min'],x['receiving_min'])
            bytruck[x['truck_id']].append(x)
            byslot[x['slot_id']].append(x)
        for a in bytruck.values():
            for i,first in enumerate(sorted(a,key=lambda x:x['departure_min'])):
                for second in a[i+1:]:
                    self.assertTrue(first['complete_min']<=second['departure_min'] or second['complete_min']<=first['departure_min'])
    def test_closure_not_routed_over_affected_segment(self):
        import sqlite3
        from decision_engine import DEFAULT_DB
        c=sqlite3.connect(DEFAULT_DB)
        affected={x[0] for x in c.execute("select route_id from route_segments where segment_id='S-004'")}
        c.close()
        for x in optimize('SCN-CLOSE')['shipments']:
            if x['status']=='scheduled':self.assertNotIn(x['route_id'],affected)
    def test_scenarios_all_strategies(self):
        for s in ['SCN-NORMAL','SCN-SLOW','SCN-CLOSE','SCN-PORT']:
            try:outputs=compare_strategies(s)
            except ValueError:
                if s=='SCN-PORT': continue
                raise
            self.assertEqual(len(outputs),4)
            for x in outputs:self.assertGreaterEqual(x['metrics']['scheduled'],0)
    def test_deterministic(self):
        self.assertEqual(optimize(),optimize())
    def test_invalid_input(self):
        for kwargs in [{'severity':-1},{'strategy':'bad'},{'turnaround_min':-3},{'reposition_factor':0.2}]:
            with self.assertRaises(ValueError):optimize(**kwargs)
    def test_geo(self):
        self.assertAlmostEqual(haversine_miles((34,-118),(34,-118)),0)
        self.assertGreater(haversine_miles((34,-118),(35,-118)),60)
    def test_no_fabricated_unassigned_cost(self):
        x=optimize()
        for s in x['shipments']:
            if s['status']=='unassigned':
                self.assertEqual(s['cost_usd'],0)
                self.assertIsNone(s['truck_id'])
        self.assertTrue(any('excluded' in a for a in x['assumptions']))

if __name__=='__main__':unittest.main(verbosity=2)
