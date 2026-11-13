"""Shared operational data model. One set of entities used by every engine."""
from datetime import datetime, timezone
from sqlalchemy import (Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey,
                        CheckConstraint, UniqueConstraint, Index, event)
from sqlalchemy.orm import declarative_base

Base = declarative_base()
def now(): return datetime.now(timezone.utc)

class Site(Base):
    __tablename__ = "sites"
    id = Column(String, primary_key=True); kind = Column(String, nullable=False)  # dealer|warehouse
    name = Column(String); lat = Column(Float); lon = Column(Float)
    __table_args__ = (CheckConstraint("kind in ('dealer','warehouse')"),)

class Part(Base):
    __tablename__ = "parts"
    id = Column(String, primary_key=True); name = Column(String, nullable=False)
    unit_price = Column(Float); compatible_models = Column(String, default="")

class PartSkill(Base):
    __tablename__ = "part_skills"
    part_name = Column(String, primary_key=True); skill = Column(String, nullable=False)

class Stock(Base):
    __tablename__ = "stock"
    site_id = Column(String, ForeignKey("sites.id"), primary_key=True)
    part_id = Column(String, ForeignKey("parts.id"), primary_key=True)
    on_hand = Column(Integer, nullable=False, default=0)
    reserved = Column(Integer, nullable=False, default=0)
    __table_args__ = (CheckConstraint("on_hand >= 0", name="ck_on_hand_nonneg"),
                      CheckConstraint("reserved >= 0", name="ck_reserved_nonneg"),
                      CheckConstraint("reserved <= on_hand", name="ck_reserved_le_on_hand"))

class Movement(Base):
    """Append-only stock ledger. on_hand at any site == sum of signed movements."""
    __tablename__ = "movements"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), default=now)
    kind = Column(String, nullable=False)  # seed|dispatch|receive|adjust
    site_id = Column(String, ForeignKey("sites.id"), nullable=False)
    part_id = Column(String, ForeignKey("parts.id"), nullable=False)
    delta = Column(Integer, nullable=False)  # signed effect on on_hand at site_id
    transfer_id = Column(String); workflow_id = Column(String)
    idempotency_key = Column(String, unique=True)
    actor = Column(String)

class Transfer(Base):
    __tablename__ = "transfers"
    id = Column(String, primary_key=True); workflow_id = Column(String, index=True)
    approval_id = Column(String, index=True)
    source = Column(String, ForeignKey("sites.id"), nullable=False)
    destination = Column(String, ForeignKey("sites.id"), nullable=False)
    part_id = Column(String, ForeignKey("parts.id"), nullable=False)
    qty = Column(Integer, nullable=False)
    status = Column(String, nullable=False)  # reserved|in_transit|received|cancelled
    route = Column(Text); route_basis = Column(String); eta_minutes = Column(Float)
    created_at = Column(DateTime(timezone=True), default=now)
    dispatched_at = Column(DateTime(timezone=True)); received_at = Column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("qty > 0"), CheckConstraint("source <> destination"))

class Supplier(Base):
    __tablename__ = "suppliers"
    id = Column(String, primary_key=True); name = Column(String); reliability = Column(Float)
    lead_time_days = Column(Integer); restricted = Column(Boolean, default=False)

class Quotation(Base):
    __tablename__ = "quotations"
    id = Column(String, primary_key=True); supplier_id = Column(String, ForeignKey("suppliers.id"))
    part_id = Column(String, ForeignKey("parts.id")); unit_price = Column(Float); delivery_days = Column(Integer)

class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    id = Column(String, primary_key=True); supplier_id = Column(String, ForeignKey("suppliers.id"))
    part_id = Column(String, ForeignKey("parts.id")); qty = Column(Integer); amount = Column(Float)
    status = Column(String, nullable=False)  # imported|ordered|received|cancelled
    destination = Column(String, ForeignKey("sites.id")); workflow_id = Column(String)
    approval_id = Column(String); approved_by = Column(String); repair_order_id = Column(String)
    expected_days = Column(Integer); created_at = Column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("qty > 0"),)

class DemandHistory(Base):
    __tablename__ = "demand_history"
    dealer_id = Column(String, ForeignKey("sites.id"), primary_key=True)
    part_id = Column(String, ForeignKey("parts.id"), primary_key=True)
    day = Column(Integer, primary_key=True)
    demand = Column(Float, nullable=False); demand_std = Column(Float); lead_time = Column(Integer)

class Forecast(Base):
    __tablename__ = "forecasts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    dealer_id = Column(String); part_id = Column(String); horizon_days = Column(Integer)
    status = Column(String); value = Column(Float); lower = Column(Float); upper = Column(Float)
    model_id = Column(String); model_version = Column(String)
    train_start = Column(Integer); train_end = Column(Integer)
    metrics = Column(Text); created_at = Column(DateTime(timezone=True), default=now)

