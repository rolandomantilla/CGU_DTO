"""Optional v0.3 UI. Does not alter original app.py."""
import pandas as pd
import streamlit as st
from decision_engine import compare, load, ACTIONS

st.set_page_config(page_title='ResilienceTwin GeoAI v0.3',layout='wide',page_icon='🌎')
st.title('ResilienceTwin GeoAI · v0.3 decision lab')
st.caption('Experimental, synthetic, human-reviewed scenario intelligence. No real-world routing or dispatch commands.')
d=load();scenarios={s['name']:s for s in d['scenario_definitions']}
with st.sidebar:
    name=st.selectbox('Disruption scenario',list(scenarios),index=1)
    sc=scenarios[name]
    severity=st.slider('Modeled severity (minutes)',0,300,int(sc['severity_min']),5)
    action=st.radio('Candidate response',ACTIONS)
base,options=compare(sc['scenario_id'],severity)
selected=next(x for x in options if x['action']==action)
m=selected['metrics']; b=base['metrics']
cols=st.columns(5)
for col,label,key,format_ in zip(cols,['Shipments at risk','Missed original appointments','Est. total cost','Est. CO₂','Flagged shipments'],['at_risk','missed_original_appointments','cost_usd','co2_kg','flagged_shipments'],['{:,.0f}','{:,.0f}','${:,.0f}','{:,.0f} kg','{:,.0f}']):
    col.metric(label,format_.format(m[key]),delta=f'{m[key]-b[key]:+,.0f} vs baseline',delta_color='inverse')
st.subheader('Compare intervention options')
frame=pd.DataFrame([{'Response':'Normal baseline' if x is base else x['action'],**x['metrics']} for x in [base]+options])
st.dataframe(frame,hide_index=True,use_container_width=True)
st.info('Comparisons show modeled outcomes, not validated feasible dispatch plans. A lower number of at-risk shipments may still require truck, driver, warehouse, and environmental review.')
st.subheader('Affected shipments and feasibility flags')
r=pd.DataFrame([{**{k:v for k,v in x.items() if k!='warnings'},'warnings':'; '.join(x['warnings'])} for x in selected['shipments']])
only=st.checkbox('Show only affected, late, or flagged shipments',value=True)
if only:r=r[(r.affected)|(r.late_min>0)|(r.warnings!='')]
st.dataframe(r,hide_index=True,use_container_width=True)
st.download_button('Export results CSV',r.to_csv(index=False),file_name='geoai_v03_decision_evidence.csv')
st.subheader('Dispatcher decision and responsible design')
st.write('**No action is executed or committed.** Review identified truck overlaps, driver-time risks, modeled road closures, unconfirmed new appointments, and possible community burden before selecting a candidate.')
for warning in selected['cautions']:st.caption('• '+warning)
st.write('**Methods:** Route segment exposure identifies affected primary paths; illustrative scenario minutes affect travel or pickup; alternative routes are checked against the modeled affected segment; truck-time overlap, driver budget, maintenance, and slot availability are flagged. Costs/emissions follow the synthetic parameters in SQLite.')
