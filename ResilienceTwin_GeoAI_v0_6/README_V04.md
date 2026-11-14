# ResilienceTwin GeoAI v0.4 — Capacity-Aware Scheduling Prototype

## Milestone
Extends v0.3 with a *conservative* time-aware dispatch candidate scheduler. No original v0.3 entrypoints have been overwritten: `app_v03.py`, `decision_engine.py`, `app.py`, and `engine.py` are retained. New files are `optimizer_v04.py`, `app_v04.py`, `test_v04.py`, and `scenario_evidence_v04.csv`.

### Features
- Uses 40 synthetic shipments, 12 trucks/drivers, original warehouse slots, modeled route segments, vehicle maintenance, synthetic time budgets, shift endings, and truck cargo capacity.
- Allows policy comparison: primary only, alternate allowed, cost priority, and emissions priority. **Greedy heuristic**, not mathematical/global optimum.
- Models sequential truck assignment. An assigned truck cannot overlap another trip; empty repositioning between facilities and a turnaround period contribute to consumed time.
- Rejects routes marked non-freight-allowed and closes any route crossing the affected segment during modeled closures.
- Prevents overbooking according to the synthetic `warehouse_slots` remaining capacity. Existing `booked` counts treated as external committed reservations because their provenance is unclear.
- Returns explicit **unassigned** shipments instead of silently promising dispatches or automatically moving appointment windows.
- Includes original-appointment feasibility, scheduled-only costs and CO₂, empty mileage, shipment-level decision evidence, and an illustrative map.

## Run in VS Code on Windows
Open the extracted **ResilienceTwin_GeoAI_v0_4** folder, or its folder inside your Git clone. In VS Code, open **Terminal > New Terminal**:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe test_v04.py
.\.venv\Scripts\python.exe test_v03.py
.\.venv\Scripts\python.exe tests.py
.\.venv\Scripts\python.exe -m streamlit run app_v04.py --server.port 8502
```
Open http://localhost:8502. If 8502 is in use, choose a free port. Use the `\.venv\Scripts\python.exe` executable on every command to avoid the **No module named streamlit** mismatch.

## Safely integrate into the existing Git repository
Do **not** replace root `engine.py`, `api.py`, `index.html`, or the original `resiliencetwin.sqlite`. The safest simple path is to copy the v0.4 package into a new top-level directory named `ResilienceTwin_GeoAI_v0_4/` in a Git-connected clone, keeping the original `ResilienceTwin_GeoAI_v0_1/` folder for reference.

From the root of your Git-connected repository, after `git status` confirms that existing work is clean:

```powershell
git pull --ff-only origin main
git switch -c feature/geoai-v04-scheduler
# Copy the complete ResilienceTwin_GeoAI_v0_4 directory into this repository now.
git status
git add ResilienceTwin_GeoAI_v0_4
git diff --cached --stat
git commit -m "Add GeoAI v0.4 conservative dispatch feasibility prototype"
git push -u origin feature/geoai-v04-scheduler
```

Review the branch on GitHub, then open a pull request. If a branch already exists, select another branch name. Avoid tracking `.venv/`, `__pycache__/` or credentials; check `git diff --cached --stat` carefully before committing.

## Modeling assumptions
1. All records and modeled event times are synthetic, not operational data.
2. Route linework from the foundation is illustrative. Segment flags are *not* authoritative truck routing restrictions.
3. Initial truck position is the synthetic `home_warehouse_id`. Empty repositioning distance = great-circle distance × user-selected multiplier, with an assumed 35 mph average. **Not truck navigation.**
4. The driver's `hours_remaining` is used as a conservative synthetic work/time cap, **not legal hours-of-service compliance**.
5. `booked` slot capacity is conservatively interpreted as external existing commitments; shipments require unallocated slots. This may double-count if values were originally generated to include simulated shipments.
6. Trailer/cargo handling compatibility, rest breaks, queue dynamics, fuel stops, real appointment confirmations, terminal access, and live traffic are not modeled or validated.
7. An unassigned shipment is explicitly left unassigned and contributes **no** cost or emissions to the scheduled-trip totals. Comparing cost totals without comparing completed shipments is misleading.
8. The algorithm is a sequential, priority-first greedy heuristic and does not explore globally feasible schedules. More optimal assignments might exist.
9. Community-impact index is illustrative, not measured exposure; no claim about specific neighborhoods is made.
10. The system is advisory and executes no dispatch, booking, or routing changes.

## Responsible design and presentation
The dashboard supports: stakeholder/driver impact (unassigned shipments and driver workload constraints), environmental responsibility (CO₂ and empty miles), transparency (assumptions and reasons), and human oversight (no automatic action). For the assignment demonstrate the normal scenario and a 75-minute slowdown and compare feasible shipments, unassigned shipments, empty miles, and modeled CO₂ *for completed trips only*. Explain why the stringent 40/12 capacity assumptions create many unassigned records rather than claiming that the system performs poorly.

## Next milestone (v0.5)
Replace the route/reposition approximations with authoritative or documented road-network geometry, explicitly model appointment reservations and per-shipment dispatch service levels, and test an integer-programming solver against this baseline heuristic. With validated freight restrictions and emissions factors, extend the scenario comparisons to full-network outcomes, including penalties for unassigned shipments.
