"""Read the operational CSV dataset without generating or mutating sample data."""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any


DATASET_FILES = (
    "dealerships",
    "warehouses",
    "parts",
    "inventory",
    "suppliers",
    "repair_orders",
    "technicians",
    "service_bays",
    "deliveries",
    "purchase_orders",
    "road_network",
    "historical_demand",
    "security_events",
    "appointments",
    "inventory_movements",
    "quotations",
    "procurement_policies",
    "vehicle_records",
    "documents",
)


def read_rows(data_dir: str | os.PathLike[str], table: str) -> list[dict[str, str]]:
    path = Path(data_dir) / f"{table}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Required telemetry file is missing: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def load_world_dataset(data_dir: str | os.PathLike[str]) -> dict[str, Any]:
    """Build the planner's data model from the current CSV files."""
    dealerships = read_rows(data_dir, "dealerships")
    warehouses = read_rows(data_dir, "warehouses")
    parts = read_rows(data_dir, "parts")
    inventory = read_rows(data_dir, "inventory")
    repairs = read_rows(data_dir, "repair_orders")
    supplier_rows = read_rows(data_dir, "suppliers")
    policy_rows = read_rows(data_dir, "procurement_policies")
    technicians = read_rows(data_dir, "technicians")
    road_rows = read_rows(data_dir, "road_network")

    sites: dict[str, dict[str, float | str]] = {}
    for row, key in [(r, "dealership_id") for r in dealerships] + [
        (r, "warehouse_id") for r in warehouses
    ]:
        sites[row[key]] = {
            "lat": float(row["lat"]),
            "lon": float(row["lon"]),
            "kind": "dealer" if key == "dealership_id" else "warehouse",
            "name": row.get("name", row[key]),
        }

    if not sites:
        raise ValueError("Telemetry dataset has no dealerships or warehouses.")
    if not parts:
        raise ValueError("Telemetry dataset has no parts.")

    stocks: dict[str, dict[str, int]] = {site: {} for site in sites}
    for row in inventory:
        site, part = row["site_id"], row["part_id"]
        if site not in stocks:
            raise ValueError(f"Inventory references unknown site {site!r}.")
        qty = int(row["qty"])
        if qty < 0:
            raise ValueError(f"Inventory quantity cannot be negative: {site}/{part}.")
        stocks[site][part] = stocks[site].get(part, 0) + qty

    part_by_id = {row["part_id"]: row for row in parts}
    unknown_parts = {
        row["part_id"] for row in inventory if row["part_id"] not in part_by_id
    }
    if unknown_parts:
        raise ValueError(
            "Inventory references unknown parts: " + ", ".join(sorted(unknown_parts))
        )

    repair_orders = []
    for row in repairs:
        if row["dealership_id"] not in sites:
            raise ValueError(
                f"Repair order references unknown site {row['dealership_id']!r}."
            )
        if row["part_id"] not in part_by_id:
            raise ValueError(
                f"Repair order references unknown part {row['part_id']!r}."
            )
        repair_orders.append({
            "id": row["repair_order_id"],
            "dealer": row["dealership_id"],
            "part": row["part_id"],
            "qty": int(row["qty"]),
            "priority": int(row["priority"]),
            "status": row["status"],
            "technician": row["technician_id"],
        })

    global_limit = max((float(row["limit"]) for row in policy_rows), default=0.0)
    vendors = {
        row["supplier_id"]: {
            "name": row["name"],
            "reliability": float(row["reliability"]),
            "lead_time": int(row["lead_time_days"]),
            "restricted": bool(int(row["restricted"])),
            "limit": global_limit,
        }
        for row in supplier_rows
    }

    tech_by_id = {
        row["technician_id"]: {
            "site": row["dealership_id"],
            "skills": set(filter(None, row["skills"].split("|"))),
            "available": bool(int(row["available"])),
        }
        for row in technicians
    }
    network_edges: dict[tuple[str, str], float] = {}
    for row in road_rows:
        start, end = row["from"], row["to"]
        if start not in sites or end not in sites:
            raise ValueError(f"Road network references unknown site: {start!r}, {end!r}.")
        cost = float(row.get("travel_cost") or row["distance_km"])
        if cost <= 0:
            raise ValueError(f"Road cost must be positive: {start}/{end}.")
        network_edges[(start, end)] = cost

    if not network_edges:
        raise ValueError("Telemetry dataset has no road-network edges.")

    return {
        "sites": sites,
        "dealerships": [row["dealership_id"] for row in dealerships],
        "parts": part_by_id,
        "stock": stocks,
        "repair_orders": repair_orders,
        "vendors": vendors,
        "technicians": tech_by_id,
        "network": {
            "nodes": {site: (float(row["lon"]), float(row["lat"])) for site, row in sites.items()},
            "edge_map": network_edges,
        },
        "updated_at": max(
            (os.path.getmtime(Path(data_dir) / f"{name}.csv") for name in DATASET_FILES),
            default=0.0,
        ),
    }


def planner_database(dataset: dict[str, Any]) -> dict[str, Any]:
    return {
        "stock": dataset["stock"],
        "ros": dataset["repair_orders"],
        "vendors": dataset["vendors"],
        "closed": set(),
        "po": {},
    }
