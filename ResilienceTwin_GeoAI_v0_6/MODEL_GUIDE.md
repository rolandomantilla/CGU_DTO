# Foundation Model Guide

## Mission
Help a fictional dispatcher evaluate **delivery reliability, cost, extra mileage and CO2** under disruptions, while exposing stakeholder impacts and uncertainty and requiring human approval.

## Data flow

`facilities` -> `shipments` -> `shipment_details` -> `warehouse_slots`

`trucks` -> `fleet_specs`; `drivers` -> `driver_profiles` -> `personnel` -> `personnel_skills` -> `skills`

`shipments` -> `routes` -> `route_segments` -> `road_segments` -> `road_nodes`

`disruptions` -> `disruption_exposures` -> `road_segments`; `scenario_definitions` -> `scenario_actions` -> `decision_audit`

`road_segments` -> `segment_community_exposure` -> `community_zones`

`dependencies` captures directed cross-domain operational links that later models can traverse.

## Synthetic business rules to implement in next engine version

1. Enforce port release readiness and one-truck/driver-at-a-time scheduling.
2. Check driver shift and remaining work hours, including rest windows.
3. Check freight-accessibility and impacted roads before recommending a route.
4. Reconcile estimated arrival with warehouse slot start, end and capacity.
5. Recompute miles, cost, CO2 and affected community proxies for each option.
6. Expose estimation confidence and separate observed from inferred status.
7. Require dispatcher review/approval before applying any operational change.
8. Save normal and changed scenario results for evidence and reproducible tests.

## Key evaluation metrics

- **At-risk shipments** = shipments with modeled arrival after latest acceptable appointment minute.
- **On-time percentage** = on-time shipments / total shipments * 100.
- **Incremental modeled transport cost** = disrupted strategy cost minus normal-strategy cost.
- **Extra miles** = strategy route miles minus normal route miles.
- **Incremental CO2 (kg)** = strategy estimate minus normal estimate.
- **Stakeholder exposure** = explanatory hypothetical proxy only; never a measured health or equity assessment.

## Data governance

Do not present synthetic staff as actual employees, schema placeholders as real telemetry, fictional community zones as schools, or planned v0.2 capabilities as implemented in the v0.1 app. All output needs an explicit simulated/estimated label.
