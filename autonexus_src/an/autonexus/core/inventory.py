"""Inventory Intelligence: shortage detection, donor search, transactional reservation/dispatch/receipt."""
from sqlalchemy import select, update, func, case
from . import models as m

class InventoryError(Exception): pass

def _row(s, site, part): return s.get(m.Stock, (site, part))
def available(s, site, part):
    r = _row(s, site, part); return (r.on_hand - r.reserved) if r else 0

def open_need(s, dealer, part):
    return int(s.scalar(select(func.coalesce(func.sum(m.RepairOrder.qty), 0)).where(
        m.RepairOrder.dealer_id == dealer, m.RepairOrder.part_id == part, m.RepairOrder.status == "open")) or 0)

def incoming(s, site, part):
    transit = s.scalar(select(func.coalesce(func.sum(m.Transfer.qty), 0)).where(
        m.Transfer.destination == site, m.Transfer.part_id == part, m.Transfer.status == "in_transit")) or 0
    pending = s.scalar(select(func.coalesce(func.sum(m.Transfer.qty), 0)).where(
        m.Transfer.destination == site, m.Transfer.part_id == part, m.Transfer.status == "reserved")) or 0
    po = s.scalar(select(func.coalesce(func.sum(m.PurchaseOrder.qty), 0)).where(
        m.PurchaseOrder.destination == site, m.PurchaseOrder.part_id == part, m.PurchaseOrder.status == "ordered")) or 0
    return {"in_transit_transfers": int(transit), "transfers_pending_approval": int(pending), "open_purchase_orders": int(po)}

def detect(s, dealer, part, required_qty=None):
    if not s.get(m.Site, dealer): raise InventoryError(f"unknown site {dealer!r}")
    if not s.get(m.Part, part): raise InventoryError(f"unknown part {part!r}")
    need = int(required_qty) if required_qty is not None else open_need(s, dealer, part)
    if need < 0: raise InventoryError("required quantity cannot be negative")
    r = _row(s, dealer, part); have = (r.on_hand - r.reserved) if r else 0
    inc = incoming(s, dealer, part)
    return {"dealer": dealer, "part": part, "need": need, "available": have, "on_hand": r.on_hand if r else 0,
            "reserved": r.reserved if r else 0, "incoming": inc, "shortage": max(0, need - have),
            "net_shortage": max(0, need - have - sum(inc.values())),
            "need_basis": "required_qty parameter" if required_qty is not None else "sum of open repair-order quantities",
            "affected_repair_orders": [x for x in s.scalars(select(m.RepairOrder.id).where(
                m.RepairOrder.dealer_id == dealer, m.RepairOrder.part_id == part, m.RepairOrder.status == "open").order_by(m.RepairOrder.priority, m.RepairOrder.id))]}

def compatibility(s, dealer, part):
    p = s.get(m.Part, part); models = set(filter(None, (p.compatible_models or "").split("|")))
    bad = []
    for ro in s.scalars(select(m.RepairOrder).where(m.RepairOrder.dealer_id == dealer, m.RepairOrder.part_id == part, m.RepairOrder.status == "open")):
        v = s.get(m.Vehicle, ro.vehicle_id)
        if not v: bad.append({"repair_order": ro.id, "reason": "vehicle record missing"})
        elif models and v.model not in models: bad.append({"repair_order": ro.id, "vehicle_model": v.model, "reason": "part not compatible"})
    return {"part_models": sorted(models), "incompatible": bad, "compatible": not bad}

def donors(s, dealer, part):
    """Sites other than the destination with surplus = available - their own open repair-order need."""
    out = []
    for r in s.scalars(select(m.Stock).where(m.Stock.part_id == part, m.Stock.site_id != dealer)):
        own = open_need(s, r.site_id, part); surplus = r.on_hand - r.reserved - own
        if surplus > 0: out.append({"site": r.site_id, "on_hand": r.on_hand, "reserved": r.reserved, "own_open_need": own, "surplus": surplus})
    return out

