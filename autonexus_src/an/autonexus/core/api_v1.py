"""Versioned API (/api/v1). Thin: validates input, enforces roles, delegates to engines. No business logic here."""
import asyncio, json, threading
from fastapi import APIRouter, Depends, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from .. import config
from . import models as m, db, seed, audit, events, security, inventory, forecast, supplier, routing, workflow, approvals
from .security import can

router = APIRouter(prefix="/api/v1", tags=["core"])
_init_lock = threading.Lock(); _ready = False

def ensure_init():
    global _ready
    if _ready: return
    with _init_lock:
        if _ready: return
        db.engine(); seed.load_csv_dataset()
        with db.write() as s: security.bootstrap_owner(s)
        _ready = True

def reset_for_tests():
    global _ready; _ready = False

def principal(authorization: str = Header(None)):
    ensure_init()
    if not (authorization or "").startswith("Bearer "): raise HTTPException(401, "authentication required")
    with db.read() as s: who = security.resolve(s, authorization[7:])
    if not who: raise HTTPException(401, "invalid or expired session")
    return {"user": who[0], "role": who[1]}

def need(perm):
    def dep(p=Depends(principal)):
        if not can(p["role"], perm):
            with db.write() as s: audit.add(s, p["user"], "access_denied", {"permission": perm}, "denied")
            raise HTTPException(403, f"permission {perm} required")
        return p
    return dep

def _wrap(fn, *a, **k):
    try: return fn(*a, **k)
    except (approvals.ApprovalError, workflow.WorkflowError) as e: raise HTTPException(e.code, str(e))
    except inventory.InventoryError as e: raise HTTPException(422, str(e))

class Login(BaseModel): email: str; password: str
class NewUser(BaseModel): email: str; password: str = Field(min_length=10); role: str
class ShortageRequest(BaseModel):
    dealer: str; part: str; required_qty: int | None = Field(default=None, ge=0)
    blocked_roads: list[list[str]] = []; horizon_days: int = Field(default=14, ge=1, le=90)
class Decision(BaseModel): decision: str; note: str = ""

@router.post("/auth/login")
def login(b: Login):
    ensure_init()
    with db.read() as s: t = security.login(s, b.email, b.password)
    if not t:
        with db.write() as s: audit.add(s, b.email, "login_failed", {}, "denied")
        raise HTTPException(401, "invalid credentials")
    return {"token": t}

@router.post("/users")
def add_user(b: NewUser, p=Depends(need("users:manage"))):
    try:
        with db.write() as s: security.create_user(s, b.email, b.password, b.role); audit.add(s, p["user"], "user_created", {"email": b.email, "role": b.role}, "ok")
    except ValueError as e: raise HTTPException(422, str(e))
    return {"email": b.email.lower(), "role": b.role}

@router.get("/platform/provenance")
def provenance():
    ensure_init()
    with db.read() as s:
        return {"tables": [{"table": r.table_name, "provenance": r.provenance, "source": r.source, "rows": r.rows, "loaded_at": r.loaded_at.isoformat()} for r in s.scalars(select(m.DataSource).order_by(m.DataSource.table_name))],
                "classes": ["OPERATIONAL", "SYNTHETIC", "IMPORTED", "SIMULATED", "EXTERNAL"], "banner": workflow._provenance(s)["banner"]}

@router.get("/platform/connectors")
def connectors():
    offline = config.get("OFFLINE_MODE", "1") == "1"
    osrm = {"configured": bool(config.get("OSRM_URL")) and not offline,
            "status": "disabled_offline" if offline else "not_configured"}
    if osrm["configured"]:
        with db.read() as s: r = routing.route(s, "DealerA", "WH1")
        osrm["status"] = "healthy" if r.get("provider", {}).get("ok") else "error"; osrm["error"] = r.get("provider", {}).get("error")
    return {"database": {"status": "connected", "dialect": db.engine().dialect.name},
            "routing_osrm": osrm,
            "erpnext": {"status": "not_connected", "detail": "no ERP adapter is implemented in this build"},
            "flower_federated": {"status": "not_connected", "detail": "no federated clients configured"},
            "siem_telemetry": {"status": "not_connected", "detail": "security_events is a dataset, not a live feed"},
            "llm": {"status": "not_used", "detail": "all decisions in this workflow are deterministic backend services"}}

