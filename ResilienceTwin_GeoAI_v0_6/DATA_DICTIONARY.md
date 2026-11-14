# Data Dictionary — all 27 tables

The **source of truth** for exact types, nullability and foreign-key specifications is `schema.sql`. This index enumerates every column and its meaning. All content is fictional and for educational demonstration.

## `community_zones` (5 records)
Fictional community impact proxy points; not actual burden measurements.

| Column | SQLite type | Notes |
|---|---|---|
| `zone_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `name` | `TEXT` | Synthetic attribute |
| `centroid_lat` | `REAL` | Approximate WGS84 decimal degrees |
| `centroid_lon` | `REAL` | Approximate WGS84 decimal degrees |
| `sensitivity_level` | `INTEGER` | Synthetic attribute |
| `sensitive_site` | `TEXT` | Synthetic attribute |
| `source_quality` | `TEXT` | Synthetic attribute |

## `cost_parameters` (6 records)
Explicit cost calculation parameters and status of use in current engine.

| Column | SQLite type | Notes |
|---|---|---|
| `param_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `category` | `TEXT` | Synthetic attribute |
| `value` | `REAL` | Model parameter or fictional value |
| `unit` | `TEXT` | Synthetic attribute |
| `scenario_basis` | `TEXT` | Synthetic attribute |
| `confidence` | `TEXT` | Synthetic attribute |

## `dataset_metadata` (8 records)
Dataset identity, assumptions and scope disclaimers.

| Column | SQLite type | Notes |
|---|---|---|
| `key` | `TEXT` | Primary key |
| `value` | `TEXT` | Model parameter or fictional value |

## `decision_audit` (1 records)
Example human-approval log record; not a real or completed decision.

| Column | SQLite type | Notes |
|---|---|---|
| `audit_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `scenario_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `action_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `reviewer_person_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `decision_status` | `TEXT` | Synthetic attribute |
| `reason` | `TEXT` | Synthetic attribute |
| `created_at_utc` | `TEXT` | Synthetic attribute |

## `dependencies` (228 records)
Directed relationships between workforce, vehicles, assets, facilities and shipments.

| Column | SQLite type | Notes |
|---|---|---|
| `dependency_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `upstream_type` | `TEXT` | Synthetic attribute |
| `upstream_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `downstream_type` | `TEXT` | Synthetic attribute |
| `downstream_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `dependency_type` | `TEXT` | Synthetic attribute |
| `criticality` | `INTEGER` | Synthetic attribute |
| `notes` | `TEXT` | Synthetic attribute |

## `disruption_exposures` (5 records)
Conceptual linkage between disruptions and network segments.

| Column | SQLite type | Notes |
|---|---|---|
| `disruption_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `segment_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `severity_factor` | `REAL` | Synthetic attribute |
| `source` | `TEXT` | Synthetic attribute |

## `disruptions` (5 records)
Legacy engine event type and illustrative severity.

| Column | SQLite type | Notes |
|---|---|---|
| `id` | `TEXT` | Primary key |
| `kind` | `TEXT` | Synthetic attribute |
| `description` | `TEXT` | Synthetic attribute |
| `delay_min` | `INTEGER` | Simulated relative minutes (unless noted) |
| `confidence` | `TEXT` | Synthetic attribute |

## `driver_profiles` (12 records)
Additional driver-hours, endorsement and staffing links.

| Column | SQLite type | Notes |
|---|---|---|
| `driver_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `person_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `endorsement` | `TEXT` | Synthetic attribute |
| `shift_start_min` | `INTEGER` | Simulated relative minutes (unless noted) |
| `shift_end_min` | `INTEGER` | Simulated relative minutes (unless noted) |
| `hours_remaining` | `REAL` | Synthetic attribute |
| `rest_required_min` | `INTEGER` | Simulated relative minutes (unless noted) |

## `drivers` (12 records)
Legacy engine driver assignment and workload.

| Column | SQLite type | Notes |
|---|---|---|
| `id` | `TEXT` | Primary key |
| `truck_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `shift_limit_hours` | `REAL` | Synthetic attribute |
| `assigned_workload_hours` | `REAL` | Synthetic attribute |

