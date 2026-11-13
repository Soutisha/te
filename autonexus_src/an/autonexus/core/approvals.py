"""Human Approval engine, enforced in the backend. Every state change is a guarded atomic transition with immutable history."""
import json, uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from . import models as m, audit, events, inventory
from .db import write
from .security import can

TTL_MINUTES = 60
class ApprovalError(Exception):
    def __init__(self, code, msg): super().__init__(msg); self.code = code  # 403 forbidden, 404 missing, 409 conflict

def _utc(dt): return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)

def create(s, workflow_id, action_type, requested_by, permission, payload, policy, evidence, ttl_minutes=TTL_MINUTES):
    a = m.Approval(id=f"APR-{uuid.uuid4().hex[:10].upper()}", workflow_id=workflow_id, action_type=action_type, status="pending",
                   requested_by=requested_by, required_permission=permission, payload=json.dumps(payload), policy=json.dumps(policy),
                   evidence=json.dumps(evidence, default=str), expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes))
    s.add(a); s.flush()
    s.add(m.ApprovalHistory(approval_id=a.id, actor=requested_by, from_status=None, to_status="pending", note="requested"))
    audit.add(s, requested_by, "approval_requested", {"approval": a.id, "type": action_type, "workflow": workflow_id}, "pending")
    events.emit(s, "approval.requested", {"approval_id": a.id, "action_type": action_type, "permission": permission}, workflow_id)
    return a

def _transition(s, a, to, actor, note, expect="pending"):
    res = s.execute(update(m.Approval).where(m.Approval.id == a.id, m.Approval.status == expect).values(status=to, decided_by=actor, decided_at=datetime.now(timezone.utc), decision_note=note))
    if res.rowcount != 1: raise ApprovalError(409, f"approval {a.id} is no longer {expect}")
    s.add(m.ApprovalHistory(approval_id=a.id, actor=actor, from_status=expect, to_status=to, note=note)); s.expire(a)

def _release_legs(s, a, clamp=False):
    for t in list(s.scalars(select(m.Transfer).where(m.Transfer.approval_id == a.id))): inventory.cancel(s, t, clamp)

def expire_due(s):
    n = 0
    for a in list(s.scalars(select(m.Approval).where(m.Approval.status == "pending"))):
        if _utc(a.expires_at) <= datetime.now(timezone.utc):
            _transition(s, a, "expired", "system", "approval window elapsed"); _release_legs(s, a); n += 1
            audit.add(s, "system", "approval_expired", {"approval": a.id}, "expired")
            events.emit(s, "approval.expired", {"approval_id": a.id}, a.workflow_id)
            from . import workflow; workflow.refresh_status(s, a.workflow_id)
    return n

def _execute(s, a, actor):
    """Execution agent: performs only what the approved payload contains."""
    p = json.loads(a.payload); result = {}
    if a.action_type == "transfer":
        done = []
        for t in s.scalars(select(m.Transfer).where(m.Transfer.approval_id == a.id)):
            inventory.dispatch(s, t, actor); done.append(t.id)
            events.emit(s, "transfer.dispatched", {"transfer_id": t.id, "source": t.source, "destination": t.destination, "part": t.part_id, "qty": t.qty, "route": json.loads(t.route), "eta_minutes": t.eta_minutes, "eta_basis": t.route_basis}, a.workflow_id)
            events.emit(s, "inventory.changed", {"site": t.source, "part": t.part_id, "on_hand": inventory._row(s, t.source, t.part_id).on_hand}, a.workflow_id)
        if not done: raise inventory.InventoryError("approval has no transfer legs to execute")
        result = {"dispatched_transfers": done}
    elif a.action_type == "purchase_order":
        po = m.PurchaseOrder(id=f"PO-{uuid.uuid4().hex[:8].upper()}", supplier_id=p["supplier"], part_id=p["part"], qty=p["qty"], amount=p["total_cost"],
                             status="ordered", destination=p["destination"], workflow_id=a.workflow_id, approval_id=a.id, approved_by=actor, expected_days=p["delivery_days"])
        s.add(po); s.flush(); result = {"purchase_order": po.id, "erp_synced": False, "note": "recorded in AUTONEXUS only; no ERP connector configured"}
        events.emit(s, "purchase_order.created", {"po": po.id, "supplier": po.supplier_id, "part": po.part_id, "qty": po.qty, "amount": po.amount}, a.workflow_id)
    else: raise inventory.InventoryError(f"unknown action type {a.action_type}")
    return result

