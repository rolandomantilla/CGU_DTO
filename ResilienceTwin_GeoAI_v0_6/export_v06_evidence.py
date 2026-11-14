"""Regenerate fixture-based scenario and per-shipment evidence for demonstration."""
import csv
from pathlib import Path
from optimizer_v06 import optimize_v06

ROOT=Path(__file__).resolve().parent
scenarios=[('Normal','SCN-NORMAL',0),('Highway slowdown','SCN-SLOW',75),('Road closure','SCN-CLOSE',150),('Pickup delay','SCN-PICKUP',90)]
rows=[];shipment_rows=[]
for label,code,minutes in scenarios:
    r=optimize_v06(code,minutes,policy='Balanced')
    rows.append({'scenario':label,'scenario_id':code,'severity_min':minutes,'policy':'Balanced',
                **r['metrics'],'provably_optimal':r['solver']['provably_optimal'],
                'network_type':'synthetic 9-node graph','measured_real_world':False})
    for s in r['shipments']:
        shipment_rows.append({'scenario':label,'shipment_id':s['shipment_id'],'priority':s['priority'],
            'status':s['status'],'truck_id':s.get('truck_id'),'trip_number':s.get('trip_number'),
            'cost_usd':s['cost_usd'],'co2_kg':s['co2_kg'],
            'loaded_miles':s.get('loaded_miles'),'empty_miles':s.get('empty_miles'),
            'route_segments':';'.join(s.get('route_segments',[])),
            'empty_route_segments':';'.join(s.get('empty_route_segments',[])),
            'reason':'; '.join(s.get('notes',[]))})
for name,data in [('scenario_evidence_v06.csv',rows),('shipment_evidence_v06.csv',shipment_rows)]:
    with (ROOT/name).open('w',newline='',encoding='utf-8') as file:
        writer=csv.DictWriter(file,fieldnames=data[0].keys());writer.writeheader();writer.writerows(data)
    print(name,'rows',len(data))
