"""In-app operating guide for ResilienceTwin."""
import streamlit as st

st.title("User guide")
st.page_link("app_v06.py", label="Back to dashboard")
st.markdown("""
### 1. Run a scenario

In **Scenario assistant**, enter **Close Highway 60 in East LA, reroute** and
select **Run scenario**. Check **Active scenario** to see what the app applied.
Enter **Lowest cost** to change the dispatch preference while keeping the closure.
Enter **Reopen the road** to return to normal conditions.

### 2. Compare costs and routes

Read the KPI cards and **Normal versus changed scenario** table. Turn on
**Adjust diesel price** and enter a price in USD per gallon to test fuel costs.

In **Network paths and assigned deliveries**, use **Basemap** to switch views.
Orange lines show recommended loaded routes, purple shows detours, dashed blue
shows empty repositioning, and red shows a simulated closure. Turn on
**Normal routes for rerouted shipments** to compare paths.

### 3. Review revised ETAs and prepare a notice

Open **Customer outreach** and select a receiving stop. Review its affected
shipments, modeled impacts, and proposed receiving slots. ETA values are in
minutes from the start of the scenario. Proposed slots require warehouse
confirmation. **No feasible ETA in modeled windows** means the model found
no workable later slot for that shipment.

Select **Send delay email (demo)** to record the notice in the demo outbox
and mark those shipments as contacted. Use **Download delay notice** to
save a copy.

### 4. Export the plan

Use the CSV buttons under **Multi-trip truck timeline** and
**Shipment-level decisions** to export the current results.
""")
