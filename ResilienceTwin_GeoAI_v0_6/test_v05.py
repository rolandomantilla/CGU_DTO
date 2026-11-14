import unittest
from collections import Counter
from optimizer_v05 import optimize_v05, build_candidates, compare_policies, route_quality
from optimizer_v04 import optimize as greedy_optimize

class TestOptimization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result=optimize_v05()
    def test_coverage(self):
        r=self.result
        self.assertEqual(len(r['shipments']),40)
        self.assertEqual(r['metrics']['scheduled']+r['metrics']['unassigned'],40)
        self.assertEqual(len({s['shipment_id'] for s in r['shipments']}),40)
    def test_single_trip_per_truck(self):
        t=[s['truck_id'] for s in self.result['shipments'] if s['status']=='scheduled']
        self.assertEqual(len(t),len(set(t)))
    def test_warehouse_capacity(self):
        slots=build_candidates()['slots'];usage=Counter(s['slot_id'] for s in self.result['shipments'] if s['status']=='scheduled')
        for k,v in usage.items():self.assertLessEqual(v,slots[k]['capacity']-slots[k]['booked'])
    def test_time_windows(self):
        for x in self.result['shipments']:
            if x['status']=='scheduled':
                self.assertLessEqual(x['receiving_min'],x['appointment_end_min'])
                self.assertLessEqual(x['receiving_min'],x['complete_min'])
    def test_priority_score(self):
        self.assertEqual(self.result['metrics']['priority_service_score'],sum({'critical':5,'high':3,'routine':1}[x['priority']] for x in self.result['shipments'] if x['status']=='scheduled'))
    def test_closed_road(self):
        from optimizer_v05 import _table
        from decision_engine import DEFAULT_DB
        affected={x['route_id'] for x in _table(DEFAULT_DB,'route_segments') if x['segment_id']=='S-004'}
        closed=optimize_v05('SCN-CLOSE')
        self.assertFalse(any(x['route_id'] in affected for x in closed['shipments'] if x['status']=='scheduled'))
    def test_all_policies(self):
        data=compare_policies()
        self.assertEqual(len(data),4)
        self.assertEqual(len({x['metrics']['priority_service_score'] for x in data}),1)
        self.assertEqual(len({x['metrics']['scheduled'] for x in data}),1)
    def test_no_false_unassigned_cost(self):
        for x in self.result['shipments']:
            if x['status']=='unassigned':self.assertIsNone(x['cost_usd'])
    def test_proven_optimality(self):
        self.assertTrue(self.result['solver']['provably_optimal'])
    def test_comparison_caveat(self):
        self.assertIn('One trip per truck',self.result['assumptions'][1])
    def test_bad_input(self):
        for kwargs in ({'policy':'unknown'},{'scenario':'bogus'},{'severity':-1},{'time_limit':0},{'reposition_factor':0.5}):
            with self.assertRaises(ValueError):optimize_v05(**kwargs)
    def test_baseline(self):
        baseline=optimize_v05('SCN-NORMAL',0)
        self.assertGreaterEqual(baseline['metrics']['scheduled'],0)
    def test_deterministic(self):
        self.assertEqual(self.result['metrics'],optimize_v05()['metrics'])

if __name__=='__main__':unittest.main(verbosity=2)
