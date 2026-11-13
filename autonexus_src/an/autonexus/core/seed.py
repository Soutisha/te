"""Load the CSV dataset into the shared database with recorded provenance.
CSV files are never claimed to be verified operational data: DATA_PROVENANCE=synthetic -> SYNTHETIC,
anything else -> IMPORTED (declared by the operator, not verified by AUTONEXUS)."""
import os
from pathlib import Path
from sqlalchemy import select, func
from .. import config
from ..telemetry import read_rows
from . import models as m, audit, events
from .db import write

DATA = Path(__file__).resolve().parents[2] / "data"

def provenance():
    return "SYNTHETIC" if config.get("DATA_PROVENANCE", "synthetic").strip().lower() == "synthetic" else "IMPORTED"

def _f(r, *keys, default=None, cast=None):
    for k in keys:
        if k in r and r[k] not in (None, ""):
            v = r[k]
            return cast(v) if cast else v
    return default

def load_csv_dataset(data_dir=DATA, actor="system:seed"):
    """Idempotent: does nothing if the database already holds sites."""
    with write() as s:
        if s.scalar(select(func.count()).select_from(m.Site)):
            return {"seeded": False}
        prov = provenance(); R = lambda t: read_rows(data_dir, t); counts = {}
        def put(table, rows, src):
            s.add_all(rows); s.flush(); counts[table] = len(rows)
            s.merge(m.DataSource(table_name=table, provenance=prov, source=f"{src}.csv", rows=len(rows)))
        put("sites", [m.Site(id=r["dealership_id"], kind="dealer", name=r["name"], lat=float(r["lat"]), lon=float(r["lon"])) for r in R("dealerships")]
            + [m.Site(id=r["warehouse_id"], kind="warehouse", name=r["name"], lat=float(r["lat"]), lon=float(r["lon"])) for r in R("warehouses")], "dealerships+warehouses")
        put("parts", [m.Part(id=r["part_id"], name=r["name"], unit_price=float(r["unit_price"]), compatible_models=r.get("compatible_models", "")) for r in R("parts")], "parts")
        put("part_skills", [m.PartSkill(part_name=r["part_name"], skill=_f(r, "required_skill", "skill", default="general")) for r in R("part_skills")], "part_skills")
        stock = {}
        for r in R("inventory"):
            stock[(r["site_id"], r["part_id"])] = stock.get((r["site_id"], r["part_id"]), 0) + int(r["qty"])
        put("stock", [m.Stock(site_id=k[0], part_id=k[1], on_hand=v, reserved=0) for k, v in stock.items()], "inventory")
        s.add_all([m.Movement(kind="seed", site_id=k[0], part_id=k[1], delta=v, idempotency_key=f"seed:{k[0]}:{k[1]}", actor=actor) for k, v in stock.items()])
        put("suppliers", [m.Supplier(id=r["supplier_id"], name=r["name"], reliability=float(r["reliability"]), lead_time_days=int(r["lead_time_days"]), restricted=bool(int(r.get("restricted", 0)))) for r in R("suppliers")], "suppliers")
        put("quotations", [m.Quotation(
            id=r["quotation_id"], supplier_id=r["supplier_id"], part_id=r["part_id"],
            unit_price=float(r["unit_price"]),
            delivery_days=int(_f(r, "delivery_days", "lead_days", default=3))
        ) for r in R("quotations")], "quotations")
        put("purchase_orders", [m.PurchaseOrder(
            id=r["po_id"], supplier_id=r["supplier_id"], part_id=r["part_id"], qty=int(r["qty"]),
            amount=float(_f(r, "amount", "value", default=0)),
            status=_f(r, "status", default="imported"),
            approved_by=_f(r, "approved_by", default=""),
            repair_order_id=_f(r, "repair_order_id", default="")
        ) for r in R("purchase_orders")], "purchase_orders")
        put("demand_history", [m.DemandHistory(
            dealer_id=r["dealership_id"], part_id=r["part_id"], day=int(r["day"]),
            demand=float(r["avg_demand"]), demand_std=float(r.get("demand_std") or 0),
            lead_time=int(r.get("lead_time") or 3)
        ) for r in R("historical_demand")], "historical_demand")
        put("repair_orders", [m.RepairOrder(
            id=r["repair_order_id"], dealer_id=r["dealership_id"], vehicle_id=r.get("vehicle_id") or "",
            part_id=r["part_id"], qty=int(r["qty"]), technician_id=r.get("technician_id") or "",
            priority=int(r.get("priority") or 3), status=r.get("status") or "open"
        ) for r in R("repair_orders")], "repair_orders")
        put("vehicles", [m.Vehicle(
            id=r["vehicle_id"], model=r.get("model") or "sedan", year=int(r.get("year") or 2020),
            dealer_id=r["dealership_id"]
        ) for r in R("vehicle_records")], "vehicle_records")
        put("technicians", [m.Technician(
            id=r["technician_id"], dealer_id=r["dealership_id"], skills=r.get("skills") or "",
            shift=r.get("shift") or "08-16", available=bool(int(r.get("available", 1)))
        ) for r in R("technicians")], "technicians")
        put("service_bays", [m.ServiceBay(
            id=r["bay_id"], dealer_id=r["dealership_id"], available=bool(int(r.get("available", 1)))
        ) for r in R("service_bays")], "service_bays")
        put("appointments", [m.Appointment(
            id=r["appointment_id"], repair_order_id=r["repair_order_id"], bay_id=r["bay_id"],
            start_hour=float(r["start_hour"]), duration_h=float(r["duration_h"])
        ) for r in R("appointments")], "appointments")
        put("road_edges", [m.RoadEdge(
            a=r["from"], b=r["to"], distance_km=float(r["distance_km"]),
            cost=float(r["travel_cost"]), time_min=float(r["travel_time_min"])
        ) for r in R("road_network")], "road_network")
        put("policies", [m.Policy(id=r["policy_id"], rule=r["rule"], limit=float(r["limit"])) for r in R("procurement_policies")], "procurement_policies")
        put("security_events", [m.SecurityEvent(
            id=r["event_id"], account=r["account"], action=r["action"],
            hour=int(r["hour"]), ip=r["ip"], is_attack=bool(int(r.get("is_attack", 0)))
        ) for r in R("security_events")], "security_events")
        audit.add(s, actor, "dataset.seeded", {"tables": counts, "provenance": prov})
        events.emit(s, "dataset.seeded", {"tables": counts, "provenance": prov})
        return {"seeded": True, "tables": counts, "provenance": prov}
