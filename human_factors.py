"""Illustrative human-variable mechanisms, separate from the disruption rules.

These equations are modeling assumptions, not estimates from the proposal's sources.
All durations are aggregate workflow task times in modeled working hours; no queue,
shift calendar, restoration, or stochastic variability is represented.
"""
import math
from copy import deepcopy


MODEL_VARIANTS = {
    'process_only': frozenset(),
    'skills_only': frozenset({'skills'}),
    'experience_only': frozenset({'experience'}),
    'relationships_only': frozenset({'relationships'}),
    'human_centered': frozenset({'skills', 'experience', 'relationships'}),
}

def _number(value, label, minimum=0, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'Invalid {label}')
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f'Invalid {label}')
    return value


def _count(value, label, minimum=0):
    _number(value, label, minimum)
    if value != int(value):
        raise ValueError(f'{label} must be a whole number')
    return value


def _fields(record, allowed, required, label):
    if not isinstance(record, dict):
        raise ValueError(f'{label} must be an object')
    if set(record) - set(allowed) or set(required) - set(record):
        raise ValueError(f'Invalid or missing fields in {label}')


def apply_employee_updates(data, updates):
    """Apply validated scenario-local edits without changing the saved model.

    Skills and experience are patches; relationships replace the selected person's
    outgoing edges. Incoming edges remain owned by their source employee.
    """
    if not isinstance(updates, list):
        raise ValueError('employee_updates must be a list')
    changed = deepcopy(data)
    employees = {e['employee_id'] for e in data['employees']}
    skill_ids = {r['skill_id'] for r in data['employee_skills']}
    skill_ids.update(r['skill_id'] for r in data['workflow_skill_requirements'])
    assigned = {(r['employee_id'], r['workflow_id']) for r in data['workflow_assignments']}
    skills = {(r['employee_id'], r['skill_id']): r for r in changed['employee_skills']}
    experience = {(r['employee_id'], r['workflow_id']): r for r in changed['human_factors']['experience']}
    seen = set()
    for update in updates:
        _fields(update, ('employee_id', 'skills', 'experience', 'relationships'), ('employee_id',), 'employee update')
        eid = update['employee_id']
        if not isinstance(eid, str) or eid not in employees or eid in seen:
            raise ValueError('Unknown or duplicate employee_id in employee_updates')
        seen.add(eid)
        if 'skills' in update:
            if not isinstance(update['skills'], dict):
                raise ValueError('skills must map skill IDs to proficiency levels')
            for sid, value in update['skills'].items():
                if sid not in skill_ids:
                    raise ValueError(f'Unknown skill_id: {sid}')
                _number(value, 'skill proficiency', 1, 5)
                if (eid, sid) in skills:
                    skills[(eid, sid)]['proficiency_1_to_5'] = value
                else:
                    record = {'employee_id': eid, 'skill_id': sid, 'proficiency_1_to_5': value}
                    changed['employee_skills'].append(record)
                    skills[(eid, sid)] = record
        if 'experience' in update:
            if not isinstance(update['experience'], list):
                raise ValueError('experience must be a list')
            seen_workflows = set()
            for record in update['experience']:
                _fields(record, ('workflow_id', 'years_in_role', 'similar_tasks_completed'), ('workflow_id',), 'experience update')
                wid = record['workflow_id']
                if not isinstance(wid, str) or (eid, wid) not in assigned or wid in seen_workflows:
                    raise ValueError('Unknown or duplicate workflow assignment in experience')
                seen_workflows.add(wid)
                measures = [k for k in ('years_in_role', 'similar_tasks_completed') if k in record]
                if len(measures) != 1:
                    raise ValueError('Experience needs exactly one measure: years_in_role or similar_tasks_completed')
                measure = measures[0]
                (_count if measure == 'similar_tasks_completed' else _number)(record[measure], measure)
                target = experience[(eid, wid)]
                target.clear()
                target.update({'employee_id': eid, **record})
        if 'relationships' in update:
            if not isinstance(update['relationships'], list):
                raise ValueError('relationships must be a list')
            outgoing = []
            for record in update['relationships']:
                fields = ('workflow_id', 'target_employee_id', 'collaboration_events', 'handoff_events', 'mean_handoff_hours')
                _fields(record, fields, fields, 'relationship update')
                # Full relationship validation follows after all replacements.
                for key in ('workflow_id', 'target_employee_id'):
                    if not isinstance(record[key], str):
                        raise ValueError(f'Invalid {key}')
                _count(record['collaboration_events'], 'collaboration_events')
                _count(record['handoff_events'], 'handoff_events', 1)
                outgoing.append({'source_employee_id': eid, **record})
            human = changed['human_factors']
            human['relationships'] = [r for r in human['relationships'] if r['source_employee_id'] != eid] + outgoing
    validate_human_data(changed['human_factors'], changed)
    return changed


