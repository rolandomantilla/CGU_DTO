# ResilienceTwin GeoAI v0.6 — Multi-trip Fleet and Synthetic Road Network

## What changed from v0.5

- `optimizer_v06.py` adds sequential **multi-trip** scheduling: a truck can perform another shipment only after the previous warehouse handoff is complete. Driver time budgets, vehicle eligibility, and remaining modeled receiving-slot capacity are checked.
- All delivery and **empty repositioning** paths are calculated with a shortest-path algorithm over the database's nine-node, thirteen-segment **synthetic** road graph. The selected shortest path can change in a simulated slowdown or closure. Paths are not street-level, validated for heavy freight, or guaranteed to represent the road network.
- Six fixed, reproducible ordering attempts reduce single-pass greedy selection sensitivity. This is a **heuristic**, not an optimal mixed-integer programming solution. v0.5 remains installed as the benchmark.
- `app_v06.py` shows shipment and fleet metrics, comparisons, orange loaded routes and blue empty repositioning, multi-trip schedules, and decision audit tables.
- `test_v06.py` checks invariants including truck non-overlap, warehouse capacity, route existence, closed-segment avoidance, deterministic output and honest reporting of unknown costs for unassigned shipments.
- `scenario_evidence_v06.csv` and `shipment_evidence_v06.csv` are deterministic synthetic demonstration evidence.

## Windows / VS Code start

1. Download the v0.6 ZIP and extract it. Open the **Git-connected** `CGU_DTO_GeoAI` repository in VS Code. Copy the extracted `ResilienceTwin_GeoAI_v0_6` folder into the repository root. Do **not** overwrite the original `engine.py`, `api.py` or any earlier GeoAI version.
2. Open **Terminal → New Terminal** at the repository root:

```powershell
cd ResilienceTwin_GeoAI_v0_6
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe test_v06.py
.\.venv\Scripts\python.exe -m streamlit run app_v06.py --server.port 8504
```

3. Open http://localhost:8504 in a browser. If `No module named streamlit` appears, confirm you used the explicit `.venv\Scripts\python.exe` commands above for both installation and launch.
4. For **all test modules** (v0.1–v0.6), run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -p 'test*.py' -q
```

The included `data/geoai.sqlite` is already populated. You do **not** need to run `seed_data.py`; doing so would rebuild only the oldest tables and lose the newer foundation.

## Safely push to GitHub

At the cloned repository root, first run `git status` and verify that you are working in a real Git repository. Make a development branch (if you do not already have one), e.g. `git switch -c feature/geoai-v06`. Ensure `.gitignore` excludes `.venv/`, `__pycache__/`, and `*.pyc`. Then:

```powershell
git add ResilienceTwin_GeoAI_v0_6
git diff --cached --stat
git commit -m "Add ResilienceTwin GeoAI v0.6 multi-trip scenario planner"
git push -u origin feature/geoai-v06
```

Create a pull request into `main`; do not overwrite the existing earlier versions or force-push.

## Interpretation and boundaries

- **Synthetic only:** All route edges, speeds, delivery windows, drivers, costs and emissions are illustrative test fixtures. Road segments are represented by straight geographic connectors. Neither `freight_allowed` nor a shortest path certifies truck-safe road travel.
- **Scenario types:** A simulated road closure removes its segment from the graph; traffic, fire and flood scenarios add time on an identified segment. No hazard data is independently verified.
- **Not a full legal driver schedule:** `hours_remaining` and `shift_end_min` are limited synthetic budgets, not FMCSA HOS or rest break compliance. The tool does not plan refueling, traffic forecasts, reloading physical containers, or legal rest breaks.
- **Warehouse limits:** `booked` is assumed to be pre-existing outside reservations. A shipment is considered feasible against the remaining slot count only; it is not actually booked.
- **Unassigned shipments:** Financial loss and CO₂ effects of unassigned containers are *unknown*, not $0 or 0 kg. Comparing totals for different delivered counts can mislead.
- **Optimization status:** v0.6 is a multi-start constructive heuristic. It cannot prove global optimality. It should not be directly compared with v0.5 as though both optimize identical models.
- **Human control:** The output is advisory; verify actual port readiness, appointments, traffic, heavy-vehicle routing, driver constraints, safety and community burden before use.

## Demonstration sequence for the class

1. Select **Normal conditions**, severity 0. Capture scheduled deliveries, critical deliveries and simulated cost/CO₂.
2. Change to **Highway slowdown**, 75 minutes. Compare counts, missed opportunities, selected segments and empty-mile changes.
3. Select **Road closure**. Confirm that segment `S-004` is not used on loaded or repositioning paths; describe the alternate synthetic graph path.
4. Compare the four preference policies. Explain trade-offs as policy-dependent, not factual environmental improvements.
5. Show the same truck completing two sequential assignments in the fleet timeline; explain appointment and driver-budget constraints.
6. Export evidence CSV. Conclude with uncertainty, community burden and human review.

## Next technical steps (v0.7)

Acquire/validate OSM or authoritative freight-network edge data for Southern California, geocode terminal gates and warehouse driveways, incorporate truck dimension/weight restrictions, perform controlled map matching and compare source provenance. Replace the multi-start scheduler with a true multi-trip optimization technique (time-expanded MILP or column-generation vehicle routing) and add structured sensitivity analysis.

## OpenAI Scenario assistant

Set `OPENAI_API_KEY` in the environment before starting Streamlit. On macOS
with zsh you can enter the key without displaying it or saving it in your shell history:

```zsh
read -rs 'OPENAI_API_KEY?OpenAI API key: '
export OPENAI_API_KEY
echo
.venv/bin/python -m streamlit run app_v06.py --server.port 8507
```

The assistant uses the OpenAI Responses API with `gpt-4o-mini` by default.
Set `RESILIENCETWIN_OPENAI_MODEL` to override it with a Structured Outputs
compatible model. The API receives your prompt, active settings, and up to five
recent requests. The app validates the returned settings before running the
simulation. Examples include “Close Highway 60 in East LA, reroute, and use
satellite,” followed by “Switch to lowest cost and keep that closure.”
Named highways are limited to the demo corridor mapping. Without an OpenAI
key, the Ollama integration or built-in scenario commands remain available.

[OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
