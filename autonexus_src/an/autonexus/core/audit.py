"""Tamper-evident audit chain stored in the shared database (same transaction as the business write)."""
import hashlib, json, time
from sqlalchemy import select, desc
from .models import AuditRecord

GENESIS = "0" * 64
def _h(body): return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()

def add(s, actor, action, resource=None, decision=None):
    last = s.scalar(select(AuditRecord).order_by(desc(AuditRecord.id)).limit(1))
    prev = last.hash if last else GENESIS
    body = {"ts": round(time.time(), 6), "actor": actor, "action": action,
            "resource": json.dumps(resource, sort_keys=True, default=str), "decision": decision, "prev": prev}
    r = AuditRecord(**body, hash=_h(body)); s.add(r); s.flush(); return r

def verify(s):
    prev = GENESIS; n = 0
    for r in s.scalars(select(AuditRecord).order_by(AuditRecord.id)):
        body = {"ts": r.ts, "actor": r.actor, "action": r.action, "resource": r.resource, "decision": r.decision, "prev": r.prev}
        if r.prev != prev or _h(body) != r.hash:
            return {"valid": False, "broken_at": r.id, "records": n}
        prev = r.hash; n += 1
    return {"valid": True, "records": n}