def validate_human_data(human, data):
    """Fail on incomplete/invalid inputs rather than invent employee measurements."""
    if human.get('schema_version') != 1:
        raise ValueError('human_factors.json requires schema_version 1')
    config = human['parameters']
    for key in ('skill_efficiency_floor', 'experience_efficiency_floor'):
        _number(config[key], key, 0.01, 1)
    for key in ('reference_years_in_role', 'reference_similar_tasks',
                'collaboration_reference_events', 'disconnected_handoff_hours'):
        _number(config[key], key, 0.000001)
    employees = {e['employee_id'] for e in data['employees']}
    workflows = {w['workflow_id'] for w in data['workflows']}
    assigned = {(a['employee_id'], a['workflow_id']) for a in data['workflow_assignments']}
    seen = set()
    role_years = {}
    for record in human['experience']:
        key = (record['employee_id'], record['workflow_id'])
        if key not in assigned or key in seen:
            raise ValueError(f'Unknown or duplicate experience assignment: {key}')
        seen.add(key)
        measures = [k for k in ('years_in_role', 'similar_tasks_completed') if k in record]
        if len(measures) != 1:
            raise ValueError('Experience needs exactly one measure: years_in_role or similar_tasks_completed')
        (_count if measures[0] == 'similar_tasks_completed' else _number)(record[measures[0]], measures[0])
        if measures[0] == 'years_in_role':
            eid = record['employee_id']
            if eid in role_years and role_years[eid] != record['years_in_role']:
                raise ValueError(f'Inconsistent years_in_role for {eid}')
            role_years[eid] = record['years_in_role']
    if seen != assigned:
        raise ValueError('Missing experience measurements for workflow assignments')
    if {eid for eid, _ in seen} != employees:
        raise ValueError('Every employee requires a workflow experience record')
    for record in data['employee_skills']:
        if record['employee_id'] not in employees:
            raise ValueError('Unknown employee in skill records')
        _number(record['proficiency_1_to_5'], 'skill proficiency', 1, 5)
    refs = human['workflow_reference']
    if set(refs) != workflows:
        raise ValueError('Workflow reference times must cover exactly the model workflows')
    for wid, ref in refs.items():
        _number(ref['task_work_hours'], f'{wid} task_work_hours', 0.000001)
    _number(human['observation_window_days'], 'observation_window_days', 0.000001)
    edges = set()
    for edge in human['relationships']:
        wid, source, target = edge['workflow_id'], edge['source_employee_id'], edge['target_employee_id']
        key = (wid, source, target)
        if (source == target or source not in employees or target not in employees
                or (source, wid) not in assigned or (target, wid) not in assigned or key in edges):
            raise ValueError(f'Invalid or duplicate relationship: {key}')
        edges.add(key)
        _count(edge['collaboration_events'], 'collaboration_events')
        _count(edge['handoff_events'], 'handoff_events', 1)
        delay = _number(edge['mean_handoff_hours'], 'mean_handoff_hours')
        if delay > config['disconnected_handoff_hours']:
            raise ValueError('Disconnected handoff delay must be at least each observed handoff delay')


def employee_profiles(data, unavailable=()):
    """Expose all three variables for every person, including lost relationships."""
    human = data['human_factors']
    unavailable = set(unavailable)
    profiles = {}
    for employee in data['employees']:
        eid = employee['employee_id']
        profiles[eid] = {
            'employee_id': eid, 'display_name': employee['display_name'],
            'role': employee['role'], 'facility_id': employee['facility_id'],
            'available': employee['status'] == 'Active' and eid not in unavailable,
            'skills': [], 'experience': [],
            'organizational_relationships': {
                'manager_id': employee['manager_id'],
                'backup_employee_id': employee['backup_employee_id'],
                'observation_window_days': human['observation_window_days'],
                'work_interactions': [],
            },
        }
    for record in data['employee_skills']:
        profiles[record['employee_id']]['skills'].append({k: v for k, v in record.items() if k != 'employee_id'})
    for record in human['experience']:
        profiles[record['employee_id']]['experience'].append({k: v for k, v in record.items() if k != 'employee_id'})
    for edge in human['relationships']:
        source, target = edge['source_employee_id'], edge['target_employee_id']
        disrupted = not (profiles[source]['available'] and profiles[target]['available'])
        for eid, peer, direction in ((source, target, 'outgoing'), (target, source, 'incoming')):
            profiles[eid]['organizational_relationships']['work_interactions'].append({
                'workflow_id': edge['workflow_id'], 'peer_employee_id': peer,
                'direction': direction, 'collaboration_events': edge['collaboration_events'],
                'collaboration_events_per_day': round(edge['collaboration_events'] / human['observation_window_days'], 4),
                'handoff_events': edge['handoff_events'],
                'mean_handoff_hours': edge['mean_handoff_hours'], 'disrupted': disrupted,
            })
    for profile in profiles.values():
        network = profile['organizational_relationships']
        interactions = network['work_interactions']
        peers = {r['peer_employee_id'] for r in interactions}
        active_peers = {r['peer_employee_id'] for r in interactions if not r['disrupted']}
        network['collaborator_count'] = len(peers)
        network['available_collaborator_count'] = len(active_peers)
        # Undirected degree centrality on the organization-wide work network.
        denominator = max(1, len(profiles) - 1)
        network['degree_centrality'] = round(len(peers) / denominator, 4)
        network['active_degree_centrality'] = round(len(active_peers) / denominator, 4)
    return list(profiles.values())


