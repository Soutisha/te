"""Generate consistent sample CSVs for AutoNexus Motors (Kolkata region).
All locations and organisations are fictional demonstration data.
"""
from __future__ import annotations

import csv
import math
import os
import random

from .data import NODES, edges

try:
    from . import ml
except Exception:
    ml = None

# Internal IDs kept stable for existing tests & core engine.
DEAL = ["DealerA", "DealerB", "DealerC", "DealerD", "DealerE"]
WH = ["WH1", "WH2"]

BRANCH_NAMES = {
    "DealerA": "AutoNexus Kolkata Central",
    "DealerB": "AutoNexus Salt Lake",
    "DealerC": "AutoNexus Howrah",
    "DealerD": "AutoNexus New Town (satellite)",
    "DealerE": "AutoNexus Rajarhat (satellite)",
    "WH1": "Regional Parts Hub – Dum Dum",
    "WH2": "Regional Parts Hub – Howrah Yard",
}

COORDS = {
    "DealerA": (22.5726, 88.3639),
    "DealerB": (22.5867, 88.4170),
    "DealerC": (22.5958, 88.2636),
    "DealerD": (22.5792, 88.4798),
    "DealerE": (22.6230, 88.4460),
    "WH1": (22.6250, 88.4000),
    "WH2": (22.5850, 88.3100),
}

PROFILE = {
    "DealerA": (1.3, (0.60, 0.90)),
    "DealerB": (0.8, (0.80, 0.98)),
    "DealerC": (1.0, (0.70, 0.95)),
    "DealerD": (1.6, (0.60, 0.85)),
    "DealerE": (0.6, (0.85, 0.99)),
}


