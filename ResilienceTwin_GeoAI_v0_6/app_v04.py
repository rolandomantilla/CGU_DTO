"""GeoAI v0.4 prototype: capacity-aware candidate dispatch scheduling."""
import json
from pathlib import Path
import pandas as pd
import pydeck as pdk
import streamlit as st
from decision_engine import load
from optimizer_v04 import optimize, STRATEGIES

st.set_page_config(page_title='ResilienceTwin GeoAI v0.4',page_icon='🚛',layout='wide')
st.title('ResilienceTwin GeoAI · v0.4')
st.caption('Time-aware, synthetic dispatch feasibility demonstrator — not a live dispatch tool or regulatory HOS solver.')
data=load()
scenarios={x['name']:x for x in data['scenario_definitions']}
with st.sidebar:
    st.header('Scenario controls')
    name=st.selectbox('Disruption',list(scenarios),index=1)
    scenario=scenarios[name]
    severity=st.slider('Disruption duration (minutes)',0,300,int(scenario['severity_min']),5)
    strategy=st.selectbox('Candidate scheduling approach',STRATEGIES,index=1)
    turn=st.slider('Receiving/turnaround service time (minutes)',0,90,25,5)
    reposition=st.slider('Empty-mile distance multiplier',1.0,2.5,1.3,0.1)
    st.caption('All inputs are simulated; no real shipments are changed.')

@st.cache_data(show_spinner=False)
def compute(scenario_id, severity, strategy, turn, reposition):
    return optimize(scenario_id,severity,strategy,turnaround_min=turn,reposition_factor=reposition)

result=compute(scenario['scenario_id'],severity,strategy,turn,reposition)
baseline=compute('SCN-NORMAL',0,strategy,turn,reposition)
m=result['metrics'];b=baseline['metrics']
a,b_,c,d,e=st.columns(5)
a.metric('Scheduled / 40',f"{m['scheduled']} / {m['shipments']}",f"{m['scheduled']-b['scheduled']:+d} vs baseline")
b_.metric('Unassigned',m['unassigned'],f"{m['unassigned']-b['unassigned']:+d} vs baseline",delta_color='inverse')
c.metric('Scheduled trips: cost',f"${m['scheduled_cost_usd']:,.0f}")
d.metric('Scheduled trips: CO₂',f"{m['scheduled_co2_kg']:,.0f} kg")
e.metric('Empty repositioning',f"{m['scheduled_empty_miles']:,.0f} mi")
st.warning('Cost, mileage and emissions include **scheduled shipments only**. Lower totals may reflect more unassigned shipments, not higher efficiency. No cost/emissions values are assigned to undelivered shipments.')

st.subheader('Compare scenarios and candidate policies')
rows=[]
for scid,severity_ in [('SCN-NORMAL',0),(scenario['scenario_id'],severity)]:
    for policy in STRATEGIES:
        q=compute(scid,severity_,policy,turn,reposition)
        rows.append({'condition':'Normal baseline' if scid=='SCN-NORMAL' else 'Changed scenario',
                     'policy':policy,**q['metrics']})
st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)

st.subheader('Geographic view — synthetic paths')
locations=[dict(x) for x in data['facilities']] if 'facilities' in data else []
if not locations:
    import sqlite3
    con=sqlite3.connect(Path(__file__).parent/'data'/'geoai.sqlite');con.row_factory=sqlite3.Row
    locations=[dict(x) for x in con.execute('select * from facilities')];con.close()
assigned=[x for x in result['shipments'] if x['status']=='scheduled' and len(x['route_coords'])>=2]
line_data=[{'path':[[lon,lat] for lon,lat in x['route_coords']], 'shipment':x['shipment_id'], 'route':x['route']} for x in assigned]
facility_data=[{'name':x['name'],'kind':x['kind'],'lat':x['lat'],'lon':x['lon']} for x in locations]
layers=[pdk.Layer('ScatterplotLayer',facility_data,get_position='[lon, lat]',get_radius=4500,
                  get_fill_color='[30, 130, 190, 190]',pickable=True),
        pdk.Layer('PathLayer',line_data,get_path='path',get_width=2800,
                  get_color='[230, 120, 30, 160]',pickable=True)]
st.pydeck_chart(pdk.Deck(layers=layers,initial_view_state=pdk.ViewState(latitude=33.93,longitude=-117.99,zoom=8.1,pitch=0),
                       tooltip={'html':'<b>{name}{shipment}</b><br>{kind}{route}'}))
st.caption('Route coordinates are illustrative synthetic paths. Empty repositioning is budgeted but not plotted as validated road geometry.')

st.subheader('Dispatch decision evidence')
show=st.radio('Shipment records',['Unassigned only','Scheduled only','All'],horizontal=True)
recs=[x for x in result['shipments'] if show=='All' or x['status']==('unassigned' if show=='Unassigned only' else 'scheduled')]
df=pd.DataFrame([{k:('; '.join(v) if k=='notes' else v) for k,v in x.items() if k!='route_coords'} for x in recs])
st.dataframe(df,use_container_width=True,hide_index=True)
st.download_button('Download scenario evidence CSV',df.to_csv(index=False).encode(),file_name='geoai_v04_dispatch_evidence.csv',mime='text/csv')
st.subheader('Model limitations and human oversight')
for warning in result['assumptions']:st.caption('• '+warning)
st.info('Recommendation is advisory. A human dispatcher must validate truck routing, shipment readiness, approved appointment slots, vehicle suitability, labor constraints, and community impacts before any action.')
