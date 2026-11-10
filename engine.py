"""Deterministic, synthetic organizational disruption model for ResilienceTwin v0.2."""
from __future__ import annotations
import json
import math
import sqlite3
from pathlib import Path
from collections import defaultdict
from human_factors import (MODEL_VARIANTS, validate_human_data, workflow_effects,
                           apply_employee_updates, employee_profiles)

DB_PATH = Path(__file__).parent / 'data' / 'resiliencetwin.sqlite'
VALID_TYPES = {'PersonnelUnavailable','FacilityOffline','RoleUnavailable','SystemOffline','EmployeeUnavailable'}

def read_rows(connection, table):
    return [dict(x) for x in connection.execute(f'SELECT * FROM {table}')]

def load_model(db_path=DB_PATH):
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        data = {table: read_rows(connection, table) for table in ('facilities','employees','employee_skills','workflows','workflow_assignments','workflow_skill_requirements','systems','workflow_system_dependencies')}
    data['human_factors'] = json.loads((Path(db_path).parent / 'human_factors.json').read_text())
    validate_human_data(data['human_factors'], data)
    return data

def _validate(s, data):
    if not isinstance(s, dict): raise ValueError('Scenario must be an object')
    if not isinstance(s.get('model_variant', 'human_centered'), str) or s.get('model_variant', 'human_centered') not in MODEL_VARIANTS:
        raise ValueError('Unsupported model_variant')
    typ=s.get('type')
    if not isinstance(typ, str) or typ not in VALID_TYPES: raise ValueError('Unsupported scenario type')
    valid = {'facility':{x['facility_id'] for x in data['facilities']}, 'employee':{x['employee_id'] for x in data['employees']},'system':{x['system_id'] for x in data['systems']}}
    if typ in ('PersonnelUnavailable','FacilityOffline','RoleUnavailable') and s.get('facility_id') not in valid['facility']: raise ValueError('Unknown facility_id')
    if typ=='EmployeeUnavailable' and s.get('employee_id') not in valid['employee']: raise ValueError('Unknown employee_id')
    if typ=='SystemOffline' and s.get('system_id') not in valid['system']: raise ValueError('Unknown system_id')
    if typ=='PersonnelUnavailable':
        pct=s.get('personnel_unavailable_pct')
        if isinstance(pct, bool) or not isinstance(pct,(int,float)) or not 0<=pct<=100: raise ValueError('personnel_unavailable_pct must be between 0 and 100')
    if typ=='RoleUnavailable' and not isinstance(s.get('role'),str): raise ValueError('Role is required')
    hours=s.get('duration_hours',24)
    if isinstance(hours,bool) or not isinstance(hours,(int,float)) or not 0<hours<=2160: raise ValueError('duration_hours must be between 0 and 2160')

