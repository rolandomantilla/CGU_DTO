"""v0.6 model invariants; synthetic tests, not operational verification."""
import unittest
from collections import Counter, defaultdict
from optimizer_v06 import SyntheticRoadNetwork, optimize_v06, compare_policies
from optimizer_v05 import _table
from decision_engine import DEFAULT_DB

class TestV06(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=optimize_v06('SCN-SLOW',75)
        cls.db=DEFAULT_DB
    def test_graph_path(self):
        p=SyntheticRoadNetwork().path('PORT-LA','WH-ONT')
        self.assertTrue(p['segments']);self.assertGreater(p['miles'],0)
    def test_same_facility_no_empty_travel(self):
        p=SyntheticRoadNetwork().path('WH-CAR','WH-CAR')
        self.assertEqual((p['minutes'],p['miles']),(0,0))
    def test_closure_avoids_segment(self):
        p=SyntheticRoadNetwork().path('PORT-LA','WH-ONT',blocked=['S-004'])
        self.assertTrue(p);self.assertNotIn('S-004',p['segments'])
    def test_coverage(self):
        r=self.r;self.assertEqual(len(r['shipments']),40)
        self.assertEqual(r['metrics']['scheduled']+r['metrics']['unassigned'],40)
    def test_multi_trip(self):
        self.assertGreater(self.r['metrics']['trucks_with_multiple_trips'],0)
        self.assertTrue(any(x['trip_number']>1 for x in self.r['shipments'] if x['status']=='scheduled'))
    def test_no_overlap(self):
        by=defaultdict(list)
        for x in self.r['shipments']:
            if x['status']=='scheduled':by[x['truck_id']].append(x)
        for recs in by.values():
            recs.sort(key=lambda x:x['reposition_start_min'])
            for a,b in zip(recs,recs[1:]):self.assertLessEqual(a['complete_min'],b['reposition_start_min'])
    def test_capacity(self):
        slots={x['slot_id']:x for x in _table(self.db,'warehouse_slots')}
        used=Counter(x['slot_id'] for x in self.r['shipments'] if x['status']=='scheduled')
        for k,v in used.items():self.assertLessEqual(v,slots[k]['capacity']-slots[k]['booked'])
    def test_appointments(self):
        for x in self.r['shipments']:
            if x['status']=='scheduled':self.assertLessEqual(x['receiving_min'],x['appointment_end_min'])
    def test_both_route_types_are_graph_paths(self):
        network=SyntheticRoadNetwork()
        for x in self.r['shipments']:
            if x['status']=='scheduled':
                self.assertTrue(all(s in network.segments for s in x['route_segments']))
                self.assertTrue(all(s in network.segments for s in x['empty_route_segments']))
    def test_closure_is_respected_loaded_and_empty(self):
        r=optimize_v06('SCN-CLOSE',150)
        for x in r['shipments']:
            if x['status']=='scheduled':
                self.assertNotIn('S-004',x['route_segments'])
                self.assertNotIn('S-004',x['empty_route_segments'])
    def test_deterministic(self):
        self.assertEqual(self.r['shipments'],optimize_v06('SCN-SLOW',75)['shipments'])
    def test_unassigned_not_zero_cost(self):
        for x in self.r['shipments']:
            if x['status']=='unassigned':self.assertIsNone(x['cost_usd'])
    def test_policy_results(self):
        self.assertEqual(len(compare_policies()),4)
    def test_invalid_input(self):
        for kwargs in ({'scenario':'missing'},{'severity':-5},{'policy':'Invalid'},
                       {'max_trips_per_truck':0},{'attempts':0},{'turnaround_min':-1}):
            with self.assertRaises(ValueError):optimize_v06(**kwargs)
    def test_honest_solver_label(self):
        self.assertFalse(self.r['solver']['provably_optimal'])

if __name__=='__main__':unittest.main(verbosity=2)
