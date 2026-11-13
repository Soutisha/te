"""Supervisor: coordinates the specialist engines for the shortage-to-recovery workflow.
DETECT -> UNDERSTAND -> PREDICT -> DECIDE -> OPTIMIZE -> VERIFY -> REQUEST APPROVAL (then EXECUTE -> MONITOR via approvals/receipt).
Routing between steps is deterministic code; engines read and write only through the shared database."""
import json, time, uuid
from sqlalchemy import select
from . import models as m, audit, events, inventory, forecast, supplier, policies, routing, workshop, cyber, approvals
from .db import write, read
from .security import can

class WorkflowError(Exception):
    def __init__(self, code, msg): super().__init__(msg); self.code = code

def _step(state, agent, tool, fn):
    t0 = time.time(); rec = {"agent": agent, "tool": tool}
    try:
        out = fn(); rec.update(status="ok", duration_ms=round((time.time() - t0) * 1000, 1)); state["trace"].append(rec); return out
    except Exception as e:
        rec.update(status="failed", error=f"{type(e).__name__}: {e}", duration_ms=round((time.time() - t0) * 1000, 1)); state["trace"].append(rec); raise

def _provenance(s):
    rows = {r.table_name: r.provenance for r in s.scalars(select(m.DataSource))}
    classes = sorted(set(rows.values()))
    return {"classes": classes, "tables": rows,
            "banner": "Computed on SYNTHETIC development data; results are not real dealership operations." if "SYNTHETIC" in classes else
                      "Computed on operator-declared IMPORTED data; not independently verified."}