class RepairOrder(Base):
    __tablename__ = "repair_orders"
    id = Column(String, primary_key=True); dealer_id = Column(String, ForeignKey("sites.id"))
    vehicle_id = Column(String); part_id = Column(String, ForeignKey("parts.id")); qty = Column(Integer)
    technician_id = Column(String); priority = Column(Integer); status = Column(String)

class Vehicle(Base):
    __tablename__ = "vehicles"
    id = Column(String, primary_key=True); model = Column(String); year = Column(Integer); dealer_id = Column(String)

class VehicleWalkUpdate(Base):
    """Append-only local lot-walk observations; the CSV remains the original sample source."""
    __tablename__ = "vehicle_walk_updates"
    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_id = Column(String, ForeignKey("vehicles.id"), nullable=False, index=True)
    location = Column(String, nullable=False)
    condition = Column(String, nullable=False)
    status = Column(String, nullable=False)
    notes = Column(Text, default="")
    transcript = Column(Text, default="")
    actor = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now)

class Technician(Base):
    __tablename__ = "technicians"
    id = Column(String, primary_key=True); dealer_id = Column(String, ForeignKey("sites.id"))
    skills = Column(String); shift = Column(String); available = Column(Boolean)

class ServiceBay(Base):
    __tablename__ = "service_bays"
    id = Column(String, primary_key=True); dealer_id = Column(String, ForeignKey("sites.id")); available = Column(Boolean)

class Appointment(Base):
    __tablename__ = "appointments"
    id = Column(String, primary_key=True); repair_order_id = Column(String); bay_id = Column(String)
    start_hour = Column(Float); duration_h = Column(Float)

class RoadEdge(Base):
    __tablename__ = "road_edges"
    a = Column(String, ForeignKey("sites.id"), primary_key=True); b = Column(String, ForeignKey("sites.id"), primary_key=True)
    distance_km = Column(Float); cost = Column(Float); time_min = Column(Float)

class Policy(Base):
    __tablename__ = "policies"
    id = Column(String, primary_key=True); rule = Column(String); limit = Column(Float)

class SecurityEvent(Base):
    __tablename__ = "security_events"
    id = Column(String, primary_key=True); account = Column(String); action = Column(String)
    hour = Column(Integer); ip = Column(String); is_attack = Column(Boolean)

class User(Base):
    __tablename__ = "users"
    email = Column(String, primary_key=True); pw_hash = Column(String, nullable=False)
    role = Column(String, nullable=False); active = Column(Boolean, default=True)

class DataSource(Base):
    """Provenance registry: every table's origin class and last load."""
    __tablename__ = "data_sources"
    table_name = Column(String, primary_key=True)
    provenance = Column(String, nullable=False)  # OPERATIONAL|SYNTHETIC|IMPORTED|SIMULATED|EXTERNAL
    source = Column(String); rows = Column(Integer); loaded_at = Column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("provenance in ('OPERATIONAL','SYNTHETIC','IMPORTED','SIMULATED','EXTERNAL')"),)

class AuditRecord(Base):
    __tablename__ = "audit"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Float, nullable=False); actor = Column(String); action = Column(String)
    resource = Column(Text); decision = Column(String); prev = Column(String(64), nullable=False)
    hash = Column(String(64), nullable=False)

class EventRecord(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(DateTime(timezone=True), default=now); type = Column(String, index=True)
    workflow_id = Column(String, index=True); payload = Column(Text); source = Column(String)

class Workflow(Base):
    __tablename__ = "workflows"
    id = Column(String, primary_key=True); type = Column(String); status = Column(String)
    requested_by = Column(String); params = Column(Text); state = Column(Text)
    created_at = Column(DateTime(timezone=True), default=now); updated_at = Column(DateTime(timezone=True), default=now)

class Approval(Base):
    __tablename__ = "approvals"
    id = Column(String, primary_key=True); workflow_id = Column(String, index=True)
    action_type = Column(String, nullable=False)  # transfer|purchase_order
    status = Column(String, nullable=False)  # pending|approved|rejected|changes_requested|expired|executed|execution_failed
    requested_by = Column(String, nullable=False); required_permission = Column(String, nullable=False)
    payload = Column(Text); policy = Column(Text); evidence = Column(Text)
    created_at = Column(DateTime(timezone=True), default=now); expires_at = Column(DateTime(timezone=True))
    decided_by = Column(String); decided_at = Column(DateTime(timezone=True)); decision_note = Column(Text)
    execution_result = Column(Text)

class ApprovalHistory(Base):
    __tablename__ = "approval_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    approval_id = Column(String, index=True); ts = Column(DateTime(timezone=True), default=now)
    actor = Column(String); from_status = Column(String); to_status = Column(String); note = Column(Text)

class Idem(Base):
    __tablename__ = "idempotency"
    key = Column(String, primary_key=True); result = Column(Text); ts = Column(DateTime(timezone=True), default=now)

def _immutable(mapper, connection, target):
    raise PermissionError(f"{type(target).__name__} records are append-only")
for _m in (AuditRecord, ApprovalHistory, Movement):
    event.listen(_m, "before_update", _immutable)
    event.listen(_m, "before_delete", _immutable)
