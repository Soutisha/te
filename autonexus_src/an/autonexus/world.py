"""Backend-driven operational world loaded from the current data-folder CSVs."""
import math
import os
from . import compliance, cybershield, optim, recovery
from .algorithms import astar, dijkstra, graph
from .audit import AuditChain
from .telemetry import load_world_dataset, planner_database, read_rows

AUTO = ["detected", "prediction", "agents", "searching", "supplier",
        "threat", "compliance", "route_planned"]
DWELL = {"detected": 2.5, "prediction": 2.5, "agents": 3, "searching": 4.5,
         "supplier": 2.5, "threat": 3, "compliance": 2.5, "route_planned": 2.5,
         "loaded": 2.5, "arrived": 2.5, "inventory_updated": 2.5, "tech_assigned": 5}
SPEED = 5.0
STOP = 6.5
_FED = None
_FED_MTIME = None


def federated_summary():
    """Run FedAvg over the currently configured historical-demand CSV."""
    global _FED, _FED_MTIME
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data",
                        "historical_demand.csv")
    modified = os.path.getmtime(path)
    if _FED is None or modified != _FED_MTIME:
        from . import federated
        result = federated.run(path)
        keys = ["label", "rounds", "clients", "federated", "centralised",
                "local_only_f1", "local_only_mean_f1", "fed_f1_curve",
                "central_f1_curve", "communication_bytes_federated",
                "raw_bytes_centralised", "privacy_note"]
        _FED = {key: result[key] for key in keys}
        _FED_MTIME = modified
    return _FED


def W(node, positions=None):
    if positions and node in positions:
        x, y = positions[node]
        return [round(x, 2), round(y, 2)]
    return [0.0, 0.0]


def pts(route, positions=None, destination=None):
    points = [W(node, positions) for node in route]
    if len(points) > 1:
        a, b = points[-2], points[-1]
        distance = math.dist(a, b)
        if distance > STOP * 2:
            ratio = (distance - STOP) / distance
            points[-1] = [a[0] + (b[0] - a[0]) * ratio,
                          a[1] + (b[1] - a[1]) * ratio]
    return points


def seglen(route, positions=None):
    points = pts(route, positions)
    return [math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)]