def _compute(s, data):
    variant = s.get('model_variant', 'human_centered')
    enabled = MODEL_VARIANTS[variant]
    emp = {e['employee_id']:e for e in data['employees']}
    facilities = {f['facility_id']:f for f in data['facilities']}
    systems = {x['system_id']:x for x in data['systems']}
    workflows = {w['workflow_id']:w for w in data['workflows']}
    assignments=defaultdict(list)
    for a in data['workflow_assignments']:assignments[a['workflow_id']].append(a)
    skills=defaultdict(dict)
    for x in data['employee_skills']:skills[x['employee_id']][x['skill_id']]=x['proficiency_1_to_5']
    reqs=defaultdict(list)
    for x in data['workflow_skill_requirements']:reqs[x['workflow_id']].append(x)
    deps=defaultdict(list)
    for x in data['workflow_system_dependencies']:deps[x['workflow_id']].append(x)
    unavailable=set()
    typ=s['type']
    if typ=='EmployeeUnavailable':unavailable.add(s['employee_id'])
    if typ=='PersonnelUnavailable':
        pool=[x for x in data['employees'] if x['facility_id']==s['facility_id'] and x['status']=='Active']
        # Stable deterministic selection: most operationally critical first. This is a deliberate worst-case stress test, not random sampling.
        pool.sort(key=lambda e:(-e['operational_criticality'],-e['knowledge_concentration'],e['employee_id']))
        n=math.ceil(len(pool)*s['personnel_unavailable_pct']/100)
        unavailable.update(e['employee_id'] for e in pool[:n])
    if typ=='RoleUnavailable':unavailable.update(e['employee_id'] for e in data['employees'] if e['facility_id']==s['facility_id'] and e['role'].casefold()==s['role'].casefold())
    if typ=='FacilityOffline':
        # Remote/hybrid eligible staff can work offsite (assumed); exclusively onsite staff cannot.
        unavailable.update(e['employee_id'] for e in data['employees'] if e['facility_id']==s['facility_id'] and (not e['remote_eligible'] or e['work_arrangement']=='Onsite'))
    system_offline={s['system_id']} if typ=='SystemOffline' else set()
    if typ=='FacilityOffline':system_offline.update(x['system_id'] for x in data['systems'] if x['hosting_facility_id']==s['facility_id'])

    output=[]
    # Shared spare capacity is computed once per employee (not independently per workflow).
    total_allocation=defaultdict(float)
    for a in data['workflow_assignments']:total_allocation[a['employee_id']]+=float(a['allocation_pct'])
    for wid,w in workflows.items():
        aa=assignments[wid]
        baseline_fte=sum(emp[a['employee_id']]['fte'] * a['allocation_pct']/100 for a in aa if emp[a['employee_id']]['status']=='Active')
        active=[a for a in aa if a['employee_id'] not in unavailable and emp[a['employee_id']]['status']=='Active']
        remaining_fte=sum(emp[a['employee_id']]['fte']*a['allocation_pct']/100 for a in active)
        baseline_count=len({a['employee_id'] for a in aa if emp[a['employee_id']]['status']=='Active'})
        active_count=len({a['employee_id'] for a in active})
        # Baseline assignment coverage is used as required assigned capacity. Headcount minimum is independent.
        staffing=remaining_fte/baseline_fte if baseline_fte else 0
        minimum=int(w['minimum_active_personnel'])
        headcount=min(1,active_count/minimum) if minimum else 1
        skill_ratios=[]; skill_gaps=[]
        for req in reqs[wid]:
            qualified=sum(1 for a in active if skills[a['employee_id']].get(req['skill_id'],0)>=req['minimum_proficiency'])
            needed=req['minimum_qualified_people']
            skill_ratios.append(min(1,qualified/needed) if needed else 1)
            if qualified<needed:skill_gaps.append({'skill':req['skill_id'],'qualified':qualified,'required':needed,'shortfall':needed-qualified,'proficiency':req['minimum_proficiency']})
        skill_factor=min(skill_ratios,default=1) if 'skills' in enabled else 1
        blocked=[d['system_id'] for d in deps[wid] if d['system_id'] in system_offline and d['dependency_type']=='Required']
        degraded=[d['system_id'] for d in deps[wid] if d['system_id'] in system_offline and d['dependency_type']!='Required']
        system_factor=0 if blocked else (0.75 if degraded else 1)
        # Bottleneck model: do not multiply correlated capacity losses; use limiting factor.
        human=min(1,staffing,headcount,skill_factor)
        effects=workflow_effects(wid, aa, unavailable, reqs[wid], emp, skills,
                                data['human_factors'], baseline_fte, human, system_factor,
                                model_variant=variant)
        coverage=effects.pop('coverage_pct')
        status='Blocked' if coverage==0 else 'At Risk' if coverage<80 else 'Degraded' if coverage<99.95 else 'Operational'
        output.append({'workflow_id':wid,'name':w['workflow_name'],'criticality':w['criticality'],'owner_facility_id':w['owner_facility_id'],
                       'coverage_pct':coverage,'status':status,'assigned_people_baseline':baseline_count,'assigned_people_active':active_count,
                       'baseline_assigned_fte':round(baseline_fte,2),'remaining_assigned_fte':round(remaining_fte,2),
                       'staffing_factor':round(staffing,3),'headcount_factor':round(headcount,3),'skill_factor':round(skill_factor,3),
                       'system_factor':system_factor,'skill_gaps':skill_gaps,'blocked_systems':blocked,'degraded_systems':degraded,
                       'lost_assigned_personnel':[a['employee_id'] for a in aa if a['employee_id'] in unavailable],
                       **effects,
                       'expected_tasks_during_scenario':round(effects['throughput_tasks_per_hour']*s.get('duration_hours',24),4)})
    # Conservative recommendations: candidate qualification + available spare allocation + availability/access checks remain human review.
    candidates=[]
    existing_by_workflow={wid:{a['employee_id'] for a in assignments[wid]} for wid in workflows}
    # Do not suggest a candidate twice beyond their available shared spare capacity.
    remaining_spare={eid:max(0,100-total_allocation[eid])/100*e['fte'] for eid,e in emp.items() if eid not in unavailable and e['status']=='Active'}
    for w in sorted(output,key=lambda x:(-x['criticality'],x['coverage_pct'])):
        if w['coverage_pct']>=100 or w['blocked_systems']: continue
        for gap in w['skill_gaps']:
            qualified=[]
            for eid,e in emp.items():
                if eid in existing_by_workflow[w['workflow_id']] or eid not in remaining_spare:continue
                if skills[eid].get(gap['skill'],0)<gap['proficiency'] or remaining_spare[eid]<.1:continue
                cross_site=e['facility_id']!=w['owner_facility_id']
                if cross_site and not(e['remote_eligible'] or e['cross_site_deployable']):continue
                qualified.append((not cross_site,-remaining_spare[eid],eid))
            for _,_,eid in sorted(qualified)[:min(gap['shortfall'],3)]:
                e=emp[eid]; amt=round(min(remaining_spare[eid],.25),2)
                remaining_spare[eid]-=amt
                candidates.append({'workflow_id':w['workflow_id'],'employee_id':eid,'employee_name':e['display_name'],
                                   'from_facility_id':e['facility_id'],'to_facility_id':w['owner_facility_id'],
                                   'skill':gap['skill'],'proficiency':skills[eid][gap['skill']], 'spare_fte_allocated':amt,
                                   'note':'Unverified candidate. Confirm shift, approvals, access, training, and task suitability.'})
    lost=[{'employee_id':eid,'name':emp[eid]['display_name'],'facility_id':emp[eid]['facility_id'],'role':emp[eid]['role'],'criticality':emp[eid]['operational_criticality']} for eid in sorted(unavailable)]
    weighted=sum(w['coverage_pct']*w['criticality'] for w in output)/sum(w['criticality'] for w in output)
    affected=sorted({emp[eid]['facility_id'] for eid in unavailable}|{w['owner_facility_id'] for w in output if w['coverage_pct']<100})
    return {'scenario':s,'summary':{'headcount_total':len(emp),'staff_unavailable':len(unavailable),'systems_offline':len(system_offline),
      'workflow_count':len(output),'workflows_at_risk':sum(w['coverage_pct']<100 for w in output),
      'workflows_blocked':sum(w['coverage_pct']==0 for w in output), 'weighted_readiness_pct':round(weighted,1),
      'candidate_transfers':len(candidates),'affected_facility_ids':affected},'workflows':output,'unavailable_employees':lost,
      'offline_systems':[{'system_id':sid,'name':systems[sid]['system_name']} for sid in sorted(system_offline)],'recovery_candidates':candidates,
      'employees':employee_profiles(data, unavailable),
      'methodology':{'model':'Deterministic bottleneck capacity stress test; not a calibrated forecast',
        'staff_reduction':'Highest-criticality personnel removed first (worst-case ordering)',
        'facility_outage':'Onsite-only employees unavailable; hybrid/remote eligible staff assumed offsite-capable; locally hosted systems offline',
        'readiness':'Criticality-weighted task-rate coverage relative to fully efficient baseline assigned FTE; limited by staffing, headcount, enabled human variables and systems',
        'model_variant':variant,
        'skills':'Enabled: task-relevant proficiency affects employee efficiency and minimum-qualified-person coverage' if 'skills' in enabled else 'Disabled in predictions; qualification diagnostics and recovery suggestions remain available',
        'experience':'Enabled: explicit years in role OR similar-task counts affect efficiency; organizational tenure is not treated as measured role experience' if 'experience' in enabled else 'Disabled in predictions',
        'relationships':'Enabled: directed workflow handoffs, collaboration frequency and unavailable endpoints affect coordination delay; degree centrality is diagnostic' if 'relationships' in enabled else 'Disabled in predictions',
        'timing':'Illustrative aggregate task completion time and fluid throughput, not an event/queue simulation. Duration is modeled working hours; no shifts or restoration. Blocked task time is null, throughput is zero',
        'calibration':'Synthetic demonstration inputs and assumed coefficients; no observed outcomes, accuracy estimates, or validated prediction improvement',
        'employee_updates':'Scenario-local overrides; saved employee records are unchanged. Baseline uses original inputs without disruption; model comparisons use the same updated employees',
        'recovery':'Candidates do not alter modeled coverage; validation and approval required',
        'data':'Fully synthetic demo data'}}