@router.post("/workflows/shortage")
def start(b: ShortageRequest, p=Depends(principal)):
    return _wrap(workflow.run_shortage, p["user"], p["role"], b.dealer, b.part, b.required_qty, [tuple(x) for x in b.blocked_roads], b.horizon_days)

@router.get("/workflows")
def list_wf(p=Depends(need("data:read"))):
    with db.read() as s:
        return [{"id": w.id, "status": w.status, "requested_by": w.requested_by, "params": json.loads(w.params), "created_at": w.created_at.isoformat()} for w in s.scalars(select(m.Workflow).order_by(m.Workflow.created_at.desc()).limit(50))]

@router.get("/workflows/{wf_id}")
def get_wf(wf_id: str, p=Depends(need("data:read"))): return _wrap(workflow.get, wf_id)

@router.get("/workflows/{wf_id}/verify")
def verify_wf(wf_id: str, p=Depends(need("data:read"))): return _wrap(workflow.verify, wf_id)

@router.get("/approvals")
def list_ap(status: str | None = None, p=Depends(need("data:read"))):
    with db.write() as s: approvals.expire_due(s)
    with db.read() as s:
        q = select(m.Approval).order_by(m.Approval.created_at.desc()).limit(100)
        if status: q = q.where(m.Approval.status == status)
        return [approvals.to_dict(a) for a in s.scalars(q)]

@router.get("/approvals/{aid}")
def get_ap(aid: str, p=Depends(need("data:read"))): return _wrap(approvals.get, aid)

@router.post("/approvals/{aid}/decision")
def decide(aid: str, b: Decision, p=Depends(principal)): return _wrap(approvals.decide, aid, p["user"], p["role"], b.decision, b.note)

@router.post("/transfers/{tid}/receive")
def receive(tid: str, p=Depends(principal)): return _wrap(workflow.receive_transfer, tid, p["user"], p["role"])

@router.get("/inventory/{part}")
def inv(part: str, p=Depends(need("data:read"))):
    with db.read() as s:
        if not s.get(m.Part, part): raise HTTPException(404, "unknown part")
        rows = [{"site": r.site_id, "on_hand": r.on_hand, "reserved": r.reserved, "available": r.on_hand - r.reserved, "open_repair_need": inventory.open_need(s, r.site_id, part), "incoming": inventory.incoming(s, r.site_id, part)} for r in s.scalars(select(m.Stock).where(m.Stock.part_id == part).order_by(m.Stock.site_id))]
        return {"part": part, "sites": rows, "ledger": inventory.ledger_check(s, part), "provenance": workflow._provenance(s)["classes"]}

@router.get("/vehicles")
def vehicles(p=Depends(need("data:read"))):
    """Read vehicle aging from the same dataset used to seed the operational core."""
    from ..telemetry import read_rows
    from .seed import DATA
    with db.read() as s:
        sites = {site.id: site.name for site in s.scalars(select(m.Site))}
        rows = read_rows(DATA, "vehicle_records")
        latest = {}
        for update in s.scalars(select(m.VehicleWalkUpdate).order_by(m.VehicleWalkUpdate.id.desc())):
            latest.setdefault(update.vehicle_id, update)
    return [{
        "vehicle_id": r["vehicle_id"],
        "dealer_id": r["dealership_id"],
        "dealer_name": sites.get(r["dealership_id"], r["dealership_id"]),
        "vin": r.get("vin", ""),
        "model": r.get("model", ""),
        "year": int(r["year"]),
        "days_in_inventory": int(r.get("days_in_inventory") or 0),
        "status": r.get("status", ""),
        "list_price": float(r.get("list_price") or 0),
        "lot_walk": ({"location": latest[r["vehicle_id"]].location,
                      "condition": latest[r["vehicle_id"]].condition,
                      "status": latest[r["vehicle_id"]].status,
                      "notes": latest[r["vehicle_id"]].notes,
                      "actor": latest[r["vehicle_id"]].actor,
                      "updated_at": latest[r["vehicle_id"]].created_at.isoformat() if latest[r["vehicle_id"]].created_at else None}
                     if r["vehicle_id"] in latest else None),
    } for r in rows]

