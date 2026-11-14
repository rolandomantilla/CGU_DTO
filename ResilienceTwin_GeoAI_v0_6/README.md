# ResilienceTwin GeoAI — Foundational Dataset v0.2

A complete reproducible **synthetic** data foundation for the GeoAI Track perspective **3. Resilience, Cost, and Sustainability Intelligence**.

## Inventory

- **27 relational tables**, **1,099 table rows**, exported as **27 UTF-8 CSV files** (`csv/`).
- SQLite: `data/geoai.sqlite` (foreign-key integrity checked).
- Schema: `schema.sql` (SQLite DDL generated from the database).
- Generator: `build_foundation.py` plus legacy `seed_data.py`.
- Existing prototype retained: `engine.py`, `app.py`, `tests.py`, and `requirements.txt`.
- Reference documentation: `DATA_DICTIONARY.md`, `MODEL_GUIDE.md`, `DATA_COUNTS.json`.

## Quick start (Windows, VS Code PowerShell)

Extract this archive to a **new folder**; do not overwrite `CGU_DTO`.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe tests.py
.\.venv\Scripts\python.exe -m streamlit run app.py
```

This package already includes the generated SQLite database. To rebuild it from scratch, use:

```powershell
.\.venv\Scripts\python.exe build_foundation.py
```

**Important:** `seed_data.py` rebuilds ONLY the six base tables and removes the current database; running it alone discards the 21 additional foundation tables. Always run **`build_foundation.py`**, which rebuilds both levels, instead.

## Integration / current application boundary

The existing v0.1 Streamlit app and Python engine use only the original 6 tables (`facilities`, `trucks`, `drivers`, `shipments`, `routes`, `disruptions`). They continue to run against the expanded database; newly added resource, labor, road segment, warehouse slot, cost and emissions tables are **not yet applied or enforced by v0.1 engine calculations**. A subsequent engine upgrade must use these new relationships and test operational feasibility.

In particular:
- Route geometry is schematic, not navigable road geometry; road segments are a logical demonstration network.
- Route-to-segment relationships are approximations, and are NOT reconciled against v0.1 route mileage or travel times.
- Truck and driver assignments are reused across shipments; scheduling, capacity and driver-hour constraints are not enforced.
- Shipment receiving slots are descriptive placeholders, not confirmed reservations; some assigned times can extend beyond the slot. A scheduling engine must reconcile them.
- Community zones and school/community-center descriptors are fictional proxies; they do not identify actual sensitive sites, census burdens, local exposure, or demographic equity.
- Cost and emissions rates are illustrative, not validated tariffs, fuel prices, or emission factors.
- One fictional approval audit row shows the target schema, not a completed approval.

## Reproducibility and safety

Generator random seeds are fixed; output is deterministic. No identifying personal data is included. All characters are synthetic. Timestamp references are illustrative; shipment times are **minutes after a simulated epoch**, not calendar appointment timestamps. WGS84 coordinates are approximate visual anchors only.

## Core database examples

```sql
SELECT s.id AS shipment, f.name AS warehouse, d.priority, d.pickup_status
FROM shipments s
JOIN shipment_details d ON d.shipment_id = s.id
JOIN facilities f ON f.id = s.destination_id
ORDER BY d.priority, s.id;

SELECT upstream_type, dependency_type, COUNT(*) AS relationships
FROM dependencies GROUP BY upstream_type, dependency_type;

SELECT route_id, group_concat(segment_id, ' -> ') AS illustrative_segments
FROM route_segments WHERE route_id='SHP-001-primary'
ORDER BY sequence_no;
```

For ArcGIS workflows, start with `csv/facilities.csv`, `csv/community_zones.csv`, and `csv/road_nodes.csv` as WGS84 point tables; `road_segments.csv` and `routes.csv` contain JSON coordinate arrays which can be converted to line features with Python. These are schematic, not verified roads.