def workflow_effects(wid, assignments, unavailable, requirements, employees, skills, human,
                     baseline_fte, capacity_factor, system_factor, model_variant='human_centered'):
    enabled = MODEL_VARIANTS[model_variant]
    config = human['parameters']
    experience = {(r['employee_id'], r['workflow_id']): r for r in human['experience']}
    diagnostics = []
    for assignment in assignments:
        eid = assignment['employee_id']
        weight = employees[eid]['fte'] * assignment['allocation_pct'] / 100
        available = employees[eid]['status'] == 'Active' and eid not in unavailable
        # Task-relevant proficiency is the weakest required competency, on 0..5.
        proficiency = min((skills[eid].get(r['skill_id'], 0) / 5 for r in requirements), default=1)
        skill_eff = config['skill_efficiency_floor'] + (1 - config['skill_efficiency_floor']) * proficiency
        if 'skills' not in enabled:
            skill_eff = 1
        record = experience[(eid, wid)]
        measure = 'years_in_role' if 'years_in_role' in record else 'similar_tasks_completed'
        reference = config['reference_years_in_role' if measure == 'years_in_role' else 'reference_similar_tasks']
        exp_eff = config['experience_efficiency_floor'] + (1 - config['experience_efficiency_floor']) * min(1, record[measure] / reference)
        if 'experience' not in enabled:
            exp_eff = 1
        diagnostics.append({
            'employee_id': eid, 'assigned_fte': weight, 'available': available,
            'relevant_proficiency_fraction': round(proficiency, 4),
            'skill_efficiency': skill_eff,
            'experience_measure': measure, 'experience_value': record[measure],
            'experience_efficiency': exp_eff,
            'effective_assigned_fte': weight * skill_eff * exp_eff if available else 0,
        })
    active_diagnostics = [r for r in diagnostics if r['available']]
    total_fte = sum(r['assigned_fte'] for r in active_diagnostics)
    def average(field):
        return sum(r['assigned_fte'] * r[field] for r in active_diagnostics) / total_fte if total_fte else 0
    effective_fte = sum(r['effective_assigned_fte'] for r in diagnostics)
    joint_eff = effective_fte / total_fte if total_fte else 0
    active_ids = {r['employee_id'] for r in active_diagnostics}
    edges = [r for r in human['relationships'] if r['workflow_id'] == wid]
    handoffs = sum(e['handoff_events'] for e in edges)
    lost_handoffs = 0
    delay_sum = 0
    neighbors = {}
    for edge in edges:
        source, target = edge['source_employee_id'], edge['target_employee_id']
        neighbors.setdefault(source, set()).add(target)
        neighbors.setdefault(target, set()).add(source)
        connected = source in active_ids and target in active_ids
        if connected:
            delay = edge['mean_handoff_hours'] / (1 + edge['collaboration_events'] / config['collaboration_reference_events'])
        else:
            delay = config['disconnected_handoff_hours']
            lost_handoffs += edge['handoff_events']
        delay_sum += edge['handoff_events'] * delay
    coordination_hours = delay_sum / handoffs if handoffs else 0
    if 'relationships' not in enabled:
        coordination_hours = 0
    reference_hours = human['workflow_reference'][wid]['task_work_hours']
    reference_time = reference_hours / baseline_fte if baseline_fte else None
    # Sum each person's contribution before applying independent capacity ceilings.
    # Removing a low-efficiency person must never increase productive capacity.
    productive_fte = min(effective_fte, baseline_fte * capacity_factor) * system_factor
    processing_hours = reference_hours / productive_fte if productive_fte else None
    task_hours = processing_hours + coordination_hours if processing_hours is not None else None
    throughput = 1 / task_hours if task_hours else 0
    # Missing personnel keep their original handoff demand; it is not silently dropped.
    degree_denominator = max(1, len({r['employee_id'] for r in human['experience'] if r['workflow_id'] == wid}) - 1)
    return {
        'skill_efficiency_factor': round(average('skill_efficiency'), 4),
        'experience_efficiency_factor': round(average('experience_efficiency'), 4),
        'joint_employee_efficiency_factor': round(joint_eff, 4),
        'effective_assigned_fte': round(effective_fte, 4),
        'productive_fte': round(productive_fte, 4),
        'coordination_delay_hours': round(coordination_hours, 4),
        'coordination_factor': round(processing_hours / task_hours, 4) if task_hours else 0,
        'relationship_edges': len(edges), 'handoff_events': handoffs,
        'disrupted_handoff_events': lost_handoffs,
        'relationship_data_status': 'recorded' if edges else 'no_handoffs_recorded',
        'degree_centrality': {eid: round(len(peers) / degree_denominator, 4) for eid, peers in sorted(neighbors.items())},
        'task_completion_hours': round(task_hours, 4) if task_hours is not None else None,
        'throughput_tasks_per_hour': round(throughput, 6),
        'coverage_pct': round(min(100, reference_time * throughput * 100), 1) if reference_time else 0,
        'employee_factors': diagnostics,
    }
