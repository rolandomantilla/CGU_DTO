# ResilienceTwin GeoAI: project roadmap

## v0.1 — Runnable proof of concept (included)
- Reproducible SQLite synthetic dataset: ports, warehouses, shipments, trucks, drivers, routes, disruptions.
- Three mitigation choices and six scenario labels, with an adjustable delay.
- Map visualization, KPIs, shipment exceptions, route comparison, CSV export.
- Tests and normal-versus-disruption evidence.
- Human selection, environmental proxy, clear labeling of simulated measurements.

## v0.2 — Geographic fidelity (next)
- Replace straight schematic route links with actual street-network paths and duration estimates from a documented routing dataset/service.
- Introduce segment-level incident exposure, explicit road closures and uncertainty confidence.
- Add geographic community-sensitive receptors (schools/residential areas), with carefully qualified exposure measures.

## v0.3 — Operational feasibility
- Enforce truck/driver schedules, warehouse time-slot capacity and working-hour constraints.
- Add route-capacity conflict and pickup-window constraints.
- Implement ranking with transparent, user-configurable trade-off weights and Pareto comparisons.

## v0.4 — Explainability and demonstration
- Per-shipment recommendation explanations and a dispatcher accept/override audit log.
- Scenario-run persistence, consistent baseline definition and downloadable evaluation charts.
- 10-minute demo deck, tests, screenshots, evidence table and documented assumptions.

## Important methodology boundary
This initial release uses deterministic simulation rather than machine learning. AI-assisted narrative explanations can be added later, but must be grounded in calculated outcomes. No AI model or live traffic feed is used in v0.1.