class LotWalkUpdateBody(BaseModel):
    location: str = Field(min_length=1, max_length=160)
    condition: str = Field(min_length=1, max_length=160)
    status: str = Field(default="needs_review", max_length=32)
    notes: str = Field(default="", max_length=2000)
    transcript: str = Field(default="", max_length=5000)

@router.post("/vehicles/{vehicle_id}/lot-walk")
def save_lot_walk(vehicle_id: str, b: LotWalkUpdateBody, p=Depends(need("vehicle:update"))):
    allowed_status = {"in_stock", "reserved", "service", "hold", "sold", "delivered", "needs_review"}
    status = b.status.strip().lower().replace(" ", "_")
    if status not in allowed_status:
        raise HTTPException(422, "unsupported lot-walk status")
    with db.write() as s:
        if not s.get(m.Vehicle, vehicle_id):
            raise HTTPException(404, "unknown vehicle")
        row = m.VehicleWalkUpdate(vehicle_id=vehicle_id, location=b.location.strip(), condition=b.condition.strip(),
                                  status=status, notes=b.notes.strip(), transcript=b.transcript.strip(), actor=p["user"])
        s.add(row); s.flush()
        audit.add(s, p["user"], "vehicle.lot_walk.updated", {"vehicle_id": vehicle_id, "location": row.location, "condition": row.condition, "status": status}, "updated")
        events.emit(s, "vehicle.lot_walk.updated", {"vehicle_id": vehicle_id, "location": row.location, "status": status})
        result = {"id": row.id, "vehicle_id": row.vehicle_id, "location": row.location, "condition": row.condition,
                  "status": row.status, "notes": row.notes, "updated_by": row.actor, "updated_at": row.created_at.isoformat() if row.created_at else None}
    return result

@router.get("/forecast")
def fc(dealer: str, part: str, horizon_days: int = Query(14, ge=1, le=90), p=Depends(need("data:read"))):
    with db.write() as s:
        if not s.get(m.Site, dealer) or not s.get(m.Part, part): raise HTTPException(404, "unknown dealer or part")
        return forecast.forecast(s, dealer, part, horizon_days, on_hand=inventory.available(s, dealer, part))

@router.get("/suppliers/rank")
def rank(part: str, qty: int = Query(ge=1), p=Depends(need("data:read"))):
    with db.read() as s: return supplier.rank(s, part, qty)

@router.get("/route")
def rt(src: str, dst: str, blocked: list[str] = Query(default=[]), p=Depends(need("data:read"))):
    with db.read() as s: return routing.route(s, src, dst, [tuple(b.split("-")) for b in blocked])

@router.get("/audit/verify")
def av(p=Depends(need("audit:read"))):
    with db.read() as s: return audit.verify(s)

@router.get("/audit")
def al(limit: int = Query(100, le=500), p=Depends(need("audit:read"))):
    with db.read() as s:
        return [{"id": r.id, "ts": r.ts, "actor": r.actor, "action": r.action, "decision": r.decision, "resource": json.loads(r.resource or "null"), "hash": r.hash} for r in s.scalars(select(m.AuditRecord).order_by(m.AuditRecord.id.desc()).limit(limit))]

@router.get("/events")
def ev(after_id: int = 0, p=Depends(need("data:read"))):
    with db.read() as s: return events.since(s, after_id)