def w(d: str, name: str, rows: list[dict]) -> None:
    path = os.path.join(d, name + ".csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)


def generate(out: str = "data", seed: int = 42) -> dict[str, int]:
    """Write all required CSVs. Deterministic for a given seed."""
    os.makedirs(out, exist_ok=True)
    r = random.Random(seed)
    T: dict[str, list] = {}

    T["dealerships"] = [
        {
            "dealership_id": d,
            "name": BRANCH_NAMES[d],
            "lat": COORDS[d][0],
            "lon": COORDS[d][1],
            "city": "Kolkata",
            "branch_code": d,
        }
        for d in DEAL
    ]
    T["warehouses"] = [
        {
            "warehouse_id": x,
            "name": BRANCH_NAMES[x],
            "lat": COORDS[x][0],
            "lon": COORDS[x][1],
            "capacity_units": r.choice([5000, 8000]),
        }
        for x in WH
    ]

    names = ["BrakePad", "OilFilter", "BrakeRotor", "Battery", "WiperBlade",
             "SparkPlug", "AirFilter", "CabinFilter", "ClutchKit", "ShockAbsorber"]
    parts = []
    for i in range(120):
        parts.append({
            "part_id": f"P{i:03d}",
            "name": "BrakePad" if i == 0 else names[i % len(names)],
            "unit_price": round(r.uniform(120, 8500), 2),
            "compatible_models": "sedan|suv|hatch|muv" if i == 0 else ("sedan|suv|hatch" if i % 2 == 0 else "suv|muv"),
            "category": "brakes" if i == 0 or "Brake" in names[i % len(names)] else "general",
        })
    T["parts"] = parts

    # Demo scenario: Kolkata Central has 0 brake pads; Salt Lake 18; Howrah 4
    inv = []
    for s in DEAL + WH:
        for p in parts:
            if p["part_id"] == "P000":
                if s == "DealerA":
                    qty = 0
                elif s == "DealerB":
                    qty = 18
                elif s == "DealerC":
                    qty = 4
                elif s == "WH1":
                    qty = 40
                else:
                    qty = r.randint(5, 25)
            else:
                qty = r.randint(0, 30)
            inv.append({"site_id": s, "part_id": p["part_id"], "qty": qty})
    T["inventory"] = inv

    T["suppliers"] = [
        {"supplier_id": "V1", "name": "Bengal Auto Components", "reliability": 0.94, "lead_time_days": 3, "restricted": 0, "defect_rate": 0.02},
        {"supplier_id": "V2", "name": "Eastern FastParts", "reliability": 0.71, "lead_time_days": 2, "restricted": 1, "defect_rate": 0.08},
        {"supplier_id": "V3", "name": "Prime OEM Kolkata", "reliability": 0.89, "lead_time_days": 5, "restricted": 0, "defect_rate": 0.015},
        {"supplier_id": "V4", "name": "Howrah Bearing Works", "reliability": 0.86, "lead_time_days": 4, "restricted": 0, "defect_rate": 0.03},
        {"supplier_id": "V5", "name": "Salt Lake Spares Hub", "reliability": 0.91, "lead_time_days": 2, "restricted": 0, "defect_rate": 0.025},
        {"supplier_id": "V6", "name": "National Brake Systems", "reliability": 0.96, "lead_time_days": 6, "restricted": 0, "defect_rate": 0.01},
        {"supplier_id": "V7", "name": "QuickMove Logistics Parts", "reliability": 0.68, "lead_time_days": 1, "restricted": 0, "defect_rate": 0.09},
        {"supplier_id": "V8", "name": "Metro Genuine Parts", "reliability": 0.92, "lead_time_days": 4, "restricted": 0, "defect_rate": 0.02},
    ]

    models = ["sedan", "suv", "hatch", "muv"]
    T["vehicle_records"] = [
        {
            "vehicle_id": f"VH{i:03d}",
            "vin": f"INANX{r.randint(100000,999999)}{i:03d}",
            "model": r.choice(models),
            "variant": r.choice(["Base", "Mid", "Top"]),
            "year": r.randint(2018, 2025),
            "dealership_id": r.choice(DEAL[:3]),
            "status": r.choice(["in_stock", "in_stock", "reserved", "sold"]),
            "days_in_inventory": r.randint(1, 120),
            "list_price": r.randint(650000, 2200000),
        }
        for i in range(30)
    ]

    skills = ["brakes", "engine", "electrical", "tyres", "ac"]
    T["technicians"] = [
        {
            "technician_id": f"T{i:02d}",
            "name": f"Tech {i:02d}",
            "dealership_id": DEAL[i % 3],
            "skills": "|".join(r.sample(skills, 2)),
            "shift": r.choice(["08-16", "10-18", "12-20"]),
            "available": 1,
        }
        for i in range(18)
    ]
    T["service_bays"] = [
        {
            "bay_id": f"B{i:02d}",
            "dealership_id": DEAL[i % 3],
            "available": 1,
            "bay_type": r.choice(["general", "quick", "heavy"]),
        }
        for i in range(12)
    ]

    ros = []
    ap = []
    for i in range(200):
        if i < 2:
            d, part, qty, pri = "DealerA", "P000", 2, 1
        else:
            d = r.choice(DEAL[:3])
            part = r.choice(parts)["part_id"]
            qty = r.randint(1, 4)
            pri = r.randint(1, 5)
        tech_pool = [t for t in T["technicians"] if t["dealership_id"] == d] or T["technicians"]
        tech = r.choice(tech_pool)["technician_id"]
        ros.append({
            "repair_order_id": f"RO{i:04d}",
            "dealership_id": d,
            "part_id": part,
            "qty": qty,
            "vehicle_id": f"VH{r.randint(0,29):03d}",
            "status": "open" if i < 40 else r.choice(["open", "in_progress", "closed"]),
            "priority": pri,
            "technician_id": tech,
            "customer_name": f"Customer {i:03d}",
        })
        if i < 30:
            bay_pool = [b for b in T["service_bays"] if b["dealership_id"] == d] or T["service_bays"]
            bay = r.choice(bay_pool)["bay_id"]
            ap.append({
                "appointment_id": f"AP{i:04d}",
                "repair_order_id": f"RO{i:04d}",
                "bay_id": bay,
                "start_hour": float(r.choice([8, 9, 10, 11, 13, 14, 15])),
                "duration_h": float(r.choice([1.5, 2.0, 2.5, 3.0])),
            })
    T["repair_orders"] = ros
    T["appointments"] = ap

    T["quotations"] = [
        {"quotation_id": f"Q{i}", "supplier_id": f"V{i}", "part_id": "P000", "unit_price": round(1800 + i * 120, 2), "lead_days": 2 + i, "valid_days": 14}
        for i in range(1, 7)
    ]
    T["purchase_orders"] = [
        {"po_id": "PO-001", "supplier_id": "V1", "part_id": "P000", "qty": 50, "status": "open", "value": 95000},
        {"po_id": "PO-002", "supplier_id": "V6", "part_id": "P003", "qty": 20, "status": "in_transit", "value": 42000},
        {"po_id": "PO-003", "supplier_id": "V3", "part_id": "P001", "qty": 100, "status": "received", "value": 28000},
    ]

    mv = []
    for i in range(120):
        a, b = r.sample(DEAL + WH, 2)
        mv.append({
            "movement_id": f"MV{i:04d}",
            "source": a,
            "destination": b,
            "part_id": r.choice(parts)["part_id"],
            "qty": r.randint(1, 10),
            "transaction_id": f"TX{i:05d}",
            "day_offset": -r.randint(0, 90),
        })
    T["inventory_movements"] = mv

    dl = []
    for i in range(60):
        a, b = r.sample(DEAL + WH, 2)
        dl.append({
            "delivery_id": f"DL{i:03d}",
            "source": a,
            "destination": b,
            "eta_hours": round(r.uniform(1, 10), 1),
            "status": r.choice(["delivered", "in_transit", "delayed"]),
        })
    T["deliveries"] = dl

    T["road_network"] = [
        {
            "from": a,
            "to": b,
            "distance_km": round(math.dist(NODES[a], NODES[b]), 2),
            "travel_cost": c,
            "travel_time_min": round(c / 40 * 60, 1),
        }
        for (a, b), c in edges().items()
    ]

    hd = []
    rng = random.Random(seed + 7)
    for k, d in enumerate(DEAL):
        sc, rr = PROFILE[d]
        for series_id in range(12):
            stock = rng.randint(5, 40)
            for day in range(120):
                demand = max(0.0, rng.gauss(sc * 1.5, 0.8))
                stock = max(0, int(stock - demand + rng.randint(0, 3)))
                stockout = 1 if stock <= 1 else 0
                hd.append({
                    "dealership_id": d,
                    "series_id": series_id,
                    "part_id": f"P{(series_id * 7) % 120:03d}",
                    "day": day,
                    "stock": stock,
                    "avg_demand": round(demand, 3),
                    "demand_std": round(abs(rng.gauss(0.5, 0.2)), 3),
                    "lead_time": rng.randint(2, 6),
                    "reliability": round(rng.uniform(*rr), 3),
                    "pending_ros": rng.randint(0, 5),
                    "season": round(0.5 + 0.5 * __import__("math").sin(day / 20), 3),
                    "incoming": rng.randint(0, 4),
                    "stockout_next7": stockout,
                })
    T["historical_demand"] = hd

    T["security_events"] = [
        {
            "event_id": f"SE{i:04d}",
            "account": "sup_x" if i >= 200 else r.choice(["mgr_a", "mgr_b", "buyer1", "sup_1"]),
            "action": r.choice(["stock_update", "purchase_request"]) if i >= 200 else r.choice(["login", "view", "login"]),
            "hour": 3 if i >= 200 else r.randint(8, 18),
            "ip": "203.0.113.9" if i >= 200 else "10.0.0.5",
            "is_attack": int(i >= 200),
        }
        for i in range(220)
    ]

    T["procurement_policies"] = [
        {"policy_id": "POL-1", "rule": "manager approval above", "limit": 50000},
        {"policy_id": "POL-2", "rule": "restricted supplier prohibited", "limit": 0},
        {"policy_id": "POL-3", "rule": "single PO max", "limit": 200000},
    ]
    T["documents"] = [
        {"document_id": "DOC000", "type": "invoice", "ref": "INV-9", "status": "mismatch"},
        {"document_id": "DOC001", "type": "purchase_order", "ref": "PO-001", "status": "validated"},
        {"document_id": "DOC002", "type": "contract", "ref": "C-1", "status": "validated"},
    ]

    T["part_skills"] = [
        {"part_name": "BrakePad", "skill": "brakes"},
        {"part_name": "OilFilter", "skill": "engine"},
        {"part_name": "BrakeRotor", "skill": "brakes"},
        {"part_name": "Battery", "skill": "electrical"},
        {"part_name": "WiperBlade", "skill": "general"},
        {"part_name": "SparkPlug", "skill": "engine"},
        {"part_name": "AirFilter", "skill": "engine"},
        {"part_name": "CabinFilter", "skill": "ac"},
        {"part_name": "ClutchKit", "skill": "engine"},
        {"part_name": "ShockAbsorber", "skill": "tyres"},
    ]

    for k, v in T.items():
        if v:
            w(out, k, v)
    return {k: len(v) for k, v in T.items()}


if __name__ == "__main__":
    print(generate())
