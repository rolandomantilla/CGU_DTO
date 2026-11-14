"""ResilienceTwin GeoAI v0.5 — mixed-integer dispatch scenario lab."""
import json
import pandas as pd
import pydeck as pdk
import streamlit as st
from decision_engine import load
from optimizer_v05 import optimize_v05, compare_policies, POLICIES, build_candidates
from optimizer_v04 import optimize as greedy_optimize

st.set_page_config(page_title='ResilienceTwin GeoAI v0.5',page_icon='🚛',layout='wide')
st.title('ResilienceTwin GeoAI · v0.5')
st.caption('Synthetic, advisory dispatch optimization | Mathematical MILP over one-trip candidate assignments | No live dispatch or truck-approved routing')
data=load()
scenarios={x['name']:x for x in data['scenario_definitions']}
with st.sidebar:
    st.header('Disruption & preference')
    index=next((i for i,s in enumerate(scenarios.values()) if s['scenario_id']=='SCN-SLOW'),0)
    scname=st.selectbox('Scenario',list(scenarios),index=index)
    scenario=scenarios[scname]
    severity=st.slider('Disruption duration, minutes',0,300,int(scenario['severity_min']),5)
    policy=st.selectbox('After maximizing priority and completed deliveries',POLICIES,index=3)
    reposition=st.slider('Synthetic empty-mile multiplier',1.0,2.5,1.3,.1)
    turnaround=st.slider('Receiving service minutes',0,90,25,5)
    st.caption('Priority-weighted service first, shipment count second; policy breaks remaining ties.')

@st.cache_data(show_spinner=False)
def run(scenario_id, minutes, preference, factor, turn):
    return optimize_v05(scenario_id,minutes,preference,reposition_factor=factor,turnaround_min=turn)

with st.spinner('Solving feasibility and policy comparison...'):
    result=run(scenario['scenario_id'],severity,policy,reposition,turnaround)
    baseline=run('SCN-NORMAL',0,policy,reposition,turnaround)
    policies=[run(scenario['scenario_id'],severity,p,reposition,turnaround) for p in POLICIES]

m=result['metrics'];base=baseline['metrics']
a,b,c,d,e=st.columns(5)
a.metric('Scheduled',f"{m['scheduled']} / {m['shipments']}",f"{m['scheduled']-base['scheduled']:+d} vs normal")
b.metric('Priority score',m['priority_service_score'],f"{m['priority_service_score']-base['priority_service_score']:+d} vs normal")
c.metric('Critical shipments',m['critical_scheduled'])
d.metric('Scheduled-trip cost',f"${m['scheduled_cost_usd']:,.0f}")
e.metric('Scheduled-trip CO₂',f"{m['scheduled_co2_kg']:,.0f} kg")
if result['solver']['provably_optimal']:
    st.success('MILP stages solved to reported optimality under the restricted, synthetic one-trip model. This does NOT prove network-wide dispatch optimality.')
else:
    st.warning('At least one solver stage did not establish mathematical optimality. Review solver diagnostics.')
st.warning('Unassigned shipment costs and impacts are unknown, not zero. Scheduled-trip totals must always be interpreted beside delivery coverage. Real truck access and HOS are unverified.')

st.subheader('Normal vs disruption — same policy and constraints')
compare_df=pd.DataFrame([{'condition':'Normal baseline',**baseline['metrics']},{'condition':'Changed scenario',**m}])
st.dataframe(compare_df,use_container_width=True,hide_index=True)

st.subheader('Policy trade-offs — delivery reliability is the primary objective')
policy_df=pd.DataFrame([{'policy':r['policy'],**r['metrics']} for r in policies])
st.dataframe(policy_df,use_container_width=True,hide_index=True)
st.caption('The model first maximizes priority service score (critical=5, high=3, routine=1), then number delivered. Cost, CO₂, or relative-weighted balanced preference only chooses among tied service outcomes.')

st.subheader('Comparison with v0.4 greedy scheduler')
greedy=greedy_optimize(scenario=scenario['scenario_id'],severity=severity,strategy='Allow alternate',reposition_factor=reposition,turnaround_min=turnaround)
st.dataframe(pd.DataFrame([
    {'model':'v0.4 greedy, multi-trip','scheduled':greedy['metrics']['scheduled'],'scheduled cost':greedy['metrics']['scheduled_cost_usd'],'scheduled CO₂':greedy['metrics']['scheduled_co2_kg']},
    {'model':'v0.5 MILP, single trip/truck','scheduled':m['scheduled'],'scheduled cost':m['scheduled_cost_usd'],'scheduled CO₂':m['scheduled_co2_kg']}
]),hide_index=True,use_container_width=True)
st.info('This is a diagnostic comparison, NOT a head-to-head optimizer victory: v0.4 permits sequential trips per truck, while v0.5 conservatively permits only one. Do not compare objectives as if they had identical feasible sets.')

st.subheader('Scheduled route geometry (synthetic)')
with st.container():
    locs=[dict(x) for x in __import__('optimizer_v05')._table(__import__('decision_engine').DEFAULT_DB,'facilities')]
    assigned=[x for x in result['shipments'] if x['status']=='scheduled']
    route_data=[{'path':x['route_coords'],'id':x['shipment_id'],'route':x['route']} for x in assigned]
    facility_data=[{'name':x['name'],'type':x['kind'],'lat':x['lat'],'lon':x['lon']} for x in locs]
    st.pydeck_chart(pdk.Deck(layers=[
       pdk.Layer('PathLayer',route_data,get_path='path',get_width=2300,get_color='[230,132,40,190]',pickable=True),
       pdk.Layer('ScatterplotLayer',facility_data,get_position='[lon,lat]',get_radius=4000,get_fill_color='[27,125,188,200]',pickable=True)],
       initial_view_state=pdk.ViewState(latitude=33.92,longitude=-117.98,zoom=8),tooltip={'text':'{name}{id} {route}'}))
    st.caption('Map paths are synthetic straight-line-style polylines, not verified truck-approved road geometry. Empty repositioning is estimated and not drawn.')

st.subheader('Shipment-level rationale and human review')
selection=st.radio('Show',['All shipments','Scheduled only','Unassigned only'],horizontal=True)
recs=[x for x in result['shipments'] if selection=='All shipments' or x['status']==('scheduled' if selection=='Scheduled only' else 'unassigned')]
frame=pd.DataFrame([{k:('; '.join(v) if isinstance(v,list) else json.dumps(v) if isinstance(v,dict) else v) for k,v in x.items() if k!='route_coords'} for x in recs])
st.dataframe(frame,use_container_width=True,hide_index=True)
st.download_button('Export evidence CSV',frame.to_csv(index=False).encode(),file_name='geoai_v05_dispatch.csv',mime='text/csv')
with st.expander('Solver diagnostics, exclusions, assumptions'):
    st.json({'solver':result['solver'],'candidate_count':result['candidate_count'],'excluded_candidate_reasons':result['exclusions']})
    for a in result['assumptions']:st.caption('• '+a)
st.info('Human oversight required: validate actual terminal readiness, driver legal HOS, truck suitability, truck-safe roads, approved warehouse appointments, and community impacts before dispatch. No operational action is executed by this app.')
