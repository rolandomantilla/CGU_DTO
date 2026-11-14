"""v0.3 experimental, non-operational, explainable disruption decision layer.
No real-world dispatch, validated routing, or HOS compliance decisions.
"""
from pathlib import Path
import sqlite3
from collections import Counter, defaultdict

DEFAULT_DB = Path(__file__).resolve().parent / 'data' / 'geoai.sqlite'
ACTIONS = ('Stay on primary', 'Use alternate route', 'Expedite dispatch', 'Request reschedule')

def load(db=DEFAULT_DB):
    c=sqlite3.connect(db); c.row_factory=sqlite3.Row
    try:
        names=('shipments','shipment_details','routes','route_segments','scenario_definitions','warehouse_slots','driver_profiles','drivers','fleet_specs','cost_parameters','emission_parameters','facility_resources','road_segments')
        return {n:[dict(x) for x in c.execute(f'SELECT * FROM {n}')] for n in names}
    finally: c.close()

def evaluate(scenario='SCN-SLOW', action='Stay on primary', severity=None, db=DEFAULT_DB):
    if action not in ACTIONS: raise ValueError('Unknown action')
    data=load(db)
    choices={s['scenario_id']:s for s in data['scenario_definitions']}
    if scenario not in choices:raise ValueError('Unknown scenario')
    cfg=choices[scenario]
    delay=int(cfg['severity_min'] if severity is None else severity)
    if delay<0 or delay>600: raise ValueError('Severity must be 0..600 minutes')
    route={(r['shipment_id'],r['variant']):r for r in data['routes']}
    segs=defaultdict(set)
    for x in data['route_segments']:segs[x['route_id']].add(x['segment_id'])
    details={x['shipment_id']:x for x in data['shipment_details']}
    driver_by_truck={x['truck_id']:x['id'] for x in data['drivers']}
    profiles={x['driver_id']:x for x in data['driver_profiles']}
    specs={x['truck_id']:x for x in data['fleet_specs']}
    slots={x['slot_id']:x for x in data['warehouse_slots']}
    cost={x['param_id']:x['value'] for x in data['cost_parameters']}
    emissions={x['param_id']:x['value'] for x in data['emission_parameters']}
    records=[]
    intervals=defaultdict(list)
    for s in sorted(data['shipments'],key=lambda x:x['id']):
        det=details[s['id']]; base=route[s['id'],'primary']; alt=route.get((s['id'],'alternate'))
        segment=cfg['affected_segment_id']
        affected=bool(segment and segment in segs[base['id']])
        if cfg['kind']=='port': affected=det['pickup_status']=='pending'
        applied=delay if affected else 0
        use_alt=(action=='Use alternate route' and affected and alt is not None and cfg['kind']!='port' and (not segment or segment not in segs[alt['id']]))
        r=alt if use_alt else base
        # Closed primary segment => blocked, not simply slow.
        blocked=(cfg['kind']=='road_closure' and affected and not use_alt)
        if cfg['kind']=='port': depart=s['pickup_ready_min']+applied
        else: depart=s['pickup_ready_min']
        if action=='Expedite dispatch':
            depart=max(s['pickup_ready_min'],depart-20) if cfg['kind']!='port' else max(0,depart-20)
            applied=max(0,applied-40)
        travel=r['travel_min'] + (0 if use_alt or cfg['kind']=='port' else applied)
        queue=10
        arrival=depart+travel+queue
        slot=slots.get(det['appointment_slot_id'])
        deadline=s['appointment_end_min']
        rescheduled=False
        if action=='Request reschedule' and arrival>deadline and slot:
            # Hypothetical appointment adjustment, not confirmed slot booking.
            deadline=max(deadline,arrival+30)
            rescheduled=True
        late=max(0,arrival-deadline)
        if blocked: late=max(late,delay)
        driver_id=driver_by_truck.get(s['truck_id'])
        profile=profiles.get(driver_id)
        truck=specs.get(s['truck_id'])
        warnings=[]
        if blocked: warnings.append('Primary route intersects modeled closure; cannot dispatch as shown')
        if affected and action=='Use alternate route' and not use_alt: warnings.append('No disruption-free alternate route represented')
        if profile and ((travel+queue)>profile['hours_remaining']*60 or arrival>profile['shift_end_min']):warnings.append('Driver time budget/shift may be exceeded (not regulatory HOS validation)')
        if truck and (truck['maintenance_state']!='serviceable' or depart<truck['available_from_min']):warnings.append('Truck maintenance or availability conflict')
        if slot and slot['booked']>=slot['capacity']:warnings.append('Original warehouse appointment slot has no modeled spare capacity')
        if rescheduled:warnings.append('Reschedule is hypothetical; warehouse confirmation required')
        if profile and truck:intervals[s['truck_id']].append((depart,arrival,s['id']))
        incremental_idle=max(0,travel-r['travel_min'])
        c=r['distance_mi']*cost['C-MI']+(travel+queue)/60*cost['C-HR']+late*cost['C-LATE']
        if action=='Expedite dispatch':c+=cost['C-EXP']
        if rescheduled:c+=cost['C-APPT'] # illustrative rescheduling service cost proxy
        e=r['distance_mi']*emissions['E-MILE']+incremental_idle*emissions['E-IDLE']
        records.append({'shipment_id':s['id'],'origin_id':s['origin_id'],'destination_id':s['destination_id'],'truck_id':s['truck_id'],
                        'driver_id':driver_id,'priority':det['priority'],'pickup_status':det['pickup_status'],
                        'affected':affected,'route':r['variant'],'blocked':blocked,'departure_min':depart,'arrival_min':arrival,
                        'appointment_end_min':deadline,'missed_original_appointment':arrival>s['appointment_end_min'] or blocked,
                        'late_min':round(late),'on_time':(arrival<=s['appointment_end_min'] and not blocked),'projected_on_time_if_approved':(late==0 and not blocked),
                        'miles':r['distance_mi'],'added_miles':round(r['distance_mi']-base['distance_mi'],1),
                        'cost_usd':round(c,2),'co2_kg':round(e,2),'community_exposure_proxy':r['community_exposure_index'],
                        'warnings':warnings,'reschedule_requested':rescheduled})
    lookup={r['shipment_id']:r for r in records}
    # Same vehicle assigned overlapping windows; flag all participating shipments.
    for truck,items in intervals.items():
        for i,a in enumerate(items):
            for b in items[i+1:]:
                if max(a[0],b[0])<min(a[1],b[1]):
                    for x,y in ((a,b),(b,a)):
                        msg=f'Overlapping synthetic truck assignment with {y[2]}'
                        if msg not in lookup[x[2]]['warnings']:lookup[x[2]]['warnings'].append(msg)
    total=len(records)
    metrics={'shipments':total,'at_risk':sum(not r['on_time'] for r in records),
             'missed_original_appointments':sum(r['missed_original_appointment'] for r in records),
             'on_time_pct':round(100*sum(r['on_time'] for r in records)/total,1),
             'projected_on_time_pct_if_approved':round(100*sum(r['projected_on_time_if_approved'] for r in records)/total,1),
             'cost_usd':round(sum(r['cost_usd'] for r in records),2),
             'co2_kg':round(sum(r['co2_kg'] for r in records),2),
             'miles':round(sum(r['miles'] for r in records),1),
             'late_minutes':sum(r['late_min'] for r in records),
             'flagged_shipments':sum(bool(r['warnings']) for r in records),
             'blocked_shipments':sum(r['blocked'] for r in records),
             'reschedule_requests':sum(r['reschedule_requested'] for r in records),
             'community_exposure_proxy':round(sum(r['community_exposure_proxy']*r['miles'] for r in records)/max(1,sum(r['miles'] for r in records)),2)}
    return {'scenario':cfg,'action':action,'severity_min':delay,'metrics':metrics,'shipments':records,
            'cautions':['Synthetic input only: neither travel-time nor road accessibility is validated.',
                        'Shared trucks may have conflicting assignments; flags are not a solved fleet schedule.',
                        'Rescheduling is a proposed request, not a booked appointment.',
                        'CO2 estimates use illustrative per-mile and delay factors; community proxy is not measured exposure.']}

def compare(scenario='SCN-SLOW',severity=None, db=DEFAULT_DB):
    return evaluate('SCN-NORMAL', db=db),[evaluate(scenario,a,severity,db) for a in ACTIONS]

if __name__=='__main__':
    base, options=compare()
    print('Baseline:',base['metrics'])
    for o in options: print(o['action'],o['metrics'])
