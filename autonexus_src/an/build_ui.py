"""Build static algorithm demos and the Living World from the current CSV dataset."""
import json
import os

from autonexus.algorithms import astar, dijkstra, graph
from autonexus.recovery import plan
from autonexus.telemetry import load_world_dataset, planner_database


ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
UI = os.path.join(ROOT, "ui")
dataset = load_world_dataset(DATA)
db = planner_database(dataset)

selected = None
for destination in dataset["dealerships"]:
    for part in dataset["parts"]:
        demand = sum(row["qty"] for row in db["ros"]
                    if row["dealer"] == destination and row["part"] == part)
        planned = plan(db, destination, part, required_qty=demand,
                       network=dataset["network"])
        if planned.get("best") and planned["shortage"]["shortage"] > 0:
            selected = destination, part, demand, planned
            break
    if selected:
        break
if not selected:
    raise RuntimeError("The current CSV dataset has no feasible shortage route to visualize.")

destination, part, demand, first = selected
route = first["best"]["route"]
rerouted = None
blocked = None
for edge in zip(route, route[1:]):
    candidate = plan(db, destination, part, [edge], required_qty=demand,
                     network=dataset["network"])
    if candidate.get("best") and candidate["best"]["route"] != route:
        rerouted, blocked = candidate, edge
        break
if rerouted is None:
    raise RuntimeError("The current route network has no alternate path for the selected shortage.")

network = dataset["network"]
source = route[0]
target = route[-1]
path_graph = graph(nodes=network["nodes"], edge_map=network["edge_map"])
normal = {
    "dijkstra": dijkstra(path_graph, source, target),
    "astar": astar(path_graph, source, target, positions=network["nodes"]),
}
blocked_graph = graph([blocked], nodes=network["nodes"], edge_map=network["edge_map"])
rerouted_paths = {
    "dijkstra": dijkstra(blocked_graph, source, target),
    "astar": astar(blocked_graph, source, target, positions=network["nodes"]),
}

longitudes = [point[0] for point in network["nodes"].values()]
latitudes = [point[1] for point in network["nodes"].values()]
lon_range = max(longitudes) - min(longitudes) or 1
lat_range = max(latitudes) - min(latitudes) or 1
nodes = {
    site: (5 + 30 * (point[0] - min(longitudes)) / lon_range,
           3 + 14 * (point[1] - min(latitudes)) / lat_range)
    for site, point in network["nodes"].items()
}
edges = [list(edge) for edge in network["edge_map"]]
normal_data = {"nodes": nodes, "edges": edges, "src": source, "dst": target,
               "blocked": list(blocked), "normal": normal, "rerouted": rerouted_paths}
with open(os.path.join(UI, "template.html"), encoding="utf-8") as stream:
    html = stream.read().replace("__DATA__", json.dumps(normal_data))
with open(os.path.join(UI, "index.html"), "w", encoding="utf-8") as stream:
    stream.write(html)

twin_data = {
    "nodes": nodes,
    "edges": edges,
    "first": route,
    "second": rerouted["best"]["route"],
    "stock": {site: values.get(part, 0) for site, values in db["stock"].items()},
    "destination": destination,
    "part": part,
    "part_name": dataset["parts"][part]["name"],
}
for template, output in [("twin_template.html", "twin.html"),
                         ("twin3d_template.html", "twin3d.html")]:
    with open(os.path.join(UI, template), encoding="utf-8") as stream:
        html = stream.read().replace("__DATA__", json.dumps(twin_data))
    with open(os.path.join(UI, output), "w", encoding="utf-8") as stream:
        stream.write(html)

# Living World: offline Three.js and GSAP are inlined; scripts are concatenated in dependency order.
modules = ["core", "chars", "v_overview", "v_inventory", "v_suppliers",
           "v_cyber", "v_sched", "v_route", "v_fed", "main"]
application = "\n".join(
    open(os.path.join(UI, "world_src", f"{module}.js"), encoding="utf-8").read()
    for module in modules
)
with open(os.path.join(UI, "world_template.html"), encoding="utf-8") as stream:
    template = stream.read()
with open(os.path.join(ROOT, "vendor", "three.min.js"), encoding="utf-8") as stream:
    three = stream.read()
with open(os.path.join(ROOT, "vendor", "gsap.min.js"), encoding="utf-8") as stream:
    gsap = stream.read()
with open(os.path.join(UI, "world.html"), "w", encoding="utf-8") as stream:
    stream.write(template.replace("__THREE__", three)
                 .replace("__GSAP__", gsap).replace("__APP__", application))
