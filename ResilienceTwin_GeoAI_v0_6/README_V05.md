# ResilienceTwin GeoAI v0.5 — Mixed-Integer Dispatch Decision Intelligence

## New in this release

- `optimizer_v05.py`: a SciPy/HiGHS mixed-integer linear optimization model selecting among feasible combinations of shipment, truck, route, and receiving slot.
- `app_v05.py`: interactive Streamlit dashboard with policy preferences, baseline/disruption comparisons, scenario map, shipment decisions, solver diagnostics, and CSV export.
- `test_v05.py`: 13 new test cases for coverage, no double-booking, slot capacity, time windows, closure avoidance, deterministic results, and reported solver status.
- `scenario_evidence_v05.csv`: normal operations, 75-minute slowdown, and closure under four tie-break policies.
- All previous v0.1–v0.4 files are retained for comparison. No changes to root `CGU_DTO` files.

## How the optimizer works

Candidate construction checks original appointments, simplified driver hour budgets, synthetic truck availability and capacity, synthetic route segment flags, blocked segments, and available warehouse slots.

The model enforces **at most one trip per truck in the entire planning period** and **at most one assignment per shipment**. It also limits assigned arrivals to spare modeled receiving capacity. It uses three *lexicographic* MILP solves:

1. Maximize priority-weighted serviced shipments (`critical=5`, `high=3`, `routine=1`).
2. Maximize completed shipment count while retaining the best weighted service score.
3. Choose a lowest-cost, lowest-CO₂, earliest-receiving, or illustrative balanced result among solutions with both primary goals preserved.

The solver's `provably_optimal` result is **only for this restricted model**. The v0.4 greedy scheduler allows multiple sequential trips per truck and v0.5 does not; therefore v0.5 and v0.4 are not equivalent feasible optimization problems. Further work is required for global multi-trip dispatch optimization.

**Important:** Lower scheduled-trip cost and emissions do **not** mean the network performed better when shipments remain unassigned. We deliberately report the unassigned count and do not assign zero cost or emissions to missing deliveries. There is no validated unserved-penalty model yet.

## Install/run on Windows in VS Code

Unzip the package and place the entire `ResilienceTwin_GeoAI_v0_5` folder inside your Git-connected `CGU_DTO_GeoAI` repository. Do not overwrite root `engine.py`, `api.py`, `index.html`, or `resiliencetwin.sqlite`.

Open `CGU_DTO_GeoAI` in Visual Studio Code and use **Terminal > New Terminal**. From the repository root:

```powershell
cd ResilienceTwin_GeoAI_v0_5
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe test_v05.py
.\.venv\Scripts\python.exe test_v04.py
.\.venv\Scripts\python.exe test_v03.py
.\.venv\Scripts\python.exe tests.py
.\.venv\Scripts\python.exe -m streamlit run app_v05.py --server.port 8503
```

Open http://localhost:8503. The included database is pre-seeded; you do not need to run seed scripts. Always invoke the venv interpreter to avoid the previously encountered `No module named streamlit` error.

**If Python or pip says SciPy is unsupported**, use a recent supported 64-bit Python 3.11–3.13 installation and recreate `.venv`. The package uses `scipy.optimize.milp` and requires SciPy >=1.11.

## Commit to GitHub safely

From the **repository root**, check status first:

```powershell
git status
```

When clean and on `main`:

```powershell
git pull --ff-only origin main
git switch -c feature/geoai-v05-milp
# Copy the v0.5 folder into this repository, if not already present.
```

Make sure `.gitignore` ignores `.venv/`, `__pycache__/`, and `*.pyc`. Then:

```powershell
git add ResilienceTwin_GeoAI_v0_5
git diff --cached --stat
git commit -m "Add GeoAI v0.5 optimization decision lab"
git push -u origin feature/geoai-v05-milp
```

Open a pull request and review before merging. If a branch already exists, choose a different name. If you do not have permission to push to the shared repository, use a fork and pull request.

## Scope and limitations

- All shipment and network records are synthetic and educational. Route polylines are illustrative; endpoint consistency and synthetic `freight_allowed` flags are checked, **but these are not authoritative heavy-vehicle navigation restrictions**.
- Empty repositioning uses haversine distance times an adjustable factor at an assumed 35 mph, **not real road-network shortest paths**.
- Simplified driver hour budgets are **not actual FMCSA hours-of-service validation**.
- Warehouse `booked` values are assumed to describe external reservations, and **no booking is executed**.
- Costs, CO₂ factors, and community-exposure proxies are not calibrated real-world measures.
- No dispatch action is taken; a human must approve every real-world use.
- The model is restricted to one trip per truck; it is not a route-based multi-trip scheduling optimizer.
- The reliability-first objective maximizes service of priority shipments; when no priorities differ within a tie, the secondary policy selects a trade-off. These preferences are illustrative and subject to stakeholder review.

## Demonstration for GeoAI assignment

1. Run the **Normal** scenario under `Balanced` and record scheduled/unassigned count, priority score, scheduled-trip cost, estimated CO₂, and modeled empty miles.
2. Select **Highway slowdown** with 75 minutes and run the same policy. Compare results against normal operations, noting that priorities and assignment sets may change.
3. Switch between **Lowest cost** and **Lowest CO2**, then compare the different routes and their values.
4. Select **Highway closure** and confirm no chosen route crosses its affected synthetic segment.
5. Show the explanatory warning, candidate exclusions, map, and shipment-level evidence; emphasize that the recommendation is advisory and must be validated by a human.

## Next milestone

To complete the **true road-network and multi-trip optimization** portions, integrate documented heavy-vehicle network data and truck routing restrictions, model time-dependent tours with exact repositioning costs, validate receiving reservations, and add an approved stakeholder-defined penalty for unserved shipments. Current version is a useful reproducible proof-of-concept, not yet those operational capabilities.
