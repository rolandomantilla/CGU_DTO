"""Rebuild reproducible, fictional ResilienceTwin GeoAI base + extended relational foundation.
Usage: python build_foundation.py. Never run over the original CGU_DTO database.
"""
from pathlib import Path
import csv, json, math, random, sqlite3
import seed_data
ROOT=Path(__file__).resolve().parent
DB=ROOT/'data'/'geoai.sqlite'
OUT=ROOT/'csv'
SEED=20261114

def main():
    seed_data.main()
    r=random.Random(SEED)
    conn=sqlite3.connect(DB)
    conn.execute('PRAGMA foreign_keys=ON')
    conn.executescript('''
    CREATE TABLE dataset_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE personnel(person_id TEXT PRIMARY KEY,display_name TEXT NOT NULL,role TEXT NOT NULL,facility_id TEXT NOT NULL REFERENCES facilities(id),skill_level INTEGER NOT NULL CHECK(skill_level BETWEEN 1 AND 5),shift_code TEXT NOT NULL,availability TEXT NOT NULL,backup_person_id TEXT REFERENCES personnel(person_id),driver_id TEXT UNIQUE REFERENCES drivers(id),fictional INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE skills(skill_id TEXT PRIMARY KEY,name TEXT NOT NULL,category TEXT NOT NULL);
    CREATE TABLE personnel_skills(person_id TEXT REFERENCES personnel(person_id),skill_id TEXT REFERENCES skills(skill_id),proficiency INTEGER CHECK(proficiency BETWEEN 1 AND 5),PRIMARY KEY(person_id,skill_id));
    CREATE TABLE facility_resources(resource_id TEXT PRIMARY KEY,facility_id TEXT REFERENCES facilities(id),resource_type TEXT NOT NULL,quantity INTEGER NOT NULL,operational_qty INTEGER NOT NULL,capacity_per_hour REAL NOT NULL,priority INTEGER NOT NULL);
    CREATE TABLE warehouse_slots(slot_id TEXT PRIMARY KEY,warehouse_id TEXT REFERENCES facilities(id),window_start_min INTEGER NOT NULL,window_end_min INTEGER NOT NULL,capacity INTEGER NOT NULL,booked INTEGER NOT NULL DEFAULT 0, CHECK(window_end_min > window_start_min), CHECK(booked <= capacity));
    CREATE TABLE shipment_details(shipment_id TEXT PRIMARY KEY REFERENCES shipments(id),container_id TEXT UNIQUE NOT NULL,customer_id TEXT NOT NULL,cargo_type TEXT NOT NULL,container_teu INTEGER NOT NULL,priority TEXT NOT NULL,pickup_status TEXT NOT NULL,appointment_start_min INTEGER NOT NULL,appointment_slot_id TEXT REFERENCES warehouse_slots(slot_id),estimated_value_usd REAL NOT NULL,handling_requirements TEXT NOT NULL,source_quality TEXT NOT NULL);
    CREATE TABLE fleet_specs(truck_id TEXT PRIMARY KEY REFERENCES trucks(id),vehicle_type TEXT NOT NULL,fuel_type TEXT NOT NULL,model_year INTEGER NOT NULL,mpg_assumed REAL NOT NULL,maintenance_state TEXT NOT NULL,available_from_min INTEGER NOT NULL,home_warehouse_id TEXT REFERENCES facilities(id));
    CREATE TABLE driver_profiles(driver_id TEXT PRIMARY KEY REFERENCES drivers(id),person_id TEXT UNIQUE NOT NULL REFERENCES personnel(person_id),endorsement TEXT NOT NULL,shift_start_min INTEGER NOT NULL,shift_end_min INTEGER NOT NULL,hours_remaining REAL NOT NULL,rest_required_min INTEGER NOT NULL);
    CREATE TABLE road_nodes(node_id TEXT PRIMARY KEY,name TEXT NOT NULL,lat REAL NOT NULL,lon REAL NOT NULL,node_type TEXT NOT NULL);
    CREATE TABLE road_segments(segment_id TEXT PRIMARY KEY,from_node_id TEXT REFERENCES road_nodes(node_id),to_node_id TEXT REFERENCES road_nodes(node_id),road_name TEXT NOT NULL,nominal_miles REAL NOT NULL,nominal_min INTEGER NOT NULL,sensitivity TEXT NOT NULL,freight_allowed INTEGER NOT NULL,geometry_json TEXT NOT NULL);
    CREATE TABLE route_segments(route_id TEXT REFERENCES routes(id),segment_id TEXT REFERENCES road_segments(segment_id),sequence_no INTEGER NOT NULL,PRIMARY KEY(route_id,sequence_no));
    CREATE TABLE scenario_definitions(scenario_id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,severity_min INTEGER NOT NULL,affected_segment_id TEXT REFERENCES road_segments(segment_id),confidence TEXT NOT NULL,description TEXT NOT NULL);
    CREATE TABLE disruption_exposures(disruption_id TEXT REFERENCES disruptions(id),segment_id TEXT REFERENCES road_segments(segment_id),severity_factor REAL NOT NULL,source TEXT NOT NULL,PRIMARY KEY(disruption_id,segment_id));
    CREATE TABLE scenario_actions(action_id TEXT PRIMARY KEY,action_type TEXT NOT NULL,description TEXT NOT NULL,requires_approval INTEGER NOT NULL,estimated_setup_min INTEGER NOT NULL);
    CREATE TABLE cost_parameters(param_id TEXT PRIMARY KEY,category TEXT NOT NULL,value REAL NOT NULL,unit TEXT NOT NULL,scenario_basis TEXT NOT NULL,confidence TEXT NOT NULL);
    CREATE TABLE emission_parameters(param_id TEXT PRIMARY KEY,mode TEXT NOT NULL,value REAL NOT NULL,unit TEXT NOT NULL,scenario_basis TEXT NOT NULL,confidence TEXT NOT NULL);
    CREATE TABLE community_zones(zone_id TEXT PRIMARY KEY,name TEXT NOT NULL,centroid_lat REAL NOT NULL,centroid_lon REAL NOT NULL,sensitivity_level INTEGER NOT NULL CHECK(sensitivity_level BETWEEN 1 AND 5),sensitive_site TEXT NOT NULL,source_quality TEXT NOT NULL);
    CREATE TABLE segment_community_exposure(segment_id TEXT REFERENCES road_segments(segment_id),zone_id TEXT REFERENCES community_zones(zone_id),impact_weight REAL NOT NULL,PRIMARY KEY(segment_id,zone_id));
    CREATE TABLE dependencies(dependency_id TEXT PRIMARY KEY,upstream_type TEXT NOT NULL,upstream_id TEXT NOT NULL,downstream_type TEXT NOT NULL,downstream_id TEXT NOT NULL,dependency_type TEXT NOT NULL,criticality INTEGER NOT NULL CHECK(criticality BETWEEN 1 AND 5),notes TEXT NOT NULL);
    CREATE TABLE decision_audit(audit_id TEXT PRIMARY KEY,scenario_id TEXT REFERENCES scenario_definitions(scenario_id),action_id TEXT REFERENCES scenario_actions(action_id),reviewer_person_id TEXT REFERENCES personnel(person_id),decision_status TEXT NOT NULL,reason TEXT NOT NULL,created_at_utc TEXT NOT NULL);
    CREATE INDEX idx_shipments_origin_dest ON shipments(origin_id,destination_id);
    CREATE INDEX idx_personnel_facility ON personnel(facility_id);
    CREATE INDEX idx_route_segments_segment ON route_segments(segment_id);
    CREATE INDEX idx_dependencies_upstream ON dependencies(upstream_type,upstream_id);
    CREATE INDEX idx_exposures_segment ON disruption_exposures(segment_id);
    ''')
    metadata={
        'dataset_name':'ResilienceTwin GeoAI foundational data v0.2',
        'classification':'100% synthetic educational sample; actual city and port names used as geographic reference only',
        'generated_date':'2026-11-14',
        'seed':str(SEED),
        'time_basis':'integer minutes relative to a fictional common dispatch epoch; NOT actual local clock times',
        'coordinates':'Approximate WGS84 latitude/longitude; schematic geometries NOT drivable routes',
        'status':'Preliminary illustrative foundation, not operationally validated',
        'engineering_note':'Existing v0.1 engine only reads six legacy tables. Additional tables are staged for v0.2 logic and must not be described as enforced by current engine.',
    }
    conn.executemany('INSERT INTO dataset_metadata VALUES (?,?)',list(metadata.items()))
    facilities=[row[0] for row in conn.execute('SELECT id FROM facilities ORDER BY id')]
    warehouses=[row[0] for row in conn.execute("SELECT id FROM facilities WHERE kind='warehouse' ORDER BY id")]
    roles=['Dispatcher','Warehouse Coordinator','Fleet Mechanic','Operations Analyst','Safety Officer','GIS Analyst','Supply Chain Planner','Security Specialist','Receiving Specialist','Logistics Manager','Truck Driver']
    staff=[]
    # Deterministic synthetic personnel across all seven sites. 12 records map to 12 modeled drivers.
    for i in range(1,101):
        pid=f'PERSON-{i:03d}'
        facility=facilities[(i-1)%len(facilities)]
        role='Truck Driver' if i<=12 else roles[1+(i-13)%(len(roles)-2)]
        drv=f'DRIVER-{i:02d}' if i<=12 else None
        staff.append((pid,f'Synthetic Staff {i:03d}',role,facility,1+(i%5),['AM','PM','NIGHT'][i%3], 'available' if i%11 else 'on_leave',None,drv,1))
    conn.executemany('INSERT INTO personnel VALUES (?,?,?,?,?,?,?,?,?,?)',staff)
    for i in range(1,101):
        backup=f'PERSON-{(i%100)+1:03d}'
        conn.execute('UPDATE personnel SET backup_person_id=? WHERE person_id=?',(backup,f'PERSON-{i:03d}'))
    skills=[('SK-GIS','GIS and spatial analysis','technical'),('SK-DISPATCH','Fleet dispatch','operations'),('SK-SAFETY','Safety assessment','safety'),('SK-HAZMAT','Hazardous materials awareness','safety'),('SK-ROUTING','Route planning','operations'),('SK-FLEET','Fleet maintenance','technical'),('SK-RECEIVING','Warehouse receiving','operations'),('SK-ANALYTICS','Data analytics','technical'),('SK-COMMS','Stakeholder communication','operations'),('SK-DRIVING','Commercial driving','operations')]
    conn.executemany('INSERT INTO skills VALUES (?,?,?)',skills)
    for i in range(1,101):
        pid=f'PERSON-{i:03d}'
        chosen={skills[(i-1)%len(skills)][0],skills[(i+2)%len(skills)][0]}
        if i<=12:chosen.add('SK-DRIVING')
        conn.executemany('INSERT INTO personnel_skills VALUES (?,?,?)',[(pid,sk,1+(i+idx)%5) for idx,sk in enumerate(sorted(chosen))])
    resources=[]
    for fac in facilities:
        for kind,qty,rate in [('forklift',5 if fac in warehouses else 9,2.0),('dock_door',4 if fac in warehouses else 12,1.2),('power_unit',2,0.0),('dispatch_terminal',3,0.0)]:
            resources.append((f'RES-{fac}-{kind}',fac,kind,qty,qty if r.random()>.2 else qty-1,rate,5 if kind=='power_unit' else 3))
    conn.executemany('INSERT INTO facility_resources VALUES (?,?,?,?,?,?,?)',resources)
    # Slots are descriptive scheduling data; v0.1 engine does not enforce slot capacities.
    slots=[]
    for wh in warehouses:
        for hour in range(0,12,2):
            slots.append((f'SLOT-{wh}-{hour:02}',wh,hour*60,(hour+2)*60,8,0))
    conn.executemany('INSERT INTO warehouse_slots VALUES (?,?,?,?,?,?)',slots)
    details=[]
    for n,sid,dest,ready,appt_end in conn.execute('SELECT rowid,id,destination_id,pickup_ready_min,appointment_end_min FROM shipments ORDER BY id'):
        start=max(0,appt_end-60)
        slot_hour=min(10,(start//120)*2)
        slot=f'SLOT-{dest}-{slot_hour:02}'
        details.append((sid,f'CONT-{n:05d}',f'CUST-{(n-1)%9+1:03d}', ['general','electronics','food_nonperishable','automotive','textiles'][n%5],1 if n%4 else 2,['routine','high','critical'][n%3], 'ready' if ready==0 else 'pending',start,slot,round(8000+n*217.35,2), 'standard' if n%7 else 'fragile','synthetic'))
    conn.executemany('INSERT INTO shipment_details VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',details)
    for slot_id,count in conn.execute('SELECT appointment_slot_id,COUNT(*) FROM shipment_details GROUP BY appointment_slot_id').fetchall():
        conn.execute('UPDATE warehouse_slots SET booked=? WHERE slot_id=?',(count,slot_id))
    fleet=[];drivers=[]
    for i in range(1,13):
        truck=f'TRUCK-{i:02d}';drv=f'DRIVER-{i:02d}'
        fleet.append((truck,'Class 8 tractor','diesel',2019+i%7,round(5.5+(i%5)*0.25,2),'serviceable' if i%6 else 'inspection_due',0,warehouses[(i-1)%5]))
        drivers.append((drv,f'PERSON-{i:03d}','CDL-A',0,600,round(3.0+(i%5)*0.8,1),30))
    conn.executemany('INSERT INTO fleet_specs VALUES (?,?,?,?,?,?,?,?)',fleet)
    conn.executemany('INSERT INTO driver_profiles VALUES (?,?,?,?,?,?,?)',drivers)
    nodes=[('N-LA','Port of Los Angeles',33.732,-118.269,'port'),('N-LB','Port of Long Beach',33.754,-118.216,'port'),('N-CAR','Carson',33.832,-118.281,'hub'),('N-COM','Commerce',34.002,-118.159,'hub'),('N-ONT','Ontario',34.064,-117.651,'hub'),('N-RIV','Riverside',33.953,-117.396,'hub'),('N-FON','Fontana',34.097,-117.435,'hub'),('N-ALT1','Alternate Junction A',33.875,-117.935,'schematic'),('N-ALT2','Alternate Junction B',34.045,-117.795,'schematic')]
    conn.executemany('INSERT INTO road_nodes VALUES (?,?,?,?,?)',nodes)
    lookup={n[0]:n for n in nodes}
    segspec=[('S-001','N-LA','N-CAR','Port access connector',9,18,'high'),('S-002','N-LB','N-CAR','Port access connector',10,20,'high'),('S-003','N-CAR','N-COM','I-710 corridor (illustrative)',17,29,'high'),('S-004','N-COM','N-ONT','I-10 corridor (illustrative)',37,45,'high'),('S-005','N-ONT','N-RIV','I-15 / SR-60 corridor (illustrative)',17,26,'medium'),('S-006','N-ONT','N-FON','I-10 east corridor (illustrative)',14,22,'high'),('S-007','N-CAR','N-ALT1','Southern alternate connector',24,39,'medium'),('S-008','N-ALT1','N-ALT2','Alternative inland route',34,45,'medium'),('S-009','N-ALT2','N-ONT','Alternate Ontario connector',17,25,'medium'),('S-010','N-ALT2','N-RIV','Alternate Riverside connector',27,37,'medium'),('S-011','N-ALT2','N-FON','Alternate Fontana connector',26,35,'medium'),('S-012','N-CAR','N-COM','Local freight road (illustrative)',20,43,'high'),('S-013','N-COM','N-ALT2','I-605 corridor (illustrative)',35,48,'medium')]
    conn.executemany('INSERT INTO road_segments VALUES (?,?,?,?,?,?,?,?,?)',[(sid,a,b,name,miles,mins,sens,1,json.dumps([[lookup[a][3],lookup[a][2]],[lookup[b][3],lookup[b][2]]])) for sid,a,b,name,miles,mins,sens in segspec])
    # Route-to-segment membership is an illustrative network approximation; route mileage is separately modeled.
    primary={'WH-CAR':['S-001'],'WH-COM':['S-001','S-003'],'WH-ONT':['S-001','S-003','S-004'],'WH-RIV':['S-001','S-003','S-004','S-005'],'WH-FON':['S-001','S-003','S-004','S-006']}
    alternates={'WH-CAR':['S-007'],'WH-COM':['S-012'],'WH-ONT':['S-007','S-008','S-009'],'WH-RIV':['S-007','S-008','S-010'],'WH-FON':['S-007','S-008','S-011']}
    for shipment_id,orig,dest in conn.execute('SELECT id,origin_id,destination_id FROM shipments'):
        for variant,seq in [('primary',primary[dest]),('alternate',alternates[dest])]:
            parts=(['S-002'] if orig=='PORT-LB' else ['S-001'])+seq[1:] if variant=='primary' else seq
            for idx,sid in enumerate(parts,1):
                conn.execute('INSERT INTO route_segments VALUES (?,?,?)',(shipment_id+'-'+variant,sid,idx))
    scenarios=[('SCN-NORMAL','Normal','normal',0,None,'synthetic','No disruption'),('SCN-SLOW','Highway slowdown','traffic',75,'S-004','synthetic','Modeled inland delay'),('SCN-CLOSE','Highway closure','road_closure',150,'S-004','synthetic','Modeled segment closure'),('SCN-PICKUP','Pickup delay','port',90,None,'synthetic','Containers not ready'),('SCN-FIRE','Wildfire disruption','wildfire',110,'S-005','synthetic','Illustrative wildfire route exposure'),('SCN-FLOOD','Flooding disruption','flood',120,'S-003','synthetic','Illustrative flooding route exposure')]
    conn.executemany('INSERT INTO scenario_definitions VALUES (?,?,?,?,?,?,?)',scenarios)
    conn.executemany('INSERT INTO disruption_exposures VALUES (?,?,?,?)',[('DIS-001','S-004',1.0,'simulated'),('DIS-002','S-004',1.0,'simulated'),('DIS-003','S-001',0.4,'simulated'),('DIS-004','S-005',0.9,'simulated'),('DIS-005','S-003',0.85,'simulated')])
    actions=[('ACT-STAY','stay_primary','No routing change; reassess appointment',1,0),('ACT-ALT','reroute','Evaluate alternate illustrative route',1,15),('ACT-EXP','expedite','Prioritize pickup and dispatch',1,10),('ACT-RES','reschedule','Request a new receiving appointment',1,30),('ACT-SWAP','reassign','Consider another available truck and driver',1,25)]
    conn.executemany('INSERT INTO scenario_actions VALUES (?,?,?,?,?)',actions)
    cost=[('C-MI','variable_vehicle',2.7,'USD/mile','v0.1 engine constant','illustrative'),('C-HR','driver_time',28,'USD/hour','v0.1 engine constant','illustrative'),('C-LATE','lateness',1.5,'USD/minute late','v0.1 engine constant','illustrative'),('C-EXP','expedite',90,'USD/shipment','v0.1 engine constant','illustrative'),('C-APPT','missed_appointment',125,'USD/event','v0.2 planning assumption (not used by v0.1)','illustrative'),('C-FUEL','diesel',4.1,'USD/gallon','v0.2 planning assumption (not used by v0.1)','illustrative')]
    conn.executemany('INSERT INTO cost_parameters VALUES (?,?,?,?,?,?)',cost)
    emissions=[('E-MILE','diesel_truck',1.65,'kg CO2/mile','v0.1 engine constant','illustrative'),('E-IDLE','diesel_truck',0.09,'kg CO2/min added','v0.1 engine constant','illustrative'),('E-FUEL','diesel_truck',10.21,'kg CO2/gallon','v0.2 planning assumption (not used by v0.1)','illustrative')]
    conn.executemany('INSERT INTO emission_parameters VALUES (?,?,?,?,?,?)',emissions)
    zones=[('ZONE-CAR','Carson community proxy',33.831,-118.273,4,'school vicinity (hypothetical)','synthetic'),('ZONE-COM','Commerce community proxy',34.004,-118.161,4,'residential vicinity (hypothetical)','synthetic'),('ZONE-ONT','Ontario community proxy',34.063,-117.647,3,'residential vicinity (hypothetical)','synthetic'),('ZONE-RIV','Riverside community proxy',33.953,-117.393,3,'community center vicinity (hypothetical)','synthetic'),('ZONE-FON','Fontana community proxy',34.097,-117.436,4,'school vicinity (hypothetical)','synthetic')]
    conn.executemany('INSERT INTO community_zones VALUES (?,?,?,?,?,?,?)',zones)
    conn.executemany('INSERT INTO segment_community_exposure VALUES (?,?,?)',[('S-001','ZONE-CAR',0.8),('S-003','ZONE-COM',0.9),('S-004','ZONE-ONT',0.6),('S-005','ZONE-RIV',0.7),('S-006','ZONE-FON',0.7),('S-007','ZONE-CAR',0.9),('S-008','ZONE-ONT',0.5),('S-009','ZONE-ONT',0.8),('S-010','ZONE-RIV',0.9),('S-011','ZONE-FON',0.8),('S-012','ZONE-COM',1.0),('S-013','ZONE-ONT',0.6)])
    deps=[]
    def add(up,uid,down,did,typ,criticality,note):
        deps.append((f'DEP-{len(deps)+1:04d}',up,uid,down,did,typ,criticality,note))
    for shipment_id,orig,dest,truck in conn.execute('SELECT id,origin_id,destination_id,truck_id FROM shipments'):
        add('facility',orig,'shipment',shipment_id,'origin_readiness',5,'Cargo must be released')
        add('facility',dest,'shipment',shipment_id,'receiving_capacity',5,'Receiving slot must be available')
        add('truck',truck,'shipment',shipment_id,'vehicle_assignment',5,'Shared truck assignment not resolved in v0.1')
        add('driver',f'DRIVER-{int(truck[-2:]):02}','shipment',shipment_id,'operator_assignment',5,'Driver hours not enforced in v0.1')
        add('route',shipment_id+'-primary','shipment',shipment_id,'planned_path',4,'Primary path schematic')
    for rid,fac,*_ in resources:
        add('resource',rid,'facility',fac,'facility_operability',3,'Resource loss can reduce throughput')
    conn.executemany('INSERT INTO dependencies VALUES (?,?,?,?,?,?,?,?)',deps)
    # A single explicitly fictional example demonstrating approval audit, not a real dispatch decision.
    conn.execute('INSERT INTO decision_audit VALUES (?,?,?,?,?,?,?)',('AUDIT-001','SCN-SLOW','ACT-ALT','PERSON-013','pending_review','Illustrative dispatcher review: compare reliability and emissions before accepting', '2026-11-14T17:00:00Z'))
    conn.commit()
    fk=conn.execute('PRAGMA foreign_key_check').fetchall()
    if fk:raise RuntimeError(f'Foreign key check failed: {fk[:5]}')
    OUT.mkdir(exist_ok=True)
    counts={}
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        rows=conn.execute(f'SELECT * FROM "{name}"')
        fields=[x[0] for x in rows.description]
        content=rows.fetchall()
        with (OUT/f'{name}.csv').open('w',newline='',encoding='utf-8-sig') as f:
            wr=csv.writer(f);wr.writerow(fields);wr.writerows(content)
        counts[name]=len(content)
    (ROOT/'DATA_COUNTS.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
    schema='\n'.join(row[0]+';' for row in conn.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type,name"))+'\n'
    (ROOT/'schema.sql').write_text(schema,encoding='utf-8')
    conn.close()
    print('Created:',DB,'| tables:',len(counts),'| rows:',sum(counts.values()))
    for key,val in counts.items():print(f'{key:30s} {val:4d}')
if __name__=='__main__':main()
