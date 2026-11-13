"""CyberShield authorisation-risk check for workflow requests. Uses the audit trail (real application events)
and states that the security_events table is not live telemetry."""
import time
from sqlalchemy import select, func
from . import models as m

WINDOW_S = 900; ELEVATED = 3

def assess_actor(s, actor):
    since = time.time() - WINDOW_S
    denied = s.scalar(select(func.count()).select_from(m.AuditRecord).where(
        m.AuditRecord.actor == actor, m.AuditRecord.ts >= since, m.AuditRecord.decision.in_(["denied", "rejected_unauthorized"]))) or 0
    src = s.get(m.DataSource, "security_events")
    return {"actor": actor, "denied_actions_last_15min": int(denied), "risk": "elevated" if denied >= ELEVATED else "normal",
            "block": denied >= ELEVATED,
            "telemetry_note": f"security_events table provenance is {src.provenance if src else 'unknown'}; it is not live network telemetry. This check uses only this application's own audit trail."}
