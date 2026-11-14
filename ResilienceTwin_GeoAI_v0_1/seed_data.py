"""Build reproducible demonstration database. All logistics records are fictional."""
import json, random, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/'data'/'geoai.sqlite'
FACILITIES=[('PORT-LA','Port of Los Angeles','port',33.732,-118.269,0),('PORT-LB','Port of Long Beach','port',33.754,-118.216,0),('WH-ONT','Ontario Distribution Center','warehouse',34.064,-117.651,10),('WH-RIV','Riverside Distribution Center','warehouse',33.953,-117.396,8),('WH-CAR','Carson Distribution Center','warehouse',33.832,-118.281,7),('WH-COM','Commerce Distribution Center','warehouse',34.002,-118.159,6),('WH-FON','Fontana Distribution Center','warehouse',34.097,-117.435,9)]

def main():
    random.seed(42); DB.parent.mkdir(exist_ok=True)
    if DB.exists():DB.unlink()
    c=sqlite3.connect(DB)
    c.executescript('''
    CREATE TABLE facilities(id TEXT PRIMARY KEY,name TEXT,kind TEXT,lat REAL,lon REAL,daily_capacity INTEGER);
    CREATE TABLE trucks(id TEXT PRIMARY KEY,capacity_teu INTEGER,status TEXT,base_port_id TEXT REFERENCES facilities(id));
    CREATE TABLE drivers(id TEXT PRIMARY KEY,truck_id TEXT REFERENCES trucks(id),shift_limit_hours REAL,assigned_workload_hours REAL);
    CREATE TABLE shipments(id TEXT PRIMARY KEY,origin_id TEXT REFERENCES facilities(id),destination_id TEXT REFERENCES facilities(id),truck_id TEXT REFERENCES trucks(id),pickup_ready_min INTEGER,appointment_end_min INTEGER,weight_tons REAL,exposed INTEGER);
    CREATE TABLE routes(id TEXT PRIMARY KEY,shipment_id TEXT REFERENCES shipments(id),variant TEXT,distance_mi REAL,travel_min INTEGER,community_exposure_index INTEGER,geojson_points TEXT, UNIQUE(shipment_id,variant));
    CREATE TABLE disruptions(id TEXT PRIMARY KEY,kind TEXT,description TEXT,delay_min INTEGER,confidence TEXT);
    ''')
    c.executemany('INSERT INTO facilities VALUES(?,?,?,?,?,?)',FACILITIES)
    c.executemany('INSERT INTO trucks VALUES(?,?,?,?)',[(f'TRUCK-{i:02}',2,'available','PORT-LA' if i%2 else 'PORT-LB') for i in range(1,13)])
    c.executemany('INSERT INTO drivers VALUES(?,?,?,?)',[(f'DRIVER-{i:02}',f'TRUCK-{i:02}',10.0,round(4+random.random()*3,1)) for i in range(1,13)])
    dests=FACILITIES[2:]
    for i in range(1,41):
        sid=f'SHP-{i:03}'; port=FACILITIES[(i-1)%2]; wh=dests[(i-1)%5]
        ready=random.choice([0,25,45,60,90]); baseline=random.randint(52,105)
        appt=ready+baseline+random.randint(20,95)
        exposed=int(wh[0] in ('WH-ONT','WH-RIV','WH-FON'))
        c.execute('INSERT INTO shipments VALUES(?,?,?,?,?,?,?,?)',(sid,port[0],wh[0],f'TRUCK-{((i-1)%12)+1:02}',ready,appt,round(random.uniform(8,22),1),exposed))
        dx=(wh[4]-port[4])*53; dy=(wh[3]-port[3])*69
        straight=(dx*dx+dy*dy)**0.5
        miles=round(max(12,straight*1.24),1)
        def points(offset):
            return [[port[4],port[3]],[(port[4]+wh[4])/2+offset,(port[3]+wh[3])/2+offset*.38],[wh[4],wh[3]]]
        variants=[('primary',miles,baseline,2,points(.04)),('alternate',round(miles*1.23,1),baseline+23,4,points(-.065))]
        for variant,dist,travel,exposure,path in variants:
            c.execute('INSERT INTO routes VALUES(?,?,?,?,?,?,?)',(sid+'-'+variant,sid,variant,dist,travel,exposure,json.dumps(path)))
    c.executemany('INSERT INTO disruptions VALUES(?,?,?,?,?)',[
        ('DIS-001','slowdown','Illustrative freeway slowdown',75,'simulated'),('DIS-002','closure','Illustrative highway closure',150,'simulated'),
        ('DIS-003','pickup','Illustrative pickup delay',90,'simulated'),('DIS-004','wildfire','Illustrative wildfire-related route disruption',110,'simulated'),
        ('DIS-005','flood','Illustrative flood-related route disruption',120,'simulated')])
    c.commit(); c.close(); print('Created',DB)
if __name__=='__main__':main()