class World:
    def __init__(self, data_dir=None):
        self.data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        self.reset()

    def reset(self, destination=None, part=None, required_qty=None, source=None):
        previous = (getattr(self, "dest", None), getattr(self, "part", None),
                    getattr(self, "custom_required_qty", None),
                    getattr(self, "source_choice", None))
        preserve_selection = destination is None and part is None
        self.dataset = load_world_dataset(self.data_dir)
        self.db = planner_database(self.dataset)
        self.network = self.dataset["network"]
        site_rows = self.dataset["sites"]
        lons = [float(row["lon"]) for row in site_rows.values()]
        lats = [float(row["lat"]) for row in site_rows.values()]
        scale = 110 / max(max(lons) - min(lons) or 1, max(lats) - min(lats) or 1)
        mid_lon, mid_lat = (max(lons) + min(lons)) / 2, (max(lats) + min(lats)) / 2
        self.world_nodes = {
            site: ((float(row["lon"]) - mid_lon) * scale,
                   -(float(row["lat"]) - mid_lat) * scale)
            for site, row in site_rows.items()
        }

        dealers = self.dataset["dealerships"]
        if not dealers:
            raise ValueError("Telemetry dataset has no dealerships.")
        self.dest = destination if destination in dealers else (
            previous[0] if previous[0] in dealers else dealers[0])
        available_parts = sorted(self.dataset["parts"])
        if not available_parts:
            raise ValueError("Telemetry dataset has no parts.")
        self.part = part if part in available_parts else (
            previous[1] if previous[1] in available_parts else available_parts[0])
        matching_qty = sum(row["qty"] for row in self.db["ros"]
                           if row["dealer"] == self.dest and row["part"] == self.part)
        custom_qty = int(required_qty) if required_qty is not None else (
            previous[2] if preserve_selection and previous[0] == self.dest
            and previous[1] == self.part else None)
        self.custom_required_qty = custom_qty
        self.required_qty = custom_qty if custom_qty is not None else matching_qty
        if source is not None:
            self.source_choice = source if source in site_rows and source != self.dest else None
        else:
            self.source_choice = previous[3] if preserve_selection and previous[3] in site_rows and previous[3] != self.dest else None

        part_name = self.dataset["parts"][self.part]["name"]
        lowered = part_name.lower()
        if "brake" in lowered or "rotor" in lowered:
            self.skill = "brakes"
        elif "filter" in lowered or "oil" in lowered:
            self.skill = "engine"
        elif "tire" in lowered or "tyre" in lowered:
            self.skill = "tyres"
        elif "battery" in lowered or "elect" in lowered:
            self.skill = "electrical"
        else:
            counts = {}
            for technician in self.dataset["technicians"].values():
                for skill in technician["skills"]:
                    counts[skill] = counts.get(skill, 0) + 1
            self.skill = max(counts, key=counts.get) if counts else ""

        self.security_events = [
            {"t": i, "acct": row["account"], "action": row["action"],
             "hour": int(row["hour"]), "ip": row["ip"]}
            for i, row in enumerate(read_rows(self.data_dir, "security_events"))
            if int(row["is_attack"])
        ]
        self.bays = read_rows(self.data_dir, "service_bays")
        self.vendors = self.db["vendors"]
        self.scn = f"{self.dest}:{self.part}"
        self.au = AuditChain()
        self.phase = "idle"
        self.t0 = self.t = self.pt = 0.0
        self.seq = 0
        self.events = []
        self.blocked = []
        self.route = []
        self.prev_route = []
        self.progress = self.hold = 0.0
        self.src = None
        self.rtype = "truck"
        self.loaded = False
        self.mechs = {}
        self.search_lit = []
        self.suppliers = {key: "idle" for key in self.vendors}
        self.selected_vendor = None
        self.threat = {"active": False, "contained": False}
        self.approver = None
        self.cands = []
        self.cands_all = []
        self.sec = self.verified = self.comp = self.explore = self.transfer = None
        self.ro_status = {}
        self.assign = {}
        self.plan = None
        self.emit("idle", "World ready. Configure a destination and part, then press START.")

    def configure(self, destination, part, required_qty=None, source=None):
        if destination not in self.dataset["dealerships"]:
            return {"ok": False, "error": "Choose a dealership from the current telemetry data."}
        if part not in self.dataset["parts"]:
            return {"ok": False, "error": "Choose a part from the current telemetry data."}
        if required_qty is not None and required_qty <= 0:
            return {"ok": False, "error": "Required quantity must be greater than zero."}
        if source is not None and (source not in self.dataset["sites"] or source == destination):
            return {"ok": False, "error": "Choose a valid source site different from the destination."}
        self.reset(destination, part, required_qty, source)
        self.source_choice = source
        need = self.need()
        return {"ok": True, "destination": self.dest, "part": self.part,
                "required_qty": self.required_qty, "on_hand": need["have"],
                "shortage": need["shortage"]}

    def emit(self, kind, msg, **data):
        self.seq += 1
        self.events.append({"seq": self.seq, "t": round(self.t, 2),
                            "kind": kind, "msg": msg, **data})

    def _set(self, phase):
        self.phase = phase
        self.t0 = self.t

    def need(self):
        return recovery.detect(self.db, self.dest, self.part, self.required_qty)

    def _network_graph(self):
        return graph(self.blocked, nodes=self.network["nodes"],
                     edge_map=self.network["edge_map"])

    def _route_plan(self, blocked=None):
        return recovery.plan(self.db, self.dest, self.part,
                             self.blocked if blocked is None else blocked,
                             required_qty=self.required_qty, network=self.network)

    def start(self):
        if self.phase != "idle":
            return {"ok": False, "error": "The current journey is already active. Reset to configure another."}
        current = self.need()
        if current["shortage"] <= 0:
            return {"ok": False, "error": "No shortage in this dataset row. Raise required quantity or choose another part/site."}
        plan = self._route_plan()
        if not plan.get("options"):
            return {"ok": False, "error": "No source site has enough stock and a connected route for this shortage."}
        if self.source_choice and not any(o["source"] == self.source_choice for o in plan["options"]):
            return {"ok": False, "error": "The chosen source cannot satisfy this shortage using the current inventory and road network."}
        self.plan = plan
        self._set("detected")
        self.emit("shortage", f"Shortage at {self.dest}: need {current['need']}, "
                  f"have {current['have']} (short {current['shortage']})", site=self.dest)
        return {"ok": True}

    def approve(self, role):
        if self.phase != "awaiting_approval":
            return {"ok": False, "error": "No approval is pending."}
        if not compliance.allowed(role, "transfer:approve"):
            self.au.add(role, "approval_denied", self.src, "rejected")
            self.emit("approval_denied", "Approval refused: account is not authorized.")
            return {"ok": False, "error": "forbidden"}
        self.approver = role
        self.au.add(role, "transfer_approved", {"src": self.src, "route": self.route}, "approved")
        self.loaded = True
        self._set("loaded")
        self.emit("approved", f"Authorized approval. Package loaded onto {self.rtype}.")
        return {"ok": True}

    def reject(self, role="authorized_owner"):
        if self.phase != "awaiting_approval":
            return {"ok": False, "error": "No approval is pending."}
        self.au.add(role, "transfer_rejected", self.src, "rejected")
        self._set("rejected")
        self.emit("rejected", "Approval rejected. Delivery will NOT execute.")
        return {"ok": True}

    def block(self, edge=None):
        if self.phase != "in_transit" or self.hold > 0:
            return {"ok": False, "error": "No moving delivery is available for a road closure."}
        segment = self._seg()
        closed = tuple(edge) if edge else (self.route[segment], self.route[segment + 1])
        if closed not in self.network["edge_map"] and closed[::-1] not in self.network["edge_map"]:
            return {"ok": False, "error": "The requested road is not present in the current road-network data."}
        self.blocked.append(closed)
        self.prev_route = list(self.route)
        self.emit("road_blocked", f"Road {closed[0]}–{closed[1]} CLOSED", edge=list(closed))
        if (closed[0] in self.route and closed[1] in self.route
                and abs(self.route.index(closed[0]) - self.route.index(closed[1])) == 1
                and min(self.route.index(closed[0]), self.route.index(closed[1])) >= segment):
            new_route = dijkstra(self._network_graph(), self.route[segment], self.dest)
            if not new_route["path"]:
                self._set("stalled")
                self.emit("no_route", "No alternative route: delivery stalled.")
                return {"ok": True, "stalled": True}
            self.route = new_route["path"]
            self.progress = 0.0
            self.hold = 2.0
            self._explore(self.route[0])
            self.emit("route_recalculated", "New route: " + " > ".join(self.route),
                      route=self.route)
            self.au.add("system", "route_recalculated", self.route, "auto")
        return {"ok": True}

    def _fed_round(self):
        if self.phase == "idle":
            return 0
        if self.phase in AUTO:
            index = AUTO.index(self.phase)
            rounds = federated_summary()["rounds"]
            return int(rounds * (index + min(1, (self.t - self.t0) / DWELL[self.phase])) / len(AUTO))
        return federated_summary()["rounds"]

    def _explore(self, start):
        g = self._network_graph()
        positions = self.network["nodes"]
        a = astar(g, start, self.dest, positions=positions)
        d = dijkstra(g, start, self.dest)
        self.explore = {"from": start, "astar": a["visited"],
                        "dijkstra": d["visited"], "cost": a["cost"], "id": self.seq}

    def _seg(self):
        lengths = seglen(self.route, self.world_nodes)
        distance = self.progress * sum(lengths)
        for i, length in enumerate(lengths):
            if distance <= length + 1e-9:
                return i
            distance -= length
        return max(0, len(lengths) - 1)

    def pos(self):
        if not self.route:
            return None
        points = pts(self.route, self.world_nodes, self.dest)
        lengths = seglen(self.route, self.world_nodes)
        distance = self.progress * sum(lengths)
        for i, length in enumerate(lengths):
            if distance <= length or i == len(lengths) - 1:
                ratio = min(1, distance / length) if length else 1
                return [points[i][0] + (points[i + 1][0] - points[i][0]) * ratio,
                        points[i][1] + (points[i + 1][1] - points[i][1]) * ratio]
            distance -= length

    def tick(self, dt):
        self.t += dt
        if self.phase == "searching":
            interval = DWELL["searching"] / (len(self.cands_all) + 1)
            self.search_lit = self.cands_all[:int((self.t - self.t0) / interval)]
        if self.phase == "in_transit":
            if self.hold > 0:
                self.hold = max(0, self.hold - dt)
                return
            total = sum(seglen(self.route, self.world_nodes))
            self.progress = min(1.0, self.progress + SPEED * dt / total) if total else 1.0
            if self.progress >= 1.0:
                self._set("arrived")
                self.loaded = False
                self.emit("arrived", f"Delivery reached {self.dest}; package unloaded.")
                return
        if self.phase in DWELL and self.t - self.t0 >= DWELL[self.phase]:
            self._advance()

    def _advance(self):
        if self.phase == "detected":
            need = self.need()
            risk = round(need["shortage"] / max(need["need"], 1), 2)
            self._set("prediction")
            self.emit("prediction", f"Shortage exposure calculated from current demand: {risk:.0%}.",
                      risk=risk)
        elif self.phase == "prediction":
            self._set("agents")
            self.emit("agents", "Recovery, inventory, supplier, compliance and scheduling checks started.")
        elif self.phase == "agents":
            self.plan = self._route_plan()
            self.cands_all = [option["source"] for option in self.plan["options"]]
            if self.source_choice:
                self.cands_all = [site for site in self.cands_all if site == self.source_choice]
            self._set("searching")
            self.emit("searching", "Checking available source sites: " + ", ".join(self.cands_all))
        elif self.phase == "searching":
            options = self.plan["options"]
            if self.source_choice:
                options = [option for option in options if option["source"] == self.source_choice]
            best = min(options, key=lambda option: option["cost"])
            self.src = best["source"]
            self.rtype = "scooter" if self.dataset["sites"][self.src]["kind"] == "dealer" else "truck"
            self.route = best["route"]
            self.cands = options
            self._explore(self.src)
            safe_vendors = [(key, vendor) for key, vendor in self.vendors.items()
                            if not vendor["restricted"]]
            self.selected_vendor = max(safe_vendors, key=lambda item: item[1]["reliability"])[0] if safe_vendors else None
            if self.selected_vendor:
                self.suppliers[self.selected_vendor] = "selected"
            restricted = [key for key, vendor in self.vendors.items() if vendor["restricted"]]
            if restricted:
                self.suppliers[restricted[0]] = "flagged"
            self._set("supplier")
            self.emit("supplier", f"Source selected: {self.src}. "
                      + (f"Eligible supplier: {self.selected_vendor}." if self.selected_vendor
                         else "No eligible supplier is listed in the dataset."),
                      src=self.src, vendor=self.selected_vendor)
        elif self.phase == "supplier":
            self.sec = cybershield.analyse(self.security_events)
            self.threat = {"active": bool(self.sec["risk"]), "contained": False,
                           "account": self.security_events[0]["acct"] if self.security_events else None}
            self._set("threat")
            self.emit("threat", f"Security risk calculated from telemetry events: {self.sec['risk']}.",
                      account=self.threat["account"])
        elif self.phase == "threat":
            self.threat["contained"] = bool(self.sec["contained"])
            account = self.threat.get("account") or "telemetry"
            if self.threat["contained"]:
                self.au.add("cybershield", "account_contained", account, "auto")
            restricted = [key for key, vendor in self.vendors.items() if vendor["restricted"]]
            candidate = restricted[0] if restricted else self.selected_vendor
            if candidate:
                quote = next((row for row in read_rows(self.data_dir, "quotations")
                              if row["supplier_id"] == candidate and row["part_id"] == self.part), None)
                amount = float(quote["unit_price"]) * self.need()["shortage"] if quote else 0
                check = compliance.check_vendor(self.vendors, candidate, amount)
                self.comp = {"checked": candidate, **check}
            else:
                self.comp = {"checked": None, "approved": False,
                             "reasons": ["No suppliers are available in the telemetry dataset."]}
            self._set("compliance")
            self.emit("compliance", "Supplier policy check completed: "
                      + (", ".join(self.comp["reasons"]) if self.comp["reasons"]
                         else "no policy violation found."))
        elif self.phase == "compliance":
            self._set("route_planned")
            self.emit("route_planned", f"Shortest feasible route: {' > '.join(self.route)}.",
                      route=self.route)
        elif self.phase == "route_planned":
            self._set("awaiting_approval")
            self.emit("approval_requested", "Authorized owner approval required; delivery is held.")
        elif self.phase == "loaded":
            self.progress = 0.0
            self._set("in_transit")
            self.emit("in_transit", "Approved delivery started.")
        elif self.phase == "arrived":
            self.plan["best"] = {**self.plan["best"], "source": self.src,
                                 "route": self.route[:-1] + [self.dest]}
            self.plan["best"]["qty"] = self.plan["shortage"]["shortage"]
            before = self.db["stock"][self.src].get(self.part, 0)
            result = recovery.execute(self.db, self.plan, self.approver, self.au)
            self.transfer = {"from": self.src, "to": self.dest,
                             "qty": before - self.db["stock"][self.src][self.part]}
            self._set("inventory_updated")
            self.emit("inventory_updated", "In-memory scenario inventory updated"
                      + ("" if result.get("ok") else ": " + str(result.get("error"))),
                      ok=result.get("ok"))
        elif self.phase == "inventory_updated":
            repairs = [row for row in self.db["ros"]
                       if row["dealer"] == self.dest and row["part"] == self.part
                       and row["status"].lower() in {"open", "pending"}]
            jobs = [(row["id"], self.skill, row["priority"]) for row in repairs]
            technicians = {key: value["skills"] for key, value in self.dataset["technicians"].items()
                           if value["site"] == self.dest and value["available"]}
            assigned = optim.assign(technicians, jobs)
            self.assign = dict(assigned)
            available_bays = [row for row in self.bays
                              if row["dealership_id"] == self.dest and int(row["available"])]
            self.mechs = {technician: index for index, technician in enumerate(assigned.values())
                          if index < len(available_bays)}
            for repair_id in assigned:
                self.ro_status[repair_id] = "in_progress"
            self._set("tech_assigned")
            self.emit("tech_assigned", "Compatible technicians assigned: "
                      + (", ".join(f"{tech} → bay {i + 1}" for tech, i in self.mechs.items())
                         if self.mechs else "no available matching technician/bay in the dataset."))
        elif self.phase == "tech_assigned":
            self.verified = self.need()["shortage"] == 0
            self._set("recovered")
            self.emit("recovered", f"Recovery verified: {self.verified}. "
                      f"Audit chain valid: {self.au.verify()}.")

    def state(self):
        shortage = self.need()
        rider_position = self.pos() if self.phase in (
            "loaded", "in_transit", "arrived", "stalled") else (
                W(self.src, self.world_nodes) if self.src and self.phase == "loaded" else None)
        parts = [
            {"id": key, "name": value["name"],
             "stock_at_destination": self.db["stock"][self.dest].get(key, 0),
             "repair_demand": sum(row["qty"] for row in self.db["ros"]
                                  if row["dealer"] == self.dest and row["part"] == key)}
            for key, value in sorted(self.dataset["parts"].items())
        ]
        matching_ros = [row for row in self.db["ros"]
                        if row["dealer"] == self.dest and row["part"] == self.part]
        techs = {key: sorted(value["skills"]) for key, value in self.dataset["technicians"].items()
                 if value["site"] == self.dest}
        bays = [{"id": row["bay_id"], "available": bool(int(row["available"]))}
                for row in self.bays if row["dealership_id"] == self.dest]
        return {
            "phase": self.phase, "t": round(self.t, 2), "pt": round(self.t - self.t0, 2),
            "scenario": self.scn, "destination": self.dest, "part": self.part,
            "part_name": self.dataset["parts"][self.part]["name"], "skill": self.skill,
            "required_qty": self.required_qty, "source_choice": self.source_choice,
            "fed_round": self._fed_round(), "destinations": self.dataset["dealerships"],
            "parts": parts, "sites": [{"id": key, "name": value["name"], "kind": value["kind"]}
                                      for key, value in self.dataset["sites"].items()],
            "vendors": {key: {**value, "status": self.suppliers.get(key, "idle")}
                        for key, value in self.vendors.items()},
            "selected_vendor": self.selected_vendor, "compliance": self.comp, "sec": self.sec,
            "transfer": self.transfer, "explore": self.explore, "assign": self.assign,
            "ros": [{"id": row["id"], "priority": row["priority"],
                     "tech": self.assign.get(row["id"]),
                     "bay": list(self.assign).index(row["id"]) if row["id"] in self.assign else None,
                     "status": self.ro_status.get(row["id"], row["status"])}
                    for row in matching_ros],
            "techs": techs, "bays": bays, "events": self.events[-40:],
            "nodes": {node: W(node, self.world_nodes) for node in self.network["nodes"]},
            "edges": [list(edge) for edge in self.network["edge_map"]],
            "blocked": [list(edge) for edge in self.blocked],
            "route": [{"n": node, "xy": W(node, self.world_nodes)} for node in self.route],
            "prev_route": self.prev_route, "progress": round(self.progress, 4),
            "hold": self.hold > 0,
            "rider": {"visible": self.phase in ("loaded", "in_transit", "arrived", "stalled"),
                      "xy": rider_position, "loaded": self.loaded, "type": self.rtype,
                      "moving": self.phase == "in_transit" and self.hold <= 0},
            "stock": {site: qty.get(self.part, 0) for site, qty in self.db["stock"].items()},
            "shortage": shortage["shortage"], "need": shortage["need"],
            "search_lit": self.search_lit, "cands": self.cands_all,
            "suppliers": self.suppliers, "threat": self.threat,
            "approval_pending": self.phase == "awaiting_approval",
            "mechs": self.mechs, "ro_status": self.ro_status, "src": self.src,
            "dest": self.dest, "required_qty": self.required_qty,
            "audit": {"records": len(self.au.rec), "valid": self.au.verify()},
            "verified": self.verified,
            "agents_active": self.phase in (
                "agents", "searching", "supplier", "threat", "compliance",
                "route_planned", "awaiting_approval", "loaded", "in_transit",
                "arrived", "inventory_updated", "tech_assigned"),
        }
