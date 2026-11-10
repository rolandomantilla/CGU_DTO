# ResilienceTwin v0.2 — Organizational Simulation Engine

Runnable, deterministic simulation built on the synthetic 100-person, five-facility organizational SQLite database from Foundation v1.

## Run

Requires Python 3.10+.

```bash
python -m pip install -r requirements.txt
python -m uvicorn api:app --reload
```

Open **http://127.0.0.1:8000/** in a browser. The page requires the API; opening `web/index.html` directly will not work.

Run the engine directly:

```bash
python engine.py --scenario data/custom_scenario.json --out output.json
```

Example `data/custom_scenario.json`:

```json
{"type":"PersonnelUnavailable","facility_id":"FAC-ATL","personnel_unavailable_pct":30,"duration_hours":72}
```

Or run any of the `scenarios.json` examples after saving one object as a separate JSON file.

Test:

```bash
python -m pytest -q
```

## API

- `GET /api/health` — service status
- `GET /api/model` — public synthetic model lookup metadata
- `POST /api/simulate` — scenario simulation request
- `GET /docs` — interactive FastAPI docs

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/simulate -H 'Content-Type: application/json' -d '{"type":"FacilityOffline","facility_id":"FAC-DEN","duration_hours":24}'
```

## Supported scenarios

- PersonnelUnavailable: facility and percentage (0–100)
- FacilityOffline: facility; on-site-only staff assumed unavailable, hosted systems offline
- RoleUnavailable: facility and exact job title
- EmployeeUnavailable: employee ID
- SystemOffline: system ID

All scenarios accept `duration_hours` as modeled working hours. Duration scales expected task counts; it does not change capacity, introduce restoration, or enforce recovery-time objectives.

## Model details and limitations

- Workflows are rated on current assigned FTE compared with the original assigned FTE, minimum active headcount, qualification count by required skills, and required/supporting systems.
- A required-system outage blocks a dependent workflow; supporting-system outages use an illustrative 25% efficiency penalty.
- A weighted readiness metric is computed using workflow criticality (not a statistical forecast).
- Personnel reduction uses a deterministic **high-criticality-first** worst-case stress test.
- Candidate recovery personnel require matching skill proficiency and unallocated FTE, with basic remote/cross-site eligibility. Suggestions are **not executed** and do not change readiness calculations; authorization, access rights, shifts, and timing are not fully modeled.
- Existing synthetic staffing allocations are used as baseline; a 100% baseline does not establish an objectively sufficient staffing plan.
- Duration scales a fluid throughput estimate; there are no shifts, queues, timed recovery, or network cascades between workflows.
- No real human data, ArcGIS connection, UNIFI integration, LLM, or predictive AI is included.
- **Not for actual operational decisions.**

## Roadmap

1. Calibrate staffing/skills/coverage rules and compare against user-defined service-level requirements.
2. Add timed restoration, alternate hosting, explicit recovery plans, and versioned scenario results.
3. Connect ArcGIS feature layers and geospatial hazards via location-based dependency records.
4. Add grounded LLM narrative with source traceability, followed by UNIFI integration.


## Editable employee human variables

The three variables follow the definitions in the supplied proposal: skills,
experience, and organizational relationships. All 100 fictional employees have
profiles exposed by `GET /api/model` and returned in simulation `employees`.

In the browser, scroll to **Employee human variables**, select an employee,
change values, and click **Apply changes & run simulation**. You can edit several
employees before running. Switching employees retains edits in this browser tab.
**Reset this employee** and **Reset all human edits** restore the starting values.
Reloading the page clears scenario edits. Exporting a result includes the scenario
with all overrides and the resulting employee profiles; it does not update the
source database or JSON records.

- **Skills:** competency IDs and proficiency levels from 1 to 5. Update existing
  competencies or add one from the model's competency catalog. Task-relevant
  proficiency affects effective assigned capacity and qualification coverage.
- **Experience:** for each assigned workflow, use years in the employee's current
  role OR a whole number of similar tasks completed. Role years are one employee
  attribute and must agree across assignments; the editor synchronizes them.
  Organizational tenure is not substituted for role experience.
- **Organizational relationships:** directed outgoing handoffs between colleagues
  assigned to the same workflow. Edit collaboration counts, handoff counts, and
  average handoff delay within the 30-day synthetic observation window. A colleague's
  incoming edge is edited by selecting its sender. Centrality and available
  collaborators are derived from the resulting network, not entered as scores.

Edits apply only to the simulation request. `employee_updates` entries use:

```json
{
  "type": "PersonnelUnavailable",
  "facility_id": "FAC-ATL",
  "personnel_unavailable_pct": 0,
  "model_variant": "human_centered",
  "employee_updates": [
    {
      "employee_id": "EMP-001",
      "skills": {"leadership": 3},
      "experience": [{"workflow_id": "WF-05", "years_in_role": 10}],
      "relationships": [
        {"workflow_id": "WF-05", "target_employee_id": "EMP-045",
         "collaboration_events": 100, "handoff_events": 7,
         "mean_handoff_hours": 0.1}
      ]
    }
  ]
}
```

Skills and experience are partial patches. `relationships` replaces **all outgoing
edges** for that employee; omitting it preserves them, and `[]` removes them.
Event counts and similar-task counts must be whole numbers; handoff counts must
be at least 1. This demo bounds mean handoff delay by its configured disconnected
handoff delay (2 hours). Invalid IDs, duplicate edges, nonfinite numbers, and
inconsistent measurements are rejected before calculation.

### Modeling and comparisons

`model_variant` supports `process_only`, `skills_only`, `experience_only`,
`relationships_only`, and `human_centered` (default). The same disruption and
updated employee inputs are used across comparisons; process-only predictions
ignore human-variable efficiency and qualification penalties. Qualification gaps
remain diagnostic even when skills are disabled.

Each person's assigned FTE is multiplied by illustrative skill and experience
efficiency factors, then contributions are summed before staffing, headcount,
qualification, and system ceilings are applied. Workflow task time combines
processing time and a handoff-weighted coordination delay. Unavailable employees
contribute zero capacity; their handoff demand remains as disrupted relationships.
Degree centrality is reported as a diagnostic and is not an extra causal multiplier.
The result includes task-completion hours, tasks per hour, and expected tasks
within the scenario duration. Blocked task times are `null`, with zero throughput.

The displayed baseline uses original employee values with no disruption. Thus,
when employee edits are present, its delta combines disruption and human-input
changes. All model comparisons use the edited values consistently.

The coefficients, added experience records, handoff records, and reference task
times are **synthetic demonstration assumptions**, not parameters estimated from
the proposal's cited studies. Fifteen employees' generated role-year values were
normalized across assignments; provenance is recorded in `data/human_factors.json`.
These mechanics have not been calibrated against observed outcomes, and no
improvement in predictive accuracy is claimed. Historical outcome data and held-out
MAE/RMSE evaluation remain separate future work.