def decide(approval_id, actor, role, decision, note=""):
    if decision not in ("approve", "reject", "request_changes"): raise ApprovalError(422, "decision must be approve, reject or request_changes")
    to = {"approve": "approved", "reject": "rejected", "request_changes": "changes_requested"}[decision]
    with write() as s: expire_due(s)  # persist any lapsed approvals before evaluating this request
    with write() as s:  # authorisation checks (denials are audited and committed)
        a = s.get(m.Approval, approval_id)
        if not a: raise ApprovalError(404, "approval not found")
        denied = None
        if not can(role, a.required_permission): denied = f"role {role!r} lacks {a.required_permission}"
        elif actor == a.requested_by: denied = "separation of duties: requester cannot decide own request"
        if denied:
            audit.add(s, actor, f"approval_{decision}_denied", {"approval": a.id, "reason": denied}, "denied"); s.commit()
            raise ApprovalError(403, denied)
        if a.status != "pending": raise ApprovalError(409, f"approval is already {a.status}")
    failure = None
    try:
        with write() as s:
            a = s.get(m.Approval, approval_id); _transition(s, a, to, actor, note)
            audit.add(s, actor, f"approval_{decision}", {"approval": a.id, "note": note}, to)
            events.emit(s, "approval.decided", {"approval_id": a.id, "decision": to, "by": actor}, a.workflow_id)
            if to == "approved":
                res = _execute(s, a, actor)
                a.execution_result = json.dumps(res); a.status = "executed"
                s.add(m.ApprovalHistory(approval_id=a.id, actor=actor, from_status="approved", to_status="executed", note=json.dumps(res)))
                audit.add(s, actor, "approval_executed", {"approval": a.id, **res}, "executed")
            else: _release_legs(s, a)
            from . import workflow; workflow.refresh_status(s, a.workflow_id)
    except inventory.InventoryError as e: failure = str(e)
    if failure:  # whole decision+execution rolled back; record the failure durably
        with write() as s:
            a = s.get(m.Approval, approval_id)
            _transition(s, a, "execution_failed", actor, failure); a.execution_result = json.dumps({"error": failure}); _release_legs(s, a, clamp=True)
            audit.add(s, actor, "approval_execution_failed", {"approval": approval_id, "error": failure}, "failed")
            events.emit(s, "approval.execution_failed", {"approval_id": approval_id, "error": failure}, a.workflow_id)
            from . import workflow; workflow.refresh_status(s, a.workflow_id)
        raise ApprovalError(409, f"execution failed and was rolled back: {failure}")
    return get(approval_id)

def to_dict(a, history=None):
    d = {"id": a.id, "workflow_id": a.workflow_id, "action_type": a.action_type, "status": a.status, "requested_by": a.requested_by,
         "required_permission": a.required_permission, "payload": json.loads(a.payload), "policy": json.loads(a.policy),
         "evidence": json.loads(a.evidence), "created_at": a.created_at.isoformat() if a.created_at else None,
         "expires_at": _utc(a.expires_at).isoformat() if a.expires_at else None, "decided_by": a.decided_by,
         "decided_at": a.decided_at.isoformat() if a.decided_at else None, "decision_note": a.decision_note,
         "execution_result": json.loads(a.execution_result) if a.execution_result else None}
    if history is not None: d["history"] = history
    return d

def get(approval_id):
    from .db import read
    with read() as s:
        a = s.get(m.Approval, approval_id)
        if not a: raise ApprovalError(404, "approval not found")
        h = [{"ts": x.ts.isoformat(), "actor": x.actor, "from": x.from_status, "to": x.to_status, "note": x.note} for x in s.scalars(select(m.ApprovalHistory).where(m.ApprovalHistory.approval_id == approval_id).order_by(m.ApprovalHistory.id))]
        return to_dict(a, h)
