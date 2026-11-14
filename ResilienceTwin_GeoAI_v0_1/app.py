"""Interactive Streamlit front end for ResilienceTwin GeoAI."""
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
from streamlit.components.v1 import html
from engine import compare, SCENARIOS, STRATEGIES
from road_routes import map_routes

st.set_page_config(page_title='ResilienceTwin GeoAI',layout='wide',page_icon='🌎')
st.title('ResilienceTwin GeoAI')
st.caption('Synthetic Southern California port-to-warehouse resilience, cost and sustainability digital twin | DEMONSTRATION ONLY')
with st.sidebar:
    st.header('Scenario controls')
    scenario=st.selectbox('Disruption',list(SCENARIOS),index=1)
    delay=st.slider('Disruption severity (minutes)',0,240,SCENARIOS[scenario]['delay'],15)
    strategy=st.radio('Dispatcher response',STRATEGIES)
    st.info('Scenario delays, costs, emissions and exposure scores use modeled assumptions.')
base, options=compare(scenario,delay)
selected=next(x for x in options if x['strategy']==strategy)
m=selected['metrics']; b=base['metrics']
cols=st.columns(5)
for col,headline,key,fmt in zip(cols,['On-time delivery','At-risk shipments','Transportation cost','CO₂ estimate','Total mileage'],['on_time_pct','at_risk','cost_usd','co2_kg','total_miles'],['{:.1f}%','{:,.0f}','${:,.0f}','{:,.0f} kg','{:,.1f} mi']):
    col.metric(headline,fmt.format(m[key]),delta=round(m[key]-b[key],1),delta_color='normal' if key=='on_time_pct' else 'inverse')
st.subheader('Compare alternatives against normal operations')
rows=[]
for result in [base]+options:
    q=result['metrics']; rows.append({'Response':'Normal baseline' if result is base else result['strategy'],'At-risk shipments':q['at_risk'],'On-time %':q['on_time_pct'],'Cost ($)':q['cost_usd'],'Mileage (mi)':q['total_miles'],'CO₂ (kg, est.)':q['co2_kg'],'Community exposure (proxy)':q['community_exposure_index']})
st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
st.caption('Community exposure is an illustrative 1–5 route proxy and cannot establish actual pollution burdens, demographic equity, or environmental justice impacts.')
left,right=st.columns([1.4,1])
with left:
    st.subheader('ArcGIS network map')
    routes, missing = map_routes(selected['facilities'], selected['shipments'])
    map_data = {
        'facilities': selected['facilities'],
        'routes': routes,
        'trafficKey': os.environ.get('ARCGIS_TRAFFIC_API_KEY', '').strip(),
    }
    embedded_data = json.dumps(map_data, allow_nan=False).replace('<', '\\u003c')
    template = Path(__file__).with_name('arcgis_map.html').read_text(encoding='utf-8')
    html(template.replace('__MAP_DATA__', embedded_data), height=550, scrolling=False)
    if missing:
        st.warning(f'Road geometry is unavailable for {missing} shipment(s).')
    st.caption(
        'Caltrans markers show reported active closures in the Los Angeles, Inland Empire, '
        'and Orange County districts. Road paths use an OpenStreetMap driving profile. '
        'Shipment times, costs, emissions, and late counts are modeled separately. '
        'Road paths are not verified for truck restrictions or current closures.'
    )
with right:
    st.subheader('Interpretation and human review')
    st.write(f"The selected response has **{m['at_risk']} of {m['shipments']} shipments at risk** versus **{b['at_risk']}** under normal conditions.")
    st.write(f"Modeled cost difference: **${m['cost_usd']-b['cost_usd']:,.0f}**; estimated emissions difference: **{m['co2_kg']-b['co2_kg']:,.1f} kg CO₂**.")
    st.warning('No response is automatically executed. Dispatcher approval is required, and changes to driver workload, receiving capacity, community exposure and network feasibility need verification.')
    st.write('**Uncertainty:** Simplified travel time, deterministic disruption impact, synthetic community score and illustrative emissions factor. The scenario assumes no capacity constraints.')
st.subheader('Shipments and exceptions')
df=pd.DataFrame(selected['shipments']).drop(columns=['route_points'])
st.dataframe(df,hide_index=True,use_container_width=True)
st.download_button('Export selected scenario results (CSV)',df.to_csv(index=False).encode(),file_name='geoai_scenario_results.csv',mime='text/csv')
