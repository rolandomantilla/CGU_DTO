# ResilienceTwin GeoAI v0.3 — Decision Lab

This additive upgrade extends the **v0.2 synthetic 27-table foundation**. It does **not** replace the original `app.py`/`engine.py`, and it does not overwrite the original CGU_DTO organizational ResilienceTwin.

## What's new

- `decision_engine.py`: row-by-row assessment of hypothetical route exposure to affected road segments, modeled slowdown/closure, pickup delay, rerouting, expedited dispatch, or proposed appointment rescheduling.
- Identifies possible overlaps when one truck is assigned to multiple simultaneous shipments.
- Flags synthetic driver time-budget/shift issues, truck availability/maintenance, and fully booked original warehouse slots.
- Uses v0.2 SQLite cost and emissions parameters and reports environmental/community proxy tradeoffs.
- `app_v03.py`: separate interactive Streamlit dashboard with CSV evidence export.
- `test_v03.py`: seven tests; original `tests.py` still passes.

## Run in Windows VS Code

Open the `CGU_DTO_GeoAI` repo **root**. Place the complete `ResilienceTwin_GeoAI_v0_3` directory in the repository without replacing existing folders; then open the terminal:

```powershell
cd ResilienceTwin_GeoAI_v0_3
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe test_v03.py
.\.venv\Scripts\python.exe -m streamlit run app_v03.py --server.port 8502
```

If the folder is already open in your terminal, omit `cd`. Test with the packaged `data/geoai.sqlite` first. Do not regenerate the database unless you explicitly intend to reset synthetic seed data.

## Interpret with care

- **Original appointment compliance** remains separate from **projected arrival compliance if a proposed reschedule is approved**; the latter is NOT a confirmed booking.
- The 40 synthetic shipments reuse only 12 trucks, so most shipments have a scheduling conflict warning. The model flags conflicts rather than finding a valid fleet assignment. **Do not describe any response as dispatch-feasible.**
- Road segments are synthetic abstractions. Route exposure only checks segment IDs, not real road closures, time-dependent travel, or truck-safe routes.
- Driver budget is a synthetic simple time check, NOT a regulatory hours-of-service compliance system.
- Cost per mile, penalty amounts, CO₂ and community impact proxies are illustrative, not observed or validated.
- `Request reschedule` models a tentative new appointment request and cannot confirm available capacity or execution.
- The demo is reproducible, explains its tradeoffs and leaves all final choices to a human.

## Integration into GitHub

Check `git status` and preserve existing changes. Add this as a **new folder** on a development branch, test, commit and push, then create a pull request. Do not copy `engine.py`, `app.py` or SQLite over any files in your previous GeoAI or original CGU_DTO modules.
