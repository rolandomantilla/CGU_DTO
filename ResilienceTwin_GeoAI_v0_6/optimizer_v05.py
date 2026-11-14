"""v0.5 MILP one-trip-per-truck dispatch optimizer (research proof of concept).

Caveats: synthetic network only; no authoritative freight routing, regulatory HOS,
actual reservations, or multi-trip scheduling. SciPy HiGHS MILP solver.
"""
from collections import defaultdict, Counter
from pathlib import Path
import json
import math
import sqlite3
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import lil_matrix
from decision_engine import load, DEFAULT_DB
from optimizer_v04 import reposition, optimize as greedy_optimize

POLICIES = ('Reliability first', 'Lowest cost', 'Lowest CO2', 'Balanced')
PRIORITY_WEIGHTS = {'critical': 5, 'high': 3, 'routine': 1}


def _table(db, name):
    c=sqlite3.connect(db)
    c.row_factory=sqlite3.Row
    try:
        return [dict(r) for r in c.execute('SELECT * FROM '+name)]
    finally:
        c.close()


def route_quality(route, origin, destination, facilities, segs, freight_flags):
    """Only validates metadata and geometry topology, not drivable truck routes."""
    try:
        coords=json.loads(route['geojson_points'])
        wellformed=len(coords)>=2 and all(len(p)==2 and -180<=p[0]<=180 and -90<=p[1]<=90 for p in coords)
    except (ValueError, TypeError):
        wellformed=False
        coords=[]
    def near(point,facility):
        return math.hypot(point[0]-facility['lon'],point[1]-facility['lat'])<=0.12
    endpoints=wellformed and near(coords[0],facilities[origin]) and near(coords[-1],facilities[destination])
    seg_ids=segs.get(route['id'],[])
    flagged=bool(seg_ids) and all(freight_flags.get(s,False) for s in seg_ids)
    return {'geometry_valid':bool(wellformed),'endpoints_near_facilities':bool(endpoints),
            'synthetic_freight_flag_ok':bool(flagged),'truck_route_verified':False,
            'routing_provenance':'Synthetic segment metadata; no authoritative heavy-vehicle validation'}


def build_candidates(scenario='SCN-SLOW',severity=None,db=DEFAULT_DB,reposition_factor=1.3,turnaround_min=25):
    if not 1<=reposition_factor<=3:raise ValueError('Reposition factor must be 1..3')
    if not 0<=turnaround_min<=240:raise ValueError('Turnaround must be 0..240')
    d=load(db)
    configs={s['scenario_id']:s for s in d['scenario_definitions']}
    if scenario not in configs:raise ValueError('Unknown scenario')
    cfg=configs[scenario]
    delay=cfg['severity_min'] if severity is None else severity
    if not isinstance(delay,(int,float)) or not 0<=delay<=600:raise ValueError('Invalid severity')
    delay=int(delay)
    shipments=d['shipments']
    details={x['shipment_id']:x for x in d['shipment_details']}
    facilities={x['id']:x for x in _table(db,'facilities')}
    trucks={x['id']:x for x in _table(db,'trucks')}
    specs={x['truck_id']:x for x in d['fleet_specs']}
    drivers={x['truck_id']:x['id'] for x in d['drivers']}
    profiles={x['driver_id']:x for x in d['driver_profiles']}
    slots={x['slot_id']:x for x in d['warehouse_slots']}
    cost={x['param_id']:x['value'] for x in d['cost_parameters']}
    emi={x['param_id']:x['value'] for x in d['emission_parameters']}
    routes=defaultdict(list)
    for x in d['routes']:routes[x['shipment_id']].append(x)
    segs=defaultdict(list)
    for x in sorted(d['route_segments'],key=lambda a:a['sequence_no']):segs[x['route_id']].append(x['segment_id'])
    freight_flags={x['segment_id']:bool(x['freight_allowed']) for x in d['road_segments']}
    candidates=[]
    exclusions=Counter()
    for shipment in shipments:
        sd=details[shipment['id']]
        for route in routes[shipment['id']]:
            q=route_quality(route,shipment['origin_id'],shipment['destination_id'],facilities,segs,freight_flags)
            if not (q['geometry_valid'] and q['endpoints_near_facilities'] and q['synthetic_freight_flag_ok']):
                exclusions['Failed synthetic route metadata checks']+=1;continue
            affected=bool(cfg['affected_segment_id'] and cfg['affected_segment_id'] in segs[route['id']])
            if affected and cfg['kind']=='road_closure':
                exclusions['Closed segment intersects route']+=1;continue
            port_delay=delay if cfg['kind']=='port' and sd['pickup_status']=='pending' else 0
            traffic_delay=delay if cfg['kind']=='traffic' and affected else 0
            slot=slots[sd['appointment_slot_id']]
            if slot['capacity']-slot['booked']<=0:
                exclusions['Slot already at capacity']+=1;continue
            for tid,truck in trucks.items():
                spec=specs.get(tid);did=drivers.get(tid);profile=profiles.get(did)
                if not spec or not profile or spec['maintenance_state']!='serviceable' or truck['status']!='available' or truck['capacity_teu']<sd['container_teu']:
                    exclusions['Truck unavailable, capacity or maintenance']+=1;continue
                empty_mi,empty_min=reposition(spec['home_warehouse_id'],shipment['origin_id'],facilities,reposition_factor)
                start=max(int(spec['available_from_min']),int(profile['shift_start_min']))
                depart=max(int(shipment['pickup_ready_min'])+port_delay,start+empty_min)
                drive=empty_min+int(route['travel_min'])+traffic_delay
                arrival=depart+int(route['travel_min'])+traffic_delay
                receive=max(arrival,int(slot['window_start_min']),int(sd['appointment_start_min']))
                finish=receive+turnaround_min
                # Conservative single-trip duty budget; not legal HOS validation.
                if (receive>min(shipment['appointment_end_min'],slot['window_end_min'])
                    or finish>profile['shift_end_min']
                    or drive>profile['hours_remaining']*60
                    or finish-start>profile['hours_remaining']*60):
                    exclusions['Appointment, shift or remaining-hour constraint']+=1;continue
                miles=empty_mi+float(route['distance_mi'])
                value=round(miles*cost['C-MI']+(drive+turnaround_min)/60*cost['C-HR'],2)
                carbon=round(miles*emi['E-MILE']+traffic_delay*emi['E-IDLE'],2)
                community=round((float(route['community_exposure_index'])*route['distance_mi']+3*empty_mi)/max(miles,1),2)
                candidates.append({'shipment_id':shipment['id'],'priority':sd['priority'],'truck_id':tid,'driver_id':did,
                   'route_id':route['id'],'route':route['variant'],'origin_id':shipment['origin_id'],'destination_id':shipment['destination_id'],
                   'slot_id':slot['slot_id'],'departure_min':depart,'arrival_min':arrival,'receiving_min':receive,'complete_min':finish,
                   'appointment_end_min':shipment['appointment_end_min'],'empty_miles':empty_mi,'loaded_miles':round(float(route['distance_mi']),2),
                   'total_miles':round(miles,2),'cost_usd':value,'co2_kg':carbon,'community_exposure_proxy':community,
                   'route_coords':json.loads(route['geojson_points']),'route_quality':q,
                   'notes':['One trip per truck in the planning horizon', 'Empty movement approximated; no verified freight route',
                            'Warehouse existing bookings treated as external reservations']})
    return {'candidates':candidates,'shipments':shipments,'details':details,'slots':slots,'scenario':cfg,
            'severity_min':delay,'exclusions':dict(exclusions)}


