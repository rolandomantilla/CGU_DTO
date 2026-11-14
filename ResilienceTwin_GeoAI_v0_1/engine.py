"""Deterministic, synthetic logistics scenario engine. Not operational routing."""
import json, math, sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parent
DB=ROOT/'data'/'geoai.sqlite'
SCENARIOS={'Normal': {'type':'normal','delay':0}, 'Highway slowdown':{'type':'slowdown','delay':75}, 'Highway closure':{'type':'closure','delay':150}, 'Pickup delay':{'type':'pickup','delay':90}, 'Wildfire disruption':{'type':'wildfire','delay':110}, 'Flooding disruption':{'type':'flood','delay':120}}
STRATEGIES=('Stay on primary','Use alternate route','Expedite dispatch')

def fetch():
    if not DB.exists():
        raise FileNotFoundError('Missing data/geoai.sqlite — run python seed_data.py')
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    try:
        return {t:[dict(x) for x in c.execute('SELECT * FROM '+t)] for t in ('facilities','shipments','trucks','drivers','routes','disruptions')}
    finally:c.close()

def evaluate(scenario='Normal', strategy='Stay on primary', delay_override=None):
    if scenario not in SCENARIOS:raise ValueError('Unknown scenario')
    if strategy not in STRATEGIES:raise ValueError('Unknown strategy')
    d=fetch(); typ=SCENARIOS[scenario]['type']; delay=SCENARIOS[scenario]['delay'] if delay_override is None else max(0,int(delay_override))
    route_by={(r['shipment_id'],r['variant']):r for r in d['routes']}
    records=[]
    for s in d['shipments']:
        base=route_by[(s['id'],'primary')]
        affected=bool(s['exposed']) and typ in ('slowdown','closure','wildfire','flood')
        applied_delay=delay if (affected or typ=='pickup') else 0
        key='alternate' if strategy=='Use alternate route' and affected else 'primary'
        r=route_by[(s['id'],key)]
        # Alternative routes bypass the modeled disruption, but add distance/time.
        if key=='alternate': applied_delay=0
        if strategy=='Expedite dispatch':applied_delay=max(0,applied_delay-45)
        queue=10 if typ=='normal' else (25 if affected else 10)
        # All times in minutes from a common illustrative dispatch epoch.
        departure=s['pickup_ready_min'] + (applied_delay if typ=='pickup' else 0)
        journey=r['travel_min']+ (applied_delay if typ!='pickup' else 0) + queue
        if strategy=='Expedite dispatch':departure=max(0,departure-25)
        arrival=departure+journey
        late=max(0, arrival-s['appointment_end_min'])
        ontime=late==0
        cost=r['distance_mi']*2.7 + journey/60*28 + (90 if strategy=='Expedite dispatch' else 0) + (late*1.5)
        # Deliberately illustrative CO2 factor, not real-world measured truck emissions.
        emissions_kg=r['distance_mi']*1.65 + (journey-r['travel_min'])*0.09
        records.append({'shipment_id':s['id'],'origin_id':s['origin_id'],'destination_id':s['destination_id'],
            'truck_id':s['truck_id'],'route':key,'affected':affected,'arrival_min':round(arrival),
            'appointment_end_min':s['appointment_end_min'],'late_min':round(late),'on_time':ontime,
            'distance_mi':round(r['distance_mi'],1),'extra_miles':round(r['distance_mi']-base['distance_mi'],1),
            'cost_usd':round(cost,2),'co2_kg':round(emissions_kg,2),
            'community_exposure_index':r['community_exposure_index'],'route_points':json.loads(r['geojson_points'])})
    n=len(records)
    metrics={'shipments':n,'at_risk':sum(not r['on_time'] for r in records),
        'on_time_pct':round(100*sum(r['on_time'] for r in records)/n,1),
        'cost_usd':round(sum(r['cost_usd'] for r in records),2),
        'co2_kg':round(sum(r['co2_kg'] for r in records),2),
        'total_miles':round(sum(r['distance_mi'] for r in records),1),
        'late_minutes':sum(r['late_min'] for r in records),
        'community_exposure_index':round(sum(r['community_exposure_index']*r['distance_mi'] for r in records)/sum(r['distance_mi'] for r in records),2)}
    return {'scenario':scenario,'strategy':strategy,'assumptions':{'delay_min':delay,'cost_per_mile_usd':2.7,'driver_hour_usd':28,'co2_kg_per_mile':1.65,'community_exposure_index':'synthetic illustrative proxy 1–5, not measured exposure'},'metrics':metrics,'shipments':records,'facilities':d['facilities']}

def compare(scenario='Highway slowdown',delay_override=None):
    normal=evaluate('Normal')
    return normal,[evaluate(scenario,x,delay_override) for x in STRATEGIES]

if __name__=='__main__':
    normal,options=compare(); print(json.dumps({'normal':normal['metrics'],'options':{r['strategy']:r['metrics'] for r in options}},indent=2))
