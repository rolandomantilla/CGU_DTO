"""Synthetic, conservative, time-aware dispatch feasibility demonstrator.

NOT operational route optimization, truck navigation, regulatory HOS compliance,
or confirmed appointment booking. Route geometry is illustrative; vehicle position
is estimated by straight-line repositioning. No live systems are modified.
"""
from collections import defaultdict
from math import radians, sin, cos, asin, sqrt, ceil
from pathlib import Path
import json

from decision_engine import load, DEFAULT_DB

PRIORITY = {'critical': 0, 'high': 1, 'routine': 2}
STRATEGIES = ('Primary only', 'Allow alternate', 'Cost priority', 'Emissions priority')


def haversine_miles(a, b):
    """Great-circle distance, miles; zero for same facility."""
    lat1, lon1 = a
    lat2, lon2 = b
    dlat, dlon = radians(lat2-lat1), radians(lon2-lon1)
    h = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 3958.8 * 2 * asin(min(1, sqrt(h)))


def reposition(a, b, facilities, road_factor=1.30, speed_mph=35):
    """Estimated empty journey; never a validated drivable truck route."""
    if a == b:
        return 0.0, 0
    x,y = facilities[a], facilities[b]
    miles = round(haversine_miles((x['lat'], x['lon']), (y['lat'], y['lon']))*road_factor, 2)
    return miles, ceil(miles/speed_mph*60)


