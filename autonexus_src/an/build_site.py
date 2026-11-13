"""Build the visual site from the current CSV dataset; never generate sample rows."""
import hashlib
import json
import os

from autonexus import cybershield, evaluation, federated, optim, recovery
from autonexus.telemetry import load_world_dataset, planner_database, read_rows


ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
UI = os.path.join(ROOT, "ui")
dataset = load_world_dataset(DATA)
db = planner_database(dataset)

chosen = None
for destination in dataset["dealerships"]:
    for part in dataset["parts"]:
        demand = sum(row["qty"] for row in db["ros"]
                    if row["dealer"] == destination and row["part"] == part)
        planned = recovery.plan(db, destination, part, required_qty=demand,
                                network=dataset["network"])
        if planned.get("best") and planned["shortage"]["shortage"] > 0:
            chosen = destination, part, demand, planned
            break
    if chosen:
        break
if not chosen:
    raise RuntimeError("The current CSV dataset has no feasible shortage route to visualize.")

destination, part, demand, first = chosen
best = first["best"]
second = None
closed = None
for edge in zip(best["route"], best["route"][1:]):
    candidate = recovery.plan(db, destination, part, [edge], required_qty=demand,
                              network=dataset["network"])
    if candidate.get("best") and candidate["best"]["route"] != best["route"]:
        second, closed = candidate, edge
        break
if second is None:
    raise RuntimeError("The current route network has no alternate route for the selected shortage.")

part_name = dataset["parts"][part]["name"]
skill_by_name = {
    "brake": "brakes", "rotor": "brakes", "filter": "engine",
    "oil": "engine", "battery": "electrical", "tire": "tyres",
}
skill = next((value for word, value in skill_by_name.items()
              if word in part_name.lower()), None)
technicians = {
    key: value["skills"]
    for key, value in dataset["technicians"].items()
    if value["site"] == destination and value["available"]
}
if skill is None:
    counts = {}
    for skills in technicians.values():
        for value in skills:
            counts[value] = counts.get(value, 0) + 1
    skill = max(counts, key=counts.get) if counts else ""

repair_orders = [row for row in db["ros"]
                 if row["dealer"] == destination and row["part"] == part
                 and row["status"].lower() in {"open", "pending"}][:5]
raw = optim.assign(
    technicians,
    [(row["id"], skill, row["priority"]) for row in repair_orders],
)
technician_ids = list(technicians)
available_bays = [
    row for row in read_rows(DATA, "service_bays")
    if row["dealership_id"] == destination and int(row["available"])
]
assign = [
    {"ro": repair_id, "tech": technician, "ti": technician_ids.index(technician),
     "bay": index}
    for index, (repair_id, technician) in enumerate(raw.items())
    if index < len(available_bays)
]

fed_result = federated.run(os.path.join(DATA, "historical_demand.csv"))
fed = {key: fed_result[key] for key in [
    "rounds", "clients", "federated", "centralised", "local_only_f1",
    "local_only_mean_f1", "fed_f1_curve", "central_f1_curve",
    "communication_bytes_federated",
]}
security_events = read_rows(DATA, "security_events")
hashes = [
    hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:6]
    for row in security_events[:9]
]
site_rows = dataset["sites"]
bay_rows = read_rows(DATA, "service_bays")
payload = {
    "nodes": dataset["network"]["nodes"],
    "edges": [list(edge) for edge in dataset["network"]["edge_map"]],
    "first": best["route"],
    "second": second["best"]["route"],
    "closed": list(closed),
    "cost1": best["cost"],
    "cost2": second["best"]["cost"],
    "stock": {site: values.get(part, 0) for site, values in db["stock"].items()},
    "need": first["shortage"]["shortage"],
    "destination": destination,
    "part": part,
    "part_name": part_name,
    "sites": site_rows,
    "bays": [int(row["available"]) for row in bay_rows
             if row["dealership_id"] == destination],
    "assign": assign,
    "assignRaw": raw,
    "fed": fed,
    "ev": evaluation.compare(30),
    "sec": cybershield.analyse(cybershield.simulate_attack()),
    "hashes": hashes,
    "provenance": "SYNTHETIC SAMPLE DATA",
}

with open(os.path.join(UI, "site_template.html"), encoding="utf-8") as stream:
    template = stream.read()
with open(os.path.join(UI, "site.html"), "w", encoding="utf-8") as stream:
    html = (template
            .replace("__LENIS__", open(os.path.join(ROOT, "vendor", "lenis.min.js"),
                                       encoding="utf-8").read())
            .replace("__DATA__", json.dumps(payload)))
    stream.write(html)
print("site.html", len(html) // 1024, "KB")
