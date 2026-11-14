"""ResilienceTwin GeoAI v0.6 dashboard: multi-trip synthetic road network."""
import json
import os
from scenario_prompt import DEFAULT, SCENARIOS, interpret
from math import hypot
from functools import lru_cache
from pathlib import Path
import pandas as pd
import streamlit as st
from streamlit.components.v1 import html
from optimizer_v06 import optimize_v06, compare_policies, POLICIES, SyntheticRoadNetwork
from optimizer_v05 import _table, optimize_v05
from decision_engine import DEFAULT_DB

st.set_page_config(page_title='ResilienceTwin GeoAI v0.6',page_icon='🚚',layout='wide')
st.title('ResilienceTwin GeoAI v0.6 | Multi-trip Decision Lab')
st.caption('Research demonstration • Synthetic Southern California road graph • No operational dispatch actions')

with st.sidebar:
    st.page_link('pages/user_guide.py', label='User guide')
    st.header('Scenario assistant')
    model = os.environ.get('RESILIENCETWIN_OLLAMA_MODEL', '').strip()
    api_key = os.environ.get('OPENAI_API_KEY', '').strip()
    openai_model = os.environ.get('RESILIENCETWIN_OPENAI_MODEL', 'gpt-4o-mini').strip() or 'gpt-4o-mini'
    if api_key:
        st.caption(f'OpenAI · {openai_model}')
    else:
        st.caption(f'Local LLM: {model}' if model else 'Built-in commands · set OPENAI_API_KEY to enable OpenAI')
    history = st.session_state.setdefault('scenario_history', [])
    settings = st.session_state.setdefault('scenario_settings', DEFAULT.copy())
    prompt = st.text_area('Describe a scenario', placeholder='Close Highway 60 in East LA, reroute')
    if st.button('Run scenario'):
        try:
            with st.spinner('Interpreting scenario…'):
                settings = interpret(prompt.strip(), settings, model, api_key=api_key,
                                     openai_model=openai_model, history=history)
            st.session_state['scenario_settings'] = settings
            history.append((prompt.strip(), settings['scenario'], settings['policy']))

        except (OSError, ValueError, KeyError, TypeError) as error:
            st.error(f'Could not apply the scenario. {error}')
    st.caption('Examples: “Close Highway 57,” then “Lowest cost” or “Reopen the road.”')
    st.markdown(f"**Active scenario** · {settings['scenario']} · {settings['severity']} min · {settings['policy']}")
    if settings['closure_segment']:
        location = settings.get('closure_location') or 'Specified segment'
        st.caption(f"{location} uses modeled corridor {settings['closure_segment']}. "
                   "The displayed paths are illustrative for this simulated closure.")
    with st.expander('Scenario conversation'):
        for request, name, preference in st.session_state.get('scenario_history', []):
            st.text(f"You: {request}")
            st.write(f"Applied {name} · {preference}")
    st.caption(f"{settings['turnaround']} min turnaround · {settings['max_trips']} trips per truck · {settings['attempts']} orderings")

scenario_label = settings['scenario']
scenario = SCENARIOS[scenario_label]
severity = settings['severity']
policy = settings['policy']
turnaround = settings['turnaround']
max_trips = settings['max_trips']
attempts = settings['attempts']

reference_fuel = next(row['value'] for row in _table(DEFAULT_DB, 'cost_parameters')
                      if row['param_id'] == 'C-FUEL')
with st.sidebar:
    adjust_fuel = st.toggle('Adjust diesel price')
    fuel_price = st.number_input('Diesel price (USD/gal)', min_value=0.0, max_value=30.0,
                                 value=float(reference_fuel), step=0.10, format='%.2f') if adjust_fuel else None
    st.caption(f"Normal baseline uses ${reference_fuel:.2f}/gal. The scenario adjusts trip costs using modeled fuel economy.")

@st.cache_data(show_spinner=False)
def run(scenario,severity,policy,turnaround,max_trips,attempts,closure_segment=None,fuel_price=None):
    return optimize_v06(scenario,severity,policy,turnaround_min=turnaround,max_trips_per_truck=max_trips,attempts=attempts,closure_segment=closure_segment,fuel_price=fuel_price)

try:
    result=run(scenario,severity,policy,turnaround,max_trips,attempts,settings["closure_segment"],fuel_price)
    baseline=run('SCN-NORMAL',0,policy,turnaround,max_trips,attempts)