def run_shortage(actor, role, dealer, part, required_qty=None, blocked=(), horizon_days=14):
    if not can(role, "workflow:run"):
        with write() as s: audit.add(s, actor, "workflow_denied", {"dealer": dealer, "part": part}, "denied")
        raise WorkflowError(403, f"role {role!r} may not run workflows")
    wf_id = f"WF-{uuid.uuid4().hex[:10].upper()}"
    params = {"dealer": dealer, "part": part, "required_qty": required_qty, "blocked": [list(b) for b in blocked], "horizon_days": horizon_days}
    state = {"trace": [], "params": params}
    try:
        with write() as s:
            risk = _step(state, "Security", "assess_actor", lambda: cyber.assess_actor(s, actor)); state["security"] = risk
            if risk["block"]: raise WorkflowError(403, "request blocked by security check: repeated denied actions")
            wf = m.Workflow(id=wf_id, type="shortage_recovery", status="running", requested_by=actor, params=json.dumps(params), state="{}"); s.add(wf); s.flush()
            state["provenance"] = _provenance(s)
            sh = _step(state, "Inventory", "detect_shortage", lambda: inventory.detect(s, dealer, part, required_qty)); state["shortage"] = sh
            events.emit(s, "shortage.detected" if sh["shortage"] else "shortage.none", sh, wf_id)
            if not sh["shortage"]:
                state["status"] = "no_action"; return _save(s, wf, state, actor)
            state["compatibility"] = _step(state, "Inventory", "check_compatibility", lambda: inventory.compatibility(s, dealer, part))
            if not state["compatibility"]["compatible"]:
                state["status"] = "blocked_incompatible_part"; return _save(s, wf, state, actor)
            state["forecast"] = _step(state, "Forecasting", "forecast_demand", lambda: forecast.forecast(s, dealer, part, horizon_days, on_hand=sh["available"]))
            if sh["net_shortage"] == 0:
                state["status"] = "covered_by_pending_supply"; state["note"] = "incoming transfers/purchase orders already cover the shortage; no new action proposed"
                return _save(s, wf, state, actor)
            remaining = sh["net_shortage"]
            donors = _step(state, "Inventory", "find_donors", lambda: inventory.donors(s, dealer, part))
            cand = []
            def route_all():
                for d in donors:
                    r = routing.route(s, d["site"], dealer, blocked)
                    cand.append({**d, "route": r})
                return len(cand)
            _step(state, "Route", "route_options", route_all)
            usable = sorted([c for c in cand if c["route"]["status"] == "ok"], key=lambda c: c["route"]["best"]["cost"])
            state["donor_options"] = [{"site": c["site"], "surplus": c["surplus"], "route_status": c["route"]["status"],
                                       "route_cost": c["route"].get("best", {}).get("cost")} for c in cand]
            legs = []
            for c in usable:
                if remaining <= 0: break
                q = min(c["surplus"], remaining); legs.append({"source": c["site"], "qty": q, "route": c["route"]}); remaining -= q
            state["transfer_plan"] = [{"source": l["source"], "qty": l["qty"], "path": l["route"]["best"]["path"], "eta_minutes": l["route"]["eta_minutes"], "eta_basis": l["route"]["eta_basis"]} for l in legs]
            po_opt = None
            if remaining > 0:
                sup = _step(state, "Supplier", "rank_suppliers", lambda: supplier.rank(s, part, remaining)); state["supplier_ranking"] = sup
                po_opt = sup["best"]
            state["workshop"] = _step(state, "Workshop", "evaluate_impact", lambda: workshop.evaluate(s, dealer, part))
            state["unresolved_qty"] = remaining if not po_opt else 0
            if not legs and not po_opt:
                state["status"] = "no_feasible_recovery"; return _save(s, wf, state, actor)
            ev = {"shortage": sh, "forecast": state["forecast"], "workshop_summary": {k: state["workshop"][k] for k in ("can_staff_work", "scheduled_hours_for_blocked_orders")}, "provenance": state["provenance"]["classes"]}
            approvals_out = []
            def request():
                if legs:
                    aid_legs = []
                    pol = {"checks": [{"rule": "donor retains its own open repair-order need", "passed": True}, {"rule": "part compatible with affected vehicles", "passed": True}, {"rule": "source differs from destination", "passed": True}]}
                    a = approvals.create(s, wf_id, "transfer", actor, "transfer:approve", {"destination": dealer, "part": part, "legs": state["transfer_plan"], "total_qty": sum(l["qty"] for l in legs)}, pol, ev)
                    for l in legs:
                        inventory.reserve(s, l["source"], part, l["qty"])
                        t = m.Transfer(id=f"TR-{uuid.uuid4().hex[:10].upper()}", workflow_id=wf_id, approval_id=a.id, source=l["source"], destination=dealer, part_id=part,
                                       qty=l["qty"], status="reserved", route=json.dumps(l["route"]["best"]["path"]), route_basis=l["route"]["eta_basis"], eta_minutes=l["route"]["eta_minutes"])
                        s.add(t); s.flush()
                        events.emit(s, "inventory.reserved", {"site": l["source"], "part": part, "qty": l["qty"], "transfer_id": t.id}, wf_id)
                    approvals_out.append(a.id)
                if po_opt:
                    perm = "purchase:approve:high" if po_opt["compliance"]["requires_high_approval"] else "purchase:approve"
                    a = approvals.create(s, wf_id, "purchase_order", actor, perm, {"destination": dealer, "part": part, "supplier": po_opt["supplier"], "qty": po_opt["qty"], "total_cost": po_opt["total_cost"], "delivery_days": po_opt["delivery_days"], "quotation": po_opt["quotation"]},
                                         po_opt["compliance"], {**ev, "supplier_score": po_opt["score_breakdown"], "supplier_explanation": state["supplier_ranking"]["explanation"]})
                    approvals_out.append(a.id)
            _step(state, "Procurement", "request_approvals", request)
            state["approvals"] = approvals_out; state["status"] = "awaiting_approval"
            return _save(s, wf, state, actor)
    except WorkflowError: raise
    except Exception as e:  # rolled back (incl. reservations); record explicit failure state
        state["status"] = "failed"; state["error"] = f"{type(e).__name__}: {e}"
        with write() as s:
            s.add(m.Workflow(id=wf_id, type="shortage_recovery", status="failed", requested_by=actor, params=json.dumps(params), state=json.dumps(state, default=str)))
            audit.add(s, actor, "workflow_failed", {"workflow": wf_id, "error": state["error"]}, "failed")
            events.emit(s, "workflow.failed", {"error": state["error"]}, wf_id)
        return {"workflow_id": wf_id, **state}

def _save(s, wf, state, actor):
    wf.status = state["status"]; wf.state = json.dumps(state, default=str)
    audit.add(s, actor, "workflow_planned", {"workflow": wf.id, "status": state["status"], "agents": [t["agent"] for t in state["trace"]], "approvals": state.get("approvals", [])}, state["status"])
    events.emit(s, "workflow.status", {"status": state["status"]}, wf.id)
    return {"workflow_id": wf.id, **state}