@router.get("/overview")
def overview(p=Depends(need("data:read"))):
    with db.read() as s:
        cnt = lambda col, *w: int(s.scalar(select(func.count()).select_from(col).where(*w)) or 0)
        return {"pending_approvals": cnt(m.Approval, m.Approval.status == "pending"), "in_transit_transfers": cnt(m.Transfer, m.Transfer.status == "in_transit"),
                "open_workflows": cnt(m.Workflow, m.Workflow.status.in_(["awaiting_approval", "in_transit", "awaiting_supply"])),
                "ledger": inventory.ledger_check(s)["consistent"], "audit": audit.verify(s), "provenance": workflow._provenance(s)}

@router.get("/twin/state")
def twin(part: str, p=Depends(need("data:read"))):
    """Digital-twin state derived only from the database: stock, shortages, transfers in motion, pending approvals."""
    with db.read() as s:
        if not s.get(m.Part, part): raise HTTPException(404, "unknown part")
        sites = []
        for st in s.scalars(select(m.Site)):
            r = s.get(m.Stock, (st.id, part)); need_q = inventory.open_need(s, st.id, part)
            av = (r.on_hand - r.reserved) if r else 0
            sites.append({"id": st.id, "kind": st.kind, "lat": st.lat, "lon": st.lon, "on_hand": r.on_hand if r else 0, "reserved": r.reserved if r else 0, "open_need": need_q, "shortage": max(0, need_q - av)})
        trs = [{"id": t.id, "source": t.source, "destination": t.destination, "qty": t.qty, "status": t.status, "route": json.loads(t.route), "dispatched_at": t.dispatched_at.isoformat() if t.dispatched_at else None, "eta_minutes": t.eta_minutes, "eta_basis": t.route_basis}
               for t in s.scalars(select(m.Transfer).where(m.Transfer.part_id == part, m.Transfer.status.in_(["reserved", "in_transit"])))]
        last = s.scalar(select(func.max(m.EventRecord.id))) or 0
        return {"part": part, "sites": sites, "transfers": trs, "last_event_id": last, "provenance": workflow._provenance(s)["classes"]}

@router.websocket("/ws/events")
async def ws_events(w: WebSocket, token: str = "", after_id: int = 0):
    await w.accept()
    ensure_init()
    with db.read() as s: who = security.resolve(s, token)
    if not who or not can(who[1], "data:read"):
        await w.close(code=4401); return
    await w.send_json({"type": "stream.open", "delivery": "persisted event log, polled every 0.5s (not a push from instruments)", "after_id": after_id})
    try:
        while True:
            def fetch():
                with db.read() as s: return events.since(s, after_id)
            for e in await asyncio.to_thread(fetch):
                await w.send_json(e); after_id = e["id"]
            await asyncio.sleep(0.5)
    except WebSocketDisconnect: return




@router.get("/forecast/xgboost")
def fc_xgb(dealer: str | None = None, part: str | None = None, horizon_days: int = Query(14, ge=1, le=90), p=Depends(need("data:read"))):
    """Train/evaluate XGBoost on demand_history and return MAE/RMSE. Honest about synthetic data."""
    with db.read() as s:
        return forecast.train_xgboost_demand(s, dealer=dealer, part=part, horizon_days=horizon_days)

# --- Workshop Intelligence ---
from . import workshop as workshop_mod

class RescheduleBody(BaseModel):
    repair_order_id: str
    bay_id: str
    start_hour: float
    duration_h: float = 2.0
    technician_id: str

@router.get("/workshop/evaluate")
def workshop_eval(dealer: str, part: str, p=Depends(need("data:read"))):
    with db.read() as s:
        if not s.get(m.Part, part):
            raise HTTPException(404, "unknown part")
        return workshop_mod.evaluate(s, dealer, part)

@router.post("/workshop/reschedule")
def workshop_reschedule(b: RescheduleBody, p=Depends(need("data:write"))):
    with db.write() as s:
        result = workshop_mod.apply_reschedule(
            s, b.repair_order_id, b.bay_id, b.start_hour, b.duration_h, b.technician_id
        )
        if not result.get("ok"):
            raise HTTPException(409, result.get("error", "reschedule failed"))
        return result