def reserve(s, site, part, qty):
    if qty <= 0: raise InventoryError("quantity must be positive")
    res = s.execute(update(m.Stock).where(m.Stock.site_id == site, m.Stock.part_id == part,
                    m.Stock.on_hand - m.Stock.reserved >= qty).values(reserved=m.Stock.reserved + qty))
    if res.rowcount != 1: raise InventoryError(f"cannot reserve {qty} of {part} at {site}: insufficient available stock")

def release(s, site, part, qty):
    res = s.execute(update(m.Stock).where(m.Stock.site_id == site, m.Stock.part_id == part,
                    m.Stock.reserved >= qty).values(reserved=m.Stock.reserved - qty))
    if res.rowcount != 1: raise InventoryError("reservation to release not found")

def dispatch(s, t, actor):
    """Authorised dispatch: stock leaves the source (on_hand and reservation) and the goods are in transit."""
    if t.status != "reserved": raise InventoryError(f"transfer {t.id} is {t.status}, not reserved")
    res = s.execute(update(m.Stock).where(m.Stock.site_id == t.source, m.Stock.part_id == t.part_id,
                    m.Stock.reserved >= t.qty, m.Stock.on_hand >= t.qty).values(
                    on_hand=m.Stock.on_hand - t.qty, reserved=m.Stock.reserved - t.qty))
    if res.rowcount != 1: raise InventoryError("reservation no longer valid; dispatch refused")
    s.add(m.Movement(kind="dispatch", site_id=t.source, part_id=t.part_id, delta=-t.qty, transfer_id=t.id,
                     workflow_id=t.workflow_id, idempotency_key=f"dispatch:{t.id}", actor=actor))
    t.status = "in_transit"; t.dispatched_at = m.now(); s.flush()

def receive(s, t, actor):
    if t.status != "in_transit": raise InventoryError(f"transfer {t.id} is {t.status}, not in_transit")
    row = _row(s, t.destination, t.part_id)
    if row: s.execute(update(m.Stock).where(m.Stock.site_id == t.destination, m.Stock.part_id == t.part_id).values(on_hand=m.Stock.on_hand + t.qty))
    else: s.add(m.Stock(site_id=t.destination, part_id=t.part_id, on_hand=t.qty, reserved=0))
    s.add(m.Movement(kind="receive", site_id=t.destination, part_id=t.part_id, delta=t.qty, transfer_id=t.id,
                     workflow_id=t.workflow_id, idempotency_key=f"receive:{t.id}", actor=actor))
    t.status = "received"; t.received_at = m.now(); s.flush()

def cancel(s, t, clamp=False):
    """Cancel a reserved leg. clamp=True (failure recovery) tolerates a corrupted reservation instead of failing."""
    if t.status != "reserved": return
    if clamp:
        s.execute(update(m.Stock).where(m.Stock.site_id == t.source, m.Stock.part_id == t.part_id).values(
            reserved=case((m.Stock.reserved >= t.qty, m.Stock.reserved - t.qty), else_=0)))
    else: release(s, t.source, t.part_id, t.qty)
    t.status = "cancelled"; s.flush()

def ledger_check(s, part=None):
    """Independent verification: on_hand must equal the sum of ledger movements for every (site, part)."""
    led = {(a, b): int(c) for a, b, c in s.execute(select(m.Movement.site_id, m.Movement.part_id, func.sum(m.Movement.delta)).group_by(m.Movement.site_id, m.Movement.part_id))}
    bad = []
    for r in s.scalars(select(m.Stock)):
        if part and r.part_id != part: continue
        if led.get((r.site_id, r.part_id), 0) != r.on_hand: bad.append({"site": r.site_id, "part": r.part_id, "stock": r.on_hand, "ledger": led.get((r.site_id, r.part_id), 0)})
    transit = {pid: int(q) for pid, q in s.execute(select(m.Transfer.part_id, func.sum(m.Transfer.qty)).where(m.Transfer.status == "in_transit").group_by(m.Transfer.part_id))}
    return {"consistent": not bad, "mismatches": bad, "in_transit_by_part": transit}
