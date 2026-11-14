# ResilienceTwin GeoAI v0.1

Prototype for the **Resilience, Cost, and Sustainability Intelligence** perspective in the GeoAI Track assignment.

## Windows / VS Code quick start

1. Extract this ZIP into its **own folder**, not directly over the existing `CGU_DTO` repository.
2. Open the extracted folder in VS Code: **File > Open Folder**.
3. Open **Terminal > New Terminal**, then run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe seed_data.py
.\.venv\Scripts\python.exe engine.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

If `py` is not installed, use `python` on the first command.

Streamlit will print the localhost address to open in your browser (usually http://localhost:8501).

## ArcGIS map

The app opens in **2D streets**. Use **3D city** for building context and **Focus**
to jump to downtown Los Angeles, Long Beach, or Ontario. The map uses the ArcGIS
Maps SDK for JavaScript and needs an internet connection. 3D also needs browser WebGL support.

**Caltrans closures** shows active highway closures from districts 7, 8 and 12.
The app checks the public feeds every five minutes and uses a point at the
reported start of each closure. [Caltrans Lane Closure System](https://cwwp2.dot.ca.gov/lane-closure.html)

To enable **Esri traffic speeds**, set `ARCGIS_TRAFFIC_API_KEY` in the Terminal
that starts Streamlit, using a browser API key authorized for Esri World Traffic.
If the key uses referrer restrictions, allow the exact local app origin, for
example `http://127.0.0.1:8502`. The browser uses the key for the traffic layer.
Zoom in to see coverage on supported roads.
[Esri traffic sample](https://developers.arcgis.com/javascript/latest/sample-code/time-layer/)

The dashboard uses cached road-network geometry for the bundled port-to-warehouse
pairs. Paths were calculated by [FOSSGIS OSRM](https://routing.openstreetmap.de/about.html)
with its OpenStreetMap car profile, which snaps facility coordinates to nearby
roads. The map uses a distinct road-network alternate where one was returned.
The cached routes do not account for live traffic, closures, or truck restrictions.
Traffic overlays provide context, while the scenario engine still supplies modeled
ETAs, costs, and emissions.

## Contents
- `seed_data.py`: generates `data/geoai.sqlite` with 2 ports, 5 warehouses, 40 shipments, 12 trucks/drivers, 80 route variants and 5 disruptions.
- `engine.py`: deterministic scenario calculation and comparison. Standard library only.
- `app.py`: map, adjustable disruption, alternative response table, KPIs, delivery exceptions and CSV export.
- `tests.py`: regression checks.
- `data/geoai.sqlite`: synthetic demo database generated for convenience.

## Responsible design
- **Environmental responsibility:** report estimated mileage and CO2 for response options; do not claim observed emissions.
- **Fairness/stakeholder impacts:** show a community-exposure proxy, caution that diversion could shift burdens, and flag need to assess drivers, warehouses, schools and nearby residents before deployment.
- **Transparency:** explicitly label simulation inputs, assumptions and limitations.
- **Human oversight:** user compares strategies and chooses one; no dispatch action is taken.

## Model caveats
This is an educational digital twin prototype, not an operational planning system. Scenario mileage and travel times are illustrative. The 1.65 kg/mile CO2 multiplier and cost factors are **illustrative assumptions** and not official calibrated emission or tariff rates. The initial model does not enforce fleet assignment conflicts, driver hours, receiving slot capacity or realistic multimodal routing. Future versions should connect a real network analysis engine and validated emission factors, then add a grounded AI explanation layer.

## Existing CGU_DTO code
The published repository targets a different domain (organizational/personnel resilience), and its API and database schema are not directly compatible. Keep this as a **separate module** until repository integration is planned and tested. Do not replace or overwrite the existing `resiliencetwin.sqlite`.

## Submission evidence
The bundled `scenario_evidence.csv` records a reproducible **normal** baseline and a **75-minute synthetic highway slowdown**, including modeled response alternatives. `PROJECT_ROADMAP.md` details the next improvements needed for more realistic routing and feasible scheduling.
