"""v0.6: multi-trip, time-aware constructive dispatch using SYNTHETIC road graph.

Not a MILP or a globally optimal solution. Not certified truck navigation,
regulatory hours-of-service validation, or a live appointment system.
"""
from __future__ import annotations
from collections import defaultdict, Counter
from heapq import heappop, heappush
from math import ceil
import json
from optimizer_v05 import _table, PRIORITY_WEIGHTS
from decision_engine import DEFAULT_DB

POLICIES = ('Reliability first','Lowest cost','Lowest CO2','Balanced')

class SyntheticRoadNetwork:
    """Bidirectional shortest paths on the database's 13 illustrative segments."""
    def __init__(self, db=DEFAULT_DB):
        self.nodes={x['node_id']:x for x in _table(db,'road_nodes')}
        self.edges=defaultdict(list)
        self.segments={x['segment_id']:x for x in _table(db,'road_segments')}
        facilities=_table(db,'facilities')
        # Explicit supported fixture IDs, not latitude proximity guessing.
        mapping={'PORT-LA':'N-LA','PORT-LB':'N-LB','WH-CAR':'N-CAR',
                 'WH-COM':'N-COM','WH-ONT':'N-ONT','WH-RIV':'N-RIV','WH-FON':'N-FON'}
        self.facility_nodes={f['id']:mapping[f['id']] for f in facilities if f['id'] in mapping}
        for e in self.segments.values():
            if not e['freight_allowed']: continue
            for src,dst in ((e['from_node_id'],e['to_node_id']),(e['to_node_id'],e['from_node_id'])):
                self.edges[src].append((dst,e))

    def path(self, origin, destination, blocked=(), slowdown_segment=None, slowdown_min=0,
             preference='time'):
        if origin not in self.facility_nodes or destination not in self.facility_nodes:
            raise ValueError('Facility lacks a synthetic road graph connector')
        start=self.facility_nodes[origin];end=self.facility_nodes[destination]
        if start==end:
            n=self.nodes[start]
            return {'miles':0.0,'minutes':0,'segments':[], 'coords':[[n['lon'],n['lat']]],'delayed_minutes':0}
        queue=[(0,0,start,())];best={start:0};blocked=set(blocked)
        while queue:
            score,_,node,chain=heappop(queue)
            if score>best.get(node,float('inf'))+1e-8:continue
            if node==end:
                miles=sum(float(self.segments[s]['nominal_miles']) for s in chain)
                delayed=sum(int(slowdown_min) for s in chain if s==slowdown_segment)
                minutes=sum(int(self.segments[s]['nominal_min']) for s in chain)+delayed
                nodes=[start];cur=start
                for sid in chain:
                    e=self.segments[sid];cur=e['to_node_id'] if e['from_node_id']==cur else e['from_node_id'];nodes.append(cur)
                return {'miles':round(miles,2),'minutes':minutes,'segments':list(chain),
                        'coords':[[self.nodes[n]['lon'],self.nodes[n]['lat']] for n in nodes],
                        'delayed_minutes':delayed}
            for nxt,edge in self.edges[node]:
                sid=edge['segment_id']
                if sid in blocked:continue
                edge_minutes=float(edge['nominal_min'])+(slowdown_min if sid==slowdown_segment else 0)
                weight=edge_minutes if preference=='time' else float(edge['nominal_miles'])
                value=score+weight
                if value<best.get(nxt,float('inf'))-1e-8:
                    best[nxt]=value;heappush(queue,(value,len(chain)+1,nxt,chain+(sid,)))
        return None


def _config(scenario, severity, db):
    configs={x['scenario_id']:x for x in _table(db,'scenario_definitions')}
    if scenario not in configs:raise ValueError('Unknown scenario')
    cfg=configs[scenario]
    delay=cfg['severity_min'] if severity is None else severity
    if not isinstance(delay,(int,float)) or not 0<=delay<=600:raise ValueError('Severity must be between 0 and 600')
    return cfg,int(delay)


