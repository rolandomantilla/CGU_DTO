import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from engine import load_model,simulate

@pytest.fixture(scope='module')
def data():return load_model()

def test_records(data):
    assert len(data['employees'])==100
    assert len(data['facilities'])==5
    assert len(data['workflows'])==12

def test_zero_reduction_is_baseline(data):
    r=simulate({'type':'PersonnelUnavailable','facility_id':'FAC-ATL','personnel_unavailable_pct':0},data)
    assert r['summary']['staff_unavailable']==0
    assert r['summary']['readiness_change_points']==0

def test_full_reduction_weakens_capacity(data):
    a=simulate({'type':'PersonnelUnavailable','facility_id':'FAC-ATL','personnel_unavailable_pct':0},data)
    b=simulate({'type':'PersonnelUnavailable','facility_id':'FAC-ATL','personnel_unavailable_pct':100},data)
    assert b['summary']['staff_unavailable']==20
    assert b['summary']['weighted_readiness_pct']<=a['summary']['weighted_readiness_pct']
    assert b['summary']['workflows_at_risk']>=a['summary']['workflows_at_risk']

def test_facility_outage_blocks_local_systems(data):
    r=simulate({'type':'FacilityOffline','facility_id':'FAC-DEN'},data)
    assert r['summary']['systems_offline']>0
    assert any(x['blocked_systems'] for x in r['workflows'])

def test_system_outage_blocks_required_workflows(data):
    r=simulate({'type':'SystemOffline','system_id':'SYS-GIS'},data)
    w=next(w for w in r['workflows'] if w['workflow_id']=='WF-02')
    assert w['coverage_pct']==0
    assert r['summary']['staff_unavailable']==0

def test_employee_target(data):
    r=simulate({'type':'EmployeeUnavailable','employee_id':'EMP-001'},data)
    assert len(r['unavailable_employees'])==1

def test_unknown_facility_rejected(data):
    with pytest.raises(ValueError):simulate({'type':'FacilityOffline','facility_id':'FAC-NOTREAL'},data)

def test_recovery_candidate_not_unavailable_and_no_double_spend(data):
    r=simulate({'type':'PersonnelUnavailable','facility_id':'FAC-ATL','personnel_unavailable_pct':100},data)
    unavailable={e['employee_id'] for e in r['unavailable_employees']}
    assert all(c['employee_id'] not in unavailable for c in r['recovery_candidates'])
    assert all(c['spare_fte_allocated']>0 for c in r['recovery_candidates'])