def simulate(scenario, data=None):
    data = data if data is not None else load_model()
    _validate(scenario,data)
    baseline_s={'type':'PersonnelUnavailable','facility_id':data['facilities'][0]['facility_id'],'personnel_unavailable_pct':0,'duration_hours':24,
                'model_variant':scenario.get('model_variant','human_centered')}
    baseline=_compute(baseline_s,data)
    updated_data=apply_employee_updates(data,scenario.get('employee_updates', []))
    result=_compute(scenario,updated_data)
    result['summary']['baseline_readiness_pct']=baseline['summary']['weighted_readiness_pct']
    result['summary']['readiness_change_points']=round(result['summary']['weighted_readiness_pct']-baseline['summary']['weighted_readiness_pct'],1)
    result['model_comparison']=[]
    for variant in MODEL_VARIANTS:
        alternative=_compute({**scenario,'model_variant':variant},updated_data)
        result['model_comparison'].append({'model_variant':variant,
            'weighted_readiness_pct':alternative['summary']['weighted_readiness_pct'],
            'workflows':[{'workflow_id':w['workflow_id'],
                          'task_completion_hours':w['task_completion_hours'],
                          'throughput_tasks_per_hour':w['throughput_tasks_per_hour']}
                         for w in alternative['workflows']]})
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description='Run the synthetic ResilienceTwin disruption simulation')
    p.add_argument('--scenario',help='JSON file with scenario specification')
    p.add_argument('--out',help='Output JSON path')
    args=p.parse_args()
    scenario=json.loads(Path(args.scenario).read_text()) if args.scenario else json.loads((DB_PATH.parent/'scenarios.json').read_text())[1]
    if isinstance(scenario,list):
        raise SystemExit('Scenario file must contain one JSON scenario object, not a list')
    result=simulate(scenario)
    output=json.dumps(result,indent=2)
    if args.out:Path(args.out).write_text(output)
    else:print(output)