def _constraints(candidates, slots):
    # Max one selection per shipment and truck; slot capacity is shared.
    groups=defaultdict(list)
    for i,x in enumerate(candidates):
        for kind,key in [('shipment',x['shipment_id']),('truck',x['truck_id']),('slot',x['slot_id'])]:
            groups[(kind,key)].append(i)
    matrix=lil_matrix((len(groups),len(candidates)),dtype=float)
    upper=[]
    for j,((kind,key),indices) in enumerate(groups.items()):
        for i in indices:matrix[j,i]=1
        upper.append(max(0,slots[key]['capacity']-slots[key]['booked']) if kind=='slot' else 1)
    return LinearConstraint(matrix.tocsr(),np.zeros(len(groups)),np.asarray(upper,dtype=float))


def optimize_v05(scenario='SCN-SLOW',severity=None,policy='Balanced',db=DEFAULT_DB,
                 reposition_factor=1.3,turnaround_min=25,time_limit=20):
    if policy not in POLICIES:raise ValueError('Unknown policy')
    if not 1<=time_limit<=180:raise ValueError('Time limit must be 1..180 seconds')
    setup=build_candidates(scenario,severity,db,reposition_factor,turnaround_min)
    candidates=setup['candidates'];n=len(candidates)
    if not n: raise RuntimeError('No feasible candidates under selected synthetic constraints')
    constraint=_constraints(candidates,setup['slots'])
    # First maximize priority-weighted delivery score. Disruptions may change the best feasible shipment set.
    w=np.array([PRIORITY_WEIGHTS.get(x['priority'],1) for x in candidates],dtype=float)
    chosen_count=np.ones(n)
    result1=milp(c=-w,integrality=np.ones(n),bounds=Bounds(0,1),constraints=constraint,
                 options={'time_limit':time_limit,'mip_rel_gap':0.0})
    if result1.x is None:raise RuntimeError(f'First MILP solve returned no feasible result: {result1.message}')
    achieved=int(round(w@np.rint(result1.x)))
    # Second maximize number of shipments without losing achieved priority score.
    priority_constraint=LinearConstraint(w.reshape(1,-1),achieved,np.inf)
    result2=milp(c=-chosen_count,integrality=np.ones(n),bounds=Bounds(0,1),constraints=[constraint,priority_constraint],
                 options={'time_limit':time_limit,'mip_rel_gap':0.0})
    if result2.x is None:raise RuntimeError(f'Second MILP solve returned no feasible result: {result2.message}')
    count=int(round(np.rint(result2.x).sum()))
    count_constraint=LinearConstraint(chosen_count.reshape(1,-1),count,np.inf)
    costs=np.array([x['cost_usd'] for x in candidates]);co2=np.array([x['co2_kg'] for x in candidates]);exposure=np.array([x['community_exposure_proxy']*x['total_miles'] for x in candidates])
    if policy=='Lowest cost':obj=costs
    elif policy=='Lowest CO2':obj=co2
    elif policy=='Reliability first':obj=np.array([x['receiving_min'] for x in candidates],dtype=float)
    else:
        # Scale-free relative weights; illustrative preference, not objective scientific utility.
        obj=0.50*costs/max(1,float(np.median(costs)))+0.35*co2/max(1,float(np.median(co2)))+0.15*exposure/max(1,float(np.median(exposure)))
    # Stable deterministic tie breaker within floating precision.
    obj=obj+np.arange(n)*1e-8
    result3=milp(c=obj,integrality=np.ones(n),bounds=Bounds(0,1),constraints=[constraint,priority_constraint,count_constraint],
                 options={'time_limit':time_limit,'mip_rel_gap':0.0})
    if result3.x is None:raise RuntimeError(f'Third MILP solve returned no feasible result: {result3.message}')
    selected=[dict(candidates[i],status='scheduled') for i in range(n) if result3.x[i]>0.5]
    by_shipment={x['shipment_id']:x for x in selected}
    for s in setup['shipments']:
        if s['id'] not in by_shipment:
            by_shipment[s['id']]={'shipment_id':s['id'],'priority':setup['details'][s['id']]['priority'],
              'status':'unassigned','origin_id':s['origin_id'],'destination_id':s['destination_id'],
              'truck_id':None,'driver_id':None,'route':None,'route_id':None,
              'slot_id':setup['details'][s['id']]['appointment_slot_id'], 'empty_miles':None,'loaded_miles':None,
              'total_miles':None,'cost_usd':None,'co2_kg':None,'route_coords':[],
              'notes':['No assignment in optimal selected candidate set; capacity, priorities or tradeoffs may have displaced it']}
    shipments=[by_shipment[s['id']] for s in setup['shipments']]
    unassigned=len(shipments)-len(selected)
    metrics={'shipments':len(shipments),'scheduled':len(selected),'unassigned':unassigned,
      'priority_service_score':int(sum(PRIORITY_WEIGHTS.get(x['priority'],1) for x in selected)),
      'critical_scheduled':sum(x['priority']=='critical' for x in selected),
      'scheduled_cost_usd':round(sum(x['cost_usd'] for x in selected),2),
      'scheduled_co2_kg':round(sum(x['co2_kg'] for x in selected),2),
      'scheduled_loaded_miles':round(sum(x['loaded_miles'] for x in selected),2),
      'scheduled_empty_miles':round(sum(x['empty_miles'] for x in selected),2),
      'scheduled_community_proxy':round(sum(x['community_exposure_proxy']*x['total_miles'] for x in selected)/max(1,sum(x['total_miles'] for x in selected)),2)}
    # Strictly conditional: optimality means solver status 0 at all three stages.
    optimal=all(x.status==0 for x in (result1,result2,result3))
    return {'policy':policy,'scenario':setup['scenario'],'severity_min':setup['severity_min'],
      'shipments':shipments,'metrics':metrics,'candidate_count':n,'exclusions':setup['exclusions'],
      'solver':{'name':'SciPy HiGHS MILP','provably_optimal':optimal,'stages':[x.message for x in (result1,result2,result3)],
                'model':'Single-trip-per-truck capacity assignment; lexicographic priority score then count then selected objective'},
      'assumptions':['All routes and segment freight flags are synthetic; no authoritative truck-safe route validation.',
          'One trip per truck (conservative). Not a multi-stop routing or multi-trip vehicle scheduling model.',
          'Pre-booked warehouse slot quantities assumed to be other reservations; not verified.',
          'Driver remaining hours modeled as simplified time budget; not DOT/FMSCA HOS compliance.',
          'Each assignment begins at the truck home facility; repositioning uses haversine distance × factor, not a road graph.',
          'No penalty is imputed for an unassigned shipment. Completed-only cost and CO2 are not whole-network totals.',
          'Environmental and community exposure factors are illustrative, not observed.',
          'The model never changes dispatch assignments or books appointments. Human review is mandatory.']}


def compare_policies(scenario='SCN-SLOW',severity=None,db=DEFAULT_DB,**kwargs):
    return [optimize_v05(scenario,severity,policy,db=db,**kwargs) for policy in POLICIES]

if __name__=='__main__':
    for r in compare_policies():print(r['policy'],r['metrics'],r['solver']['provably_optimal'])
