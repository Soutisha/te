"""Persisted operational event log. Consumers (WebSocket, twin, dashboard) read this; nothing is invented."""
import json
from sqlalchemy import select
from .models import EventRecord

def emit(s, type_, payload, workflow_id=None, source="backend"):
    e = EventRecord(type=type_, payload=json.dumps(payload, default=str), workflow_id=workflow_id, source=source)
    s.add(e); s.flush(); return e

def since(s, after_id=0, limit=200, workflow_id=None):
    q = select(EventRecord).where(EventRecord.id > after_id)
    if workflow_id: q = q.where(EventRecord.workflow_id == workflow_id)
    return [{"id": e.id, "ts": e.ts.isoformat() if e.ts else None, "type": e.type, "workflow_id": e.workflow_id,
             "source": e.source, "payload": json.loads(e.payload or "{}")} for e in s.scalars(q.order_by(EventRecord.id).limit(limit))]
