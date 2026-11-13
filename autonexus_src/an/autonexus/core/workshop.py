"""Workshop Intelligence: skills, availability, bays, conflicts, and simple reschedule suggestions."""
from sqlalchemy import select
from . import models as m


def evaluate(s, dealer, part):
    p = s.get(m.Part, part)
    skill = s.scalar(select(m.PartSkill.skill).where(m.PartSkill.part_name == p.name))
    ros = list(
        s.scalars(
            select(m.RepairOrder)
            .where(
                m.RepairOrder.dealer_id == dealer,
                m.RepairOrder.part_id == part,
                m.RepairOrder.status == "open",
            )
            .order_by(m.RepairOrder.priority, m.RepairOrder.id)
        )
    )
    techs = list(s.scalars(select(m.Technician).where(m.Technician.dealer_id == dealer)))
    qualified = [
        t.id
        for t in techs
        if t.available and skill and skill in (t.skills or "").split("|")
    ]
    bays = list(s.scalars(select(m.ServiceBay).where(m.ServiceBay.dealer_id == dealer)))
    bay_ids = {b.id for b in bays}
    appts = [a for a in s.scalars(select(m.Appointment)) if a.bay_id in bay_ids]
    conflicts = []
    for i, a in enumerate(appts):
        for b in appts[i + 1 :]:
            if (
                a.bay_id == b.bay_id
                and a.start_hour < b.start_hour + b.duration_h
                and b.start_hour < a.start_hour + a.duration_h
            ):
                conflicts.append({"bay": a.bay_id, "appointments": [a.id, b.id]})
    ro_ids = {r.id for r in ros}
    blocked_hours = round(
        sum(a.duration_h for a in appts if a.repair_order_id in ro_ids), 2
    )

    # Simple reschedule suggestions (does not mutate; returns proposals only)
    suggestions = _suggest_reschedule(ros, techs, bays, appts, skill)

    return {
        "dealer": dealer,
        "part": part,
        "required_skill": skill,
        "skill_requirement_source": (
            "part_skills table"
            if skill
            else "no skill mapping for this part; technician match not evaluated"
        ),
        "blocked_repair_orders": [
            {
                "id": r.id,
                "priority": r.priority,
                "qty": r.qty,
                "assigned_technician": r.technician_id,
            }
            for r in ros
        ],
        "qualified_available_technicians": qualified,
        "bays_total": len(bays),
        "bays_available": sum(1 for b in bays if b.available),
        "scheduled_hours_for_blocked_orders": blocked_hours,
        "appointment_conflicts": conflicts,
        "can_staff_work": bool(qualified) and any(b.available for b in bays),
        "reschedule_suggestions": suggestions,
        "note": "Suggestions are proposals only; call apply_reschedule to to commit.",
    }


def _suggest_reschedule(ros, techs, bays, appts, skill):
    """Propose alternative bay + hour slots for open repair orders that lack a clean slot."""
    suggestions = []
    used = {}
    for a in appts:
        used.setdefault(a.bay_id, []).append((a.start_hour, a.start_hour + a.duration_h))

    available_bays = [b for b in bays if b.available]
    qualified_techs = [
        t
        for t in techs
        if t.available and (not skill or skill in (t.skills or "").split("|"))
    ]
    if not available_bays or not qualified_techs:
        return suggestions

    for r in ros:
        duration = 2.0  # default assumed duration in hours
        found = None
        for bay in available_bays:
            slots = sorted(used.get(bay.id, []))
            # try hours 8..16
            for hour in range(8, 17):
                end = hour + duration
                if end > 18:
                    continue
                overlap = any(
                    not (end <= s or hour >= e) for s, e in slots
                )
                if not overlap:
                    found = {
                        "repair_order_id": r.id,
                        "proposed_bay": bay.id,
                        "proposed_start_hour": hour,
                        "proposed_duration_h": duration,
                        "proposed_technician": qualified_techs[0].id,
                        "reason": "first free slot on available bay with qualified tech",
                    }
                    break
            if found:
                break
        if found:
            suggestions.append(found)
    return suggestions


def apply_reschedule(s, repair_order_id, bay_id, start_hour, duration_h, technician_id):
    """Apply a single reschedule proposal. Creates or updates the appointment."""
    ro = s.get(m.RepairOrder, repair_order_id)
    if not ro or ro.status != "open":
        return {"ok": False, "error": "repair order not open or not found"}
    bay = s.get(m.ServiceBay, bay_id)
    if not bay or not bay.available:
        return {"ok": False, "error": "bay unavailable"}
    tech = s.get(m.Technician, technician_id)
    if not tech or not tech.available:
        return {"ok": False, "error": "technician unavailable"}

    # Check conflict
    appts = list(s.scalars(select(m.Appointment).where(m.Appointment.bay_id == bay_id)))
    for a in appts:
        if a.start_hour < start_hour + duration_h and start_hour < a.start_hour + a.duration_h:
            return {"ok": False, "error": f"conflicts with appointment {a.id}"}

    existing = s.scalar(
        select(m.Appointment).where(m.Appointment.repair_order_id == repair_order_id)
    )
    if existing:
        existing.bay_id = bay_id
        existing.start_hour = float(start_hour)
        existing.duration_h = float(duration_h)
        appt_id = existing.id
    else:
        appt = m.Appointment(
            repair_order_id=repair_order_id,
            bay_id=bay_id,
            start_hour=float(start_hour),
            duration_h=float(duration_h),
        )
        s.add(appt)
        s.flush()
        appt_id = appt.id

    ro.technician_id = technician_id
    return {
        "ok": True,
        "appointment_id": appt_id,
        "repair_order_id": repair_order_id,
        "bay_id": bay_id,
        "start_hour": start_hour,
        "technician_id": technician_id,
    }
