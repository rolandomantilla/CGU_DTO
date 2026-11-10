"""Scenario-local employee inputs must change mechanisms without mutating defaults."""
import copy
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import load_model, simulate
from human_factors import MODEL_VARIANTS, apply_employee_updates, employee_profiles

BASELINE = {'type': 'PersonnelUnavailable', 'facility_id': 'FAC-ATL', 'personnel_unavailable_pct': 0}


@pytest.fixture(scope='module')
def data():
    return load_model()


def workflow(result, wid='WF-01'):
    return next(w for w in result['workflows'] if w['workflow_id'] == wid)


def role_experience(data, eid, years):
    return [{'workflow_id': r['workflow_id'], 'years_in_role': years}
            for r in data['human_factors']['experience'] if r['employee_id'] == eid]


def run(data, update, variant='human_centered'):
    return simulate({**BASELINE, 'model_variant': variant, 'employee_updates': [update]}, data)


def test_every_employee_has_all_three_variables(data):
    result = simulate(BASELINE, data)
    assert len(result['employees']) == 100
    for employee in result['employees']:
        assert employee['skills']
        assert employee['experience']
        assert 'work_interactions' in employee['organizational_relationships']
        assert 0 <= employee['organizational_relationships']['degree_centrality'] <= 1


def test_skill_changes_affect_task_time_and_qualification(data):
    required = {r['skill_id'] for r in data['workflow_skill_requirements'] if r['workflow_id'] == 'WF-01'}
    low = run(data, {'employee_id': 'EMP-002', 'skills': {sid: 1 for sid in required}})
    high = run(data, {'employee_id': 'EMP-002', 'skills': {sid: 5 for sid in required}})
    assert workflow(high)['task_completion_hours'] < workflow(low)['task_completion_hours']
    assert workflow(high)['throughput_tasks_per_hour'] > workflow(low)['throughput_tasks_per_hour']


def test_experience_changes_affect_task_time_and_baseline_stays_original(data):
    low = run(data, {'employee_id': 'EMP-002', 'experience': role_experience(data, 'EMP-002', 0)})
    high = run(data, {'employee_id': 'EMP-002', 'experience': role_experience(data, 'EMP-002', 10)})
    assert workflow(high)['task_completion_hours'] < workflow(low)['task_completion_hours']
    assert high['summary']['baseline_readiness_pct'] == low['summary']['baseline_readiness_pct']


def test_similar_task_measure_replaces_role_years_for_assignment(data):
    result = run(data, {'employee_id': 'EMP-002', 'experience': [
        {'workflow_id': 'WF-01', 'similar_tasks_completed': 500}]})
    employee = next(e for e in result['employees'] if e['employee_id'] == 'EMP-002')
    record = next(r for r in employee['experience'] if r['workflow_id'] == 'WF-01')
    assert record == {'workflow_id': 'WF-01', 'similar_tasks_completed': 500}


def test_relationship_changes_affect_coordination_and_peers(data):
    edge = {'workflow_id': 'WF-01', 'target_employee_id': 'EMP-003',
            'collaboration_events': 0, 'handoff_events': 5, 'mean_handoff_hours': 2}
    slow = run(data, {'employee_id': 'EMP-002', 'relationships': [edge]})
    fast = run(data, {'employee_id': 'EMP-002', 'relationships': [
        {**edge, 'collaboration_events': 100, 'mean_handoff_hours': 0.1}]})
    assert workflow(fast)['coordination_delay_hours'] < workflow(slow)['coordination_delay_hours']
    assert workflow(fast)['task_completion_hours'] < workflow(slow)['task_completion_hours']
    employee = next(e for e in fast['employees'] if e['employee_id'] == 'EMP-002')
    outgoing = [r for r in employee['organizational_relationships']['work_interactions']
                if r['direction'] == 'outgoing']
    assert len(outgoing) == 1
    assert outgoing[0]['peer_employee_id'] == 'EMP-003'


def test_unavailable_endpoints_retain_and_disrupt_handoffs(data):
    baseline = simulate(BASELINE, data)
    outage = simulate({'type': 'EmployeeUnavailable', 'employee_id': 'EMP-002'}, data)
    assert workflow(outage)['handoff_events'] == workflow(baseline)['handoff_events']
    assert workflow(outage)['disrupted_handoff_events'] > 0
    employee = next(e for e in outage['employees'] if e['employee_id'] == 'EMP-002')
    assert not employee['available']
    assert employee['organizational_relationships']['active_degree_centrality'] == 0
    assert all(r['disrupted'] for r in employee['organizational_relationships']['work_interactions'])
    assert workflow(outage)['productive_fte'] <= workflow(baseline)['productive_fte']