def optimize_v06(scenario='SCN-SLOW',severity=None,policy='Balanced',db=DEFAULT_DB,
                 turnaround_min=25,max_trips_per_truck=4,attempts=6,closure_segment=None,fuel_price=None):
    if policy not in POLICIES:raise ValueError('Unknown policy')
    if not isinstance(turnaround_min,int) or not 0<=turnaround_min<=240:raise ValueError('Invalid turnaround')
    if not isinstance(max_trips_per_truck,int) or not 1<=max_trips_per_truck<=15:raise ValueError('Invalid max trips')
    if not isinstance(attempts,int) or not 1<=attempts<=24:raise ValueError('Invalid attempts')
    cfg,delay=_config(scenario,severity,db)
    network=SyntheticRoadNetwork(db)
    shipments=_table(db,'shipments');details={x['shipment_id']:x for x in _table(db,'shipment_details')}
    trucks={x['id']:x for x in _table(db,'trucks')}
    specs={x['truck_id']:x for x in _table(db,'fleet_specs')}
    driver_ids={x['truck_id']:x['id'] for x in _table(db,'drivers')}
    profiles={x['driver_id']:x for x in _table(db,'driver_profiles')}
    slots={x['slot_id']:x for x in _table(db,'warehouse_slots')}
    cost={x['param_id']:x['value'] for x in _table(db,'cost_parameters')}
    fuel_delta = 0 if fuel_price is None else fuel_price - cost['C-FUEL']
    emi={x['param_id']:x['value'] for x in _table(db,'emission_parameters')}
    if closure_segment is not None and (
        cfg['kind'] != 'road_closure' or closure_segment not in network.segments
    ):
        raise ValueError('A closure override must identify a modeled road segment.')
    seg=closure_segment or cfg['affected_segment_id']
    # Only an explicit closure blocks access. Other hazards are modeled as slowdown.
    blocked=[seg] if cfg['kind']=='road_closure' and seg else []
    slow=seg if cfg['kind'] in ('traffic','wildfire','flood') else None
    paths={}
    facilities=list(network.facility_nodes)
    # Repositioning uses time-minimizing shortest graph paths, including closures.
    for a in facilities:
        for b in facilities:
            paths[(a,b)]=network.path(a,b,blocked,slow,delay,'time')
    reasons=Counter()
    def evaluate(shipment, state, occup, recovery_slot=None):
        det=details[shipment['id']];slot=recovery_slot or slots[det['appointment_slot_id']]
        options=[]
        if occup[slot['slot_id']]>=slot['capacity']:
            return [],'No modeled receiving capacity in original appointment slot'
        for tid,t in trucks.items():
            spec=specs.get(tid);did=driver_ids.get(tid);profile=profiles.get(did)
            if not spec or not profile or not tid in state:continue
            s=state[tid]
            if s['trips']>=max_trips_per_truck or t['status']!='available' or spec['maintenance_state']!='serviceable' or t['capacity_teu']<det['container_teu']:
                continue
            empty=paths[(s['location'],shipment['origin_id'])]
            loaded=paths[(shipment['origin_id'],shipment['destination_id'])]
            if empty is None or loaded is None:continue
            start=max(s['available'],profile['shift_start_min'])
            pickup_delay=delay if cfg['kind']=='port' and det['pickup_status']=='pending' else 0
            departure=max(start+empty['minutes'],shipment['pickup_ready_min']+pickup_delay)
            arrival=departure+loaded['minutes']
            receive=max(arrival,slot['window_start_min'],det['appointment_start_min'])
            finished=receive+turnaround_min
            drive=empty['minutes']+loaded['minutes']
            used_duty=finished-start
            window_end = slot['window_end_min'] if recovery_slot else min(slot['window_end_min'], shipment['appointment_end_min'])
            if receive > window_end:continue
            if finished>profile['shift_end_min']:continue
            # Simplified remaining shift budget. Waiting counts toward duty time.
            budget=int(profile['hours_remaining']*60)
            if s['duty_used']+used_duty>budget:continue
            if s['drive_used']+drive>budget:continue
            miles=empty['miles']+loaded['miles'];idle=empty['delayed_minutes']+loaded['delayed_minutes']
            fuel_adjustment = miles / float(spec['mpg_assumed']) * fuel_delta
            dollars=round(miles*cost['C-MI']+(drive+turnaround_min)/60*cost['C-HR']+fuel_adjustment,2)
            co2=round(miles*emi['E-MILE']+idle*emi['E-IDLE'],2)
            community=round(miles*3.0,2) # intentionally a rough proxy, not exposure measurement
            if policy=='Lowest cost': score=(dollars,receive,co2)
            elif policy=='Lowest CO2':score=(co2,receive,dollars)
            elif policy=='Reliability first':score=(receive,dollars,co2)
            else:score=(.50*dollars/300+.35*co2/150+.15*community/150,receive,dollars)
            options.append((score+(tid,),{'shipment_id':shipment['id'],'priority':det['priority'],'status':'scheduled',
                'origin_id':shipment['origin_id'],'destination_id':shipment['destination_id'],
                'truck_id':tid,'driver_id':did,'trip_number':s['trips']+1,
                'reposition_start_min':start,'departure_min':departure,'arrival_min':arrival,
                'receiving_min':receive,'complete_min':finished,'appointment_end_min':shipment['appointment_end_min'],
                'slot_id':slot['slot_id'],'empty_miles':empty['miles'],'empty_minutes':empty['minutes'],
                'loaded_miles':loaded['miles'],'loaded_minutes':loaded['minutes'],
                'total_miles':round(miles,2),'cost_usd':dollars,'co2_kg':co2,
                'community_exposure_proxy':community,'route_segments':loaded['segments'],
                'empty_route_segments':empty['segments'],'route_coords':loaded['coords'],
                'empty_route_coords':empty['coords'],'route_source':'synthetic road-segment graph',
                'notes':['Graph shortest path, not actual truck routing',
                         'No confirmed warehouse reservation or legal HOS validation']},
                drive,used_duty))
        return options,'No time-feasible truck/driver/route combination'

    def reserve(record, drive, duty, state, occupancy):
        truck = state[record['truck_id']]
        truck['location'] = record['destination_id']
        truck['available'] = record['complete_min']
        truck['trips'] += 1
        truck['duty_used'] += duty
        truck['drive_used'] += drive
        occupancy[record['slot_id']] += 1

    best=None
    for trial in range(attempts):
        # Deterministic alternative orderings to reduce dependence on one greedy pass.
        def key(x):
            d=details[x['id']];p=-PRIORITY_WEIGHTS.get(d['priority'],1)
            if trial%3==0:return (p,x['appointment_end_min'],x['pickup_ready_min'],x['id'])
            if trial%3==1:return (p,x['pickup_ready_min'],x['appointment_end_min'],x['id'])
            return (p,(x['appointment_end_min']-x['pickup_ready_min']),x['appointment_end_min'],x['id'])
        ordered=sorted(shipments,key=key)
        if trial>=3:ordered=list(reversed(ordered)) if trial==3 else sorted(ordered,key=lambda x:(-PRIORITY_WEIGHTS.get(details[x['id']]['priority'],1), (int(x['id'].split('-')[-1])* (trial+1))%43))
        state={}
        for tid,truck in trucks.items():
            spec=specs.get(tid);did=driver_ids.get(tid);p=profiles.get(did)
            if not spec or not p:continue
            state[tid]={'location':spec['home_warehouse_id'],
                'available':max(spec['available_from_min'],p['shift_start_min']),
                'trips':0,'duty_used':0,'drive_used':0}
        occupancy={k:int(v['booked']) for k,v in slots.items()}
        output={}
        for sh in ordered:
            opts,reason=evaluate(sh,state,occupancy)
            if opts:
                _,rec,drive,duty=min(opts,key=lambda z:z[0])
                reserve(rec, drive, duty, state, occupancy)
                output[sh['id']]=rec
            else:
                output[sh['id']]={'shipment_id':sh['id'],'priority':details[sh['id']]['priority'],
                  'status':'unassigned','origin_id':sh['origin_id'],'destination_id':sh['destination_id'],
                  'truck_id':None,'trip_number':None,'cost_usd':None,'co2_kg':None,'total_miles':None,
                  'route_coords':[],'empty_route_coords':[],'notes':[reason]}
        recs=[output[x['id']] for x in shipments]
        scheduled=[x for x in recs if x['status']=='scheduled']
        score=sum(PRIORITY_WEIGHTS.get(x['priority'],1) for x in scheduled)
        dollars=sum(x['cost_usd'] for x in scheduled);carbon=sum(x['co2_kg'] for x in scheduled)
        tie=({'Lowest cost':dollars,'Lowest CO2':carbon,'Reliability first':sum(x['receiving_min'] for x in scheduled),
              'Balanced':dollars/300+.7*carbon/150}[policy])
        ranking=(score,len(scheduled),-tie)
        if best is None or ranking>best[0]:best=(ranking,recs,trial,state,occupancy)
    records=best[1];selected=[r for r in records if r['status']=='scheduled']
    for x in records:
        if x['status']=='unassigned':reasons[x['notes'][0]]+=1
    # Build a provisional recovery plan after the committed trips.
    state, occupancy = best[3], best[4]
    shipment_by_id = {shipment['id']: shipment for shipment in shipments}
    unassigned = sorted((record for record in records if record['status'] == 'unassigned'),
                        key=lambda record: (-PRIORITY_WEIGHTS.get(record['priority'], 1),
                                            record['shipment_id']))
    for record in unassigned:
        shipment = shipment_by_id[record['shipment_id']]
        candidates = []
        for slot in slots.values():
            if (slot['warehouse_id'] == shipment['destination_id']
                    and slot['window_end_min'] > shipment['appointment_end_min']):
                options, _ = evaluate(shipment, state, occupancy, slot)
                candidates.extend(option for option in options
                                  if option[1]['receiving_min'] > shipment['appointment_end_min'])
        if candidates:
            _, recovery, drive, duty = min(
                candidates, key=lambda option: (option[1]['receiving_min'], option[0])
            )
            reserve(recovery, drive, duty, state, occupancy)
            record['recovery'] = {
                key: recovery[key] for key in ('arrival_min', 'receiving_min', 'slot_id', 'truck_id')
            }

    coverage=len(selected)/max(1,len(records))
    metrics={'shipments':len(records),'scheduled':len(selected),'unassigned':len(records)-len(selected),
       'coverage_pct':round(100*coverage,1),'priority_service_score':sum(PRIORITY_WEIGHTS.get(x['priority'],1) for x in selected),
       'critical_scheduled':sum(x['priority']=='critical' for x in selected),
       'trucks_used':len(set(x['truck_id'] for x in selected)),
       'trucks_with_multiple_trips':sum(c>1 for c in Counter(x['truck_id'] for x in selected).values()),
       'scheduled_cost_usd':round(sum(x['cost_usd'] for x in selected),2),
       'scheduled_co2_kg':round(sum(x['co2_kg'] for x in selected),2),
       'scheduled_loaded_miles':round(sum(x['loaded_miles'] for x in selected),2),
       'scheduled_empty_miles':round(sum(x['empty_miles'] for x in selected),2),
       'unassigned_cost_usd':None,'unassigned_co2_kg':None}
    return {'policy':policy,'scenario':cfg,'severity_min':delay,'shipments':records,'metrics':metrics,
      'solver':{'name':'Multi-start deterministic constructive scheduling',
                'provably_optimal':False,'trials':attempts,'best_trial':best[2],
                'model':'Multiple sequential trips per truck, no overlap, synthetic graph paths'},
      'unassigned_reasons':dict(reasons),
      'assumptions':['Synthetic graph nodes/edges only. Paths are not commercial truck-verified.',
          'Each truck may serve multiple nonoverlapping trips; drivers remain fixed to their assigned truck.',
          'Driver hours_remaining is simplified duty and drive allowance; regulatory HOS rules are not modeled.',
          'Warehouse booked counts treated as other demand, not verified external reservations.',
          'Only explicitly labeled road closures remove graph edges; other events add synthetic travel delay.',
          'No objective penalty for unassigned shipments; scheduled-trip totals exclude unmet demand.',
          'Costs and CO2 are illustrative; stakeholder proxy is not measured community exposure.',
          'Greedy multi-start does not prove global optimality; no actual dispatch or bookings are made.']}


def compare_policies(scenario='SCN-SLOW',severity=None,db=DEFAULT_DB,**kwargs):
    return [optimize_v06(scenario,severity,p,db=db,**kwargs) for p in POLICIES]

if __name__=='__main__':
    for x in compare_policies(): print(x['policy'],x['metrics'])