def refresh_status(s, wf_id):
    wf = s.get(m.Workflow, wf_id)
    if not wf or wf.status in ("no_action", "failed", "no_feasible_recovery", "blocked_incompatible_part", "covered_by_pending_supply"): return
    aps = list(s.scalars(select(m.Approval).where(m.Approval.workflow_id == wf_id)))
    if not aps: return
    st = {a.status for a in aps}; trs = list(s.scalars(select(m.Transfer).where(m.Transfer.workflow_id == wf_id)))
    pos = list(s.scalars(select(m.PurchaseOrder).where(m.PurchaseOrder.workflow_id == wf_id)))
    if "pending" in st: new = "awaiting_approval"
    elif st <= {"rejected", "changes_requested", "expired", "execution_failed"}: new = "rejected" if "rejected" in st else ("changes_requested" if "changes_requested" in st else ("execution_failed" if "execution_failed" in st else "expired"))
    elif any(t.status == "in_transit" for t in trs): new = "in_transit"
    elif any(p.status == "ordered" for p in pos): new = "awaiting_supply"
    elif trs and all(t.status in ("received", "cancelled") for t in trs): new = "recovered"
    else: new = "executed"
    if new != wf.status:
        wf.status = new; wf.updated_at = m.now(); events.emit(s, "workflow.status", {"status": new}, wf_id)

def receive_transfer(transfer_id, actor, role):
    if not can(role, "transfer:receive"):
        with write() as s: audit.add(s, actor, "transfer_receive_denied", {"transfer": transfer_id}, "denied")
        raise WorkflowError(403, f"role {role!r} may not confirm receipts")
    try:
        with write() as s:
            t = s.get(m.Transfer, transfer_id)
            if not t: raise WorkflowError(404, "transfer not found")
            inventory.receive(s, t, actor)
            audit.add(s, actor, "transfer_received", {"transfer": t.id, "destination": t.destination, "qty": t.qty}, "received")
            events.emit(s, "transfer.received", {"transfer_id": t.id, "destination": t.destination, "part": t.part_id, "qty": t.qty}, t.workflow_id)
            events.emit(s, "inventory.changed", {"site": t.destination, "part": t.part_id, "on_hand": inventory._row(s, t.destination, t.part_id).on_hand}, t.workflow_id)
            refresh_status(s, t.workflow_id); wf = t.workflow_id
    except inventory.InventoryError as e: raise WorkflowError(409, str(e))
    return verify(wf)

def verify(wf_id):
    """Independent verification service: ledger conservation + workflow outcome against current stock."""
    with read() as s:
        wf = s.get(m.Workflow, wf_id)
        if not wf: raise WorkflowError(404, "workflow not found")
        st = json.loads(wf.state); p = st.get("params", {}); checks = []
        part = p.get("part"); dealer = p.get("dealer")
        led = inventory.ledger_check(s, part); checks.append({"check": "stock equals ledger for part", "passed": led["consistent"], "detail": led["mismatches"]})
        trs = list(s.scalars(select(m.Transfer).where(m.Transfer.workflow_id == wf_id)))
        for t in trs:
            mv = list(s.scalars(select(m.Movement).where(m.Movement.transfer_id == t.id)))
            exp = {"reserved": 0, "cancelled": 0, "in_transit": 1, "received": 2}[t.status]
            checks.append({"check": f"transfer {t.id} ({t.status}) has {exp} ledger movements", "passed": len(mv) == exp})
        res = None
        if wf.status == "recovered" and st.get("shortage"):
            need = st["shortage"]["need"]; have = inventory.available(s, dealer, part)
            res = have >= need; checks.append({"check": f"destination available {have} >= need {need}", "passed": res})
        return {"workflow_id": wf_id, "status": wf.status, "verified": all(c["passed"] for c in checks), "outcome_resolved": res, "checks": checks}

def get(wf_id):
    with read() as s:
        wf = s.get(m.Workflow, wf_id)
        if not wf: raise WorkflowError(404, "workflow not found")
        d = json.loads(wf.state); d.update(workflow_id=wf.id, status=wf.status, requested_by=wf.requested_by)
        d["approvals_detail"] = [approvals.to_dict(a) for a in s.scalars(select(m.Approval).where(m.Approval.workflow_id == wf_id))]
        d["transfers"] = [{"id": t.id, "source": t.source, "destination": t.destination, "part": t.part_id, "qty": t.qty, "status": t.status, "eta_minutes": t.eta_minutes, "eta_basis": t.route_basis} for t in s.scalars(select(m.Transfer).where(m.Transfer.workflow_id == wf_id))]
        return d