def test_process_variant_ignores_employee_factor_changes(data):
    required = {r['skill_id'] for r in data['workflow_skill_requirements'] if r['workflow_id'] == 'WF-01'}
    original = simulate({**BASELINE, 'model_variant': 'process_only'}, data)
    updated = run(data, {'employee_id': 'EMP-002',
                         'skills': {sid: 1 for sid in required},
                         'experience': role_experience(data, 'EMP-002', 0),
                         'relationships': []}, variant='process_only')
    assert updated['summary']['weighted_readiness_pct'] == original['summary']['weighted_readiness_pct']
    assert [w['task_completion_hours'] for w in updated['workflows']] == [w['task_completion_hours'] for w in original['workflows']]
    assert {c['model_variant'] for c in updated['model_comparison']} == set(MODEL_VARIANTS)


def test_updates_are_isolated_and_reproducible(data):
    original = copy.deepcopy(data)
    update = {'employee_id': 'EMP-002', 'experience': role_experience(data, 'EMP-002', 0)}
    first = run(data, update)
    second = run(data, update)
    assert first == second
    assert data == original
    assert simulate(BASELINE, data)['employees'] == employee_profiles(data)
    assert apply_employee_updates(data, []) == data


def test_empty_relationship_replacement_preserves_incoming(data):
    updated = apply_employee_updates(data, [{'employee_id': 'EMP-002', 'relationships': []}])
    assert not any(r['source_employee_id'] == 'EMP-002' for r in updated['human_factors']['relationships'])
    assert [r for r in updated['human_factors']['relationships'] if r['target_employee_id'] == 'EMP-002'] == [
        r for r in data['human_factors']['relationships'] if r['target_employee_id'] == 'EMP-002']


@pytest.mark.parametrize('updates', [
    None, {}, [{'employee_id': 'EMP-MISSING'}],
    [{'employee_id': 'EMP-002'}, {'employee_id': 'EMP-002'}],
    [{'employee_id': 'EMP-002', 'unexpected': 4}],
    [{'employee_id': 'EMP-002', 'skills': {'unknown_skill': 3}}],
    [{'employee_id': 'EMP-002', 'skills': {'leadership': True}}],
    [{'employee_id': 'EMP-002', 'skills': {'leadership': 0}}],
    [{'employee_id': 'EMP-002', 'skills': {'leadership': 6}}],
    [{'employee_id': 'EMP-002', 'skills': {'leadership': math.inf}}],
    [{'employee_id': 'EMP-002', 'experience': [{'workflow_id': 'WF-01'}]}],
    [{'employee_id': 'EMP-002', 'experience': [{'workflow_id': 'WF-01', 'years_in_role': -1}]}],
    [{'employee_id': 'EMP-002', 'experience': [{'workflow_id': 'WF-01', 'similar_tasks_completed': 1.5}]}],
    [{'employee_id': 'EMP-002', 'experience': [{'workflow_id': 'WF-01', 'years_in_role': 3, 'similar_tasks_completed': 100}]}],
    [{'employee_id': 'EMP-002', 'experience': [{'workflow_id': 'WF-MISSING', 'years_in_role': 3}]}],
    [{'employee_id': 'EMP-002', 'experience': [{'workflow_id': 'WF-01', 'similar_tasks_completed': 1}, {'workflow_id': 'WF-01', 'similar_tasks_completed': 2}]}],
    [{'employee_id': 'EMP-002', 'relationships': [{'workflow_id': 'WF-01', 'target_employee_id': 'EMP-002', 'collaboration_events': 1, 'handoff_events': 1, 'mean_handoff_hours': 0.1}]}],
    [{'employee_id': 'EMP-002', 'relationships': [{'workflow_id': 'WF-01', 'target_employee_id': 'EMP-003', 'collaboration_events': 1, 'handoff_events': 0, 'mean_handoff_hours': 0.1}]}],
    [{'employee_id': 'EMP-002', 'relationships': [{'workflow_id': 'WF-01', 'target_employee_id': 'EMP-003', 'collaboration_events': 1, 'handoff_events': 1, 'mean_handoff_hours': 3}]}],
])
def test_invalid_updates_are_atomic(data, updates):
    before = copy.deepcopy(data)
    with pytest.raises(ValueError):
        apply_employee_updates(data, updates)
    assert data == before