## `emission_parameters` (3 records)
Explicit emissions modeling factors and status of use.

| Column | SQLite type | Notes |
|---|---|---|
| `param_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `mode` | `TEXT` | Synthetic attribute |
| `value` | `REAL` | Model parameter or fictional value |
| `unit` | `TEXT` | Synthetic attribute |
| `scenario_basis` | `TEXT` | Synthetic attribute |
| `confidence` | `TEXT` | Synthetic attribute |

## `facilities` (7 records)
Geographic anchors for two ports and five warehouses. Coordinates are approximate.

| Column | SQLite type | Notes |
|---|---|---|
| `id` | `TEXT` | Primary key |
| `name` | `TEXT` | Synthetic attribute |
| `kind` | `TEXT` | Synthetic attribute |
| `lat` | `REAL` | Approximate WGS84 decimal degrees |
| `lon` | `REAL` | Approximate WGS84 decimal degrees |
| `daily_capacity` | `INTEGER` | Synthetic attribute |

## `facility_resources` (28 records)
Material-handling and operational resources, including availability.

| Column | SQLite type | Notes |
|---|---|---|
| `resource_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `facility_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `resource_type` | `TEXT` | Synthetic attribute |
| `quantity` | `INTEGER` | Synthetic attribute |
| `operational_qty` | `INTEGER` | Synthetic attribute |
| `capacity_per_hour` | `REAL` | Synthetic attribute |
| `priority` | `INTEGER` | Synthetic attribute |

## `fleet_specs` (12 records)
Fuel, vehicle, state and expected availability details.

| Column | SQLite type | Notes |
|---|---|---|
| `truck_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `vehicle_type` | `TEXT` | Synthetic attribute |
| `fuel_type` | `TEXT` | Synthetic attribute |
| `model_year` | `INTEGER` | Synthetic attribute |
| `mpg_assumed` | `REAL` | Synthetic attribute |
| `maintenance_state` | `TEXT` | Synthetic attribute |
| `available_from_min` | `INTEGER` | Simulated relative minutes (unless noted) |
| `home_warehouse_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |

## `personnel` (100 records)
100 fictional staff with operational role, work shift, availability and a backup reference.

| Column | SQLite type | Notes |
|---|---|---|
| `person_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `display_name` | `TEXT` | Synthetic attribute |
| `role` | `TEXT` | Synthetic attribute |
| `facility_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `skill_level` | `INTEGER` | Synthetic attribute |
| `shift_code` | `TEXT` | Synthetic attribute |
| `availability` | `TEXT` | Synthetic attribute |
| `backup_person_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `driver_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `fictional` | `INTEGER` | Always 1 for sample people |

## `personnel_skills` (210 records)
Many-to-many employee skills with synthetic proficiency.

| Column | SQLite type | Notes |
|---|---|---|
| `person_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `skill_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `proficiency` | `INTEGER` | Synthetic attribute |

## `road_nodes` (9 records)
Approximate reference and demonstration junction coordinates.

| Column | SQLite type | Notes |
|---|---|---|
| `node_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `name` | `TEXT` | Synthetic attribute |
| `lat` | `REAL` | Approximate WGS84 decimal degrees |
| `lon` | `REAL` | Approximate WGS84 decimal degrees |
| `node_type` | `TEXT` | Synthetic attribute |

## `road_segments` (13 records)
Schematic network links and freight accessibility assumptions.

| Column | SQLite type | Notes |
|---|---|---|
| `segment_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `from_node_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `to_node_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `road_name` | `TEXT` | Synthetic attribute |
| `nominal_miles` | `REAL` | Synthetic attribute |
| `nominal_min` | `INTEGER` | Simulated relative minutes (unless noted) |
| `sensitivity` | `TEXT` | Synthetic attribute |
| `freight_allowed` | `INTEGER` | Synthetic attribute |
| `geometry_json` | `TEXT` | JSON array of [longitude, latitude] pairs |

## `route_segments` (200 records)
Sequence of schematic road segments associated with route variants.

| Column | SQLite type | Notes |
|---|---|---|
| `route_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `segment_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `sequence_no` | `INTEGER` | Primary key |

## `routes` (80 records)
Legacy primary/alternate route geometry and estimates.

| Column | SQLite type | Notes |
|---|---|---|
| `id` | `TEXT` | Primary key |
| `shipment_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `variant` | `TEXT` | Synthetic attribute |
| `distance_mi` | `REAL` | Synthetic attribute |
| `travel_min` | `INTEGER` | Simulated relative minutes (unless noted) |
| `community_exposure_index` | `INTEGER` | Synthetic attribute |
| `geojson_points` | `TEXT` | JSON array of [longitude, latitude] pairs |