except Exception as e:
    st.error(f'Scenario engine error: {e}');st.stop()

m=result['metrics'];b=baseline['metrics']
a,c,d,e,f=st.columns(5)
a.metric('Scheduled',f"{m['scheduled']}/{m['shipments']}",f"{m['scheduled']-b['scheduled']:+d} shipments vs baseline")
c.metric('Critical served',m['critical_scheduled'],f"{m['critical_scheduled']-b['critical_scheduled']:+d} shipments vs baseline")
d.metric('Multi-trip trucks', f"{m['trucks_with_multiple_trips']} trucks",
         f"{m['trucks_with_multiple_trips']-b['trucks_with_multiple_trips']:+d} trucks vs baseline")
e.metric('Completed-trip cost',f"${m['scheduled_cost_usd']:,.0f}",
         f"{m['scheduled_cost_usd']-b['scheduled_cost_usd']:+,.0f} USD vs baseline", delta_color='inverse')
f.metric('Est. completed-trip CO₂',f"{m['scheduled_co2_kg']:,.0f} kg",
         f"{m['scheduled_co2_kg']-b['scheduled_co2_kg']:+,.0f} kg CO₂ vs baseline", delta_color='inverse')
st.warning('Only scheduled-trip costs/emissions are counted. Unassigned deliveries have unknown costs and impacts. The algorithm is a multi-start heuristic, not proven globally optimal. Roads are an illustrative graph, not truck-certified routes.')

st.subheader('Normal versus changed scenario')
st.dataframe(pd.DataFrame([{'condition':'Normal',**b},{'condition':scenario_label,**m}]),hide_index=True,use_container_width=True)

st.subheader('Delivery preference trade-offs')
try:
    policies=[run(scenario,severity,p,turnaround,max_trips,attempts,settings["closure_segment"],fuel_price) for p in POLICIES]
    st.dataframe(pd.DataFrame([{'policy':x['policy'],**x['metrics']} for x in policies]),hide_index=True,use_container_width=True)
except Exception as e:st.error(str(e))

st.subheader('Network paths and assigned deliveries')
network=SyntheticRoadNetwork(DEFAULT_DB)
warehouses = [facility for facility in _table(DEFAULT_DB, 'facilities')
              if facility['kind'] == 'warehouse']
warehouse_nodes = {network.facility_nodes.get(facility['id']) for facility in warehouses}
node_rows = [node for node_id, node in network.nodes.items() if node_id not in warehouse_nodes]
selected=[x for x in result['shipments'] if x['status']=='scheduled']
road_paths = json.loads(Path(__file__).with_name('data').joinpath('display_roads.json').read_text())
node_at = {(node['lon'], node['lat']): node_id for node_id, node in network.nodes.items()}


def map_trip_paths(trips, segment_key, coordinate_key):
    paths = []
    for trip in trips:
        for segment, start in zip(trip[segment_key], trip[coordinate_key]):
            coords = road_paths[f'{segment}:{node_at[tuple(start)]}']
            paths.append({'path': coords, 'shipment': trip['shipment_id'], 'truck': trip['truck_id']})
    return paths


recommendations = []
normal_trips = []
changed_shipments = set()
for trip in selected:
    normal = network.path(trip['origin_id'], trip['destination_id'])
    changed = normal['segments'] != trip['route_segments']
    if changed:
        changed_shipments.add(trip['shipment_id'])
        normal_trips.append({**trip, 'route_segments': normal['segments'],
                             'route_coords': normal['coords']})
    recommendations.append({
        'Shipment': trip['shipment_id'], 'From': trip['origin_id'],
        'To': trip['destination_id'], 'Recommended route': ' → '.join(trip['route_segments']),
        'Decision': 'Reroute' if changed else 'Keep normal route',
        'Recommended drive (min)': trip['loaded_minutes'],
        'Normal drive (min)': normal['minutes'],
    })

st.write(f"**{len(changed_shipments)} of {len(selected)} scheduled shipments** have a different "
         "loaded route under this scenario.")
if recommendations:
    with st.expander("Recommended routes by shipment"):
        st.dataframe(pd.DataFrame(recommendations), hide_index=True)
else:
    st.info("No shipments could be scheduled for this scenario.")

loaded = map_trip_paths(selected, 'route_segments', 'route_coords')
for row in loaded:
    row['rerouted'] = row['shipment'] in changed_shipments