def optimize(scenario='SCN-SLOW', severity=None, strategy='Allow alternate', db=DEFAULT_DB,
             reposition_factor=1.30, turnaround_min=25, traffic_idling=True):
    if strategy not in STRATEGIES:
        raise ValueError('Unknown strategy')
    if reposition_factor < 1 or reposition_factor > 3:
        raise ValueError('Reposition factor must be between 1 and 3')
    if not 0 <= turnaround_min <= 240:
        raise ValueError('Turnaround outside 0..240 minutes')
    d=load(db)
    scenario_by_id={s['scenario_id']:s for s in d['scenario_definitions']}
    if scenario not in scenario_by_id:raise ValueError('Unknown scenario')
    cfg=scenario_by_id[scenario]
    delay=int(cfg['severity_min'] if severity is None else severity)
    if not 0 <= delay <= 600:raise ValueError('Delay outside 0..600 minutes')
    facilities={x['id']:x for x in d['facilities']} if 'facilities' in d else _load_facilities(db)
    trucks={x['truck_id']:x for x in d['fleet_specs']}
    truck_capacity={x['id']:x for x in d['trucks']} if 'trucks' in d else _load_trucks(db)
    assignments={x['truck_id']:x['id'] for x in d['drivers']}
    profiles={x['driver_id']:x for x in d['driver_profiles']}
    routes=defaultdict(list)
    for r in d['routes']:routes[r['shipment_id']].append(r)
    segment_details={x['segment_id']:x for x in d['road_segments']}
    route_segments=defaultdict(list)
    for link in sorted(d['route_segments'],key=lambda x:x['sequence_no']):
        route_segments[link['route_id']].append(link['segment_id'])
    details={x['shipment_id']:x for x in d['shipment_details']}
    slots={x['slot_id']:x for x in d['warehouse_slots']}
    cost={x['param_id']:x['value'] for x in d['cost_parameters']}
    emis={x['param_id']:x['value'] for x in d['emission_parameters']}
    # Explicitly model booked as third-party reservations; dataset doesn't confirm
    # whether those counts already include the 40 shipments.
    occupancy={id_:int(x['booked']) for id_,x in slots.items()}
    truck_state={}
    for tid,t in trucks.items():
        did=assignments.get(tid)
        p=profiles.get(did)
        if p:
            truck_state[tid]={'location':t['home_warehouse_id'],
                              'available':max(t['available_from_min'],p['shift_start_min']),
                              'drive_used':0,'driver_id':did,'profile':p,
                              'work_used':0}
    records=[]
    priorities=sorted(d['shipments'],key=lambda x:(PRIORITY.get(details[x['id']]['priority'],3),x['appointment_end_min'],x['pickup_ready_min'],x['id']))
    for s in priorities:
        det=details[s['id']]
        blocked_candidates=[]
        candidates=[]
        eligible_routes=routes[s['id']]
        if strategy=='Primary only': eligible_routes=[r for r in eligible_routes if r['variant']=='primary']
        primary=next(r for r in routes[s['id']] if r['variant']=='primary')
        for route in eligible_routes:
            seg_ids=route_segments[route['id']]
            if any(not segment_details[seg]['freight_allowed'] for seg in seg_ids):
                blocked_candidates.append('Segment is not flagged as freight-allowed in synthetic data')
                continue
            impacted=cfg['affected_segment_id'] in seg_ids if cfg['affected_segment_id'] else False
            if cfg['kind']=='road_closure' and impacted:
                blocked_candidates.append('Route intersects modeled road closure')
                continue
            port_delay=delay if cfg['kind']=='port' and det['pickup_status']=='pending' else 0
            traffic_delay=delay if impacted and cfg['kind']=='traffic' else 0
            for tid,state in truck_state.items():
                t=trucks[tid];p=state['profile']
                if t['maintenance_state']!='serviceable':continue
                if truck_capacity[tid]['status']!='available' or truck_capacity[tid]['capacity_teu'] < det['container_teu']:continue
                if t['available_from_min']>p['shift_end_min']:continue
                empty_mi,empty_min=reposition(state['location'],s['origin_id'],facilities,reposition_factor)
                # truck must finish previous drop/handling before repositioning
                move_start=max(state['available'],p['shift_start_min'])
                port_eta=move_start+empty_min
                ready=max(s['pickup_ready_min']+port_delay,port_eta)
                depart=ready
                journey=int(route['travel_min'])+traffic_delay
                arrive=depart+journey
                # Scheduled window is not shifted or silently approved
                slot=slots[det['appointment_slot_id']]
                # Earliest arrival can wait for receiving slot to open
                receive=max(arrive,int(slot['window_start_min']),int(det['appointment_start_min']))
                end=receive+turnaround_min
                drive=empty_min+journey
                # "hours_remaining" is conservative synthetic drive/work allowance;
                # this is not the FMCSA duty-hours calculation.
                budget=int(p['hours_remaining']*60)
                if (state['drive_used']+drive>budget or end>p['shift_end_min'] or
                    depart>p['shift_end_min'] or state['work_used']+end-move_start>budget):
                    continue
                # The original appointment slot is required; no auto-rescheduling
                if receive>min(s['appointment_end_min'],slot['window_end_min']):
                    continue
                if occupancy[slot['slot_id']]>=slot['capacity']:
                    continue
                mi=float(route['distance_mi'])+empty_mi
                expense=mi*cost['C-MI']+(drive+turnaround_min)/60*cost['C-HR']
                co2=mi*emis['E-MILE']+(traffic_delay*emis['E-IDLE'] if traffic_idling else 0)
                exposure=(float(route['community_exposure_index'])*route['distance_mi']+empty_mi*3)/max(mi,1)
                # Always favor honoring appointments; secondary objectives differ
                if strategy=='Emissions priority': score=(co2,expense,receive,tid)
                elif strategy=='Cost priority': score=(expense,co2,receive,tid)
                else: score=(receive,expense,co2,tid)
                candidates.append((score,{'shipment_id':s['id'],'priority':det['priority'],
                    'status':'scheduled','origin_id':s['origin_id'],'destination_id':s['destination_id'],
                    'truck_id':tid,'driver_id':state['driver_id'], 'route':route['variant'],
                    'route_id':route['id'],'departure_min':depart,'arrival_min':arrive,
                    'receiving_min':receive,'complete_min':end,'appointment_end_min':s['appointment_end_min'],
                    'slot_id':slot['slot_id'],'empty_miles':round(empty_mi,2),
                    'empty_minutes':empty_min,'loaded_miles':round(route['distance_mi'],2),
                    'total_miles':round(mi,2),'delay_minutes':traffic_delay,
                    'cost_usd':round(expense,2),'co2_kg':round(co2,2),
                    'community_exposure_proxy':round(exposure,2),
                    'route_coords':json.loads(route['geojson_points']),
                    'notes':['Repositioning estimated from straight-line distance, not street routing',
                             'Warehouse original reservation not independently verified']},
                    drive,move_start))
        if candidates:
            _,chosen,drive,move_start=min(candidates,key=lambda x:x[0])
            state=truck_state[chosen['truck_id']]
            state['drive_used']+=drive
            state['work_used']+=chosen['complete_min']-move_start
            state['available']=chosen['complete_min']
            state['location']=s['destination_id']
            occupancy[chosen['slot_id']]+=1
            records.append(chosen)
        else:
            reasons=[]
            if blocked_candidates: reasons+=sorted(set(blocked_candidates))
            reasons.append('No truck, driver, and original warehouse slot combination satisfies all modeled constraints')
            records.append({'shipment_id':s['id'],'priority':det['priority'],
                            'status':'unassigned','origin_id':s['origin_id'],
                            'destination_id':s['destination_id'],'truck_id':None,
                            'driver_id':None,'route':None,'route_id':None,
                            'departure_min':None,'arrival_min':None,'receiving_min':None,
                            'complete_min':None,'appointment_end_min':s['appointment_end_min'],
                            'slot_id':det['appointment_slot_id'],'empty_miles':0,
                            'empty_minutes':0,'loaded_miles':0,'total_miles':0,
                            'delay_minutes':0,'cost_usd':0,'co2_kg':0,'community_exposure_proxy':0,
                            'route_coords':[],'notes':reasons})
    scheduled=[x for x in records if x['status']=='scheduled']
    unassigned=[x for x in records if x['status']=='unassigned']
    # Cost and emissions are totals for scheduled journeys, not full network outcomes.
    # No fictitious $0 interpretation for unassigned deliveries.
    metrics={'shipments':len(records),'scheduled':len(scheduled),'unassigned':len(unassigned),
             'original_appointment_feasibility_pct':round(100*len(scheduled)/max(len(records),1),1),
             'scheduled_cost_usd':round(sum(x['cost_usd'] for x in scheduled),2),
             'scheduled_co2_kg':round(sum(x['co2_kg'] for x in scheduled),2),
             'scheduled_loaded_miles':round(sum(x['loaded_miles'] for x in scheduled),1),
             'scheduled_empty_miles':round(sum(x['empty_miles'] for x in scheduled),1),
             'scheduled_community_proxy':round(sum(x['community_exposure_proxy']*x['total_miles'] for x in scheduled)/max(1,sum(x['total_miles'] for x in scheduled)),2)}
    return {'scenario':cfg,'severity_min':delay,'strategy':strategy,'metrics':metrics,
            'shipments':sorted(records,key=lambda x:x['shipment_id']),
            'assumptions':['Illustrative road segments, routes and delays; no truck-specific street routing or live closure feed.',
                           'Empty reposition estimates use straight-line distance × factor at assumed 35 mph.',
                           'Every shipment requires its original receiving slot; booked counts treated as pre-existing outside reservations.',
                           'Trailer availability, terminal queues, handling compatibility, fuel stops and legal hours-of-service are not validated.',
                           'Greedy priority-first scheduler is not a global optimizer; it may leave feasible alternative schedules unexplored.',
                           'Costs and CO₂ cover scheduled journeys only; unassigned shipment penalties and emissions are excluded.',
                           'Community exposure is a synthetic proxy, not measured pollution or burden.',
                           'No dispatch or warehouse booking changes are executed.']}


def _load_trucks(db):
    import sqlite3
    c=sqlite3.connect(db);c.row_factory=sqlite3.Row
    try:return {x['id']:dict(x) for x in c.execute('select * from trucks')}
    finally:c.close()

def _load_facilities(db):
    import sqlite3
    c=sqlite3.connect(db);c.row_factory=sqlite3.Row
    try:return {x['id']:dict(x) for x in c.execute('select * from facilities')}
    finally:c.close()


def compare_strategies(scenario='SCN-SLOW',severity=None,db=DEFAULT_DB,**kwargs):
    return [optimize(scenario,severity,strategy,db=db,**kwargs) for strategy in STRATEGIES]

if __name__=='__main__':
    for r in compare_strategies():print(r['strategy'],r['metrics'])