## `scenario_actions` (5 records)
Human-review response choices and estimated setup times.

| Column | SQLite type | Notes |
|---|---|---|
| `action_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `action_type` | `TEXT` | Synthetic attribute |
| `description` | `TEXT` | Synthetic attribute |
| `requires_approval` | `INTEGER` | Synthetic attribute |
| `estimated_setup_min` | `INTEGER` | Simulated relative minutes (unless noted) |

## `scenario_definitions` (6 records)
Normal and changed-condition scenarios with affected segment references.

| Column | SQLite type | Notes |
|---|---|---|
| `scenario_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `name` | `TEXT` | Synthetic attribute |
| `kind` | `TEXT` | Synthetic attribute |
| `severity_min` | `INTEGER` | Simulated relative minutes (unless noted) |
| `affected_segment_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `confidence` | `TEXT` | Synthetic attribute |
| `description` | `TEXT` | Synthetic attribute |

## `segment_community_exposure` (12 records)
Hypothetical linkage of road segments to nearby proxy communities.

| Column | SQLite type | Notes |
|---|---|---|
| `segment_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `zone_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `impact_weight` | `REAL` | Synthetic attribute |

## `shipment_details` (40 records)
Container, priority, appointment and cargo attributes.

| Column | SQLite type | Notes |
|---|---|---|
| `shipment_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `container_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `customer_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `cargo_type` | `TEXT` | Synthetic attribute |
| `container_teu` | `INTEGER` | Synthetic attribute |
| `priority` | `TEXT` | Synthetic attribute |
| `pickup_status` | `TEXT` | Synthetic attribute |
| `appointment_start_min` | `INTEGER` | Simulated relative minutes (unless noted) |
| `appointment_slot_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `estimated_value_usd` | `REAL` | Model parameter or fictional value |
| `handling_requirements` | `TEXT` | Synthetic attribute |
| `source_quality` | `TEXT` | Synthetic attribute |

## `shipments` (40 records)
Core dispatch commitments and legacy engine shipment records.

| Column | SQLite type | Notes |
|---|---|---|
| `id` | `TEXT` | Primary key |
| `origin_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `destination_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `truck_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `pickup_ready_min` | `INTEGER` | Simulated relative minutes (unless noted) |
| `appointment_end_min` | `INTEGER` | Simulated relative minutes (unless noted) |
| `weight_tons` | `REAL` | Synthetic attribute |
| `exposed` | `INTEGER` | Synthetic attribute |

## `skills` (10 records)
Catalog of example operational and technical capabilities.

| Column | SQLite type | Notes |
|---|---|---|
| `skill_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `name` | `TEXT` | Synthetic attribute |
| `category` | `TEXT` | Synthetic attribute |

## `trucks` (12 records)
Legacy engine truck inventory and assigned home port.

| Column | SQLite type | Notes |
|---|---|---|
| `id` | `TEXT` | Primary key |
| `capacity_teu` | `INTEGER` | Synthetic attribute |
| `status` | `TEXT` | Synthetic attribute |
| `base_port_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |

## `warehouse_slots` (30 records)
Synthetic capacity and bookings in relative minute windows.

| Column | SQLite type | Notes |
|---|---|---|
| `slot_id` | `TEXT` | Primary key; Identifier/reference; see `schema.sql` for FK |
| `warehouse_id` | `TEXT` | Identifier/reference; see `schema.sql` for FK |
| `window_start_min` | `INTEGER` | Simulated relative minutes (unless noted) |
| `window_end_min` | `INTEGER` | Simulated relative minutes (unless noted) |
| `capacity` | `INTEGER` | Synthetic attribute |
| `booked` | `INTEGER` | Synthetic attribute |