empty = map_trip_paths(selected, 'empty_route_segments', 'empty_route_coords')
normal_paths = map_trip_paths(normal_trips, 'route_segments', 'route_coords')
# Spread truck markers over interior road vertices, clear of warehouse markers.
truck_paths = {}
for row in loaded:
    truck_paths.setdefault(row['truck'], []).append(row['path'])
trucks = {}
warehouse_points = [(site['lon'], site['lat']) for site in warehouses]
for index, (truck, paths) in enumerate(sorted(truck_paths.items())):
    ordered = sorted(paths, key=lambda path: -sum(
        hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:])
    ))
    fraction = 0.2 + 0.6 * (index + 1) / (len(truck_paths) + 1)
    for path in ordered:
        candidates = sorted(range(1, len(path) - 1),
                            key=lambda i: abs(i / (len(path) - 1) - fraction))
        occupied = [*warehouse_points, *trucks.values()]
        position = next((path[i] for i in candidates if all(
            hypot(path[i][0] - lon, path[i][1] - lat) >= 0.018
            for lon, lat in occupied
        )), None)
        if position is not None:
            trucks[truck] = position
            break

closure_paths = []
if scenario == 'SCN-CLOSE':
    segment = settings['closure_segment'] or 'S-004'
    edge = network.segments[segment]
    closure_paths = [{
        'path': road_paths[f"{segment}:{edge['from_node_id']}"],
        'label': settings.get('closure_location') or 'Road closure',
        'segment': segment,
    }]
map_data = json.dumps({'basemap': settings.get('basemap', 'streets'), 'nodes': node_rows, 'warehouses': warehouses, 'loaded': loaded, 'normal': normal_paths, 'closures': closure_paths, 'empty': empty, 'trucks': trucks},
                      allow_nan=False).replace('<', '\\u003c')
template = Path(__file__).with_name('arcgis_map_v06.html').read_text(encoding='utf-8')
html(template.replace('__MAP_DATA__', map_data), height=540)
st.caption('Purple marks recommended detours. Turn on Normal routes for rerouted shipments to compare them. Displayed paths follow mapped roads between scenario nodes. The simulation still uses synthetic corridors, mileage and travel times. Truck markers show simulated positions along mapped routes.')

st.subheader('Multi-trip truck timeline')
if selected:
    timeline=pd.DataFrame([{'truck':x['truck_id'],'trip':x['trip_number'],'shipment':x['shipment_id'],
            'reposition start (min)':x['reposition_start_min'],'pickup (min)':x['departure_min'],
            'warehouse arrival (min)':x['arrival_min'],'available again (min)':x['complete_min'],
            'empty miles':x['empty_miles'],'loaded miles':x['loaded_miles']} for x in selected]).sort_values(['truck','trip'])
    st.dataframe(timeline,hide_index=True,use_container_width=True)
    st.download_button('Export truck schedule CSV',timeline.to_csv(index=False),file_name='geoai_v06_schedule.csv',mime='text/csv')
else:st.info('No trips assigned under these constraints.')

st.subheader('Customer outreach')
st.caption('Demo contacts and current modeled delivery impacts. Send notices to the demo outbox.')
contacts = {
    site['id']: {**site, 'email': f"{site['id'].lower()}@example.invalid",
                 'phone': f'(213) 555-{100 + index:04d}'}
    for index, site in enumerate(sorted(warehouses, key=lambda site: site['id']))
}
shipment_details = {row['shipment_id']: row for row in _table(DEFAULT_DB, 'shipment_details')}
receiving_slots = {row['slot_id']: row for row in _table(DEFAULT_DB, 'warehouse_slots')}
baseline_shipments = {row['shipment_id']: row for row in baseline['shipments']}
exceptions = []
for trip in result['shipments']:
    shipment = trip['shipment_id']
    slot_id = shipment_details[shipment]['appointment_slot_id']
    slot = receiving_slots[slot_id]
    if trip['status'] == 'scheduled':
        minutes_late = trip['arrival_min'] - trip['appointment_end_min']
        if minutes_late <= 0:
            continue
        impact = f'{minutes_late} min past appointment end'
        next_step = 'Confirm the revised receiving time with the warehouse.'
    else:
        impact = trip['notes'][0].rstrip('.')
        next_step = (
            'Request another receiving window before quoting an ETA.'
            if 'receiving capacity' in impact.lower()
            else 'Check truck, driver, and route availability, then confirm a receiving window.'
        )
    recovery = trip.get('recovery')
    if recovery:
        next_step = f"Confirm proposed slot {recovery['slot_id']} with the warehouse."
        eta = f"Scenario minute {recovery['arrival_min']} (proposed)"
    elif trip['status'] == 'scheduled':
        eta = f"Scenario minute {trip['arrival_min']}"
    else:
        eta = 'No feasible ETA in modeled windows'
    previous = baseline_shipments[shipment]
    contact = contacts[trip['destination_id']]
    exceptions.append({
        'Shipment': shipment, 'Stop': contact['id'], 'Receiving location': contact['name'],
        'Phone': contact['phone'], 'Email': contact['email'],
        'Original slot': slot_id,
        'Original window (scenario min)': f"{slot['window_start_min']}–{slot['window_end_min']}",
        'Baseline status': previous['status'].capitalize(),
        'Modeled impact': impact, 'Next step': next_step,
        'Revised ETA': eta,
        'Proposed receiving minute': recovery['receiving_min'] if recovery else None,
    })

