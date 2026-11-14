"""Match modeled shipments to the bundled road-network geometry."""
import json
from pathlib import Path


def map_routes(facilities, shipments):
    catalog_path = Path(__file__).with_name("data") / "road_routes.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    by_id = {facility["id"]: facility for facility in facilities}
    routes = {}
    missing = 0
    for shipment in shipments:
        origin = by_id[shipment["origin_id"]]
        destination = by_id[shipment["destination_id"]]
        pair = f'{origin["id"]}:{destination["id"]}'
        saved = catalog.get(pair)
        stops = [[facility["lon"], facility["lat"]] for facility in (origin, destination)]
        wants_alternate = shipment["route"] == "alternate"
        option_index = int(wants_alternate)
        if not saved or saved["stops"] != stops or len(saved["options"]) <= option_index:
            missing += 1
            continue
        key = (pair, option_index)
        if key not in routes:
            option = saved["options"][option_index]
            routes[key] = {
                "coordinates": option["coordinates"],
                "attributes": {
                    "origin": origin["name"], "destination": destination["name"],
                    "variant": "Alternate" if wants_alternate else "Primary",
                    "miles": option["miles"], "shipments": 0, "late": 0,
                },
            }
        attributes = routes[key]["attributes"]
        attributes["shipments"] += 1
        attributes["late"] += int(not shipment["on_time"])
    return list(routes.values()), missing