outbox = st.session_state.setdefault('customer_outbox', {})
if exceptions:
    for row in exceptions:
        row['Contacted stop'] = (row['Stop'], row['Shipment'], scenario, row['Modeled impact'], row['Revised ETA'], row['Next step']) in outbox
    st.dataframe(pd.DataFrame(exceptions), hide_index=True)
    stop = st.selectbox('Prepare a notice for',
                        sorted({row['Stop'] for row in exceptions}),
                        format_func=lambda stop_id: contacts[stop_id]['name'])
    contact = contacts[stop]
    stop_rows = [row for row in exceptions if row['Stop'] == stop]
    st.write(f"**Receiving stop:** {stop} · {contact['name']} · {contact['phone']}")
    st.dataframe(pd.DataFrame(stop_rows), hide_index=True)
    details = '\n'.join(
        f"• {row['Shipment']} · original slot {row['Original slot']} "
        f"(scenario minutes {row['Original window (scenario min)']}) · "
        f"{row['Modeled impact']}. {row['Next step']} Revised ETA: {row['Revised ETA']}."
        for row in stop_rows
    )
    notice = (
        f"To: {contact['email']}\n"
        f"Subject: Delivery update for {contact['name']}\n\n"
        f"Hello {contact['name']} receiving team,\n\n"
        f"We’re reaching out about a possible delivery delay due to the modeled "
        f"{scenario_label.lower()} scenario. Here’s the current shipment update:\n\n"
        f"{details}\n\n"
        "Please let us know which revised delivery windows your team can accommodate. "
        "We’ll follow up once the delivery timing is confirmed.\n\n"
        "ResilienceTwin Dispatch Demo"
    )
    st.text(notice)
    notice_keys = {(stop, row['Shipment'], scenario, row['Modeled impact'], row['Revised ETA'], row['Next step']) for row in stop_rows}
    sent = notice_keys.issubset(outbox)
    if st.button('Send delay email (demo)', disabled=sent):
        for key in notice_keys:
            outbox[key] = notice
        st.rerun()
    if sent:
        st.success('Notice recorded in the demo outbox. These shipments are marked contacted.')
    st.download_button('Download delay notice', notice, file_name=f'{stop}-delay-notice.txt')
else:
    st.info('There are no late or unassigned shipments in this scenario.')

st.subheader('Shipment-level decisions')
show=st.radio('Display',['All','Scheduled','Unassigned'],horizontal=True)
rows=[x for x in result['shipments'] if show=='All' or x['status'].lower()==show.lower()]
view=pd.DataFrame([{k:('; '.join(map(str,v)) if isinstance(v,list) else v) for k,v in r.items()
                    if k not in ('route_coords','empty_route_coords')} for r in rows])
st.dataframe(view,hide_index=True,use_container_width=True)
st.download_button('Export shipment decisions CSV',view.to_csv(index=False),file_name='geoai_v06_decisions.csv',mime='text/csv')
with st.expander('Unassigned reasons, modeling boundaries, and human oversight'):
    st.json({'solver':result['solver'],'unassigned_reasons':result['unassigned_reasons']})
    for a in result['assumptions']:st.write('• '+a)
st.info('Dispatcher must verify real roads/truck restrictions, legal driver hours, terminal availability, and warehouse appointments before any real action. No dispatch or booking operation is performed.')
